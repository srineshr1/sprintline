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
    source_path: Optional[str] = None
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


class CodebaseContextMeta(BaseModel):
    """Which repo files were packed for the LLM (bodies omitted)."""

    root: Optional[str] = None
    exists: bool = False
    file_paths: list[str] = Field(default_factory=list)
    file_count: int = 0
    total_chars: int = 0
    tree_preview: str = ""
    note: str = ""
    skipped_dirs: list[str] = Field(default_factory=list)


class BacklogGenerateResponse(BaseModel):
    epics: list[EpicOut]
    rationale: str
    agent: str = "backlog_stub"
    pipeline: Optional[PipelineMeta] = None
    critic: Optional[CriticReport] = None
    metrics_preview: Optional[dict[str, Any]] = None
    codebase_context: Optional[CodebaseContextMeta] = None
    llm_error: Optional[str] = None


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
    llm_error: Optional[str] = None


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
    llm_error: Optional[str] = None


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


# ---- Directory import ----
class ImportScanRequest(BaseModel):
    """Dry-run scan. ``root_path`` must resolve inside an allowed root.

    Scan is always heuristic-only (use_ai ignored) to protect token budgets.
    """

    root_path: Optional[str] = None
    use_ai: bool = False


class ImportStoryPreview(BaseModel):
    title: str
    status: str = "todo"
    points: int = 3
    priority: str = "medium"
    description: str = ""


class ImportEpicPreview(BaseModel):
    title: str
    stories: list[ImportStoryPreview] = Field(default_factory=list)


class ImportProjectPreview(BaseModel):
    name: str
    folder: str
    source_path: str
    brief: str = ""
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    brief_source: Optional[str] = None
    story_sources: list[str] = Field(default_factory=list)
    epics: list[ImportEpicPreview] = Field(default_factory=list)
    epic_count: int = 0
    story_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    sample_titles: list[str] = Field(default_factory=list)
    # Set by the router: an already-imported folder re-syncs instead of
    # creating a second project.
    existing_project_id: Optional[int] = None
    new_story_count: Optional[int] = None
    # AI enrichment (when use_ai on scan)
    ai_used: bool = False
    ai_agent: Optional[str] = None
    ai_analysis: Optional[str] = None
    ai_rationale: Optional[str] = None
    tech_stack: list[str] = Field(default_factory=list)
    codebase_context: Optional[CodebaseContextMeta] = None
    llm_error: Optional[str] = None
    ai_cached: bool = False


class ImportScanResponse(BaseModel):
    root_path: str
    default_root: str = ""
    projects: list[ImportProjectPreview] = Field(default_factory=list)
    skipped: list[dict[str, str]] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    total_projects: int = 0
    total_stories: int = 0
    use_ai: bool = False
    ai_status: Optional[dict[str, Any]] = None
    ai_note: Optional[str] = None


class ImportApplyRequest(BaseModel):
    root_path: Optional[str] = None
    # Folder names to import. Empty/omitted means "everything found".
    selections: list[str] = Field(default_factory=list)
    # AI only runs for selected folders (compact + cheap model + cache).
    use_ai: bool = True


class ImportApplyResult(BaseModel):
    folder: str
    name: str
    source_path: str
    project_id: int
    epics_created: int = 0
    stories_created: int = 0
    resynced: bool = False
    ai_used: bool = False
    ai_cached: bool = False


class ImportApplyResponse(BaseModel):
    root_path: str
    imported: list[ImportApplyResult] = Field(default_factory=list)
    skipped: list[dict[str, str]] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    projects_created: int = 0
    projects_resynced: int = 0
    stories_created: int = 0
    ai_enriched: int = 0
    ai_cached: int = 0
    ai_errors: int = 0


class ImportRootsResponse(BaseModel):
    default_root: str
    allowed_roots: list[str] = Field(default_factory=list)


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
