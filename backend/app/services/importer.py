"""Scan a local projects directory and turn folders into importable projects.

Scanning rules
--------------
* The root directory holds **one folder per project**; each immediate
  subdirectory is a candidate project. Files at the root are ignored.
* ``name``   — folder name, humanized (``my_cool-app`` → "My Cool App").
* ``brief``  — first of README.md / PROJECT.md / brief.md / description.md,
  converted to plain-ish text and capped at :data:`BRIEF_CAP` characters.
* ``goals`` / ``constraints`` — bullet lists under a "Goals"/"Objectives" and
  "Constraints"/"Non-goals" heading in that same file, when present.
* Stories come from, in priority order:
    1. ``TODO.md`` / ``TODOS.md`` / ``BACKLOG.md`` / ``TASKS.md`` — markdown
       checklists. ``##`` headings become epics, checklist items under a
       heading become that epic's stories.
    2. ``todos.json`` / ``backlog.json`` / ``tasks.json`` — a list of strings,
       a list of objects, or ``{"todos"|"items"|"tasks"|"stories": [...]}``.
    3. ``.todo`` — one task per line (checklist syntax optional).
  Every source found contributes; missing ones are skipped silently.
* Checklist state maps ``[ ]`` → todo, ``[~]``/``[/]``/``[-]`` (or an explicit
  "in progress"/"wip" marker) → in_progress, ``[x]`` → done.
* ``(5)`` in a line sets points, ``[high]``/``[medium]``/``[low]`` sets
  priority; both are stripped from the title. Defaults: 3 points, medium.
* If no ``##`` epic structure is found, everything lands in a single
  "Imported backlog" epic.

Security
--------
Scanning is confined to an allowlist of roots (``PROJECTS_ROOT``, or
``PROJECTS_ROOTS`` for several). Requested paths are fully resolved before the
containment check, so ``..`` traversal and symlinks that escape the root are
both rejected rather than followed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

# ── Limits (keep a pathological directory from hanging a request) ──────────
MAX_PROJECTS = 200
MAX_STORIES_PER_PROJECT = 300
MAX_FILE_BYTES = 512 * 1024
BRIEF_CAP = 700
TITLE_CAP = 380
SAMPLE_TITLES = 4

VALID_STATUS = ("todo", "in_progress", "done")
VALID_PRIORITY = ("high", "medium", "low")

DEFAULT_EPIC_TITLE = "Imported backlog"

BRIEF_FILES = ("README.md", "PROJECT.md", "brief.md", "description.md")
CHECKLIST_FILES = ("TODO.md", "TODOS.md", "BACKLOG.md", "TASKS.md")
JSON_FILES = ("todos.json", "backlog.json", "tasks.json")
PLAIN_FILES = (".todo",)

# Directories that are never projects.
SKIP_DIRS = {
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    "target",
    "out",
    "coverage",
    "vendor",
    "site-packages",
    ".git",
    ".idea",
    ".vscode",
    ".cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "worktrees",
}

GOAL_HEADINGS = ("goals", "goal", "objectives", "objective")
CONSTRAINT_HEADINGS = (
    "constraints",
    "constraint",
    "non-goals",
    "non goals",
    "nongoals",
    "out of scope",
    "limitations",
)


class ImportError_(Exception):
    """Raised for a request-level problem (bad or disallowed root path)."""


# ══════════════════════════════════════════════════════════════════════════
# Root resolution / security
# ══════════════════════════════════════════════════════════════════════════


def _repo_root() -> Path:
    # .../backend/app/services/importer.py → .../ai-project-lifecycle
    return Path(__file__).resolve().parents[3]


def default_root() -> Path:
    """Configured default scan root.

    ``PROJECTS_ROOT`` wins; otherwise the repository's parent directory, which
    is the common "all my projects live here" layout.
    """
    env = os.environ.get("PROJECTS_ROOT", "").strip()
    if env:
        return Path(env).expanduser()
    return _repo_root().parent


def allowed_roots() -> list[Path]:
    """Roots that may be scanned, fully resolved.

    ``PROJECTS_ROOTS`` (os.pathsep-separated) extends the allowlist; the
    default root is always included.
    """
    roots: list[Path] = []

    def add(p: Path) -> None:
        try:
            resolved = p.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            return
        if resolved.is_dir() and resolved not in roots:
            roots.append(resolved)

    add(default_root())
    extra = os.environ.get("PROJECTS_ROOTS", "").strip()
    if extra:
        for chunk in extra.split(os.pathsep):
            if chunk.strip():
                add(Path(chunk.strip()))
    return roots


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_root(raw: Optional[str]) -> Path:
    """Validate a requested scan root against the allowlist.

    Resolution happens **before** the containment check, so ``..`` segments and
    symlinks are normalized away and cannot be used to escape an allowed root.
    """
    roots = allowed_roots()
    if not roots:
        raise ImportError_(
            "No scannable directory is configured. Set PROJECTS_ROOT to a "
            "directory containing your project folders."
        )

    if raw is None or not str(raw).strip():
        return roots[0]

    candidate = str(raw).strip()
    if "\x00" in candidate:
        raise ImportError_("Invalid path")

    try:
        resolved = Path(candidate).expanduser().resolve(strict=True)
    except FileNotFoundError:
        raise ImportError_(f"Path does not exist: {candidate}") from None
    except (OSError, RuntimeError):
        raise ImportError_(f"Path could not be read: {candidate}") from None

    if not resolved.is_dir():
        raise ImportError_(f"Not a directory: {candidate}")

    if not any(_is_within(resolved, root) for root in roots):
        # Deliberately does not echo the allowlist back to the caller.
        raise ImportError_(
            "Path is outside the allowed projects directory. "
            "Set PROJECTS_ROOT (or PROJECTS_ROOTS) to permit it."
        )
    return resolved


# ══════════════════════════════════════════════════════════════════════════
# Text helpers
# ══════════════════════════════════════════════════════════════════════════

_WORD_SPLIT = re.compile(r"[-_.\s]+")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_FENCE = re.compile(r"```.*?```", re.S)
_MD_INLINE_CODE = re.compile(r"`([^`]*)`")
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_EMPHASIS = re.compile(r"(\*\*|__|\*|_)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_CHECKLIST = re.compile(r"^\s*[-*+]\s*\[([ xX~\-/])\]\s*(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_POINTS_TAG = re.compile(r"\((\d{1,2})\)")
_PRIORITY_TAG = re.compile(r"\[(high|medium|med|low)\]", re.I)
_WIP_MARKER = re.compile(r"\b(in[\s\-_]?progress|wip|doing|started)\b", re.I)
_TRAILING_META = re.compile(r"^[\s\-–—:·|,]+|[\s\-–—:·|,]+$")


def humanize(name: str) -> str:
    """``my_cool-app`` → ``My Cool App``; existing capitalisation is kept."""
    parts = [p for p in _WORD_SPLIT.split(name.strip()) if p]
    if not parts:
        return name.strip() or "Untitled project"
    out: list[str] = []
    for p in parts:
        # Don't flatten deliberate casing like "AI", "GPUcal", "iOS".
        out.append(p if any(c.isupper() for c in p[1:]) else p[:1].upper() + p[1:])
    return " ".join(out)


def _read_text(path: Path) -> str:
    """Read a small text file, or '' if it is missing/binary/too large."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def md_to_text(md: str) -> str:
    """Markdown → plain-ish prose, good enough for a project brief."""
    s = _MD_FENCE.sub(" ", md)
    s = _MD_IMAGE.sub("", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _MD_INLINE_CODE.sub(r"\1", s)
    s = _HTML_TAG.sub("", s)
    lines: list[str] = []
    for raw in s.splitlines():
        line = raw.strip()
        if not line or line.startswith(("|", ">", "---", "===")):
            continue
        h = _HEADING.match(line)
        if h:
            # Skip the title heading; keep no heading text in the brief body.
            continue
        line = _MD_EMPHASIS.sub("", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


#: Below this many characters, an intro is treated as absent rather than short.
#: Only meant to catch title-only or badge-only intros — a one-line
#: description is a perfectly good brief and must survive.
MIN_LEAD_CHARS = 16


def lead_section(md: str) -> str:
    """The document's intro: everything before the first ``##`` heading.

    A README's description is normally the prose under the title, while the
    ``##`` sections that follow are goals, install steps, licence and so on —
    including those would make the brief restate the goals we extract
    separately. Falls back to the whole document only when the intro carries
    essentially no prose (e.g. READMEs that open straight into "## Overview").
    """
    cut = md
    for i, raw in enumerate(md.splitlines()):
        h = _HEADING.match(raw.strip())
        if h and len(h.group(1)) >= 2:
            cut = "\n".join(md.splitlines()[:i])
            break
    return cut if len(md_to_text(cut)) >= MIN_LEAD_CHARS else md


def _cap(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a sentence/word boundary over a hard slice.
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > limit * 0.5 else cut).strip() + "…"


def _section_bullets(md: str, headings: Iterable[str]) -> list[str]:
    """Bullet items directly under any heading whose text matches."""
    wanted = {h.lower() for h in headings}
    out: list[str] = []
    capturing = False
    for raw in md.splitlines():
        h = _HEADING.match(raw.strip())
        if h:
            title = _MD_EMPHASIS.sub("", h.group(2)).strip().rstrip(":").lower()
            capturing = title in wanted
            continue
        if not capturing:
            continue
        line = raw.strip()
        if not line:
            continue
        check = _CHECKLIST.match(line)
        bullet = _BULLET.match(line)
        text = check.group(2) if check else (bullet.group(1) if bullet else None)
        if text is None:
            # Prose after the bullets ends the section.
            if out:
                capturing = False
            continue
        cleaned = _MD_EMPHASIS.sub("", _MD_LINK.sub(r"\1", text)).strip()
        if cleaned:
            out.append(_cap(cleaned, 200))
        if len(out) >= 12:
            break
    return out


# ══════════════════════════════════════════════════════════════════════════
# Story extraction
# ══════════════════════════════════════════════════════════════════════════


def _normalize_status(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if s in ("done", "complete", "completed", "closed", "finished"):
        return "done"
    if s in ("in_progress", "inprogress", "wip", "doing", "started", "active"):
        return "in_progress"
    return "todo"


def _normalize_priority(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("high", "urgent", "critical", "p0", "p1"):
        return "high"
    if s in ("low", "minor", "p3", "p4"):
        return "low"
    return "medium"


def _marker_status(marker: str) -> str:
    m = marker.strip().lower()
    if m == "x":
        return "done"
    if m in ("~", "/", "-"):
        return "in_progress"
    return "todo"


def _parse_task_line(text: str, status: str) -> dict[str, Any]:
    """Pull points/priority tags out of a checklist line's text."""
    points = 3
    priority = "medium"

    pm = _POINTS_TAG.search(text)
    if pm:
        try:
            val = int(pm.group(1))
            if 0 < val <= 21:
                points = val
                text = text.replace(pm.group(0), " ", 1)
        except ValueError:
            pass

    prm = _PRIORITY_TAG.search(text)
    if prm:
        priority = _normalize_priority(prm.group(1))
        text = text.replace(prm.group(0), " ", 1)

    if status == "todo" and _WIP_MARKER.search(text):
        status = "in_progress"
        text = _WIP_MARKER.sub("", text, count=1)

    title = _MD_EMPHASIS.sub("", _MD_LINK.sub(r"\1", text))
    title = _MD_INLINE_CODE.sub(r"\1", title)
    title = re.sub(r"\(\s*\)|\[\s*\]", "", title)
    title = _TRAILING_META.sub("", re.sub(r"\s+", " ", title))

    return {
        "title": _cap(title, TITLE_CAP),
        "status": status,
        "points": points,
        "priority": priority,
    }


def parse_markdown_checklist(md: str) -> list[dict[str, Any]]:
    """Parse a TODO-style markdown file into epic groups.

    Returns ``[{"title": epic, "stories": [...]}]``. ``##``-level headings (and
    deeper) open a new epic; items before any heading go to a default epic.
    """
    groups: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None

    def ensure(title: str) -> dict[str, Any]:
        nonlocal current
        for g in groups:
            if g["title"].lower() == title.lower():
                current = g
                return g
        g = {"title": _cap(title, 280), "stories": []}
        groups.append(g)
        current = g
        return g

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        h = _HEADING.match(line.strip())
        if h:
            level = len(h.group(1))
            title = _MD_EMPHASIS.sub("", h.group(2)).strip().rstrip(":")
            # Level 1 is the document title, not an epic.
            if level >= 2 and title:
                ensure(title)
            continue

        check = _CHECKLIST.match(line)
        if check:
            story = _parse_task_line(check.group(2), _marker_status(check.group(1)))
            if story["title"]:
                (current or ensure(DEFAULT_EPIC_TITLE))["stories"].append(story)

    return [g for g in groups if g["stories"]]


def parse_json_todos(raw: str) -> list[dict[str, Any]]:
    """Parse the simple JSON shapes into a flat story list."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    items: Any = data
    if isinstance(data, dict):
        for key in ("todos", "items", "tasks", "stories", "backlog"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            return []
    if not isinstance(items, list):
        return []

    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            title = item.strip()
            if title:
                out.append(_parse_task_line(title, "todo"))
            continue
        if not isinstance(item, dict):
            continue
        title = str(
            item.get("title") or item.get("text") or item.get("name") or ""
        ).strip()
        if not title:
            continue
        status = _normalize_status(item.get("status") or item.get("state"))
        if status == "todo" and item.get("done") is True:
            status = "done"
        if status == "todo" and item.get("completed") is True:
            status = "done"
        points = item.get("points") or item.get("estimate") or 3
        try:
            points = int(points)
        except (TypeError, ValueError):
            points = 3
        out.append(
            {
                "title": _cap(title, TITLE_CAP),
                "status": status,
                "points": points if 0 < points <= 21 else 3,
                "priority": _normalize_priority(item.get("priority")),
                "description": _cap(str(item.get("description") or ""), 400),
            }
        )
    return out


def parse_plain_todos(raw: str) -> list[dict[str, Any]]:
    """One task per line; checklist markers honoured when present."""
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        check = _CHECKLIST.match(line)
        if check:
            story = _parse_task_line(check.group(2), _marker_status(check.group(1)))
        else:
            bullet = _BULLET.match(line)
            story = _parse_task_line(bullet.group(1) if bullet else text, "todo")
        if story["title"]:
            out.append(story)
    return out


# ══════════════════════════════════════════════════════════════════════════
# Per-folder scan
# ══════════════════════════════════════════════════════════════════════════


def _find_file(folder: Path, names: Iterable[str]) -> Optional[Path]:
    """Case-insensitive lookup of the first matching direct child file.

    The resolved match must still sit inside ``folder`` so a symlinked
    ``TODO.md`` cannot pull in content from elsewhere on disk.
    """
    try:
        entries = {e.name.lower(): e for e in folder.iterdir() if e.is_file()}
    except OSError:
        return None
    for name in names:
        entry = entries.get(name.lower())
        if entry is None:
            continue
        try:
            if _is_within(entry.resolve(strict=True), folder.resolve(strict=True)):
                return entry
        except (OSError, RuntimeError):
            continue
    return None


def story_key(title: str) -> str:
    """Loose identity for a task title.

    Used both to dedupe within a scan and to decide, on re-sync, whether a
    discovered todo already exists as a story. Punctuation- and case-
    insensitive so light editing of a TODO line doesn't re-import it.
    """
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def _dedupe_stories(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in stories:
        key = story_key(s["title"])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= MAX_STORIES_PER_PROJECT:
            break
    return out


def scan_project_folder(folder: Path) -> dict[str, Any]:
    """Inspect one folder and describe the project it would import as."""
    brief = ""
    goals: list[str] = []
    constraints: list[str] = []

    brief_file = _find_file(folder, BRIEF_FILES)
    if brief_file is not None:
        md = _read_text(brief_file)
        if md:
            # Brief comes from the intro only; goals/constraints are pulled
            # from their own sections so the brief doesn't restate them.
            brief = _cap(md_to_text(lead_section(md)), BRIEF_CAP)
            goals = _section_bullets(md, GOAL_HEADINGS)
            constraints = _section_bullets(md, CONSTRAINT_HEADINGS)

    epics: list[dict[str, Any]] = []
    sources: list[str] = []

    # 1. Markdown checklists — the only source that can define epics.
    for name in CHECKLIST_FILES:
        f = _find_file(folder, (name,))
        if f is None:
            continue
        groups = parse_markdown_checklist(_read_text(f))
        if groups:
            epics.extend(groups)
            sources.append(f.name)

    # 2. JSON, then 3. plain — flat lists folded into one epic each.
    flat: list[dict[str, Any]] = []
    for name in JSON_FILES:
        f = _find_file(folder, (name,))
        if f is None:
            continue
        items = parse_json_todos(_read_text(f))
        if items:
            flat.extend(items)
            sources.append(f.name)
    for name in PLAIN_FILES:
        f = _find_file(folder, (name,))
        if f is None:
            continue
        items = parse_plain_todos(_read_text(f))
        if items:
            flat.extend(items)
            sources.append(f.name)

    if flat:
        existing = next(
            (g for g in epics if g["title"] == DEFAULT_EPIC_TITLE), None
        )
        if existing:
            existing["stories"].extend(flat)
        else:
            epics.append({"title": DEFAULT_EPIC_TITLE, "stories": flat})

    # Dedupe across sources, then drop epics left empty.
    for g in epics:
        g["stories"] = _dedupe_stories(g["stories"])
    epics = [g for g in epics if g["stories"]]

    # Global cap across epics.
    total = 0
    capped: list[dict[str, Any]] = []
    for g in epics:
        if total >= MAX_STORIES_PER_PROJECT:
            break
        room = MAX_STORIES_PER_PROJECT - total
        g["stories"] = g["stories"][:room]
        total += len(g["stories"])
        capped.append(g)
    epics = capped

    all_stories = [s for g in epics for s in g["stories"]]
    counts = {k: 0 for k in VALID_STATUS}
    for s in all_stories:
        counts[s["status"]] = counts.get(s["status"], 0) + 1

    return {
        "name": humanize(folder.name),
        "folder": folder.name,
        "source_path": str(folder),
        "brief": brief,
        "goals": goals,
        "constraints": constraints,
        "brief_source": brief_file.name if brief_file else None,
        "story_sources": sources,
        "epics": epics,
        "epic_count": len(epics),
        "story_count": len(all_stories),
        "status_counts": counts,
        "sample_titles": [s["title"] for s in all_stories[:SAMPLE_TITLES]],
    }


def scan(root_path: Optional[str] = None) -> dict[str, Any]:
    """Dry run: describe every importable folder under ``root_path``.

    Per-folder failures are collected rather than aborting the scan.
    """
    root = resolve_root(root_path)

    projects: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        raise ImportError_(f"Could not read directory: {exc}") from exc

    for entry in entries:
        if len(projects) >= MAX_PROJECTS:
            skipped.append(
                {"folder": entry.name, "reason": f"scan limit ({MAX_PROJECTS}) reached"}
            )
            continue
        try:
            if not entry.is_dir():
                continue
            if entry.name.startswith(".") or entry.name in SKIP_DIRS:
                skipped.append({"folder": entry.name, "reason": "ignored directory"})
                continue
            # Never follow a symlink that leaves the root.
            resolved = entry.resolve(strict=True)
            if entry.is_symlink() and not _is_within(resolved, root):
                skipped.append(
                    {"folder": entry.name, "reason": "symlink outside root"}
                )
                continue
            projects.append(scan_project_folder(entry))
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append({"folder": entry.name, "error": str(exc)[:200]})

    return {
        "root_path": str(root),
        "default_root": str(allowed_roots()[0]) if allowed_roots() else "",
        "projects": projects,
        "skipped": skipped,
        "errors": errors,
        "total_projects": len(projects),
        "total_stories": sum(p["story_count"] for p in projects),
    }
