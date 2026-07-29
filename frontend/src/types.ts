export type Priority = 'high' | 'medium' | 'low'
export type StoryStatus = 'todo' | 'in_progress' | 'done'

export interface Project {
  id: number
  name: string
  brief: string
  goals: string[]
  constraints: string[]
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
