import type { EvaluationResponse } from '../types'

export function MetricsPanel({
  metrics,
  loading,
}: {
  metrics: EvaluationResponse | null
  loading?: boolean
}) {
  if (loading) {
    return (
      <div style={{ display: 'grid', gap: 8 }}>
        <div className="skeleton" style={{ height: 48 }} />
        <div className="skeleton" style={{ height: 48 }} />
      </div>
    )
  }
  if (!metrics) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
        Run metrics to see AC coverage, INVEST scores, and sprint points.
      </p>
    )
  }

  const ac = metrics.ac_coverage
  const inv = metrics.invest
  const board = metrics.board
  const rates = inv.dimension_pass_rates || {}

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div className="metric-row">
        <div className="metric-card">
          <div className="metric-label">AC coverage</div>
          <div className="metric-value">{ac.coverage_pct}%</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {ac.with_ac}/{ac.total_stories} stories
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">INVEST avg</div>
          <div className="metric-value">{inv.average_pct}%</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            score {inv.average_score}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Board done</div>
          <div className="metric-value">{board.completion_pct}%</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            {board.completed_points}/{board.total_points} pts
          </div>
        </div>
      </div>

      {Object.keys(rates).length > 0 && (
        <div className="panel" style={{ padding: 12 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 8,
              color: 'var(--text-secondary)',
            }}
          >
            INVEST dimensions
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 6,
            }}
          >
            {Object.entries(rates).map(([dim, pct]) => (
              <div
                key={dim}
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 5,
                  padding: '6px 8px',
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    textTransform: 'uppercase',
                    color: 'var(--text-muted)',
                  }}
                >
                  {dim}
                </div>
                <div
                  style={{
                    fontWeight: 600,
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {pct}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {metrics.sprints?.length > 0 && (
        <div className="panel" style={{ padding: 12 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 8,
              color: 'var(--text-secondary)',
            }}
          >
            Sprints
          </div>
          {metrics.sprints.map((sp) => (
            <div
              key={String(sp.sprint_id ?? sp.sprint_name)}
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
                fontSize: 12,
                padding: '6px 0',
                borderTop: '1px solid var(--border)',
              }}
            >
              <strong>{sp.sprint_name}</strong>
              <span className="mono-id">
                planned {sp.planned_points}/{sp.capacity_points}
              </span>
              <span className="mono-id">done {sp.completed_points}</span>
              <span className="mono-id">left {sp.remaining_points}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
