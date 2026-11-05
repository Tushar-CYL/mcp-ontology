import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bot,
  ChartColumn,
  ChevronRight,
  FileText,
  Sparkles,
  Layers,
  Menu,
  Network,
  Plug,
  X,
} from 'lucide-react'
import { useSource } from '../context/SourceContext'
import { cx } from '../utils/cx'

/* Grouped by who uses it: data teams govern, BI teams define metrics,
   agents consume the packed context. */
type NavItem = { to: string; label: string; icon: typeof Plug }

const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  { label: 'Connect', items: [{ to: '/onboarding', label: 'Data sources', icon: Plug }] },
  {
    label: 'Accelerators',
    items: [{ to: '/tools/ontology', label: 'Ontology', icon: Sparkles }],
  },
  {
    label: 'The four layers',
    items: [
      { to: '/layers/ontology', label: '1 Ontology', icon: Layers },
      { to: '/layers/graph', label: '2 Knowledge graph', icon: Network },
      { to: '/layers/semantic', label: '3 Semantic', icon: ChartColumn },
      { to: '/layers/context', label: '4 Context', icon: FileText },
    ],
  },
  { label: 'Use them', items: [{ to: '/agents', label: 'Agents', icon: Bot }] },
]

const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items)

export function AppShell() {
  const { health, healthError, loading } = useSource()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()
  const currentLabel = useMemo(() => {
    const item = NAV_ITEMS.find((nav) => location.pathname.startsWith(nav.to))
    return item?.label ?? 'Workspace'
  }, [location.pathname])

  useEffect(() => {
    setDrawerOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!drawerOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [drawerOpen])

  const apiState = healthError
    ? { label: 'API unreachable', tone: 'rose' as const }
    : health?.warming
      ? { label: 'Opening saved sources…', tone: 'neutral' as const }
      : health
        ? { label: 'API online', tone: 'teal' as const }
      : { label: loading ? 'Checking API' : 'API status unknown', tone: 'neutral' as const }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside
        id="sidebar"
        className={cx('sidebar', drawerOpen && 'sidebar--open')}
        aria-label="Primary navigation"
      >
        <div className="sidebar__brand">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <div className="brand-text">
            <p className="brand-name">Strata</p>
            <p className="brand-tagline">Trusted context for every agent</p>
          </div>
          <button
            type="button"
            className="sidebar__close"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <nav className="sidebar__nav" aria-label="Workspace">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="nav-group">
              <p className="nav-group-label">{group.label}</p>
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => cx('nav-item', isActive && 'nav-item--active')}
                  >
                    <Icon size={17} aria-hidden="true" />
                    <span>{item.label}</span>
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="sidebar__note">
            <p className="sidebar__note-title">Your data stays yours</p>
            <p className="sidebar__note-text">
              No API key in the browser. The AI sees column names and a few sample values, never whole tables.
            </p>
          </div>
          <p className="sidebar__version">Strata · v1.0</p>
        </div>
      </aside>

      {drawerOpen ? (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setDrawerOpen(false)}
        />
      ) : null}

      <div className="app-main">
        <header className="topbar">
          <button
            type="button"
            className="topbar__menu"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            aria-controls="sidebar"
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={18} aria-hidden="true" />
          </button>

          <div className="topbar__crumbs" aria-label="Breadcrumb">
            <span className="topbar__crumb-label">Workspace</span>
            <ChevronRight size={13} aria-hidden="true" />
            <span className="topbar__crumb-current">{currentLabel}</span>
          </div>

          <div className="topbar__right">
            <span
              className={cx('api-state', `api-state--${apiState.tone}`)}
              role="status"
              title={healthError instanceof Error ? healthError.message : undefined}
            >
              <span className="api-state__dot" aria-hidden="true" />
              {apiState.label}
            </span>
          </div>
        </header>

        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
