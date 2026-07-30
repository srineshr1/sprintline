"""Scan a local projects directory and import folders as projects.

* ``POST /api/import/scan``  — **always heuristic only** (no Groq). Fast preview.
* ``POST /api/import/apply`` — create/re-sync selected folders; optional AI enrich
  (compact card + cheap import model + disk cache) **only for selected** folders.

This split avoids burning the free-tier daily token budget on bulk scans.
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
    """Compact-card Groq enrich; merge onto heuristic preview."""
    settings = get_settings()
    if not settings.use_llm():
        preview["ai_used"] = False
        preview["ai_agent"] = None
        preview["llm_error"] = "LLM not configured (set GROQ_API_KEY)"
        return preview

    result = ai_agents.analyze_project_folder(
        preview["source_path"],
        heuristic=preview,
        use_cache=True,
    )
    preview["codebase_context"] = result.get("codebase_context")
    preview["ai_cached"] = bool(result.get("cached"))
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
            preview["brief_source"] = "ai:compact"
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
        tag = "ai:cache" if result.get("cached") else "ai:compact"
        if tag not in sources:
            sources.append(tag)
        preview["story_sources"] = sources
    return preview


def _annotate_existing(db: Session, result: dict) -> dict:
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
    """Heuristic dry-run only. Never calls Groq (use_ai is ignored for cost safety)."""
    try:
        result = importer.scan(body.root_path)
    except importer.ImportError_ as exc:
        raise HTTPException(400, str(exc)) from None

    settings = get_settings()
    for preview in result["projects"]:
        preview.setdefault("ai_used", False)
        preview.setdefault("ai_agent", None)
        preview.setdefault("llm_error", None)

    result["use_ai"] = False  # scan is never AI
    result["ai_status"] = settings.ai_status()
    result["ai_note"] = (
        "Scan is heuristic-only (no Groq). Enable AI enrich on Import for "
        "selected folders only — compact card + cheap model + cache."
    )
    return _annotate_existing(db, result)


@router.post("/apply", response_model=schemas.ImportApplyResponse)
def apply_import(
    body: schemas.ImportApplyRequest = schemas.ImportApplyRequest(),
    db: Session = Depends(get_db),
):
    """Create or re-sync selected folders. Optional AI only for those folders."""
    try:
        result = importer.scan(body.root_path)
    except importer.ImportError_ as exc:
        raise HTTPException(400, str(exc)) from None

    wanted = {s.strip() for s in body.selections if s and s.strip()}
    settings = get_settings()
    use_ai = bool(body.use_ai and settings.use_llm())

    imported: list[dict] = []
    skipped: list[dict[str, str]] = list(result["skipped"])
    errors: list[dict[str, str]] = list(result["errors"])
    ai_errors = 0
    ai_ok = 0
    ai_cached = 0

    for preview in result["projects"]:
        folder = preview["folder"]
        if wanted and folder not in wanted and preview["source_path"] not in wanted:
            continue

        if use_ai:
            try:
                preview = _enrich_with_ai(preview)
                if preview.get("ai_used"):
                    ai_ok += 1
                    if preview.get("ai_cached"):
                        ai_cached += 1
                elif preview.get("llm_error"):
                    ai_errors += 1
                    # Stop further AI calls if we hit daily quota — save the rest
                    err = (preview.get("llm_error") or "").lower()
                    if "daily" in err or "token limit" in err:
                        use_ai = False  # remaining folders: heuristic only
            except Exception as exc:  # noqa: BLE001
                preview["ai_used"] = False
                preview["llm_error"] = str(exc)[:200]
                ai_errors += 1

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
        "ai_enriched": ai_ok,
        "ai_cached": ai_cached,
        "ai_errors": ai_errors,
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
                    "ai_cached": preview.get("ai_cached"),
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
        "ai_used": bool(preview.get("ai_used")),
        "ai_cached": bool(preview.get("ai_cached")),
    }
