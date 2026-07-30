export type Priority = 'high' | 'medium' | 'low'
export type StoryStatus = 'todo' | 'in_progress' | 'done'

export interface Project {
  id: number
  name: string
  brief: string
  goals: string[]
  constraints: string[]
  /** Folder this project was imported from; null when created by hand. */
  source_path: string | null
  created_at: string
}

export interface Story {
  id: number
  epic_id: number
  title: string
  description: string
  acceptance_criteria: string[]
  points: number
  priority: Priority | string
  status: StoryStatus | string
  rationale: string
  order: number
}

export interface Epic {
  id: number
  project_id: number
  title: string
  description: string
  order: number
  stories: Story[]
}

export interface SprintItem {
  id: number
  sprint_id: number
  story_id: number
  story: Story | null
}

export interface Sprint {
  id: number
  project_id: number
  name: string
  goal: string
  start: string | null
  end: string | null
  capacity_points: number
  status: string
  items: SprintItem[]
}

// ---- Directory import ----
export interface ImportStoryPreview {
  title: string
  status: StoryStatus | string
  points: number
  priority: Priority | string
  description?: string
}

export interface ImportEpicPreview {
  title: string
  stories: ImportStoryPreview[]
}

export interface CodebaseContextMeta {
  root?: string | null
  exists: boolean
  file_paths: string[]
  file_count: number
  total_chars: number
  tree_preview: string
  note: string
  skipped_dirs: string[]
}

export interface ImportProjectPreview {
  name: string
  folder: string
  source_path: string
  brief: string
  goals: string[]
  constraints: string[]
  brief_source: string | null
  story_sources: string[]
  epics: ImportEpicPreview[]
  epic_count: number
  story_count: number
  status_counts: Record<string, number>
  sample_titles: string[]
  /** Set when this folder was imported before — apply re-syncs it. */
  existing_project_id: number | null
  /** Stories not already present in the existing project. */
  new_story_count: number | null
  ai_used?: boolean
  ai_agent?: string | null
  ai_analysis?: string | null
  ai_rationale?: string | null
  tech_stack?: string[]
  codebase_context?: CodebaseContextMeta | null
  llm_error?: string | null
}

export interface ImportScanResponse {
  root_path: string
  default_root: string
  projects: ImportProjectPreview[]
  skipped: Array<{ folder: string; reason: string }>
  errors: Array<{ folder: string; error: string }>
  total_projects: number
  total_stories: number
  use_ai?: boolean
  ai_status?: {
    mode: string
    provider: string
    model?: string | null
    configured: boolean
    llm_active: boolean
  }
}

export interface ImportApplyResult {
  folder: string
  name: string
  source_path: string
  project_id: number
  epics_created: number
  stories_created: number
  resynced: boolean
}

export interface ImportApplyResponse {
  root_path: string
  imported: ImportApplyResult[]
  skipped: Array<{ folder: string; reason: string }>
  errors: Array<{ folder: string; error: string }>
  projects_created: number
  projects_resynced: number
  stories_created: number
}

export interface ImportRootsResponse {
  default_root: string
  allowed_roots: string[]
}

export interface CriticFinding {
  code: string
  severity: string
  message: string
  story_id?: number | string | null
  field?: string | null
}

export interface CriticReport {
  findings: CriticFinding[]
  summary: Record<string, number | string>
  rationale: string
  agent: string
}

export interface PipelineMeta {
  steps: string[]
  rationale: string
}

export interface BacklogGenerateResponse {
  epics: Epic[]
  rationale: string
  agent: string
  pipeline?: PipelineMeta
  critic?: CriticReport
  metrics_preview?: {
    ac_coverage?: { coverage_pct?: number; with_ac?: number; total_stories?: number }
    invest_average_pct?: number
    invest_rationale?: string
  }
  codebase_context?: CodebaseContextMeta | null
  llm_error?: string | null
}

export interface SprintPlanResponse {
  suggested_story_ids: number[]
  total_points: number
  rationale: string
  stories: Story[]
  agent: string
  pipeline?: PipelineMeta
  critic?: CriticReport
}

export interface StandupResponse {
  summary: string
  done: string[]
  in_progress: string[]
  todo: string[]
  blockers: string[]
  rationale: string
  agent: string
  pipeline?: PipelineMeta
  critic?: CriticReport
  metrics_snapshot?: Record<string, unknown>
}

export interface EvaluationResponse {
  ac_coverage: {
    total_stories: number
    with_ac: number
    without_ac: number
    coverage_pct: number
    rationale: string
  }
  invest: {
    story_count: number
    average_score: number
    average_pct: number
    dimension_pass_rates: Record<string, number>
    rationale: string
    per_story?: Array<{
      story_id?: number
      title?: string
      score: number
      checks: Record<string, boolean>
    }>
  }
  sprints: Array<{
    sprint_id?: number
    sprint_name?: string
    capacity_points: number
    planned_points: number
    completed_points: number
    remaining_points: number
    in_progress_points?: number
    utilization_pct: number
    completion_pct: number
    rationale?: string
  }>
  board: {
    status_counts: Record<string, number>
    total_points: number
    completed_points: number
    completion_pct: number
  }
  rationale: string
  agent: string
}
