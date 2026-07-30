"""Test-suite wiring.

Point the app at a throwaway SQLite file before ``app.main`` is imported, so
test runs never write demo rows into the development database
(``backend/data/app.db``). Test modules import ``app.main`` at module scope, and
conftest is loaded first, so setting the environment variable here is early
enough.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "sprintline-test.db"

# A stale file from a previous run would leak state between sessions.
_TMP_DB.unlink(missing_ok=True)

os.environ["SPRINTLINE_DB_PATH"] = str(_TMP_DB)
# Keep API tests offline and deterministic (no Groq calls).
os.environ["SPRINTLINE_AI_MODE"] = "stub"
# Settings are cached; force rebuild if config was imported early.
try:
    from app.config import get_settings

    get_settings.cache_clear()
except Exception:
    pass
