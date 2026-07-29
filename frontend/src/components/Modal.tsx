import { useEffect, useRef, type ReactNode } from 'react'
import { useBodyScrollLock, usePresence } from '../hooks/usePresence'

export function Modal({
  open,
  onClose,
  children,
  labelledBy,
}: {
  open: boolean
  onClose: () => void
  children: ReactNode
  labelledBy?: string
}) {
  const { mounted, entered } = usePresence(open, 200)
  useBodyScrollLock(mounted)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!mounted || !entered) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    // Focus first focusable
    const root = panelRef.current
    const el = root?.querySelector<HTMLElement>(
      'input, textarea, select, button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    el?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [mounted, entered, onClose])

  if (!mounted) return null

  return (
    <div
      className={`modal-backdrop${entered ? ' is-open' : ''}`}
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        className={`modal${entered ? ' is-open' : ''}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
      >
        {children}
      </div>
    </div>
  )
}
