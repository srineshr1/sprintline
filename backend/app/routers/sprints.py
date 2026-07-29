from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..serializers import sprint_to_dict

router = APIRouter(prefix="/api/projects/{project_id}/sprints", tags=["sprints"])


def _get_project(db: Session, project_id: int) -> models.Project:
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.get("", response_model=list[schemas.SprintOut])
def list_sprints(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    sprints = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.project_id == project_id)
        .order_by(models.Sprint.id.desc())
        .all()
    )
    return [sprint_to_dict(s) for s in sprints]


@router.post("", response_model=schemas.SprintOut, status_code=201)
def create_sprint(
    project_id: int, body: schemas.SprintCreate, db: Session = Depends(get_db)
):
    _get_project(db, project_id)
    sp = models.Sprint(
        project_id=project_id,
        name=body.name,
        goal=body.goal,
        start=body.start,
        end=body.end,
        capacity_points=body.capacity_points,
        status=body.status,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sprint_to_dict(sp)


@router.get("/{sprint_id}", response_model=schemas.SprintOut)
def get_sprint(project_id: int, sprint_id: int, db: Session = Depends(get_db)):
    sp = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.id == sprint_id, models.Sprint.project_id == project_id)
        .first()
    )
    if not sp:
        raise HTTPException(404, "Sprint not found")
    return sprint_to_dict(sp)


@router.patch("/{sprint_id}", response_model=schemas.SprintOut)
def update_sprint(
    project_id: int,
    sprint_id: int,
    body: schemas.SprintUpdate,
    db: Session = Depends(get_db),
):
    sp = (
        db.query(models.Sprint)
        .filter(models.Sprint.id == sprint_id, models.Sprint.project_id == project_id)
        .first()
    )
    if not sp:
        raise HTTPException(404, "Sprint not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(sp, k, v)
    db.commit()
    db.refresh(sp)
    return sprint_to_dict(sp)


@router.post("/{sprint_id}/stories", response_model=schemas.SprintOut)
def add_stories(
    project_id: int,
    sprint_id: int,
    body: schemas.SprintAddStories,
    db: Session = Depends(get_db),
):
    sp = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.id == sprint_id, models.Sprint.project_id == project_id)
        .first()
    )
    if not sp:
        raise HTTPException(404, "Sprint not found")

    existing = {i.story_id for i in sp.items}
    for sid in body.story_ids:
        story = db.get(models.Story, sid)
        if not story or story.epic.project_id != project_id:
            raise HTTPException(400, f"Story {sid} not in project")
        if sid not in existing:
            db.add(models.SprintItem(sprint_id=sprint_id, story_id=sid))
    db.commit()

    sp = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.id == sprint_id)
        .first()
    )
    return sprint_to_dict(sp)


@router.delete("/{sprint_id}/stories/{story_id}", response_model=schemas.SprintOut)
def remove_story(
    project_id: int, sprint_id: int, story_id: int, db: Session = Depends(get_db)
):
    sp = (
        db.query(models.Sprint)
        .filter(models.Sprint.id == sprint_id, models.Sprint.project_id == project_id)
        .first()
    )
    if not sp:
        raise HTTPException(404, "Sprint not found")
    item = (
        db.query(models.SprintItem)
        .filter(
            models.SprintItem.sprint_id == sprint_id,
            models.SprintItem.story_id == story_id,
        )
        .first()
    )
    if item:
        db.delete(item)
        db.commit()
    sp = (
        db.query(models.Sprint)
        .options(
            joinedload(models.Sprint.items).joinedload(models.SprintItem.story)
        )
        .filter(models.Sprint.id == sprint_id)
        .first()
    )
    return sprint_to_dict(sp)


