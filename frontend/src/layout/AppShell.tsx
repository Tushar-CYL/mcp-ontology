import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import {
  Bot,
  Brain,
  ChevronRight,
  Database,
  Menu,
  MessageSquare,
  PackageOpen,
  Scale,
  Sparkles,
  Waypoints,
  X,
} from 'lucide-react'
import { api } from '../api/client'
import type { StrataLayer } from '../api/types'
import { useSource } from '../context/SourceContext'
import { clearSession, readSession } from '../session'
import { cx } from '../utils/cx'

/* NVIDIA's rail, then the options this app already had. */
type NavItem = { to: string; label: string; icon: typeof Database; layer?: StrataLayer }

const NVIDIA_ITEMS: NavItem[] = [
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/data', label: 'Data', icon: Database },
]

const OUR_ITEMS: NavItem[] = [
  { to: '/tools/ontology', label: 'Ontology', icon: Sparkles },
  { to: '/tools/graph', label: 'Knowledge graph', icon: Waypoints, layer: 'graph' },
  { to: '/tools/semantic', label: 'Semantic', icon: Scale, layer: 'semantic' },
  { to: '/tools/context', label: 'Context', icon: Brain, layer: 'context' },
  { to: '/agents', label: 'Agents', icon: Bot, layer: 'agents' },
  { to: '/use', label: 'Use anywhere', icon: PackageOpen },
]

const NAV_ITEMS: NavItem[] = [...NVIDIA_ITEMS, ...OUR_ITEMS]

export function AppShell() {
  const session = readSession()
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

  // Only the layers this server offers (STRATA_LAYERS); all when it does not say.
  const on = health?.layers
  const ours = OUR_ITEMS.filter((item) => !item.layer || !on || on.includes(item.layer))
  const items = [...NVIDIA_ITEMS, ...ours]
  if (!session) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  const apiState = healthError
    ? { label: 'API unreachable', tone: 'error' as const }
    : health?.warming
      ? { label: 'Opening saved sources…', tone: 'neutral' as const }
      : health
        ? { label: 'API online', tone: 'ok' as const }
      : { label: loading ? 'Checking API' : 'API status unknown', tone: 'neutral' as const }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="topbar">
        <a className="topbar__brand" href="/tools/ontology" aria-label="EY Strata home">
          <img src="/ey-com-logo.png" alt="EY" className="topbar__logo" width={36} height={36} />
        </a>

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
          <AccountMenu email={session.email} onSignOut={() => {
            clearSession()
            void api.logout().finally(() => window.location.assign('/login'))
          }} />
        </div>
      </header>

      <div className="app-body">
        <aside
          id="sidebar"
          className={cx('sidebar', drawerOpen && 'sidebar--open')}
          aria-label="Primary navigation"
        >
          <div className="sidebar__panel">
            <button
              type="button"
              className="sidebar__close"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
            >
              <X size={18} aria-hidden="true" />
            </button>
            <nav className="sidebar__nav" aria-label="Workspace">
              {items.map((item, index) => {
                const Icon = item.icon
                const split = index === NVIDIA_ITEMS.length
                return (
                  <span key={item.to} className={cx(split && 'nav-split-wrap')}>
                    {split ? <span className="nav-split" /> : null}
                    <NavLink
                      to={item.to}
                      title={item.label}
                      className={({ isActive }) => cx('nav-item', isActive && 'nav-item--active')}
                    >
                      <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
                      <span>{item.label}</span>
                    </NavLink>
                  </span>
                )
              })}
            </nav>
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
          <main id="main" className="content" tabIndex={-1}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}

function AccountMenu({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const initial = (email.trim().charAt(0) || 'A').toUpperCase()

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="account" ref={box}>
      <button
        type="button"
        className="account__avatar"
        aria-label="User menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {initial}
      </button>
      {open ? (
        <div className="account__menu" role="menu">
          <p className="account__email">{email}</p>
          <p className="account__role">Admin</p>
          <button type="button" role="menuitem" onClick={onSignOut}>Sign out</button>
        </div>
      ) : null}
    </div>
  )
}
