from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..serializers import epic_to_dict, project_to_dict, sprint_to_dict
from ..services.export_service import export_json, export_markdown

router = APIRouter(prefix="/api/projects/{project_id}/export", tags=["export"])


def _build_payload(db: Session, project_id: int) -> dict:
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    epics = (
        db.query(models.Epic)
        .options(joinedload(models.Epic.stories))
        .filter(models.Epic.project_id == project_id)
        .order_by(models.Epic.order, models.Epic.id)
        .all()
    )
    sprints = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.project_id == project_id)
        .order_by(models.Sprint.id)
        .all()
    )
    return {
        "project": project_to_dict(p),
        "epics": [epic_to_dict(e) for e in epics],
        "sprints": [sprint_to_dict(s) for s in sprints],
    }


@router.get("")
def export_project(
    project_id: int,
    format: str = Query("markdown", pattern="^(markdown|json|md)$"),
    db: Session = Depends(get_db),
):
    payload = _build_payload(db, project_id)
    if format in ("markdown", "md"):
        content, filename = export_markdown(payload)
        media = "text/markdown; charset=utf-8"
        fmt = "markdown"
    else:
        content, filename = export_json(payload)
        media = "application/json; charset=utf-8"
        fmt = "json"

    return PlainTextResponse(
        content=content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Format": fmt,
            "X-Export-Filename": filename,
        },
    )
