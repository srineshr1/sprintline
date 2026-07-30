"""Disk cache for AI folder analysis — skip Groq when folder content is unchanged."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

# backend/data/ai_cache/
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "ai_cache"
_MAX_AGE_SEC = 7 * 24 * 3600  # 7 days


def _ensure_dir() -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def content_fingerprint(folder: str | Path, extra: str = "") -> str:
    """Hash of relative paths + sizes + mtimes for text-ish files (cheap)."""
    root = Path(folder)
    h = hashlib.sha256()
    h.update(extra.encode("utf-8", errors="replace"))
    if not root.is_dir():
        h.update(b"missing")
        return h.hexdigest()[:32]

    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # prune heavy / secret dirs
            dirnames[:] = [
                d
                for d in sorted(dirnames)
                if d
                not in {
                    "node_modules",
                    ".git",
                    ".venv",
                    "venv",
                    "dist",
                    "build",
                    "__pycache__",
                    ".next",
                    "target",
                }
                and not d.startswith(".")
            ]
            rel_dir = os.path.relpath(dirpath, root)
            depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
            if depth > 3:
                dirnames.clear()
                continue
            for name in sorted(filenames)[:80]:
                if name.startswith(".env"):
                    continue
                full = Path(dirpath) / name
                try:
                    st = full.stat()
                except OSError:
                    continue
                if st.st_size > 400_000:
                    continue
                rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                h.update(rel.encode("utf-8", errors="replace"))
                h.update(str(st.st_size).encode())
                h.update(str(int(st.st_mtime)).encode())
                count += 1
                if count >= 200:
                    return h.hexdigest()[:32]
    except OSError:
        pass
    h.update(str(count).encode())
    return h.hexdigest()[:32]


def get(key: str) -> Optional[dict[str, Any]]:
    path = _ensure_dir() / f"{key}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    ts = float(raw.get("_cached_at") or 0)
    if ts and (time.time() - ts) > _MAX_AGE_SEC:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    data = raw.get("payload")
    return data if isinstance(data, dict) else None


def put(key: str, payload: dict[str, Any]) -> None:
    path = _ensure_dir() / f"{key}.json"
    try:
        path.write_text(
            json.dumps(
                {"_cached_at": time.time(), "payload": payload},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def cache_key(folder: str | Path, model: str, mode: str = "import_v2") -> str:
    fp = content_fingerprint(folder, extra=f"{model}|{mode}")
    # Include path so two folders with identical trees don't collide wrongly
    # (they can share cache if content matches — that's fine)
    h = hashlib.sha256(f"{mode}|{model}|{fp}".encode()).hexdigest()[:40]
    return h
