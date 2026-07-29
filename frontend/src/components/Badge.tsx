export function PriorityPill({ value }: { value: string }) {
  const v = (value || 'medium').toLowerCase()
  const cls =
    v === 'high' ? 'pill-high' : v === 'low' ? 'pill-low' : 'pill-medium'
  return <span className={`pill ${cls}`}>{v}</span>
}

export function StatusPill({ value }: { value: string }) {
  const v = (value || 'todo').toLowerCase()
  const cls =
    v === 'done'
      ? 'pill-done'
      : v === 'in_progress'
        ? 'pill-progress'
        : 'pill-todo'
  const label =
    v === 'in_progress' ? 'In progress' : v === 'done' ? 'Done' : 'To do'
  return <span className={`pill ${cls}`}>{label}</span>
}

export function PointsPill({ value }: { value: number }) {
  return <span className="pill pill-points">{value} pts</span>
}
