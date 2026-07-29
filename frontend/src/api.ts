import type {
  BacklogGenerateResponse,
  CriticReport,
  Epic,
  EvaluationResponse,
  Project,
  Sprint,
  SprintPlanResponse,
  StandupResponse,
  Story,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  listProjects: () => request<Project[]>('/projects'),
  createProject: (body: {
    name: string
    brief?: string
    goals?: string[]
    constraints?: string[]
  }) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  updateProject: (
    id: number,
    body: Partial<Pick<Project, 'name' | 'brief' | 'goals' | 'constraints'>>,
  ) =>
    request<Project>(`/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteProject: (id: number) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),

  listEpics: (projectId: number) =>
    request<Epic[]>(`/projects/${projectId}/epics`),
  listStories: (projectId: number) =>
    request<Story[]>(`/projects/${projectId}/stories`),
  getStory: (projectId: number, storyId: number) =>
    request<Story>(`/projects/${projectId}/stories/${storyId}`),
  updateStory: (
    projectId: number,
    storyId: number,
    body: Partial<
      Pick<
        Story,
        | 'title'
        | 'description'
        | 'acceptance_criteria'
        | 'points'
        | 'priority'
        | 'status'
        | 'rationale'
        | 'order'
      >
    >,
  ) =>
    request<Story>(`/projects/${projectId}/stories/${storyId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  generateBacklog: (projectId: number, replace = true) =>
    request<BacklogGenerateResponse>(
      `/projects/${projectId}/ai/generate-backlog`,
      {
        method: 'POST',
        body: JSON.stringify({ replace }),
      },
    ),

  listSprints: (projectId: number) =>
    request<Sprint[]>(`/projects/${projectId}/sprints`),
  createSprint: (
    projectId: number,
    body: {
      name: string
      goal?: string
      capacity_points?: number
      start?: string
      end?: string
      status?: string
    },
  ) =>
    request<Sprint>(`/projects/${projectId}/sprints`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateSprint: (
    projectId: number,
    sprintId: number,
    body: Partial<Pick<Sprint, 'name' | 'goal' | 'capacity_points' | 'status'>>,
  ) =>
    request<Sprint>(`/projects/${projectId}/sprints/${sprintId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  addSprintStories: (projectId: number, sprintId: number, storyIds: number[]) =>
    request<Sprint>(`/projects/${projectId}/sprints/${sprintId}/stories`, {
      method: 'POST',
      body: JSON.stringify({ story_ids: storyIds }),
    }),

  planSprint: (
    projectId: number,
    sprintId: number,
    opts?: { capacity_points?: number; apply?: boolean },
  ) =>
    request<SprintPlanResponse>(`/projects/${projectId}/ai/plan-sprint`, {
      method: 'POST',
      body: JSON.stringify({
        sprint_id: sprintId,
        capacity_points: opts?.capacity_points,
        apply: opts?.apply ?? false,
      }),
    }),

  standup: (projectId: number) =>
    request<StandupResponse>(`/projects/${projectId}/ai/standup`, {
      method: 'POST',
    }),

  critique: (projectId: number) =>
    request<CriticReport>(`/projects/${projectId}/ai/critique`, {
      method: 'POST',
    }),

  evaluate: (projectId: number) =>
    request<EvaluationResponse>(`/projects/${projectId}/ai/evaluate`),

  exportUrl: (projectId: number, format: 'markdown' | 'json' = 'markdown') =>
    `${BASE}/projects/${projectId}/export?format=${format}`,

  exportContent: async (
    projectId: number,
    format: 'markdown' | 'json' = 'markdown',
  ) => {
    const res = await fetch(api.exportUrl(projectId, format))
    if (!res.ok) throw new Error('Export failed')
    const content = await res.text()
    const filename =
      res.headers.get('X-Export-Filename') ||
      `project-export.${format === 'json' ? 'json' : 'md'}`
    return { content, filename }
  },
}
