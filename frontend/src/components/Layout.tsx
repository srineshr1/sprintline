import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ToastProvider } from './Toast'

export function Layout() {
  const { pathname } = useLocation()
  const projectsActive =
    pathname === '/' || pathname.startsWith('/projects')

  const [navOpen, setNavOpen] = useState(false)

  // Close drawer when route changes
  useEffect(() => {
    setNavOpen(false)
  }, [pathname])

  // Escape closes mobile nav
  useEffect(() => {
    if (!navOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setNavOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navOpen])

  return (
    <ToastProvider>
      <div className={`app-shell${navOpen ? ' nav-open' : ''}`}>
        {/* Backdrop for mobile drawer */}
        <div
          className={`nav-backdrop${navOpen ? ' is-open' : ''}`}
          onClick={() => setNavOpen(false)}
          aria-hidden={!navOpen}
        />

        <aside className={`sidebar${navOpen ? ' is-open' : ''}`} id="app-sidebar">
          <div className="sidebar-top">
            <NavLink
              to="/"
              className="sidebar-brand"
              end
              onClick={() => setNavOpen(false)}
            >
              <span className="sidebar-mark">S</span>
              Sprintline
            </NavLink>
            <button
              type="button"
              className="icon-btn sidebar-close"
              aria-label="Close menu"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setNavOpen(false)
              }}
            >
              <span className="icon-x" aria-hidden />
            </button>
          </div>

          <nav style={{ display: 'grid', gap: 2 }}>
            <NavLink
              to="/"
              end
              className={() => `nav-item${projectsActive ? ' active' : ''}`}
              aria-current={projectsActive ? 'page' : undefined}
              onClick={() => setNavOpen(false)}
            >
              Projects
            </NavLink>
            <button
              type="button"
              className="nav-item"
              disabled
              title="Coming soon"
            >
              Archive
            </button>
          </nav>

          <div className="sidebar-foot">
            <div className="user-chip">
              <span className="user-avatar">Y</span>
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text)' }}>You</div>
                <div style={{ fontSize: 11 }}>demo</div>
              </div>
            </div>
          </div>
        </aside>

        <div className="main-area">
          <header className="topbar">
            <button
              type="button"
              className="icon-btn hamburger"
              aria-label="Open menu"
              aria-expanded={navOpen}
              aria-controls="app-sidebar"
              onClick={() => setNavOpen(true)}
            >
              <span className="hamburger-lines" aria-hidden>
                <span />
                <span />
                <span />
              </span>
            </button>
            <NavLink to="/" className="topbar-brand" end>
              <span className="sidebar-mark">S</span>
              <span>Sprintline</span>
            </NavLink>
          </header>
          <Outlet />
        </div>
      </div>
    </ToastProvider>
  )
}
