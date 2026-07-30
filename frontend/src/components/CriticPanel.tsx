import type { CriticReport } from '../types'

export function CriticPanel({
  report,
  title = 'Quality check',
}: {
  report: CriticReport | null | undefined
  title?: string
}) {
  if (!report) return null
  const findings = report.findings || []
  const summary = report.summary || {}

  return (
    <div className="panel" style={{ padding: 12 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 8,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{title}</h3>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {String(summary.errors ?? 0)} errors · {String(summary.warnings ?? summary.open_warnings ?? 0)} warnings
        </span>
      </div>
      {report.rationale && (
        <p
          style={{
            margin: '0 0 8px',
            fontSize: 12,
            color: 'var(--text-secondary)',
          }}
        >
          {report.rationale}
        </p>
      )}
      {findings.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>
          No issues flagged.
        </p>
      ) : (
        <div style={{ maxHeight: 200, overflow: 'auto' }}>
          {findings.slice(0, 30).map((f, i) => (
            <div
              key={`${f.code}-${f.story_id}-${i}`}
              className={`finding ${f.severity}`}
              style={{ ['--i' as string]: i }}
            >
              <strong style={{ textTransform: 'uppercase', fontSize: 10 }}>
                {f.severity}
              </strong>{' '}
              <span style={{ color: 'var(--text-muted)' }}>{f.code}</span>
              {f.story_id != null && (
                <span className="mono-id"> · ST-{f.story_id}</span>
              )}
              <div style={{ marginTop: 2 }}>{f.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
