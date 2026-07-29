import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { usePresence } from '../hooks/usePresence'

type ToastCtx = { toast: (msg: string) => void }

const Ctx = createContext<ToastCtx>({ toast: () => undefined })

const TOAST_MS = 2200

function ToastView({
  message,
  onDone,
}: {
  message: string
  onDone: () => void
}) {
  const [open, setOpen] = useState(true)
  const { mounted, entered } = usePresence(open, 160)

  useEffect(() => {
    const t = window.setTimeout(() => setOpen(false), TOAST_MS)
    return () => window.clearTimeout(t)
  }, [])

  useEffect(() => {
    if (!open && !mounted) onDone()
  }, [open, mounted, onDone])

  if (!mounted) return null

  return (
    <div
      className={`toast${entered ? ' is-open' : ''}`}
      role="status"
      aria-live="polite"
    >
      {message}
      <span className="toast-progress" aria-hidden />
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null)
  const [key, setKey] = useState(0)

  const toast = useCallback((m: string) => {
    setMsg(m)
    setKey((k) => k + 1)
  }, [])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <Ctx.Provider value={value}>
      {children}
      {msg && (
        <ToastView
          key={key}
          message={msg}
          onDone={() => setMsg(null)}
        />
      )}
    </Ctx.Provider>
  )
}

export function useToast() {
  return useContext(Ctx)
}
