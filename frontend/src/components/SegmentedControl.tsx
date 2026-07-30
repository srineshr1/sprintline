import { useEffect, useLayoutEffect, useRef, useState } from 'react'

/**
 * Segmented control with a pill indicator that slides between options.
 *
 * The indicator is measured from the active button rather than derived from
 * index math, so it stays correct when labels have different widths or wrap.
 * First paint (and resize) jumps into place instead of sliding from x=0.
 */
export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T
  options: readonly (readonly [T, string])[]
  onChange: (next: T) => void
  ariaLabel: string
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState<{ x: number; w: number } | null>(null)
  // Suppress the slide on the very first measurement and on resize.
  const [animate, setAnimate] = useState(false)

  const measure = () => {
    const wrap = wrapRef.current
    if (!wrap) return
    const active = wrap.querySelector<HTMLElement>('.seg-btn.active')
    if (!active) {
      setBox(null)
      return
    }
    setBox({ x: active.offsetLeft - 2, w: active.offsetWidth })
  }

  // Re-measure when the selection changes (after layout, before paint).
  useLayoutEffect(measure, [value, options])

  // Enable sliding only after the indicator has a real starting position.
  useEffect(() => {
    if (!box || animate) return
    const id = requestAnimationFrame(() => setAnimate(true))
    return () => cancelAnimationFrame(id)
  }, [box, animate])

  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => {
      setAnimate(false)
      measure()
    })
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="seg" role="group" aria-label={ariaLabel} ref={wrapRef}>
      <span
        className={`seg-indicator${box ? ' is-ready' : ''}${animate ? '' : ' no-anim'}`}
        style={
          box
            ? { transform: `translateX(${box.x}px)`, width: box.w }
            : undefined
        }
        aria-hidden
      />
      {options.map(([val, label]) => (
        <button
          key={val}
          type="button"
          className={`seg-btn${value === val ? ' active' : ''}`}
          aria-pressed={value === val}
          onClick={() => onChange(val)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
