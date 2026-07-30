"""Groq chat completions (OpenAI-compatible HTTP API)."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

from openai import APIError, OpenAI, RateLimitError

from ..config import get_settings


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable content."""

    def __init__(self, message: str, *, retry_after_sec: Optional[float] = None):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec
        self.user_message = message


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
