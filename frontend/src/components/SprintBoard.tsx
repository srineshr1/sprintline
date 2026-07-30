import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type DragEvent,
  type ReactNode,
} from 'react'
import type { Story } from '../types'
import { PointsPill, PriorityPill } from './Badge'
import { useToast } from './Toast'
import {
  animateFlight,
  animateShift,
  captureRects,
  makeFlightClone,
  prefersReducedMotion,
} from '../lib/flip'

const COLUMNS: { id: string; label: string }[] = [
  { id: 'todo', label: 'To do' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'done', label: 'Done' },
]

/** Don't flag a move as slow until the API has actually been slow. */
const SLOW_AFTER_MS = 280
const LANDED_MS = 480
const FLASH_MS = 620

/** Bumps when its value changes — used for column counts and points. */
function AnimatedCount({
  value,
  children,
}: {
  value: string | number
  children: ReactNode
}) {
  const [bump, setBump] = useState(false)
  const prev = useRef(value)

  useEffect(() => {
    if (prev.current === value) return
    prev.current = value
    setBump(true)
    const t = window.setTimeout(() => setBump(false), 340)
    return () => window.clearTimeout(t)
  }, [value])

  return <span className={bump ? 'count-bump' : undefined}>{children}</span>
}

export function SprintBoard({
  stories,
  selectedId,
  onStatusChange,
  onOpen,
  loading = false,
}: {
  stories: Story[]
  selectedId?: number | null
  onStatusChange: (story: Story, status: string) => Promise<void>
  onOpen: (story: Story) => void
  loading?: boolean
}) {
  const { toast } = useToast()

  /** Live card nodes by story id, for rect capture. */
  const nodesRef = useRef(new Map<number, HTMLElement>())
  /** Queued FLIP job, consumed by the layout effect after the next commit. */
  const flipRef = useRef<{ id: number; rects: Map<number, DOMRect> } | null>(
    null,
  )
  const timersRef = useRef<number[]>([])

  /**
   * Optimistic status per story. The board renders from this first so a card
   * lands in its new column immediately; the parent's `stories` catch up when
   * the PATCH resolves. Cleared on success (parent now agrees) or rollback.
   */
  const [overrides, setOverrides] = useState<Map<number, string>>(new Map())
  const [pending, setPending] = useState<Set<number>>(new Set())
  const [slow, setSlow] = useState<Set<number>>(new Set())
  const [flashCol, setFlashCol] = useState<string | null>(null)
  const [landedId, setLandedId] = useState<number | null>(null)
  const [dragId, setDragId] = useState<number | null>(null)
  const [dragOverCol, setDragOverCol] = useState<string | null>(null)

  const track = (id: number) => {
    timersRef.current.push(id)
  }

  useEffect(
    () => () => {
      for (const t of timersRef.current) window.clearTimeout(t)
    },
    [],
  )

  const statusOf = useCallback(
    (s: Story) => overrides.get(s.id) ?? s.status ?? 'todo',
    [overrides],
  )

  // Drop an override once the server-confirmed story matches it, so we never
  // keep shadowing real data (e.g. a status changed from the story drawer).
  useEffect(() => {
    setOverrides((prev) => {
      if (prev.size === 0) return prev
      let changed = false
      const next = new Map(prev)
      for (const s of stories) {
        if (next.get(s.id) === s.status) {
          next.delete(s.id)
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [stories])

  /**
   * FLIP, second half. Runs after the commit that re-parented the card:
   * measure the landing rect, fly a clone from the captured start rect, and
   * slide any sibling that got pushed around.
   */
  useLayoutEffect(() => {
    const job = flipRef.current
    if (!job) return
    flipRef.current = null

    const { id, rects } = job
    const el = nodesRef.current.get(id)
    const from = rects.get(id)
    if (!el || !from) return

    // Make sure the landing slot is actually on screen before measuring it.
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    const to = el.getBoundingClientRect()

    // Nothing moved (same column, same slot) — skip the flight.
    if (Math.abs(to.left - from.left) < 1 && Math.abs(to.top - from.top) < 1) {
      return
    }

    // Siblings that shifted stay inside their own list, so they can animate
    // in place without clipping trouble.
    for (const [otherId, node] of nodesRef.current) {
      if (otherId === id || !node.isConnected) continue
      const prevRect = rects.get(otherId)
      if (!prevRect) continue
      const nowRect = node.getBoundingClientRect()
      const dx = prevRect.left - nowRect.left
      const dy = prevRect.top - nowRect.top
      if (Math.abs(dx) > 1 || Math.abs(dy) > 1) animateShift(node, dx, dy)
    }

    const clone = makeFlightClone(el, from)
    el.style.visibility = 'hidden'

    void animateFlight(clone, from, to).then(() => {
      clone.remove()
      el.style.visibility = ''
      setLandedId(id)
      track(window.setTimeout(() => setLandedId((c) => (c === id ? null : c)), LANDED_MS))
    })
  })

  const move = useCallback(
    async (story: Story, status: string) => {
      const id = story.id
      const current = overrides.get(id) ?? story.status ?? 'todo'
      // Guard against double-clicks and no-op moves.
      if (status === current || pending.has(id)) return

      const reduced = prefersReducedMotion()
      const rects = reduced
        ? new Map<number, DOMRect>()
        : captureRects(nodesRef.current)

      if (!reduced) flipRef.current = { id, rects }

      setOverrides((prev) => new Map(prev).set(id, status))
      setPending((prev) => new Set(prev).add(id))
      setFlashCol(status)
      track(window.setTimeout(() => setFlashCol((c) => (c === status ? null : c)), FLASH_MS))

      // Only surface a spinner if the request outlives the flight animation.
      const slowTimer = window.setTimeout(() => {
        setSlow((prev) => new Set(prev).add(id))
      }, SLOW_AFTER_MS)
      track(slowTimer)

      try {
        await onStatusChange(story, status)
        if (reduced) {
          setLandedId(id)
          track(
            window.setTimeout(
              () => setLandedId((c) => (c === id ? null : c)),
              LANDED_MS,
            ),
          )
        }
      } catch (err) {
        // Roll the card back with the same flight, in reverse.
        if (!reduced) {
          flipRef.current = { id, rects: captureRects(nodesRef.current) }
        }
        setOverrides((prev) => {
          const next = new Map(prev)
          next.delete(id)
          return next
        })
        setFlashCol(null)
        toast(
          err instanceof Error
            ? `Move failed — ${err.message}`
            : 'Move failed — reverted',
        )
      } finally {
        window.clearTimeout(slowTimer)
        setSlow((prev) => {
          if (!prev.has(id)) return prev
          const next = new Set(prev)
          next.delete(id)
          return next
        })
        setPending((prev) => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
      }
    },
    [onStatusChange, overrides, pending, toast],
  )

  const onDrop = (e: DragEvent<HTMLDivElement>, colId: string) => {
    e.preventDefault()
    setDragOverCol(null)
    setDragId(null)
    const raw = e.dataTransfer.getData('text/plain')
    const id = Number(raw)
    if (!Number.isFinite(id)) return
    const story = stories.find((s) => s.id === id)
    if (story) void move(story, colId)
  }

  if (loading) {
    return (
      <div className="board-scroll" role="region" aria-label="Sprint board">
        <div className="board">
          {COLUMNS.map((col, ci) => (
            <div key={col.id} className="board-col" data-col={col.id}>
              <div className="board-col-head">
                <span className="board-col-title">
                  <span className="board-col-dot" aria-hidden />
                  {col.label}
                </span>
                <span className="board-col-meta">·</span>
              </div>
              <ul className="board-cards">
                {Array.from({ length: 3 - ci }, (_, i) => (
                  <li
                    key={i}
                    className="board-sk-card anim-fade"
                    style={{ ['--i' as string]: ci * 2 + i }}
                  >
                    <div className="skeleton" style={{ width: '38%' }} />
                    <div className="skeleton" style={{ width: '88%' }} />
                    <div className="skeleton" style={{ width: '62%' }} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="board-scroll" role="region" aria-label="Sprint board">
      <div className="board">
        {COLUMNS.map((col) => {
          const items = stories.filter((s) => statusOf(s) === col.id)
          const pts = items.reduce((n, s) => n + (s.points || 0), 0)
          return (
            <div
              key={col.id}
              className={[
                'board-col',
                flashCol === col.id ? 'is-flash' : '',
                dragOverCol === col.id ? 'is-drag-over' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              data-col={col.id}
              onDragOver={(e) => {
                if (dragId === null) return
                e.preventDefault()
                e.dataTransfer.dropEffect = 'move'
                setDragOverCol(col.id)
              }}
              onDragLeave={(e) => {
                // Ignore bubbling from children still inside the column.
                if (e.currentTarget.contains(e.relatedTarget as Node)) return
                setDragOverCol((c) => (c === col.id ? null : c))
              }}
              onDrop={(e) => onDrop(e, col.id)}
            >
              <div className="board-col-head">
                <span className="board-col-title">
                  <span className="board-col-dot" aria-hidden />
                  {col.label}
                </span>
                <span className="board-col-meta">
                  <AnimatedCount value={`${items.length}:${pts}`}>
                    {items.length} · {pts} pts
                  </AnimatedCount>
                </span>
              </div>
              <ul className="board-cards">
                {items.length === 0 && (
                  <li className="board-empty">No stories</li>
                )}
                {items.map((story) => {
                  const isPending = pending.has(story.id)
                  return (
                    <li
                      key={story.id}
                      ref={(node) => {
                        if (node) nodesRef.current.set(story.id, node)
                        else nodesRef.current.delete(story.id)
                      }}
                      className={[
                        'board-card',
                        selectedId === story.id ? 'is-selected' : '',
                        landedId === story.id ? 'is-landed' : '',
                        slow.has(story.id) ? 'is-pending' : '',
                        dragId === story.id ? 'is-dragging' : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      draggable={!isPending}
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', String(story.id))
                        e.dataTransfer.effectAllowed = 'move'
                        setDragId(story.id)
                      }}
                      onDragEnd={() => {
                        setDragId(null)
                        setDragOverCol(null)
                      }}
                    >
                      <span className="board-card-grip" aria-hidden>
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
                          <circle cx="2" cy="2" r="1" />
                          <circle cx="8" cy="2" r="1" />
                          <circle cx="2" cy="5" r="1" />
                          <circle cx="8" cy="5" r="1" />
                          <circle cx="2" cy="8" r="1" />
                          <circle cx="8" cy="8" r="1" />
                        </svg>
                      </span>
                      <div className="board-card-meta">
                        <span className="mono-id">ST-{story.id}</span>
                        <div className="board-card-pills">
                          <PriorityPill value={story.priority} />
                          <PointsPill value={story.points} />
                        </div>
                      </div>
                      <button
                        type="button"
                        className="board-card-title"
                        onClick={() => onOpen(story)}
                      >
                        {story.title}
                      </button>
                      <div className="board-moves">
                        {COLUMNS.filter((c) => c.id !== col.id).map((c) => (
                          <button
                            key={c.id}
                            type="button"
                            className="btn btn-sm"
                            disabled={isPending}
                            aria-label={`Move ST-${story.id} to ${c.label}`}
                            onClick={() => void move(story, c.id)}
                          >
                            {isPending && slow.has(story.id) ? (
                              <span className="spinner" aria-hidden />
                            ) : null}
                            → {c.label}
                          </button>
                        ))}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
