import { useEffect, useRef, useState } from 'react'
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import ApiProvider from './api/ApiProvider'
import PlanningRunProvider from './planning/PlanningRunProvider'
import ComparisonPage from './pages/ComparisonPage'
import DataSource from './components/DataSource'
import HealthStatus from './components/HealthStatus'
import RoutesPage from './pages/RoutesPage'
import TaskPage from './pages/TaskPage'
import ReviewPage from './pages/ReviewPage'
import UploadPage from './pages/UploadPage'
import InspectionPage from './pages/InspectionPage'
import AssistantPage from './pages/AssistantPage'
import WorkflowGuide from './components/WorkflowGuide'
import CrewPage from './pages/CrewPage'
import AuthProvider from './auth/AuthProvider'
import { canOpen, homeFor, roleNames, useAuth } from './auth/context'

const pages = [
  {
    path: '/inspections/new',
    number: '01',
    title: 'Upload and results',
    short: 'Upload inspection',
    description: 'Start with a road photo and record its location and detection result.',
    areas: ['Image and location', 'Primary detection', 'Task or review entry'],
    next: { path: '/reviews', label: 'Go to manual review' },
  },
  {
    path: '/reviews',
    number: '02',
    title: 'Manual review',
    short: 'Manual review',
    description: 'Review pending inspections and retain the basis for each confirmation, correction and rejection.',
    areas: ['Pending review queue', 'Image and detection evidence', 'Review actions and history'],
    next: { path: '/tasks', label: 'Go to task workspace' },
  },
  {
    path: '/tasks',
    number: '03',
    title: 'Task workspace',
    short: 'Repair tasks',
    description: 'Manage accepted repair tasks with traceable sources.',
    areas: ['Task list and filters', 'Rules and repair advice', 'Task status and history'],
    next: { path: '/routes', label: 'Go to four-crew routes' },
  },
  {
    path: '/routes',
    number: '04',
    title: 'Four-crew routes',
    short: 'Four-crew routes',
    description: 'View crew availability, stop order and unassigned tasks.',
    areas: ['Crews and availability', 'Map and stop order', 'Planning and stale status'],
    next: { path: '/comparison', label: 'Go to algorithm comparison' },
  },
  {
    path: '/comparison',
    number: '05',
    title: 'Algorithm comparison',
    short: 'Algorithm comparison',
    description: 'Compare GA and Greedy plans using the same inputs and constraints.',
    areas: ['Same-run plans and sources', 'Task and time metrics', 'Differences and limitations'],
    next: { path: '/assistant', label: 'Go to route assistant' },
  },
  {
    path: '/crew',
    number: '06',
    title: 'Crew workspace',
    short: 'Crew workspace',
    description: 'View your crew route, check repair tasks and record completion.',
    areas: ['My crew route', 'Repair details', 'Completion progress'],
    next: { path: '/routes', label: 'Go to four-crew routes' },
  },
  {
    path: '/assistant',
    number: '07',
    title: 'Route assistant',
    short: 'Route assistant',
    description: 'Explain saved plans; preview crew changes before confirming them.',
    areas: ['Plan questions and citations', 'Crew change preview', 'Confirm, cancel and results'],
    next: { path: '/inspections/new', label: 'Return to upload inspection' },
  },
] as const

export default function App() {
  return (
    <AuthProvider><ApiProvider>
      <PlanningRunProvider><Workspace /></PlanningRunProvider>
    </ApiProvider></AuthProvider>
  )
}

