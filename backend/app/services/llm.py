"""Groq chat completions (OpenAI-compatible HTTP API)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from openai import APIError, OpenAI, RateLimitError

from ..config import get_settings


class LLMError(Exception):
    """Raised when the LLM call fails or returns unusable content."""


def _client() -> OpenAI:
    s = get_settings()
    if not s.groq_api_key:
        raise LLMError("GROQ_API_KEY is not set")
    return OpenAI(api_key=s.groq_api_key, base_url=s.groq_base_url)


def chat_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call Groq and parse a JSON object from the reply."""
    s = get_settings()
    client = _client()
    try:
        resp = client.chat.completions.create(
            model=s.groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except RateLimitError as exc:
        raise LLMError(f"Groq rate limit: {exc}") from exc
    except APIError as exc:
        raise LLMError(f"Groq API error: {exc}") from exc
    except Exception as exc:  # network, etc.
        raise LLMError(f"Groq request failed: {exc}") from exc

    content = (resp.choices[0].message.content or "").strip()
    if not content:
        raise LLMError("Empty response from Groq")
    return _parse_json(content)


def chat_text(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 2048,
) -> str:
    s = get_settings()
    client = _client()
    try:
        resp = client.chat.completions.create(
            model=s.groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except RateLimitError as exc:
        raise LLMError(f"Groq rate limit: {exc}") from exc
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
        # Fallback: extract first {...} block
        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            raise LLMError(f"Could not parse JSON from model: {content[:200]}")
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            raise LLMError("JSON root must be an object")
        return data


def model_label() -> str:
    s = get_settings()
    return f"groq:{s.groq_model}"
