/**
 * FLIP helpers for the sprint board's cross-column card transfer.
 *
 * Why a clone instead of animating the card itself: `.board-cards` is a
 * scroll container (`overflow-y: auto`), which makes it a clipping box. A card
 * translated from one column toward another would be cut off at the column
 * edge. So we fly a fixed-position clone above the board and keep the real
 * (already re-parented) card invisible until the flight lands.
 *
 * Siblings that shift *within* a column are animated in place — they never
 * leave their list, so clipping isn't a concern there.
 */

export const FLIGHT_MS = 400
export const SHIFT_MS = 240

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** Snapshot viewport rects for every currently-mounted card. */
export function captureRects(
  nodes: Map<number, HTMLElement>,
): Map<number, DOMRect> {
  const out = new Map<number, DOMRect>()
  for (const [id, el] of nodes) {
    if (el.isConnected) out.set(id, el.getBoundingClientRect())
  }
  return out
}

/**
 * Detached copy of a card, pinned in viewport coordinates at `rect`.
 * Appended to <body> so no ancestor can clip it.
 */
export function makeFlightClone(el: HTMLElement, rect: DOMRect): HTMLElement {
  const clone = el.cloneNode(true) as HTMLElement
  clone.classList.add('is-flying')
  clone.classList.remove('is-landed', 'is-pending')
  clone.setAttribute('aria-hidden', 'true')
  clone.style.position = 'fixed'
  clone.style.left = `${rect.left}px`
  clone.style.top = `${rect.top}px`
  clone.style.width = `${rect.width}px`
  clone.style.height = `${rect.height}px`
  clone.style.margin = '0'
  clone.style.pointerEvents = 'none'
  clone.style.listStyle = 'none'
  document.body.appendChild(clone)
  return clone
}

/**
 * Fly the clone from its pinned position to `to`, with a slight lift at the
 * apex so it reads as picked-up-and-placed rather than slid.
 */
export function animateFlight(
  clone: HTMLElement,
  from: DOMRect,
  to: DOMRect,
  duration = FLIGHT_MS,
): Promise<void> {
  const dx = to.left - from.left
  const dy = to.top - from.top

  const anim = clone.animate(
    [
      { transform: 'translate3d(0, 0, 0) scale(1)', offset: 0 },
      {
        transform: `translate3d(${dx * 0.5}px, ${dy * 0.5 - 6}px, 0) scale(1.045)`,
        offset: 0.5,
      },
      { transform: `translate3d(${dx}px, ${dy}px, 0) scale(1)`, offset: 1 },
    ],
    {
      duration,
      easing: 'cubic-bezier(0.22, 0.9, 0.24, 1)',
      fill: 'forwards',
    },
  )

  return anim.finished.then(
    () => undefined,
    () => undefined, // cancelled mid-flight — treat as done
  )
}

/** Slide an element from a previous position back to its current one. */
export function animateShift(
  el: HTMLElement,
  dx: number,
  dy: number,
  duration = SHIFT_MS,
): void {
  el.animate(
    [
      { transform: `translate3d(${dx}px, ${dy}px, 0)` },
      { transform: 'translate3d(0, 0, 0)' },
    ],
    { duration, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' },
  )
}
