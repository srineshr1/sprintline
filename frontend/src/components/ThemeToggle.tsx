import { useTheme, type ThemeMode } from './ThemeProvider'

/**
 * Sun / moon toggle cycling light → dark → system.
 *
 * The icon shows the theme you are *currently seeing* (resolved), and an
 * accent dot marks "following system" — so the button never lies about the
 * painted theme while still exposing the three-state preference.
 */

const NEXT_LABEL: Record<ThemeMode, string> = {
  light: 'Switch to dark theme',
  dark: 'Use system theme',
  system: 'Switch to light theme',
}

const TITLE: Record<ThemeMode, string> = {
  light: 'Theme: light',
  dark: 'Theme: dark',
  system: 'Theme: system',
}

function SunIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg
      width="17"
      height="17"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.4 14.2A8.6 8.6 0 1 1 9.8 3.6a6.9 6.9 0 0 0 10.6 10.6z" />
    </svg>
  )
}

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { mode, resolved, cycleMode } = useTheme()

  return (
    <button
      type="button"
      className={`icon-btn theme-toggle${className ? ` ${className}` : ''}`}
      onClick={cycleMode}
      aria-label={NEXT_LABEL[mode]}
      title={`${TITLE[mode]} — click to ${NEXT_LABEL[mode].toLowerCase().replace('switch to ', '').replace('use ', '')}`}
    >
      {/* key re-triggers the swap animation on every change */}
      <span key={resolved} className="theme-toggle-icon">
        {resolved === 'dark' ? <MoonIcon /> : <SunIcon />}
      </span>
      {mode === 'system' && <span className="theme-toggle-dot" aria-hidden />}
    </button>
  )
}
