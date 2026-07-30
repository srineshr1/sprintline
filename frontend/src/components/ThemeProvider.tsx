import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'sprintline-theme'
/** Keep in sync with the pre-paint transition window in index.css. */
const THEME_TRANSITION_MS = 200

type ThemeCtx = {
  /** User preference — what is persisted. */
  mode: ThemeMode
  /** Concrete theme actually painted (system resolved). */
  resolved: ResolvedTheme
  setMode: (mode: ThemeMode) => void
  /** Light → Dark → System → Light. */
  cycleMode: () => void
}

const Ctx = createContext<ThemeCtx>({
  mode: 'system',
  resolved: 'light',
  setMode: () => undefined,
  cycleMode: () => undefined,
})

const MODES: ThemeMode[] = ['light', 'dark', 'system']

function readStored(): ThemeMode {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    /* private mode / storage disabled */
  }
  return 'system'
}

function systemPrefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )
}

function resolve(mode: ThemeMode): ResolvedTheme {
  if (mode === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return mode
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readStored)
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolve(readStored()))

  // Paint the resolved theme onto <html>. The inline script in index.html has
  // already done this for the first paint; this keeps it in sync afterwards.
  useEffect(() => {
    const next = resolve(mode)
    setResolved(next)
    const root = document.documentElement
    if (root.getAttribute('data-theme') === next) return

    // Opt into the cross-fade only while the theme is actually changing, so we
    // never pay transition cost on unrelated hover/state changes.
    root.classList.add('is-theme-switching')
    root.setAttribute('data-theme', next)
    const t = window.setTimeout(
      () => root.classList.remove('is-theme-switching'),
      THEME_TRANSITION_MS + 40,
    )
    return () => window.clearTimeout(t)
  }, [mode])

  // Follow the OS while in "system" mode.
  useEffect(() => {
    if (mode !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const next: ResolvedTheme = mq.matches ? 'dark' : 'light'
      setResolved(next)
      const root = document.documentElement
      root.classList.add('is-theme-switching')
      root.setAttribute('data-theme', next)
      window.setTimeout(
        () => root.classList.remove('is-theme-switching'),
        THEME_TRANSITION_MS + 40,
      )
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [mode])

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* non-fatal — theme just won't persist */
    }
  }, [])

  const cycleMode = useCallback(() => {
    setMode(MODES[(MODES.indexOf(readStored()) + 1) % MODES.length])
  }, [setMode])

  const value = useMemo(
    () => ({ mode, resolved, setMode, cycleMode }),
    [mode, resolved, setMode, cycleMode],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme() {
  return useContext(Ctx)
}