function Workspace() {
  const auth = useAuth()!
  const account = auth.session!.user
  const home = homeFor(account.role)
  const visiblePages = pages.filter((page) => canOpen(account.role, page.path))
  const [logoutError, setLogoutError] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  async function logout() {
    if (loggingOut) return
    setLoggingOut(true); setLogoutError('')
    try { await auth.logout() }
    catch { setLogoutError('Sign-out failed. Check your connection and try again.'); setLoggingOut(false) }
  }
  const location = useLocation()
  const [mobileMenu, setMobileMenu] = useState(false)
  const currentPage = pages.find((page) => page.path === location.pathname)
  const mainRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const page = pages.find((item) => item.path === location.pathname)
    document.title = `${page?.title ?? (location.pathname.startsWith('/inspections/') ? 'Inspection result' : 'Page not found')} · RoadGuard`
    mainRef.current?.focus({ preventScroll: true })
    document.documentElement.scrollTop = 0
  }, [location.pathname])

  return (
    <div className={`app-shell refined-shell${location.pathname === '/reviews' ? ' review-shell' : ''}${location.pathname === '/crew' ? ' crew-shell' : ''}${mobileMenu ? ' menu-open' : ''}`}>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <Link className="brand" to={home} aria-label="RoadGuard Home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none"><path d="M8 25 13 7h6l5 18M12 18h8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /><path d="M16 10v3m0 9v3" stroke="currentColor" strokeWidth="2" /></svg>
          </span>
          <span>
            RoadGuard<small>Road maintenance workspace</small>
          </span>
        </Link>
        <button className="mobile-workspace-menu" aria-expanded={mobileMenu} aria-controls="workspace-navigation" onClick={() => setMobileMenu((value) => !value)}>{mobileMenu ? 'Collapse menu' : 'Menu ☰'}</button>
        <nav id="workspace-navigation" aria-label="Main navigation">
          {visiblePages.map((page, index) => (
            <div className="nav-entry" key={page.path}>
            {index === 0 && <p className="nav-label">{roleNames[account.role]} workspace</p>}
            <NavLink
              to={page.path}
              onClick={() => setMobileMenu(false)}
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              <span className="nav-number">{page.number}</span>
              {page.short}
              <span className="nav-arrow" aria-hidden="true">›</span>
            </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="scope-dot" />
          Jurong East & West<p>4 crews · Departing NUS-ISS</p><p>Group 7</p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span className="breadcrumbs">Road maintenance <span>/</span> <strong>{currentPage?.short ?? 'Inspection result'}</strong></span>
          <div className="account-controls"><span>{account.username}<small>{roleNames[account.role]}{account.crew_id ? ` · ${account.crew_id}` : ''}</small></span><button className="text-button" disabled={loggingOut} onClick={() => void logout()}>{loggingOut ? 'Signing out…' : 'Sign out'}</button></div>
        </header>
        {logoutError && <p className="account-error" role="alert">{logoutError}</p>}
        <div className="service-strip">{account.role === 'dispatcher' && <DataSource />}<HealthStatus /></div>
        <main id="main-content" ref={mainRef} tabIndex={-1}>
          {['/inspections/new', '/reviews', '/tasks', '/routes', '/comparison'].includes(location.pathname) && <details key={location.pathname} className="review-help workspace-help"><summary>{location.pathname === '/reviews' ? 'Review instructions and workflow' : 'Instructions and workflow'}</summary><WorkflowGuide path={location.pathname} /></details>}
          <Routes>
            <Route path="/" element={<Navigate to={home} replace />} />
            {pages.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={
                  !canOpen(account.role, page.path) ? <Navigate to={home} replace /> : page.path === '/assistant' ? (
                    <AssistantPage />
                  ) : page.path === '/crew' ? (
                    <CrewPage />
                  ) : page.path === '/comparison' ? (
                    <ComparisonPage />
                  ) : page.path === '/routes' ? (
                    <RoutesPage />
                  ) : page.path === '/tasks' ? (
                    <TaskPage />
                  ) : page.path === '/reviews' ? (
                    <ReviewPage />
                  ) : page.path === '/inspections/new' ? (
                    <UploadPage />
                  ) : (
                    null
                  )
                }
              />
            ))}
            <Route
              path="/inspections/:inspectionId"
              element={<InspectionPage key={location.pathname} />}
            />
            <Route
              path="*"
              element={
                <div className="not-found">
                  <p className="eyebrow">404</p>
                  <h1>Page not found</h1>
                  <p>This page is unavailable. Continue using the workspace navigation.</p>
                  <Link className="button" to={home}>
                    Return to workspace
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="page-footer">
          RoadGuard / AIS08FT<span>Singapore · Jurong</span>
        </footer>
      </div>
    </div>
  )
}
