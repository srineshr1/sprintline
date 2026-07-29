import { useState } from 'react'
import type { Story } from '../types'
import { PointsPill, PriorityPill } from './Badge'

const COLUMNS: { id: string; label: string }[] = [
  { id: 'todo', label: 'To do' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'done', label: 'Done' },
]

export function SprintBoard({
  stories,
  selectedId,
  onStatusChange,
  onOpen,
}: {
  stories: Story[]
  selectedId?: number | null
  onStatusChange: (story: Story, status: string) => Promise<void>
  onOpen: (story: Story) => void
}) {
  const [flashCol, setFlashCol] = useState<string | null>(null)
  const [movedId, setMovedId] = useState<number | null>(null)

  const move = async (story: Story, status: string) => {
    await onStatusChange(story, status)
    setFlashCol(status)
    setMovedId(story.id)
    window.setTimeout(() => setFlashCol(null), 420)
    window.setTimeout(() => setMovedId(null), 400)
  }

  return (
    <div className="board-scroll" role="region" aria-label="Sprint board">
      <div className="board">
        {COLUMNS.map((col) => {
          const items = stories.filter((s) => (s.status || 'todo') === col.id)
          const pts = items.reduce((n, s) => n + (s.points || 0), 0)
          return (
            <div
              key={col.id}
              className={`board-col${flashCol === col.id ? ' is-flash' : ''}`}
              data-col={col.id}
            >
              <div className="board-col-head">
                <span className="board-col-title">{col.label}</span>
                <span className="board-col-meta">
                  {items.length} · {pts} pts
                </span>
              </div>
              <ul className="board-cards">
                {items.length === 0 && (
                  <li className="board-empty">No stories</li>
                )}
                {items.map((story) => (
                  <li
                    key={story.id}
                    className={[
                      'board-card',
                      selectedId === story.id ? 'is-selected' : '',
                      movedId === story.id ? 'is-just-moved' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                  >
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
                          onClick={() => void move(story, c.id)}
                        >
                          → {c.label}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
