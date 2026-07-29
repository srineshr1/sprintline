import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import type { Story } from '../types'
import { PriorityPill, StatusPill } from './Badge'
import { useBodyScrollLock, usePresence } from '../hooks/usePresence'

export function StoryEditor({
  open,
  story,
  epicTitle,
  onSave,
  onClose,
}: {
  open: boolean
  story: Story
  epicTitle?: string
  onSave: (patch: Partial<Story>) => Promise<void>
  onClose: () => void
}) {
  const { mounted, entered } = usePresence(open, 220)
  useBodyScrollLock(mounted)

  const [title, setTitle] = useState(story.title)
  const [description, setDescription] = useState(story.description)
  const [acText, setAcText] = useState(
    (story.acceptance_criteria || []).join('\n'),
  )
  const [points, setPoints] = useState(story.points)
  const [priority, setPriority] = useState(story.priority)
  const [status, setStatus] = useState(story.status)
  const [rationale, setRationale] = useState(story.rationale)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const titleRef = useRef<HTMLTextAreaElement>(null)
  const closeBtnRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setTitle(story.title)
    setDescription(story.description)
    setAcText((story.acceptance_criteria || []).join('\n'))
    setPoints(story.points)
    setPriority(story.priority)
    setStatus(story.status)
    setRationale(story.rationale)
    setError(null)
  }, [story])

  useEffect(() => {
    if (!mounted || !entered) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    // Prefer title field, else close
    const t = window.setTimeout(() => {
      titleRef.current?.focus()
      if (document.activeElement !== titleRef.current) {
        closeBtnRef.current?.focus()
      }
    }, 30)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(t)
    }
  }, [mounted, entered, onClose])

  const dirty = useMemo(() => {
    const ac = acText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    const orig = story.acceptance_criteria || []
    return (
      title !== story.title ||
      description !== story.description ||
      points !== story.points ||
      priority !== story.priority ||
      status !== story.status ||
      rationale !== story.rationale ||
      JSON.stringify(ac) !== JSON.stringify(orig)
    )
  }, [title, description, acText, points, priority, status, rationale, story])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSave({
        title: title.trim(),
        description,
        acceptance_criteria: acText
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean),
        points: Number(points) || 0,
        priority,
        status,
        rationale,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!mounted) return null

  return (
    <>
      <div
        className={`drawer-backdrop${entered ? ' is-open' : ''}`}
        onClick={onClose}
        role="presentation"
      />
      <aside
        className={`drawer${entered ? ' is-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Story editor"
      >
        <div className="drawer-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="mono-id">ST-{story.id}</span>
            <StatusPill value={status} />
            <PriorityPill value={priority} />
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <form
          onSubmit={submit}
          style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
        >
          <div className="drawer-body">
            {epicTitle && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Epic · {epicTitle}
              </div>
            )}

            <label className="label">
              Title
              <textarea
                ref={titleRef}
                className="textarea"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                style={{ minHeight: 64, fontWeight: 500, fontSize: 14 }}
              />
            </label>

            <label className="label">
              Description
              <textarea
                className="textarea"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ minHeight: 80 }}
              />
            </label>

            <label className="label">
              Acceptance criteria
              <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>
                {' '}
                (one per line)
              </span>
              <textarea
                className="textarea"
                value={acText}
                onChange={(e) => setAcText(e.target.value)}
                style={{ minHeight: 100, fontFamily: 'inherit' }}
                placeholder={'User can…\nSystem shows…'}
              />
            </label>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 8,
              }}
            >
              <label className="label">
                Points
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={21}
                  value={points}
                  onChange={(e) => setPoints(Number(e.target.value))}
                />
              </label>
              <label className="label">
                Priority
                <select
                  className="select"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
              <label className="label">
                Status
                <select
                  className="select"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="todo">To do</option>
                  <option value="in_progress">In progress</option>
                  <option value="done">Done</option>
                </select>
              </label>
            </div>

            {(rationale || dirty) && (
              <details className="details-box">
                <summary>AI rationale</summary>
                <textarea
                  className="textarea"
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  style={{ minHeight: 56, marginTop: 4 }}
                  placeholder="Why this story was suggested…"
                />
              </details>
            )}

            {error && <div className="alert">{error}</div>}
          </div>

          <div className="drawer-foot">
            {dirty && (
              <span
                style={{
                  marginRight: 'auto',
                  fontSize: 12,
                  color: 'var(--text-muted)',
                  alignSelf: 'center',
                }}
              >
                Unsaved changes
              </span>
            )}
            <button type="button" className="btn" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving || !dirty}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </aside>
    </>
  )
}
