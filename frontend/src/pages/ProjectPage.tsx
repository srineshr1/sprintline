import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import {
  PointsPill,
  PriorityPill,
  StatusPill,
} from '../components/Badge'
import { CriticPanel } from '../components/CriticPanel'
import { MetricsPanel } from '../components/MetricsPanel'
import { Modal } from '../components/Modal'
import { RationalePanel } from '../components/RationalePanel'
import { SegmentedControl } from '../components/SegmentedControl'
import { SprintBoard } from '../components/SprintBoard'
import { StoryEditor } from '../components/StoryEditor'
import { useToast } from '../components/Toast'
import type {
  CriticReport,
  Epic,
  EvaluationResponse,
  Project,
  Sprint,
  Story,
} from '../types'

type Tab = 'overview' | 'backlog' | 'board' | 'reports'
type StatusFilter = 'all' | 'todo' | 'in_progress' | 'done'
type PriorityFilter = 'all' | 'high' | 'medium' | 'low'

const TABS: Tab[] = ['overview', 'backlog', 'board', 'reports']

/** Landing tab when no `?tab=` is present. Kept out of the URL. */
const DEFAULT_TAB: Tab = 'overview'

function parseTab(raw: string | null): Tab {
  if (raw && (TABS as string[]).includes(raw)) return raw as Tab
  return DEFAULT_TAB
}

