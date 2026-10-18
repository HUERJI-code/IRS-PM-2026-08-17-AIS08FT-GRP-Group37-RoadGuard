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
import WorkspacePage from './pages/WorkspacePage'
import WorkflowGuide from './components/WorkflowGuide'
import CrewPage from './pages/CrewPage'
import AuthProvider from './auth/AuthProvider'
import { canOpen, homeFor, roleNames, useAuth } from './auth/context'

const pages = [
  {
    path: '/inspections/new',
    number: '01',
    title: '上传与结果',
    short: '上传巡检',
    description: '从一张道路照片开始，记录位置与检测结果。',
    areas: ['图片与位置', '主检测结果', '任务或审核入口'],
    next: { path: '/reviews', label: '前往人工审核' },
  },
  {
    path: '/reviews',
    number: '02',
    title: '人工审核',
    short: '人工审核',
    description: '复核待审巡检，保留每一次确认、纠正与驳回的依据。',
    areas: ['待审核队列', '图片与检测依据', '审核操作与记录'],
    next: { path: '/tasks', label: '前往任务工作区' },
  },
  {
    path: '/tasks',
    number: '03',
    title: '任务工作区',
    short: '维修任务',
    description: '汇集已接受的维修任务，让每项安排都有来源可查。',
    areas: ['任务列表与筛选', '规则与维修建议', '任务状态与历史'],
    next: { path: '/routes', label: '前往四队路线' },
  },
  {
    path: '/routes',
    number: '04',
    title: '四队路线',
    short: '四队路线',
    description: '查看工程队的可用状态、访问顺序和未分配任务。',
    areas: ['队伍与可用状态', '地图与路线顺序', '规划与过期状态'],
    next: { path: '/comparison', label: '前往算法比较' },
  },
  {
    path: '/comparison',
    number: '05',
    title: '算法比较',
    short: '算法比较',
    description: '在相同输入与约束下，比较 GA 和 Greedy 的规划结果。',
    areas: ['同轮方案与来源', '任务与时间指标', '差异与适用限制'],
    next: { path: '/assistant', label: '前往路线助手' },
  },
  {
    path: '/crew',
    number: '06',
    title: '施工队工作台',
    short: '施工队工作台',
    description: '查看本队路线，核对维修任务并记录完成。',
    areas: ['本队路线', '维修详情', '完成进度'],
    next: { path: '/routes', label: '前往四队路线' },
  },
  {
    path: '/assistant',
    number: '07',
    title: '路线助手',
    short: '路线助手',
    description: '基于已保存方案解释安排，队伍调整须先预览再确认。',
    areas: ['方案问答与引用', '队伍调整预览', '确认、取消与结果'],
    next: { path: '/inspections/new', label: '返回上传巡检' },
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
    catch { setLogoutError('退出未成功，请检查连接后重试。'); setLoggingOut(false) }
  }
  const location = useLocation()
  const [mobileMenu, setMobileMenu] = useState(false)
  const currentPage = pages.find((page) => page.path === location.pathname)
  const mainRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const page = pages.find((item) => item.path === location.pathname)
    document.title = `${page?.title ?? (location.pathname.startsWith('/inspections/') ? '巡检结果' : '页面不存在')} · RoadGuard`
    mainRef.current?.focus({ preventScroll: true })
    document.documentElement.scrollTop = 0
  }, [location.pathname])

  return (
    <div className={`app-shell refined-shell${location.pathname === '/reviews' ? ' review-shell' : ''}${location.pathname === '/crew' ? ' crew-shell' : ''}${mobileMenu ? ' menu-open' : ''}`}>
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <Link className="brand" to={home} aria-label="RoadGuard 首页">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none"><path d="M8 25 13 7h6l5 18M12 18h8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /><path d="M16 10v3m0 9v3" stroke="currentColor" strokeWidth="2" /></svg>
          </span>
          <span>
            RoadGuard<small>道路维护工作台</small>
          </span>
        </Link>
        <button className="mobile-workspace-menu" aria-expanded={mobileMenu} aria-controls="workspace-navigation" onClick={() => setMobileMenu((value) => !value)}>{mobileMenu ? '收起菜单' : '菜单 ☰'}</button>
        <nav id="workspace-navigation" aria-label="主要导航">
          {visiblePages.map((page, index) => (
            <div className="nav-entry" key={page.path}>
            {index === 0 && <p className="nav-label">{roleNames[account.role]}工作区</p>}
            <NavLink
              to={page.path}
              onClick={() => setMobileMenu(false)}
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              <span className="nav-number">{page.number}</span>
              {page.short}
              {page.path === '/assistant' ? <span className="nav-soon">开发中</span> : <span className="nav-arrow" aria-hidden="true">›</span>}
            </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="scope-dot" />
          Jurong East & West<p>4 支工程队 · NUS-ISS 出发</p><p>Group 7</p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span className="breadcrumbs">道路维护 <span>/</span> <strong>{currentPage?.short ?? '巡检结果'}</strong></span>
          <div className="account-controls"><span>{account.display_name}<small>{roleNames[account.role]}{account.crew_id ? ` · ${account.crew_id}` : ''}</small></span><button className="text-button" disabled={loggingOut} onClick={() => void logout()}>{loggingOut ? '退出中…' : '退出登录'}</button></div>
        </header>
        {logoutError && <p className="account-error" role="alert">{logoutError}</p>}
        <div className="service-strip">{account.role === 'dispatcher' && <DataSource />}<HealthStatus /></div>
        <main id="main-content" ref={mainRef} tabIndex={-1}>
          {['/inspections/new', '/reviews', '/tasks', '/routes', '/comparison'].includes(location.pathname) && <details key={location.pathname} className="review-help workspace-help"><summary>{location.pathname === '/reviews' ? '审核说明与流程' : '操作说明与流程'}</summary><WorkflowGuide path={location.pathname} /></details>}
          <Routes>
            <Route path="/" element={<Navigate to={home} replace />} />
            {pages.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={
                  !canOpen(account.role, page.path) ? <Navigate to={home} replace /> : page.path === '/crew' ? (
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
                    <WorkspacePage {...page} next={{ path: home, label: '返回工作区' }} />
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
                  <h1>页面不存在</h1>
                  <p>这个地址尚未提供页面，请从工作区导航继续。</p>
                  <Link className="button" to={home}>
                    返回工作区
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="page-footer">
          RoadGuard / AIS08FT<span>新加坡 · Jurong</span>
        </footer>
      </div>
    </div>
  )
}
