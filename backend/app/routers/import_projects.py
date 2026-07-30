"""Scan a local projects directory and import folders as projects.

Two endpoints mirror the UI flow:

* ``POST /api/import/scan``  — dry run. Reads the filesystem, writes nothing,
  and annotates each folder with whether it was imported before.
  With ``use_ai=true`` (default), key files are packed and sent to Groq for
  brief/goals/backlog enrichment.
* ``POST /api/import/apply`` — creates (or re-syncs) the selected folders.

Idempotency: ``Project.source_path`` holds the absolute folder path. A folder
that already has a project re-syncs — only todos whose titles aren't already
stories get added, so existing edits, points and statuses survive a re-scan.

Each folder is committed on its own, so one bad folder can't roll back the
others; failures come back in ``errors``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..database import get_db
from ..serializers import dumps
from ..services import ai_agents, importer

router = APIRouter(prefix="/api/import", tags=["import"])


def _projects_by_source(db: Session) -> dict[str, models.Project]:
    rows = (
        db.query(models.Project)
        .filter(models.Project.source_path.isnot(None))
        .all()
    )
    return {p.source_path: p for p in rows if p.source_path}


def _existing_story_keys(db: Session, project_id: int) -> set[str]:
    rows = (
        db.query(models.Story.title)
        .join(models.Epic)
        .filter(models.Epic.project_id == project_id)
        .all()
    )
    return {importer.story_key(title) for (title,) in rows}


def _status_counts(epics: list[dict]) -> dict[str, int]:
    counts = {"todo": 0, "in_progress": 0, "done": 0}
    for epic in epics:
        for story in epic.get("stories") or []:
            st = story.get("status") or "todo"
            if st not in counts:
                counts[st] = 0
            counts[st] += 1
    return counts


def _enrich_with_ai(preview: dict) -> dict:
    """Pack folder files + call Groq; merge onto heuristic preview."""
    settings = get_settings()
    if not settings.use_llm():
        preview["ai_used"] = False
        preview["ai_agent"] = None
        preview["llm_error"] = "LLM not configured (set GROQ_API_KEY)"
        return preview

    result = ai_agents.analyze_project_folder(
        preview["source_path"],
        heuristic=preview,
    )
    preview["codebase_context"] = result.get("codebase_context")
    if not result.get("ok"):
        preview["ai_used"] = False
        preview["ai_agent"] = None
        preview["llm_error"] = result.get("error") or "AI analysis failed"
        return preview

    preview["ai_used"] = True
    preview["ai_agent"] = result.get("agent")
    preview["ai_analysis"] = result.get("analysis") or ""
    preview["ai_rationale"] = result.get("rationale") or ""
    preview["tech_stack"] = result.get("tech_stack") or []
    preview["llm_error"] = None

    if result.get("name"):
        preview["name"] = result["name"]
    if result.get("brief"):
        preview["brief"] = result["brief"]
        if not preview.get("brief_source"):
            preview["brief_source"] = "ai:codebase"
    if result.get("goals"):
        preview["goals"] = result["goals"]
    if result.get("constraints"):
        preview["constraints"] = result["constraints"]
    if result.get("epics"):
        preview["epics"] = result["epics"]
        all_stories = [s for e in preview["epics"] for s in e.get("stories") or []]
        preview["epic_count"] = len(preview["epics"])
        preview["story_count"] = len(all_stories)
        preview["status_counts"] = _status_counts(preview["epics"])
        preview["sample_titles"] = [s["title"] for s in all_stories[:4]]
        sources = list(preview.get("story_sources") or [])
        if "ai:codebase" not in sources:
            sources.append("ai:codebase")
        preview["story_sources"] = sources
    return preview


def _scan_payload(
    root_path: str | None,
    use_ai: bool,
    *,
    only_folders: set[str] | None = None,
) -> dict:
    result = importer.scan(root_path)
    settings = get_settings()
    # Only run AI when requested and LLM is live. Sequential to stay under rate limits.
    if use_ai and settings.use_llm():
        enriched = []
        for preview in result["projects"]:
            if only_folders is not None and preview["folder"] not in only_folders:
                preview.setdefault("ai_used", False)
                enriched.append(preview)
                continue
            try:
                enriched.append(_enrich_with_ai(preview))
            except Exception as exc:  # noqa: BLE001 — keep scan resilient
                preview["ai_used"] = False
                preview["llm_error"] = str(exc)[:200]
                enriched.append(preview)
        result["projects"] = enriched
        result["total_stories"] = sum(p.get("story_count") or 0 for p in enriched)
    else:
        for preview in result["projects"]:
            preview.setdefault("ai_used", False)
    result["use_ai"] = bool(use_ai and settings.use_llm())
    result["ai_status"] = settings.ai_status()
    return result


@router.get("/roots", response_model=schemas.ImportRootsResponse)
def get_roots():
    """Where scanning is allowed — used to pre-fill the path input."""
    roots = importer.allowed_roots()
    return {
        "default_root": str(roots[0]) if roots else "",
        "allowed_roots": [str(r) for r in roots],
    }


@router.post("/scan", response_model=schemas.ImportScanResponse)
def scan_directory(
    body: schemas.ImportScanRequest = schemas.ImportScanRequest(),
    db: Session = Depends(get_db),
):
    """Dry-run preview of importable projects. Never writes to the database."""
    try:
        result = _scan_payload(body.root_path, body.use_ai)
    except importer.ImportError_ as exc:
        raise HTTPException(400, str(exc)) from None

    known = _projects_by_source(db)
    for preview in result["projects"]:
        existing = known.get(preview["source_path"])
        if existing is None:
            preview["existing_project_id"] = None
            preview["new_story_count"] = preview["story_count"]
            continue
        seen = _existing_story_keys(db, existing.id)
        fresh = sum(
            1
            for epic in preview["epics"]
            for story in epic["stories"]
            if importer.story_key(story["title"]) not in seen
        )
        preview["existing_project_id"] = existing.id
        preview["new_story_count"] = fresh

    return result


@router.post("/apply", response_model=schemas.ImportApplyResponse)
def apply_import(
    body: schemas.ImportApplyRequest = schemas.ImportApplyRequest(),
    db: Session = Depends(get_db),
):
    """Create or re-sync the selected folders as projects."""
    wanted = {s.strip() for s in body.selections if s and s.strip()}
    try:
        # Only AI-enrich folders we will import (saves tokens + latency).
        result = _scan_payload(
            body.root_path,
            body.use_ai,
            only_folders=wanted or None,
        )
    except importer.ImportError_ as exc:
        raise HTTPException(400, str(exc)) from None

    imported: list[dict] = []
    skipped: list[dict[str, str]] = list(result["skipped"])
    errors: list[dict[str, str]] = list(result["errors"])

    for preview in result["projects"]:
        folder = preview["folder"]
        # Selections name folders; empty selection means "import everything".
        if wanted and folder not in wanted and preview["source_path"] not in wanted:
            continue
        if preview["story_count"] == 0 and not preview["brief"]:
            skipped.append({"folder": folder, "reason": "nothing to import"})
            continue

        try:
            imported.append(_apply_one(db, preview))
        except SQLAlchemyError as exc:
            db.rollback()
            errors.append({"folder": folder, "error": str(exc)[:200]})

    return {
        "root_path": result["root_path"],
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "projects_created": sum(1 for r in imported if not r["resynced"]),
        "projects_resynced": sum(1 for r in imported if r["resynced"]),
        "stories_created": sum(r["stories_created"] for r in imported),
    }


def _apply_one(db: Session, preview: dict) -> dict:
    """Import one scanned folder. Commits on success, raises on DB failure."""
    source_path = preview["source_path"]
    project = (
        db.query(models.Project)
        .filter(models.Project.source_path == source_path)
        .one_or_none()
    )
    resynced = project is not None

    if project is None:
        project = models.Project(
            name=preview["name"],
            brief=preview["brief"],
            goals=dumps(preview["goals"]),
            constraints=dumps(preview["constraints"]),
            source_path=source_path,
        )
        db.add(project)
        db.flush()
        seen: set[str] = set()
    else:
        # Re-sync: fill in a brief that was empty before, but never clobber
        # one the user has since written. Same for goals/constraints.
        if not (project.brief or "").strip() and preview["brief"]:
            project.brief = preview["brief"]
        if project.goals in (None, "", "[]") and preview["goals"]:
            project.goals = dumps(preview["goals"])
        if project.constraints in (None, "", "[]") and preview["constraints"]:
            project.constraints = dumps(preview["constraints"])
        seen = _existing_story_keys(db, project.id)

    epics_by_title = {
        e.title.strip().lower(): e
        for e in db.query(models.Epic)
        .filter(models.Epic.project_id == project.id)
        .all()
    }
    next_epic_order = len(epics_by_title)

    epics_created = 0
    stories_created = 0

    for group in preview["epics"]:
        # Only the stories that aren't already in this project.
        fresh = [
            s for s in group["stories"] if importer.story_key(s["title"]) not in seen
        ]
        if not fresh:
            continue

        title = group["title"]
        epic = epics_by_title.get(title.strip().lower())
        if epic is None:
            epic = models.Epic(
                project_id=project.id,
                title=title,
                description=f"Imported from {preview['folder']}",
                order=next_epic_order,
            )
            db.add(epic)
            db.flush()
            epics_by_title[title.strip().lower()] = epic
            next_epic_order += 1
            epics_created += 1
            story_order = 0
        else:
            story_order = len(epic.stories or [])

        for story in fresh:
            rationale = story.get("rationale") or (
                f"Imported from {preview['folder']}"
                + (
                    f" ({', '.join(preview['story_sources'])})"
                    if preview.get("story_sources")
                    else ""
                )
            )
            if preview.get("ai_used") and not story.get("rationale"):
                rationale = f"AI import ({preview.get('ai_agent')}) from {preview['folder']}"
            db.add(
                models.Story(
                    epic_id=epic.id,
                    title=story["title"],
                    description=story.get("description", ""),
                    acceptance_criteria=dumps(story.get("acceptance_criteria") or []),
                    points=story.get("points", 3),
                    priority=story.get("priority", "medium"),
                    status=story.get("status", "todo"),
                    rationale=rationale,
                    order=story_order,
                )
            )
            seen.add(importer.story_key(story["title"]))
            story_order += 1
            stories_created += 1

    db.add(
        models.Activity(
            project_id=project.id,
            type="project_imported" if not resynced else "project_resynced",
            payload=dumps(
                {
                    "source_path": source_path,
                    "epics_created": epics_created,
                    "stories_created": stories_created,
                    "sources": preview.get("story_sources"),
                    "ai_used": preview.get("ai_used"),
                    "ai_agent": preview.get("ai_agent"),
                    "files_sent": (preview.get("codebase_context") or {}).get(
                        "file_paths"
                    ),
                }
            ),
        )
    )
    db.commit()

    return {
        "folder": preview["folder"],
        "name": project.name,
        "source_path": source_path,
        "project_id": project.id,
        "epics_created": epics_created,
        "stories_created": stories_created,
        "resynced": resynced,
    }
