from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..serializers import dumps, sprint_to_dict, story_to_dict
from ..services import pipeline

router = APIRouter(prefix="/api/projects/{project_id}/ai", tags=["ai"])


def _get_project(db: Session, project_id: int) -> models.Project:
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _project_stories(db: Session, project_id: int) -> list[dict]:
    stories = (
        db.query(models.Story)
        .join(models.Epic)
        .filter(models.Epic.project_id == project_id)
        .all()
    )
    return [story_to_dict(s) for s in stories]


def _project_sprints(db: Session, project_id: int) -> list[dict]:
    sprints = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.project_id == project_id)
        .order_by(models.Sprint.id)
        .all()
    )
    return [sprint_to_dict(s) for s in sprints]


@router.post("/plan-sprint", response_model=schemas.SprintPlanResponse)
def plan_sprint(
    project_id: int,
    body: schemas.SprintPlanRequest,
    db: Session = Depends(get_db),
):
    _get_project(db, project_id)
    sp = (
        db.query(models.Sprint)
        .filter(
            models.Sprint.id == body.sprint_id,
            models.Sprint.project_id == project_id,
        )
        .first()
    )
    if not sp:
        raise HTTPException(404, "Sprint not found")

    capacity = (
        body.capacity_points if body.capacity_points is not None else sp.capacity_points
    )
    story_dicts = _project_stories(db, project_id)
    result = pipeline.run_sprint_pipeline(story_dicts, capacity, sp.name)

    if body.apply:
        existing = {
            i.story_id
            for i in db.query(models.SprintItem)
            .filter(models.SprintItem.sprint_id == sp.id)
            .all()
        }
        for sid in result["suggested_story_ids"]:
            if sid not in existing:
                db.add(models.SprintItem(sprint_id=sp.id, story_id=sid))
        if body.capacity_points is not None:
            sp.capacity_points = capacity
        db.add(
            models.Activity(
                project_id=project_id,
                type="ai_sprint_planned",
                payload=dumps(
                    {
                        "sprint_id": sp.id,
                        "story_ids": result["suggested_story_ids"],
                        "total_points": result["total_points"],
                        "pipeline": (result.get("pipeline") or {}).get("steps"),
                        "critic_errors": (result.get("critic") or {})
                        .get("summary", {})
                        .get("errors"),
                    }
                ),
            )
        )
        db.commit()

    return {
        "suggested_story_ids": result["suggested_story_ids"],
        "total_points": result["total_points"],
        "rationale": result["rationale"],
        "stories": result["stories"],
        "agent": result.get("agent", "sprint_stub"),
        "pipeline": result.get("pipeline"),
        "critic": result.get("critic"),
    }


@router.post("/standup", response_model=schemas.StandupResponse)
def standup(project_id: int, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    story_dicts = _project_stories(db, project_id)
    sprint_dicts = _project_sprints(db, project_id)
    activities = (
        db.query(models.Activity)
        .filter(models.Activity.project_id == project_id)
        .order_by(models.Activity.id.desc())
        .limit(5)
        .all()
    )
    recent = [a.type for a in activities]
    result = pipeline.run_standup_pipeline(
        story_dicts, p.name, recent, sprint_dicts
    )
    db.add(
        models.Activity(
            project_id=project_id,
            type="ai_standup",
            payload=dumps(
                {
                    "summary_len": len(result["summary"]),
                    "pipeline": (result.get("pipeline") or {}).get("steps"),
                }
            ),
        )
    )
    db.commit()
    return result


@router.post("/critique", response_model=schemas.CriticOnlyResponse)
def critique_project(project_id: int, db: Session = Depends(get_db)):
    """Run critic quality pass on current persisted backlog (no overwrite)."""
    _get_project(db, project_id)
    story_dicts = _project_stories(db, project_id)
    result = pipeline.run_critic_only(story_dicts)
    db.add(
        models.Activity(
            project_id=project_id,
            type="ai_critique",
            payload=dumps(
                {
                    "errors": result.get("summary", {}).get("errors"),
                    "warnings": result.get("summary", {}).get("warnings"),
                }
            ),
        )
    )
    db.commit()
    return result


@router.get("/evaluate", response_model=schemas.EvaluationResponse)
def evaluate_project(project_id: int, db: Session = Depends(get_db)):
    """Compute AC coverage, INVEST scores, sprint planned vs done metrics."""
    _get_project(db, project_id)
    story_dicts = _project_stories(db, project_id)
    sprint_dicts = _project_sprints(db, project_id)
    return pipeline.run_evaluation(story_dicts, sprint_dicts)
