from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..serializers import dumps, epic_to_dict, story_to_dict
from ..services import pipeline

router = APIRouter(prefix="/api/projects/{project_id}", tags=["backlog"])


def _get_project(db: Session, project_id: int) -> models.Project:
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.get("/epics", response_model=list[schemas.EpicOut])
def list_epics(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    epics = (
        db.query(models.Epic)
        .options(joinedload(models.Epic.stories))
        .filter(models.Epic.project_id == project_id)
        .order_by(models.Epic.order, models.Epic.id)
        .all()
    )
    return [epic_to_dict(e) for e in epics]


@router.get("/stories", response_model=list[schemas.StoryOut])
def list_stories(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    stories = (
        db.query(models.Story)
        .join(models.Epic)
        .filter(models.Epic.project_id == project_id)
        .order_by(models.Story.order, models.Story.id)
        .all()
    )
    return [story_to_dict(s) for s in stories]


@router.post("/epics", response_model=schemas.EpicOut, status_code=201)
def create_epic(
    project_id: int, body: schemas.EpicCreate, db: Session = Depends(get_db)
):
    _get_project(db, project_id)
    e = models.Epic(
        project_id=project_id,
        title=body.title,
        description=body.description,
        order=body.order,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return epic_to_dict(e)


@router.post("/stories", response_model=schemas.StoryOut, status_code=201)
def create_story(
    project_id: int, body: schemas.StoryCreate, db: Session = Depends(get_db)
):
    epic = db.get(models.Epic, body.epic_id)
    if not epic or epic.project_id != project_id:
        raise HTTPException(404, "Epic not found in this project")
    s = models.Story(
        epic_id=body.epic_id,
        title=body.title,
        description=body.description,
        acceptance_criteria=dumps(body.acceptance_criteria),
        points=body.points,
        priority=body.priority,
        status=body.status,
        rationale=body.rationale,
        order=body.order,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return story_to_dict(s)


@router.get("/stories/{story_id}", response_model=schemas.StoryOut)
def get_story(project_id: int, story_id: int, db: Session = Depends(get_db)):
    s = db.get(models.Story, story_id)
    if not s or s.epic.project_id != project_id:
        raise HTTPException(404, "Story not found")
    return story_to_dict(s)


@router.patch("/stories/{story_id}", response_model=schemas.StoryOut)
def update_story(
    project_id: int,
    story_id: int,
    body: schemas.StoryUpdate,
    db: Session = Depends(get_db),
):
    s = db.get(models.Story, story_id)
    if not s or s.epic.project_id != project_id:
        raise HTTPException(404, "Story not found")
    data = body.model_dump(exclude_unset=True)
    if "acceptance_criteria" in data and data["acceptance_criteria"] is not None:
        s.acceptance_criteria = dumps(data.pop("acceptance_criteria"))
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    db.add(
        models.Activity(
            project_id=project_id,
            type="story_updated",
            payload=dumps({"story_id": s.id, "title": s.title, "status": s.status}),
        )
    )
    db.commit()
    return story_to_dict(s)


@router.delete("/stories/{story_id}", status_code=204)
def delete_story(project_id: int, story_id: int, db: Session = Depends(get_db)):
    s = db.get(models.Story, story_id)
    if not s or s.epic.project_id != project_id:
        raise HTTPException(404, "Story not found")
    db.delete(s)
    db.commit()


@router.post("/ai/generate-backlog", response_model=schemas.BacklogGenerateResponse)
def generate_backlog(
    project_id: int,
    body: schemas.BacklogGenerateRequest = schemas.BacklogGenerateRequest(),
    db: Session = Depends(get_db),
):
    """Multi-agent pipeline: backlog draft → critic → metrics preview, then persist."""
    p = _get_project(db, project_id)
    from ..serializers import _loads_list

    goals = _loads_list(p.goals)
    constraints = _loads_list(p.constraints)
    result = pipeline.run_backlog_pipeline(
        p.name, p.brief or "", goals, constraints
    )

    if body.replace:
        existing = (
            db.query(models.Epic).filter(models.Epic.project_id == project_id).all()
        )
        for e in existing:
            db.delete(e)
        db.flush()

    created_epics: list[models.Epic] = []
    for ep in result["epics"]:
        epic = models.Epic(
            project_id=project_id,
            title=ep["title"],
            description=ep.get("description", ""),
            order=ep.get("order", 0),
        )
        db.add(epic)
        db.flush()
        for st in ep.get("stories") or []:
            story = models.Story(
                epic_id=epic.id,
                title=st["title"],
                description=st.get("description", ""),
                acceptance_criteria=dumps(st.get("acceptance_criteria") or []),
                points=st.get("points", 3),
                priority=st.get("priority", "medium"),
                status=st.get("status", "todo"),
                rationale=st.get("rationale", ""),
                order=st.get("order", 0),
            )
            db.add(story)
        created_epics.append(epic)

    critic_summary = (result.get("critic") or {}).get("summary") or {}
    db.add(
        models.Activity(
            project_id=project_id,
            type="ai_backlog_generated",
            payload=dumps(
                {
                    "agent": result.get("agent"),
                    "epic_count": len(created_epics),
                    "rationale": result.get("rationale", "")[:500],
                    "pipeline": (result.get("pipeline") or {}).get("steps"),
                    "critic_errors": critic_summary.get("errors"),
                    "critic_warnings": critic_summary.get("warnings"),
                }
            ),
        )
    )
    db.commit()

    # Reload with stories
    epics = (
        db.query(models.Epic)
        .options(joinedload(models.Epic.stories))
        .filter(models.Epic.id.in_([e.id for e in created_epics]))
        .order_by(models.Epic.order, models.Epic.id)
        .all()
    )
    return {
        "epics": [epic_to_dict(e) for e in epics],
        "rationale": result["rationale"],
        "agent": result.get("agent", "backlog_stub"),
        "pipeline": result.get("pipeline"),
        "critic": result.get("critic"),
        "metrics_preview": result.get("metrics_preview"),
    }
