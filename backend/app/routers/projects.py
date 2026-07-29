from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..serializers import dumps, project_to_dict

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _log(db: Session, project_id: int, type_: str, payload: dict) -> None:
    db.add(
        models.Activity(
            project_id=project_id,
            type=type_,
            payload=dumps(payload),
        )
    )


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    rows = db.query(models.Project).order_by(models.Project.id.desc()).all()
    return [project_to_dict(p) for p in rows]


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(body: schemas.ProjectCreate, db: Session = Depends(get_db)):
    p = models.Project(
        name=body.name,
        brief=body.brief or "",
        goals=dumps(body.goals),
        constraints=dumps(body.constraints),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    _log(db, p.id, "project_created", {"name": p.name})
    db.commit()
    return project_to_dict(p)


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return project_to_dict(p)


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int, body: schemas.ProjectUpdate, db: Session = Depends(get_db)
):
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if body.name is not None:
        p.name = body.name
    if body.brief is not None:
        p.brief = body.brief
    if body.goals is not None:
        p.goals = dumps(body.goals)
    if body.constraints is not None:
        p.constraints = dumps(body.constraints)
    db.commit()
    db.refresh(p)
    _log(db, p.id, "project_updated", {"name": p.name})
    db.commit()
    return project_to_dict(p)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    db.delete(p)
    db.commit()
