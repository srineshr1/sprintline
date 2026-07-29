import { useEffect, useState } from 'react'

/**
 * Mount/unmount with enter+exit for CSS transitions.
 * open → mount (entered=false) → next frame entered=true
 * close → entered=false → after exitMs unmount
 */
export function usePresence(open: boolean, exitMs = 220) {
  const [mounted, setMounted] = useState(open)
  const [entered, setEntered] = useState(false)

  useEffect(() => {
    if (open) {
      setMounted(true)
      return
    }
    setEntered(false)
  }, [open])

  useEffect(() => {
    if (!open || !mounted) return
    let cancelled = false
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!cancelled) setEntered(true)
      })
    })
    return () => {
      cancelled = true
      cancelAnimationFrame(id)
    }
  }, [open, mounted])

  useEffect(() => {
    if (open || !mounted) return
    const t = window.setTimeout(() => setMounted(false), exitMs)
    return () => window.clearTimeout(t)
  }, [open, mounted, exitMs])

  return { mounted, entered }
}

export function useBodyScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [locked])
}
