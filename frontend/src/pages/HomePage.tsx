import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Project } from '../types'
import { ImportDialog } from '../components/ImportDialog'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'

export function HomePage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [name, setName] = useState('')
  const [brief, setBrief] = useState('')
  const [goals, setGoals] = useState('')
  const [constraints, setConstraints] = useState('')
  const [creating, setCreating] = useState(false)
  const [meta, setMeta] = useState<
    Record<number, { stories: number; sprint: string }>
  >({})

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const list = await api.listProjects()
      setProjects(list)
      const m: Record<number, { stories: number; sprint: string }> = {}
      await Promise.all(
        list.map(async (p) => {
          try {
            const [stories, sprints] = await Promise.all([
              api.listStories(p.id),
              api.listSprints(p.id),
            ])
            const active =
              sprints.find((s) => s.status === 'active') || sprints[0]
            m[p.id] = {
              stories: stories.length,
              sprint: active ? active.name : '—',
            }
          } catch {
            m[p.id] = { stories: 0, sprint: '—' }
          }
        }),
      )
      setMeta(m)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const onCreate = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      const p = await api.createProject({
        name: name.trim(),
        brief: brief.trim(),
        goals: goals
          .split('\n')
          .map((g) => g.trim())
          .filter(Boolean),
        constraints: constraints
          .split('\n')
          .map((c) => c.trim())
          .filter(Boolean),
      })
      toast('Project created')
      navigate(`/projects/${p.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="page">
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-sub">Your Agile workspaces</p>
        </div>
        <div className="toolbar-spacer" />
        <button
          type="button"
          className="btn"
          onClick={() => setShowImport(true)}
        >
          Import from folder
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowNew(true)}
        >
          New project
        </button>
      </div>

      {error && (
        <div className="alert" style={{ marginBottom: 12 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Stories</th>
                <th>Sprint</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {[0, 1, 2, 3].map((i) => (
                <tr key={i}>
                  <td>
                    <div className="skeleton" style={{ width: '46%' }} />
                    <div
                      className="skeleton"
                      style={{ width: '72%', height: 10, marginTop: 6 }}
                    />
                  </td>
                  <td>
                    <div className="skeleton" style={{ width: 24 }} />
                  </td>
                  <td>
                    <div className="skeleton" style={{ width: 68 }} />
                  </td>
                  <td>
                    <div className="skeleton" style={{ width: 60 }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : projects.length === 0 ? (
        <div className="panel empty">
          <p style={{ margin: '0 0 12px' }}>
            Create a project from a brief, or import existing folders with their
            READMEs and todos.
          </p>
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'center',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              className="btn"
              onClick={() => setShowImport(true)}
            >
              Import from folder
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowNew(true)}
            >
              New project
            </button>
          </div>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Stories</th>
                <th>Sprint</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr
                  key={p.id}
                  tabIndex={0}
                  onClick={() => navigate(`/projects/${p.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      navigate(`/projects/${p.id}`)
                    }
                  }}
                >
                  <td>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        fontWeight: 500,
                      }}
                    >
                      <span className="truncate">{p.name}</span>
                      {p.source_path && (
                        <span
                          className="pill pill-muted"
                          title={p.source_path}
                        >
                          imported
                        </span>
                      )}
                    </div>
                    <div
                      className="truncate"
                      style={{
                        color: 'var(--text-muted)',
                        fontSize: 12,
                        maxWidth: 420,
                      }}
                    >
                      {p.brief || 'No brief'}
                    </div>
                  </td>
                  <td className="mono-id">{meta[p.id]?.stories ?? '—'}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>
                    {meta[p.id]?.sprint ?? '—'}
                  </td>
                  <td className="mono-id">
                    {p.created_at
                      ? new Date(p.created_at).toLocaleDateString()
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ImportDialog
        open={showImport}
        onClose={() => setShowImport(false)}
        onImported={() => {
          void load()
        }}
      />

      <Modal
        open={showNew}
        onClose={() => {
          if (!creating) setShowNew(false)
        }}
        labelledBy="new-project-title"
      >
        <div className="modal-head">
          <h2 id="new-project-title" className="page-title">
            New project
          </h2>
          <p className="page-sub">
            Name the workspace and paste a product brief.
          </p>
        </div>
        <form onSubmit={onCreate}>
          <div className="modal-body">
            <label className="label">
              Name
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Campus Events App"
                required
              />
            </label>
            <label className="label">
              Brief
              <textarea
                className="textarea textarea-sm"
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="What are you building? Who is it for?"
                rows={3}
              />
            </label>
            <label className="label">
              Goals (one per line)
              <textarea
                className="textarea textarea-sm"
                value={goals}
                onChange={(e) => setGoals(e.target.value)}
                placeholder="Optional"
                rows={2}
              />
            </label>
            <label className="label">
              Constraints (one per line)
              <textarea
                className="textarea textarea-sm"
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                placeholder="Optional"
                rows={2}
              />
            </label>
          </div>
          <div className="modal-foot">
            <button
              type="button"
              className="btn"
              disabled={creating}
              onClick={() => setShowNew(false)}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={creating || !name.trim()}
            >
              {creating && <span className="spinner" aria-hidden />}
              {creating ? 'Creating…' : 'Create project'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
