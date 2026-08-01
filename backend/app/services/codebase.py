"""Pack a project directory into LLM-safe context (file tree + key sources).

Never reads secret-looking files. Caps total bytes so requests stay within
model context and stay snappy.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Limits — frugal free-tier defaults (~12k TPM shared by prompt + completion).
# generate_backlog overrides via Settings (SPRINTLINE_BACKLOG_MAX_*).
MAX_FILES = 12
MAX_TOTAL_CHARS = 10_000
MAX_FILE_CHARS = 2_200
MAX_TREE_ENTRIES = 80
MAX_DEPTH = 3

SKIP_DIR_NAMES = {
    "node_modules",
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "out",
    "coverage",
    "vendor",
    "site-packages",
    ".idea",
    ".vscode",
    ".cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "worktrees",
    "eggs",
    ".eggs",
    "htmlcov",
    "staticfiles",
    "media",
    ".turbo",
    ".parcel-cache",
    "storybook-static",
}

# Never open these (secrets / noise)
SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".war",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".svg",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".webm",
    ".wav",
    ".lock",
    ".map",
    ".min.js",
    ".min.css",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# Prefer these when ranking which files to include
PRIORITY_NAMES = {
    "readme.md": 100,
    "project.md": 95,
    "package.json": 90,
    "pyproject.toml": 90,
    "cargo.toml": 90,
    "go.mod": 90,
    "composer.json": 85,
    "gemfile": 85,
    "requirements.txt": 85,
    "todo.md": 80,
    "todos.md": 80,
    "backlog.md": 80,
    "tasks.md": 80,
    "dockerfile": 70,
    "docker-compose.yml": 70,
    "docker-compose.yaml": 70,
    "makefile": 65,
    "main.py": 60,
    "app.py": 60,
    "index.ts": 55,
    "index.tsx": 55,
    "main.ts": 55,
    "main.tsx": 55,
    "app.tsx": 55,
    "app.ts": 55,
    "schema.prisma": 50,
}

PRIORITY_SUFFIXES = {
    ".md": 40,
    ".py": 35,
    ".ts": 34,
    ".tsx": 34,
    ".js": 30,
    ".jsx": 30,
    ".go": 30,
    ".rs": 30,
    ".java": 28,
    ".kt": 28,
    ".rb": 28,
    ".php": 26,
    ".toml": 25,
    ".yaml": 22,
    ".yml": 22,
    ".json": 20,
    ".sql": 18,
    ".sh": 15,
    ".css": 10,
    ".html": 12,
}


def _is_secret_name(name: str) -> bool:
    lower = name.lower()
    if lower in SKIP_FILE_NAMES:
        return True
    if lower.startswith(".env"):
        return True
    if "secret" in lower or "credential" in lower or "private" in lower:
        if lower.endswith((".pem", ".key", ".p12", ".pfx", ".json", ".txt")):
            return True
    return False


def _score_file(rel: str) -> int:
    name = Path(rel).name.lower()
    score = PRIORITY_NAMES.get(name, 0)
    if score == 0:
        for suf, s in PRIORITY_SUFFIXES.items():
            if name.endswith(suf):
                score = s
                break
    # Prefer shallower paths
    depth = rel.count(os.sep)
    score -= depth * 3
    # Prefer src/app over tests for product understanding
    lower = rel.lower()
    if "/test" in f"/{lower}" or lower.startswith("test") or "/__tests__" in lower:
        score -= 15
    if lower.startswith("src/") or lower.startswith("app/") or "/src/" in lower:
        score += 8
    return score


def _safe_read(path: Path, limit: int = MAX_FILE_CHARS) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in raw[:4096]:
        return ""  # binary
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return ""
    text = text.replace("\r\n", "\n")
    if len(text) > limit:
        text = text[:limit] + "\n… [truncated]"
    return text


def collect_project_context(
    root: str | Path,
    *,
    max_files: int = MAX_FILES,
    max_total_chars: int = MAX_TOTAL_CHARS,
) -> dict[str, Any]:
    """Walk ``root`` and return tree + selected file contents for the LLM.

    Returns::
        {
          "root": str,
          "exists": bool,
          "tree": str,                 # indented file tree
          "files": [{path, chars, content}, ...],
          "file_paths": [str, ...],    # paths included with content
          "skipped_dirs": [str, ...],
          "total_chars": int,
          "note": str,
        }
    """
    root_path = Path(root).expanduser()
    try:
        root_path = root_path.resolve(strict=True)
    except (OSError, RuntimeError, FileNotFoundError):
        return {
            "root": str(root),
            "exists": False,
            "tree": "",
            "files": [],
            "file_paths": [],
            "skipped_dirs": [],
            "total_chars": 0,
            "note": "Project path does not exist or is unreadable.",
        }

    if not root_path.is_dir():
        return {
            "root": str(root_path),
            "exists": False,
            "tree": "",
            "files": [],
            "file_paths": [],
            "skipped_dirs": [],
            "total_chars": 0,
            "note": "Path is not a directory.",
        }

    candidates: list[tuple[int, str, Path]] = []
    tree_lines: list[str] = [root_path.name + "/"]
    skipped_dirs: list[str] = []
    tree_count = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        rel_dir = os.path.relpath(dirpath, root_path)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth > MAX_DEPTH:
            dirnames.clear()
            continue

        # prune dirs in-place
        kept: list[str] = []
        for d in sorted(dirnames):
            if d in SKIP_DIR_NAMES or d.startswith("."):
                skipped_dirs.append(
                    d if rel_dir == "." else f"{rel_dir}/{d}"
                )
                continue
            kept.append(d)
        dirnames[:] = kept

        indent = "  " * depth
        if rel_dir != "." and tree_count < MAX_TREE_ENTRIES:
            tree_lines.append(f"{indent}{Path(dirpath).name}/")
            tree_count += 1

        for name in sorted(filenames):
            if _is_secret_name(name):
                continue
            lower = name.lower()
            if any(lower.endswith(s) for s in SKIP_SUFFIXES):
                continue
            full = Path(dirpath) / name
            try:
                if not full.is_file() or full.stat().st_size > 400_000:
                    continue
            except OSError:
                continue
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            rel = rel.replace("\\", "/")
            if tree_count < MAX_TREE_ENTRIES:
                tree_lines.append(f"{indent}  {name}")
                tree_count += 1
            candidates.append((_score_file(rel), rel, full))

    candidates.sort(key=lambda t: (-t[0], t[1]))

    files: list[dict[str, Any]] = []
    total = 0
    for _score, rel, full in candidates:
        if len(files) >= max_files:
            break
        remaining = max_total_chars - total
        if remaining < 400:
            break
        content = _safe_read(full, min(MAX_FILE_CHARS, remaining))
        if not content.strip():
            continue
        files.append({"path": rel, "chars": len(content), "content": content})
        total += len(content)

    note_parts = [
        f"Included {len(files)} file(s), {total} chars of content.",
        f"Tree shows up to depth {MAX_DEPTH}.",
    ]
    if skipped_dirs:
        uniq = sorted(set(skipped_dirs))[:12]
        note_parts.append("Skipped dirs: " + ", ".join(uniq))

    return {
        "root": str(root_path),
        "exists": True,
        "tree": "\n".join(tree_lines),
        "files": files,
        "file_paths": [f["path"] for f in files],
        "skipped_dirs": sorted(set(skipped_dirs))[:40],
        "total_chars": total,
        "note": " ".join(note_parts),
    }


def format_context_for_prompt(ctx: dict[str, Any], *, max_chars: int = MAX_TOTAL_CHARS) -> str:
    """Render packed context as a single prompt section."""
    if not ctx.get("exists"):
        return f"(No codebase at {ctx.get('root')}: {ctx.get('note', '')})"

    parts = [
        f"## Project root\n{ctx['root']}",
        f"## File tree\n```\n{ctx.get('tree') or '(empty)'}\n```",
        "## Selected file contents",
    ]
    used = sum(len(p) for p in parts)
    for f in ctx.get("files") or []:
        block = f"\n### {f['path']}\n```\n{f['content']}\n```\n"
        if used + len(block) > max_chars:
            parts.append("\n… further files omitted for length.\n")
            break
        parts.append(block)
        used += len(block)
    parts.append(f"\n_Context note: {ctx.get('note', '')}_")
    return "\n".join(parts)


def context_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    """Compact metadata safe to return to the UI (no full file bodies)."""
    return {
        "root": ctx.get("root"),
        "exists": bool(ctx.get("exists")),
        "file_paths": list(ctx.get("file_paths") or []),
        "file_count": len(ctx.get("file_paths") or []),
        "total_chars": int(ctx.get("total_chars") or 0),
        "tree_preview": (ctx.get("tree") or "")[:2500],
        "note": ctx.get("note") or "",
        "skipped_dirs": list(ctx.get("skipped_dirs") or [])[:20],
    }


# Manifest / docs only — used for token-frugal import AI (not full source dump)
_COMPACT_NAMES = {
    "readme.md",
    "project.md",
    "package.json",
    "pyproject.toml",
    "cargo.toml",
    "go.mod",
    "composer.json",
    "gemfile",
    "requirements.txt",
    "todo.md",
    "todos.md",
    "backlog.md",
    "tasks.md",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def collect_compact_card(
    root: str | Path,
    *,
    max_total_chars: int = 4_000,
    readme_chars: int = 1_000,
) -> dict[str, Any]:
    """Token-frugal pack: shallow tree + README/manifests only (no full src dump).

    Aimed at import enrichment on free-tier Groq (~1–2k tokens/folder).
    """
    base = collect_project_context(
        root, max_files=6, max_total_chars=max_total_chars
    )
    if not base.get("exists"):
        return base

    # Prefer only high-signal names; re-read with tighter caps
    root_path = Path(base["root"])
    files: list[dict[str, Any]] = []
    total = 0
    tree_lines = (base.get("tree") or "").splitlines()[:80]
    tree = "\n".join(tree_lines)

    # Walk top 2 levels for compact-name files
    found: list[tuple[int, str, Path]] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root_path):
            rel_dir = os.path.relpath(dirpath, root_path)
            depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
            if depth > 2:
                dirnames.clear()
                continue
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and not d.startswith(".")
            ]
            for name in filenames:
                lower = name.lower()
                if lower not in _COMPACT_NAMES and not lower.endswith(
                    (".toml", ".md")
                ):
                    # allow one main entry if shallow
                    if depth > 0 or lower not in {
                        "main.py",
                        "app.py",
                        "index.ts",
                        "index.tsx",
                        "main.ts",
                        "main.tsx",
                    }:
                        if lower not in _COMPACT_NAMES:
                            continue
                if _is_secret_name(name):
                    continue
                rel = name if rel_dir == "." else f"{rel_dir}/{name}".replace("\\", "/")
                pri = 100 if lower in _COMPACT_NAMES else 40
                if "readme" in lower:
                    pri = 120
                found.append((pri, rel, Path(dirpath) / name))
    except OSError:
        pass

    found.sort(key=lambda t: (-t[0], t[1]))
    for _pri, rel, full in found[:8]:
        limit = readme_chars if "readme" in rel.lower() else 700
        remaining = max_total_chars - total - len(tree)
        if remaining < 200:
            break
        content = _safe_read(full, min(limit, remaining))
        if not content.strip():
            continue
        files.append({"path": rel, "chars": len(content), "content": content})
        total += len(content)

    note = (
        f"Compact card: {len(files)} docs/manifests, {total} chars + tree "
        f"(no full source dump — import mode)."
    )
    return {
        "root": str(root_path),
        "exists": True,
        "tree": tree,
        "files": files,
        "file_paths": [f["path"] for f in files],
        "skipped_dirs": base.get("skipped_dirs") or [],
        "total_chars": total + len(tree),
        "note": note,
        "mode": "compact",
    }