export function ProjectPage() {
  const { id } = useParams()
  const projectId = Number(id)
  const [searchParams, setSearchParams] = useSearchParams()
  const { toast } = useToast()

  const tab = parseTab(searchParams.get('tab'))
  const setTab = useCallback(
    (next: Tab) => {
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          // Keep the landing tab out of the URL; everything else is shareable.
          if (next === DEFAULT_TAB) p.delete('tab')
          else p.set('tab', next)
          return p
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const [project, setProject] = useState<Project | null>(null)
  const [epics, setEpics] = useState<Epic[]>([])
  const [stories, setStories] = useState<Story[]>([])
  const [sprints, setSprints] = useState<Sprint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [aiRationale, setAiRationale] = useState<string | null>(null)
  const [pipelineRationale, setPipelineRationale] = useState<string | null>(
    null,
  )
  const [aiAgent, setAiAgent] = useState<string | undefined>()
  const [codeFiles, setCodeFiles] = useState<string[] | null>(null)
  const [criticReport, setCriticReport] = useState<CriticReport | null>(null)
  const [metrics, setMetrics] = useState<EvaluationResponse | null>(null)
  const [selectedStory, setSelectedStory] = useState<Story | null>(null)
  const [standup, setStandup] = useState<string | null>(null)
  const [showGenerate, setShowGenerate] = useState(false)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all')
  const [epicFilter, setEpicFilter] = useState<number | 'all'>('all')
  const [headerScrolled, setHeaderScrolled] = useState(false)
  const lastStoryRef = useRef<Story | null>(null)
  if (selectedStory) lastStoryRef.current = selectedStory
  const drawerStory = selectedStory ?? lastStoryRef.current

  useEffect(() => {
    const onScroll = () => setHeaderScrolled(window.scrollY > 4)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const epicById = useMemo(() => {
    const m = new Map<number, Epic>()
    for (const e of epics) m.set(e.id, e)
    return m
  }, [epics])

  const refresh = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    setError(null)
    try {
      const [p, e, s, sp] = await Promise.all([
        api.getProject(projectId),
        api.listEpics(projectId),
        api.listStories(projectId),
        api.listSprints(projectId),
      ])
      setProject(p)
      setEpics(e)
      setStories(s)
      setSprints(sp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load failed')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const filteredStories = useMemo(() => {
    return stories.filter((s) => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false
      if (priorityFilter !== 'all' && s.priority !== priorityFilter) return false
      if (epicFilter !== 'all' && s.epic_id !== epicFilter) return false
      return true
    })
  }, [stories, statusFilter, priorityFilter, epicFilter])

  const activeSprint = sprints.find((s) => s.status === 'active') || sprints[0]

  /**
   * Completion rolled up from the stories already in state — no extra request,
   * and it stays in sync with board moves for free.
   *
   * Percentage is points-based when the backlog is estimated, since a 13-point
   * story finishing is not the same as a 1-pointer; falls back to story counts
   * when nothing has points yet.
   */
  const progress = useMemo(() => {
    const buckets: Record<string, { count: number; points: number }> = {
      done: { count: 0, points: 0 },
      in_progress: { count: 0, points: 0 },
      todo: { count: 0, points: 0 },
    }
    for (const s of stories) {
      const key = s.status in buckets ? s.status : 'todo'
      buckets[key].count += 1
      buckets[key].points += s.points || 0
    }
    const totalCount = stories.length
    const totalPoints = Object.values(buckets).reduce((n, b) => n + b.points, 0)
    const byPoints = totalPoints > 0
    const pct = byPoints
      ? Math.round((buckets.done.points / totalPoints) * 100)
      : totalCount > 0
        ? Math.round((buckets.done.count / totalCount) * 100)
        : 0
    return { buckets, totalCount, totalPoints, byPoints, pct }
  }, [stories])

  const loadMetrics = useCallback(
    async (opts?: { quiet?: boolean }) => {
      if (!projectId) return
      if (!opts?.quiet) setBusy('metrics')
      try {
        setMetrics(await api.evaluate(projectId))
      } catch (err) {
        if (!opts?.quiet) {
          setError(err instanceof Error ? err.message : 'Metrics failed')
        }
      } finally {
        if (!opts?.quiet) setBusy(null)
      }
    },
    [projectId],
  )

  // Keep Reports in sync when stories change while on that tab
  useEffect(() => {
    if (tab !== 'reports' || !projectId || loading) return
    void loadMetrics({ quiet: true })
  }, [tab, stories, projectId, loading, loadMetrics])

  const runCritique = async () => {
    setBusy('critique')
    try {
      const c = await api.critique(projectId)
      setCriticReport(c)
      setAiRationale(c.rationale)
      setAiAgent(c.agent)
      setTab('reports')
      toast('Quality check complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Critique failed')
    } finally {
      setBusy(null)
    }
  }

  const generateBacklog = async (replace = true) => {
    setBusy('generate')
    setError(null)
    try {
      const res = await api.generateBacklog(projectId, replace)
      setAiRationale(res.rationale)
      setAiAgent(res.agent)
      setPipelineRationale(res.pipeline?.rationale || null)
      setCodeFiles(res.codebase_context?.file_paths ?? null)
      if (res.critic) setCriticReport(res.critic)
      setShowGenerate(false)
      await refresh()
      setTab('backlog')
      const n = res.codebase_context?.file_count || 0
      toast(
        n > 0
          ? `Backlog generated via ${res.agent} (${n} files)`
          : `Backlog generated via ${res.agent}`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generate failed')
    } finally {
      setBusy(null)
    }
  }

  const ensureSprint = async () => {
    if (sprints.length > 0) return sprints[0]
    const sp = await api.createSprint(projectId, {
      name: 'Sprint 1',
      goal: 'First vertical slice',
      capacity_points: 20,
      status: 'active',
    })
    setSprints([sp, ...sprints])
    return sp
  }

  const planSprint = async (apply: boolean) => {
    setBusy(apply ? 'plan-apply' : 'plan')
    try {
      const sp = await ensureSprint()
      const res = await api.planSprint(projectId, sp.id, {
        capacity_points: sp.capacity_points,
        apply,
      })
      setAiRationale(res.rationale)
      setAiAgent(res.agent)
      setPipelineRationale(res.pipeline?.rationale || null)
      if (res.critic) setCriticReport(res.critic)
      await refresh()
      toast(apply ? 'Sprint plan applied' : 'Sprint plan ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Plan failed')
    } finally {
      setBusy(null)
    }
  }

  const runStandup = async () => {
    setBusy('standup')
    try {
      const res = await api.standup(projectId)
      setStandup(res.summary)
      setAiRationale(res.rationale)
      setAiAgent(res.agent)
      setPipelineRationale(res.pipeline?.rationale || null)
      if (res.critic) setCriticReport(res.critic)
      setTab('reports')
      toast('Standup draft ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Standup failed')
    } finally {
      setBusy(null)
    }
  }

  const onStorySave = async (patch: Partial<Story>) => {
    if (!selectedStory) return
    const updated = await api.updateStory(projectId, selectedStory.id, patch)
    setSelectedStory(updated)
    setStories((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    setEpics((prev) =>
      prev.map((e) => ({
        ...e,
        stories: (e.stories || []).map((s) =>
          s.id === updated.id ? updated : s,
        ),
      })),
    )
    // Nested sprint story status for overview counts
    setSprints((prev) =>
      prev.map((sp) => ({
        ...sp,
        items: (sp.items || []).map((it) =>
          it.story_id === updated.id || it.story?.id === updated.id
            ? { ...it, story: updated }
            : it,
        ),
      })),
    )
    toast('Story saved')
  }

  const onStatusChange = async (story: Story, status: string) => {
    const updated = await api.updateStory(projectId, story.id, { status })
    setStories((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    setEpics((prev) =>
      prev.map((e) => ({
        ...e,
        stories: (e.stories || []).map((s) =>
          s.id === updated.id ? updated : s,
        ),
      })),
    )
    setSprints((prev) =>
      prev.map((sp) => ({
        ...sp,
        items: (sp.items || []).map((it) =>
          it.story_id === updated.id || it.story?.id === updated.id
            ? { ...it, story: updated }
            : it,
        ),
      })),
    )
    if (selectedStory?.id === updated.id) setSelectedStory(updated)
  }

  if (loading && !project) {
    return (
      <div className="page">
        <div className="skeleton" style={{ width: 200, height: 16, marginBottom: 12 }} />
        <div className="skeleton" style={{ width: '60%', height: 12 }} />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="page">
        <p className="alert">{error || 'Project not found'}</p>
        <Link to="/" className="btn" style={{ marginTop: 12, display: 'inline-flex' }}>
          Back to projects
        </Link>
      </div>
    )
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'backlog', label: 'Backlog' },
    { id: 'board', label: 'Board' },
    { id: 'reports', label: 'Reports' },
  ]

  return (
    <div className="page page-wide">
      <div
        className={`project-chrome${headerScrolled ? ' is-scrolled' : ''}`}
      >
        <div className="toolbar" style={{ marginBottom: 8 }}>
          <div style={{ minWidth: 0 }}>
            <nav className="crumb" aria-label="Breadcrumb">
              <Link to="/">Projects</Link>
              <span className="crumb-sep">/</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                {project.name}
              </span>
            </nav>
            <h1 className="page-title" style={{ marginTop: 4 }}>
              {project.name}
            </h1>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 8,
                marginTop: 4,
                alignItems: 'center',
              }}
            >
              {activeSprint ? (
                <span className="pill pill-progress">{activeSprint.name}</span>
              ) : (
                <span className="pill pill-muted">No sprint</span>
              )}
              <span className="mono-id">
                {stories.length} stories ·{' '}
                {stories.reduce((n, s) => n + (s.points || 0), 0)} pts
              </span>
            </div>
          </div>
          <div className="toolbar-spacer" />
          <button
            type="button"
            className="btn btn-primary"
            disabled={!!busy}
            onClick={() => setShowGenerate(true)}
          >
            Generate backlog
          </button>
        </div>

        <div className="tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`tab${tab === t.id ? ' active' : ''}`}
              onClick={() => {
                setTab(t.id)
                // Always re-fetch metrics when opening Reports (board moves are live)
                if (t.id === 'reports') void loadMetrics({ quiet: true })
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="alert" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {tab === 'overview' && (
        <div key="overview" className="tab-panel" style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
          <div className="panel" style={{ padding: 14 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: 'var(--text-muted)',
                marginBottom: 6,
              }}
            >
              Brief
            </div>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5 }}>
              {project.brief || 'No brief yet.'}
            </p>
          </div>

          <div className="panel" style={{ padding: 14 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: 'var(--text-muted)',
                marginBottom: 6,
              }}
            >
              Completion
            </div>

            {progress.totalCount === 0 ? (
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
                No stories yet. Generate a backlog to track completion.
              </p>
            ) : (
              <>
                <div className="progress-head">
                  <span className="progress-pct">{progress.pct}%</span>
                  <span className="mono-id">
                    {progress.byPoints
                      ? `${progress.buckets.done.points}/${progress.totalPoints} pts done`
                      : `${progress.buckets.done.count}/${progress.totalCount} stories done`}
                  </span>
                </div>

                <div
                  className="progress-track"
                  role="img"
                  aria-label={
                    `${progress.pct}% complete — ` +
                    `${progress.buckets.done.count} done, ` +
                    `${progress.buckets.in_progress.count} in progress, ` +
                    `${progress.buckets.todo.count} to do`
                  }
                >
                  {(['done', 'in_progress'] as const).map((seg) => {
                    const b = progress.buckets[seg]
                    const total = progress.byPoints
                      ? progress.totalPoints
                      : progress.totalCount
                    const value = progress.byPoints ? b.points : b.count
                    const width = total > 0 ? (value / total) * 100 : 0
                    return (
                      <span
                        key={seg}
                        className="progress-seg"
                        data-seg={seg}
                        style={{ width: `${width}%` }}
                      />
                    )
                  })}
                </div>

                <div className="progress-legend">
                  {(
                    [
                      ['done', 'Done'],
                      ['in_progress', 'In progress'],
                      ['todo', 'To do'],
                    ] as const
                  ).map(([seg, label]) => (
                    <span key={seg} className="progress-legend-item">
                      <span className="progress-legend-dot" data-seg={seg} />
                      {label}
                      <span className="progress-legend-count">
                        {progress.buckets[seg].count}
                      </span>
                      {progress.byPoints && (
                        <span style={{ color: 'var(--text-muted)' }}>
                          · {progress.buckets[seg].points} pts
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div
            className="overview-split"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 10,
            }}
          >
            <div className="panel" style={{ padding: 14 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-muted)',
                  marginBottom: 6,
                }}
              >
                Goals
              </div>
              {project.goals?.length ? (
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                  {project.goals.map((g) => (
                    <li key={g} style={{ marginBottom: 4 }}>
                      {g}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: 0, color: 'var(--text-muted)' }}>None</p>
              )}
            </div>
            <div className="panel" style={{ padding: 14 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-muted)',
                  marginBottom: 6,
                }}
              >
                Constraints
              </div>
              {project.constraints?.length ? (
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                  {project.constraints.map((c) => (
                    <li key={c} style={{ marginBottom: 4 }}>
                      {c}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ margin: 0, color: 'var(--text-muted)' }}>None</p>
              )}
            </div>
          </div>
          {sprints.length > 0 && (
            <div className="panel" style={{ padding: 14 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-muted)',
                  marginBottom: 8,
                }}
              >
                Sprints
              </div>
              {sprints.map((sp) => {
                const pts = (sp.items || []).reduce(
                  (n, i) => n + (i.story?.points || 0),
                  0,
                )
                return (
                  <div
                    key={sp.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 13,
                      padding: '6px 0',
                      borderTop: '1px solid var(--border)',
                    }}
                  >
                    <span>
                      <strong>{sp.name}</strong>
                      <span style={{ color: 'var(--text-muted)' }}>
                        {' '}
                        · {sp.status}
                      </span>
                    </span>
                    <span className="mono-id">
                      {pts}/{sp.capacity_points} pts
                    </span>
                  </div>
                )
              })}
            </div>
          )}
          <div className="toolbar">
            <button
              type="button"
              className="btn"
              disabled={!!busy || stories.length === 0}
              onClick={() => void planSprint(true)}
            >
              Plan sprint
            </button>
            <button
              type="button"
              className="btn"
              disabled={!!busy}
              onClick={() => void runStandup()}
            >
              Draft standup
            </button>
          </div>
        </div>
      )}

      {tab === 'backlog' && (
        <div key="backlog" className="tab-panel">
          <div className="filter-bar">
            <div className="filter-group">
              <span className="filter-label">Status</span>
              <SegmentedControl
                value={statusFilter}
                ariaLabel="Filter by status"
                onChange={setStatusFilter}
                options={
                  [
                    ['all', 'All'],
                    ['todo', 'To do'],
                    ['in_progress', 'In progress'],
                    ['done', 'Done'],
                  ] as const
                }
              />
            </div>

            <div className="filter-group">
              <label className="filter-label" htmlFor="filter-priority">
                Priority
              </label>
              <select
                id="filter-priority"
                className="filter-select"
                value={priorityFilter}
                onChange={(e) =>
                  setPriorityFilter(e.target.value as PriorityFilter)
                }
              >
                <option value="all">All priorities</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label" htmlFor="filter-epic">
                Epic
              </label>
              <select
                id="filter-epic"
                className="filter-select filter-select-wide"
                value={epicFilter === 'all' ? 'all' : String(epicFilter)}
                onChange={(e) => {
                  const v = e.target.value
                  setEpicFilter(v === 'all' ? 'all' : Number(v))
                }}
              >
                <option value="all">All epics</option>
                {epics.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.title}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-meta">
              <span className="mono-id">
                {filteredStories.length} of {stories.length} stories
              </span>
              {(statusFilter !== 'all' ||
                priorityFilter !== 'all' ||
                epicFilter !== 'all') && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setStatusFilter('all')
                    setPriorityFilter('all')
                    setEpicFilter('all')
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>
          </div>

          {stories.length === 0 ? (
            <div className="panel empty">
              No stories yet. Generate a backlog from the project brief.
            </div>
          ) : filteredStories.length === 0 ? (
            <div className="panel empty">
              No stories match these filters.
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => {
                    setStatusFilter('all')
                    setPriorityFilter('all')
                    setEpicFilter('all')
                  }}
                >
                  Clear filters
                </button>
              </div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Epic</th>
                    <th>Pts</th>
                    <th>Priority</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStories.map((story, i) => (
                    <tr
                      key={story.id}
                      className={[
                        'row-enter',
                        selectedStory?.id === story.id ? 'selected' : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      style={{ ['--i' as string]: i }}
                      tabIndex={0}
                      onClick={() => setSelectedStory(story)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setSelectedStory(story)
                        }
                      }}
                    >
                      <td className="mono-id">ST-{story.id}</td>
                      <td style={{ fontWeight: 500, maxWidth: 420 }}>
                        <div className="truncate">{story.title}</div>
                      </td>
                      <td
                        style={{
                          color: 'var(--text-secondary)',
                          maxWidth: 160,
                        }}
                      >
                        <div className="truncate">
                          {epicById.get(story.epic_id)?.title || '—'}
                        </div>
                      </td>
                      <td>
                        <PointsPill value={story.points} />
                      </td>
                      <td>
                        <PriorityPill value={story.priority} />
                      </td>
                      <td>
                        <StatusPill value={story.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'board' && (
        <div key="board" className="tab-panel">
          <SprintBoard
            stories={stories}
            selectedId={selectedStory?.id}
            onStatusChange={onStatusChange}
            onOpen={setSelectedStory}
            loading={loading}
          />
        </div>
      )}

      {tab === 'reports' && (
        <div key="reports" className="tab-panel" style={{ display: 'grid', gap: 12, maxWidth: 800 }}>
          <div className="toolbar">
            <button
              type="button"
              className="btn"
              disabled={!!busy || stories.length === 0}
              onClick={() => void runCritique()}
            >
              Run quality check
            </button>
            <button
              type="button"
              className="btn"
              disabled={!!busy}
              onClick={() => void loadMetrics()}
            >
              Refresh metrics
            </button>
            <button
              type="button"
              className="btn"
              disabled={!!busy}
              onClick={() => void runStandup()}
            >
              Draft standup
            </button>
            <button
              type="button"
              className="btn"
              disabled={!!busy || stories.length === 0}
              onClick={() => void planSprint(true)}
            >
              Plan sprint
            </button>
          </div>

          {(pipelineRationale || aiRationale || codeFiles) && (
            <div>
              {pipelineRationale && (
                <RationalePanel title="Pipeline" agent="pipeline">
                  {pipelineRationale}
                </RationalePanel>
              )}
              {aiRationale && (
                <RationalePanel title="Agent notes" agent={aiAgent}>
                  {aiRationale}
                </RationalePanel>
              )}
              {codeFiles && codeFiles.length > 0 && (
                <RationalePanel
                  title="Files sent to AI"
                  agent={`${codeFiles.length} files`}
                >
                  <ul
                    style={{
                      margin: 0,
                      paddingLeft: 18,
                      fontFamily:
                        'var(--font-mono, ui-monospace, monospace)',
                      fontSize: 11.5,
                    }}
                  >
                    {codeFiles.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </RationalePanel>
              )}
            </div>
          )}

          {standup && (
            <div className="panel" style={{ padding: 12 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 8,
                }}
              >
                <strong style={{ fontSize: 13 }}>Standup draft</strong>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setStandup(null)}
                >
                  Dismiss
                </button>
              </div>
              <pre
                style={{
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'inherit',
                  fontSize: 12.5,
                  color: 'var(--text-secondary)',
                }}
              >
                {standup}
              </pre>
            </div>
          )}

          <CriticPanel report={criticReport} />
          <MetricsPanel metrics={metrics} loading={busy === 'metrics'} />
        </div>
      )}

      {drawerStory && (
        <StoryEditor
          open={!!selectedStory}
          story={drawerStory}
          epicTitle={epicById.get(drawerStory.epic_id)?.title}
          onSave={onStorySave}
          onClose={() => setSelectedStory(null)}
        />
      )}

      <Modal
        open={showGenerate}
        onClose={() => busy !== 'generate' && setShowGenerate(false)}
        labelledBy="gen-title"
      >
        <div className="modal-head">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 4,
            }}
          >
            <h2 id="gen-title" className="page-title">
              Generate backlog
            </h2>
            <span className="badge-stub">Stub generator</span>
          </div>
          <p className="page-sub">
            Builds epics and stories from the project brief. Replaces the
            current backlog if you continue.
          </p>
        </div>
        <div className="modal-body">
          <div
            className="panel"
            style={{
              padding: 10,
              background: 'var(--surface-2)',
              fontSize: 12.5,
              color: 'var(--text-secondary)',
              maxHeight: 140,
              overflow: 'auto',
            }}
          >
            <strong style={{ color: 'var(--text)' }}>Brief</strong>
            <p style={{ margin: '6px 0 0' }}>
              {project.brief ||
                'No brief — generation will use project name only.'}
            </p>
          </div>
          {busy === 'generate' && (
            <div style={{ display: 'grid', gap: 8 }}>
              <div className="skeleton" style={{ height: 14, width: '80%' }} />
              <div className="skeleton" style={{ height: 14, width: '60%' }} />
              <div className="skeleton" style={{ height: 14, width: '70%' }} />
            </div>
          )}
        </div>
        <div className="modal-foot">
          <button
            type="button"
            className="btn"
            disabled={busy === 'generate'}
            onClick={() => setShowGenerate(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy === 'generate'}
            onClick={() => void generateBacklog(true)}
          >
            {busy === 'generate' ? 'Generating…' : 'Generate'}
          </button>
        </div>
      </Modal>
    </div>
  )
}
