import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useBodyScrollLock, usePresence } from '../hooks/usePresence'

export function Modal({
  open,
  onClose,
  children,
  labelledBy,
  wide = false,
}: {
  open: boolean
  onClose: () => void
  children: ReactNode
  labelledBy?: string
  /** Roomier panel for content-heavy dialogs (e.g. the import preview). */
  wide?: boolean
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

  // Portal to body so position:fixed is relative to the viewport — never a
  // transformed ancestor (.page uses animation transforms, which otherwise
  // pin the dialog off-center inside the content column).
  return createPortal(
    <div
      className={`modal-backdrop${entered ? ' is-open' : ''}`}
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        className={`modal${wide ? ' modal-lg' : ''}${entered ? ' is-open' : ''}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
