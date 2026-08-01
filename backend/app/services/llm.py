"""Groq chat completions (OpenAI-compatible HTTP API)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Optional

from openai import APIError, OpenAI, RateLimitError

from ..config import get_settings

logger = logging.getLogger(__name__)

# Process-local usage counters (reset on process restart).
_usage_lock = threading.Lock()
_usage: dict[str, Any] = {
    "calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "by_model": {},
    "last_call": None,
}


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable content."""

    def __init__(self, message: str, *, retry_after_sec: Optional[float] = None):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec
        self.user_message = message


def usage_snapshot() -> dict[str, Any]:
    """Return a copy of process-local Groq token counters."""
    with _usage_lock:
        by_model = {
            k: dict(v) for k, v in (_usage.get("by_model") or {}).items()
        }
        last = _usage.get("last_call")
        return {
            "calls": int(_usage.get("calls") or 0),
            "prompt_tokens": int(_usage.get("prompt_tokens") or 0),
            "completion_tokens": int(_usage.get("completion_tokens") or 0),
            "total_tokens": int(_usage.get("total_tokens") or 0),
            "by_model": by_model,
            "last_call": dict(last) if isinstance(last, dict) else None,
        }


def reset_usage() -> None:
    """Clear process-local usage counters (tests / diagnostics)."""
    with _usage_lock:
        _usage["calls"] = 0
        _usage["prompt_tokens"] = 0
        _usage["completion_tokens"] = 0
        _usage["total_tokens"] = 0
        _usage["by_model"] = {}
        _usage["last_call"] = None


def _record_usage(resp: Any, *, model: str) -> None:
    """Accumulate prompt/completion tokens from an OpenAI-compatible response."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    entry = {
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "at": time.time(),
    }
    with _usage_lock:
        _usage["calls"] = int(_usage["calls"]) + 1
        _usage["prompt_tokens"] = int(_usage["prompt_tokens"]) + prompt
        _usage["completion_tokens"] = int(_usage["completion_tokens"]) + completion
        _usage["total_tokens"] = int(_usage["total_tokens"]) + total
        by_model: dict[str, Any] = _usage.setdefault("by_model", {})
        slot = by_model.setdefault(
            model,
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        slot["calls"] = int(slot["calls"]) + 1
        slot["prompt_tokens"] = int(slot["prompt_tokens"]) + prompt
        slot["completion_tokens"] = int(slot["completion_tokens"]) + completion
        slot["total_tokens"] = int(slot["total_tokens"]) + total
        _usage["last_call"] = entry

    try:
        if get_settings().log_llm_usage:
            logger.info(
                "groq usage model=%s prompt=%d completion=%d total=%d",
                model,
                prompt,
                completion,
                total,
            )
    except Exception:
        # Never let settings/logging failures break the chat path
        pass


def _client() -> OpenAI:
    s = get_settings()
    if not s.groq_api_key:
        raise LLMError("GROQ_API_KEY is not set")
    return OpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url)


def _friendly_rate_limit(exc: Exception) -> LLMError:
    """Turn Groq's raw 429 payload into a short human message."""
    text = str(exc)
    retry_after: Optional[float] = None
    # "Please try again in 1h27m10.656s" or "in 12.3s"
    m = re.search(
        r"try again in\s+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?",
        text,
        re.I,
    )
    if m:
        h = int(m.group(1) or 0)
        mi = int(m.group(2) or 0)
        sec = float(m.group(3) or 0)
        retry_after = h * 3600 + mi * 60 + sec
    tpd = re.search(r"tokens per day \(TPD\).*?Limit\s+(\d+).*?Used\s+(\d+)", text, re.I)
    if tpd or "TPD" in text or "tokens per day" in text.lower():
        msg = "Groq daily token limit reached"
        if retry_after and retry_after > 60:
            mins = int(retry_after // 60)
            msg += f" — try again in ~{mins} min"
        elif retry_after:
            msg += f" — try again in ~{int(retry_after)}s"
        else:
            msg += ". Wait for the daily reset, or uncheck AI enrich."
        return LLMError(msg, retry_after_sec=retry_after)
    if "tokens per minute" in text.lower() or "TPM" in text:
        msg = "Groq rate limit (tokens/min)"
        if retry_after:
            msg += f" — retry in ~{int(retry_after)}s"
        return LLMError(msg, retry_after_sec=retry_after or 30.0)
    return LLMError(
        "Groq rate limit — slow down or wait before more AI imports",
        retry_after_sec=retry_after,
    )


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    model: Optional[str] = None,
    retries: int = 1,
) -> dict[str, Any]:
    """Call Groq and parse a JSON object from the reply."""
    s = get_settings()
    client = _client()
    use_model = (model or s.groq_model).strip()
    last_err: Optional[Exception] = None

    for attempt in range(max(1, retries + 1)):
        try:
            resp = client.chat.completions.create(
                model=use_model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            _record_usage(resp, model=use_model)
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise LLMError("Empty response from Groq")
            return _parse_json(content)
        except RateLimitError as exc:
            friendly = _friendly_rate_limit(exc)
            last_err = friendly
            # Retry only short TPM waits, not daily TPD
            wait = friendly.retry_after_sec or 0
            if attempt < retries and 0 < wait <= 45:
                time.sleep(min(wait + 1, 45))
                continue
            raise friendly from exc
        except APIError as exc:
            raise LLMError(f"Groq API error: {exc}") from exc
        except LLMError:
            raise
        except Exception as exc:  # network, etc.
            raise LLMError(f"Groq request failed: {exc}") from exc

    raise last_err or LLMError("Groq request failed")


def chat_text(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> str:
    s = get_settings()
    client = _client()
    use_model = (model or s.groq_model).strip()
    try:
        resp = client.chat.completions.create(
            model=use_model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except RateLimitError as exc:
        raise _friendly_rate_limit(exc) from exc
    except APIError as exc:
        raise LLMError(f"Groq API error: {exc}") from exc
    except Exception as exc:
        raise LLMError(f"Groq request failed: {exc}") from exc

    _record_usage(resp, model=use_model)
    return (resp.choices[0].message.content or "").strip()


def _parse_json(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
        raise LLMError("JSON root must be an object")
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            raise LLMError(f"Could not parse JSON from model: {content[:200]}")
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            raise LLMError("JSON root must be an object")
        return data


def model_label(model: Optional[str] = None) -> str:
    s = get_settings()
    return f"groq:{(model or s.groq_model).strip()}"
