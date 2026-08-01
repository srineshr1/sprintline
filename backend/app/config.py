"""Runtime settings loaded from environment / backend/.env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# backend/.env (gitignored)
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_PATH, override=False)
# Also allow process env / repo-root .env
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 1_000_000) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, n))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


@lru_cache(maxsize=1)
def get_settings() -> "Settings":
    return Settings()


class Settings:
    def __init__(self) -> None:
        self.groq_api_key: str = (os.environ.get("GROQ_API_KEY") or "").strip()
        # Quality tasks: backlog generate, sprint plan, standup
        self.groq_model: str = (
            os.environ.get("GROQ_MODEL") or "llama-3.3-70b-versatile"
        ).strip()
        # Cheap/fast model for bulk import enrich (token-frugal)
        self.groq_import_model: str = (
            os.environ.get("GROQ_IMPORT_MODEL") or "llama-3.1-8b-instant"
        ).strip()
        self.groq_base_url: str = (
            os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
        ).strip()
        mode = (os.environ.get("SPRINTLINE_AI_MODE") or "auto").strip().lower()
        if mode not in ("auto", "groq", "stub"):
            mode = "auto"
        self.ai_mode: str = mode

        # --- Token budgets (frugal free-tier defaults; raise for quality) ---
        # Backlog generate packs repo context into the prompt — largest lever.
        self.backlog_max_files: int = _env_int("SPRINTLINE_BACKLOG_MAX_FILES", 12, maximum=40)
        self.backlog_max_chars: int = _env_int(
            "SPRINTLINE_BACKLOG_MAX_CHARS", 10_000, minimum=1_000, maximum=40_000
        )
        self.backlog_max_tokens: int = _env_int(
            "SPRINTLINE_BACKLOG_MAX_TOKENS", 2_500, minimum=400, maximum=8_000
        )
        self.sprint_max_tokens: int = _env_int(
            "SPRINTLINE_SPRINT_MAX_TOKENS", 1_200, minimum=200, maximum=4_000
        )
        self.standup_max_tokens: int = _env_int(
            "SPRINTLINE_STANDUP_MAX_TOKENS", 900, minimum=200, maximum=4_000
        )
        self.import_max_tokens: int = _env_int(
            "SPRINTLINE_IMPORT_MAX_TOKENS", 1_400, minimum=200, maximum=4_000
        )
        self.import_max_chars: int = _env_int(
            "SPRINTLINE_IMPORT_MAX_CHARS", 4_000, minimum=500, maximum=12_000
        )
        # Log Groq prompt/completion tokens to the server log + /api/health
        self.log_llm_usage: bool = _env_bool("SPRINTLINE_LOG_LLM_USAGE", True)

    @property
    def has_groq_key(self) -> bool:
        return bool(self.groq_api_key)

    def use_llm(self) -> bool:
        if self.ai_mode == "stub":
            return False
        if self.ai_mode == "groq":
            return self.has_groq_key
        # auto
        return self.has_groq_key

    def token_budgets(self) -> dict:
        return {
            "backlog_max_files": self.backlog_max_files,
            "backlog_max_chars": self.backlog_max_chars,
            "backlog_max_tokens": self.backlog_max_tokens,
            "sprint_max_tokens": self.sprint_max_tokens,
            "standup_max_tokens": self.standup_max_tokens,
            "import_max_tokens": self.import_max_tokens,
            "import_max_chars": self.import_max_chars,
        }

    def ai_status(self) -> dict:
        from .services.llm import usage_snapshot

        return {
            "mode": self.ai_mode,
            "provider": "groq" if self.use_llm() else "stub",
            "model": self.groq_model if self.use_llm() else None,
            "import_model": self.groq_import_model if self.use_llm() else None,
            "configured": self.has_groq_key,
            "llm_active": self.use_llm(),
            "token_budgets": self.token_budgets(),
            "usage": usage_snapshot(),
        }
