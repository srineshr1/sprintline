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

    def ai_status(self) -> dict:
        return {
            "mode": self.ai_mode,
            "provider": "groq" if self.use_llm() else "stub",
            "model": self.groq_model if self.use_llm() else None,
            "import_model": self.groq_import_model if self.use_llm() else None,
            "configured": self.has_groq_key,
            "llm_active": self.use_llm(),
        }
