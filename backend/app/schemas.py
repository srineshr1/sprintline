from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- Project ----
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brief: str = ""
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    brief: Optional[str] = None
    goals: Optional[list[str]] = None
    constraints: Optional[list[str]] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    brief: str
    goals: list[str]
    constraints: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Epic / Story ----
class EpicCreate(BaseModel):
    title: str
    description: str = ""
    order: int = 0


class EpicOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    order: int
    stories: list["StoryOut"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StoryCreate(BaseModel):
    epic_id: int
    title: str
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    points: int = 3
    priority: str = "medium"
    status: str = "todo"
    rationale: str = ""
    order: int = 0


class StoryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[list[str]] = None
    points: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    rationale: Optional[str] = None
    order: Optional[int] = None
    epic_id: Optional[int] = None


class StoryOut(BaseModel):
    id: int
    epic_id: int
    title: str
    description: str
    acceptance_criteria: list[str]
    points: int
    priority: str
    status: str
    rationale: str
    order: int

    model_config = {"from_attributes": True}


# ---- Sprint ----
class SprintCreate(BaseModel):
    name: str
    goal: str = ""
    start: Optional[str] = None
    end: Optional[str] = None
    capacity_points: int = 20
    status: str = "planned"


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    capacity_points: Optional[int] = None
    status: Optional[str] = None


class SprintItemOut(BaseModel):
    id: int
    sprint_id: int
    story_id: int
    story: Optional[StoryOut] = None

    model_config = {"from_attributes": True}


class SprintOut(BaseModel):
    id: int
    project_id: int
    name: str
    goal: str
    start: Optional[str]
    end: Optional[str]
    capacity_points: int
    status: str
    items: list[SprintItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SprintAddStories(BaseModel):
    story_ids: list[int]


# ---- Critic / pipeline shared ----
class CriticFinding(BaseModel):
    code: str
    severity: str
    message: str
    story_id: Optional[Any] = None
    field: Optional[str] = None


class CriticReport(BaseModel):
    findings: list[CriticFinding] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    agent: str = "critic"


class PipelineMeta(BaseModel):
    steps: list[str] = Field(default_factory=list)
    rationale: str = ""


# ---- AI ----
class BacklogGenerateRequest(BaseModel):
    replace: bool = False  # if true, wipe existing epics/stories first


class BacklogGenerateResponse(BaseModel):
    epics: list[EpicOut]
    rationale: str
    agent: str = "backlog_stub"
    pipeline: Optional[PipelineMeta] = None
    critic: Optional[CriticReport] = None
    metrics_preview: Optional[dict[str, Any]] = None


class SprintPlanRequest(BaseModel):
    sprint_id: int
    capacity_points: Optional[int] = None
    apply: bool = False  # if true, assign suggested stories to sprint


class SprintPlanResponse(BaseModel):
    suggested_story_ids: list[int]
    total_points: int
    rationale: str
    stories: list[StoryOut] = Field(default_factory=list)
    agent: str = "sprint_stub"
    pipeline: Optional[PipelineMeta] = None
    critic: Optional[CriticReport] = None


class StandupResponse(BaseModel):
    summary: str
    done: list[str]
    in_progress: list[str]
    todo: list[str]
    blockers: list[str]
    rationale: str
    agent: str = "standup_stub"
    pipeline: Optional[PipelineMeta] = None
    critic: Optional[CriticReport] = None
    metrics_snapshot: Optional[dict[str, Any]] = None


class EvaluationResponse(BaseModel):
    ac_coverage: dict[str, Any]
    invest: dict[str, Any]
    sprints: list[dict[str, Any]] = Field(default_factory=list)
    board: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    agent: str = "evaluation"


class CriticOnlyResponse(BaseModel):
    findings: list[CriticFinding] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    agent: str = "critic"


# ---- Export ----
class ExportResponse(BaseModel):
    format: str
    content: str
    filename: str


# ---- Activity ----
class ActivityOut(BaseModel):
    id: int
    project_id: int
    type: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


# Resolve forward refs
EpicOut.model_rebuild()
