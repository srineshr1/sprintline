import type { ReactNode } from 'react'

/** Quiet collapsible note — not a hero banner. */
export function RationalePanel({
  title = 'Notes',
  agent,
  children,
}: {
  title?: string
  agent?: string
  children: ReactNode
}) {
  if (!children) return null
  return (
    <details className="details-box" style={{ marginBottom: 10 }}>
      <summary>
        {title}
        {agent ? (
          <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>
            {' '}
            · {agent}
          </span>
        ) : null}
      </summary>
      <div className="details-body" style={{ whiteSpace: 'pre-wrap' }}>
        {children}
      </div>
    </details>
  )
}
