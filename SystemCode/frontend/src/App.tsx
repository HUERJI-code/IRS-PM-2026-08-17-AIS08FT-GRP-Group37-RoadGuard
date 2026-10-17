import { useEffect, useRef } from 'react'
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
    path: '/assistant',
    number: '06',
    title: '路线助手',
    short: '路线助手',
    description: '基于已保存方案解释安排，队伍调整须先预览再确认。',
    areas: ['方案问答与引用', '队伍调整预览', '确认、取消与结果'],
    next: { path: '/inspections/new', label: '返回上传巡检' },
  },
] as const

export default function App() {
  return (
    <ApiProvider>
      <PlanningRunProvider><Workspace /></PlanningRunProvider>
    </ApiProvider>
  )
}

function Workspace() {
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const page = pages.find((item) => item.path === location.pathname)
    document.title = `${page?.title ?? (location.pathname.startsWith('/inspections/') ? '巡检结果' : '页面不存在')} · RoadGuard`
    mainRef.current?.focus({ preventScroll: true })
  }, [location.pathname])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/tasks" aria-label="RoadGuard 首页">
          <span className="brand-mark" aria-hidden="true">
            R<span>↗</span>
          </span>
          <span>
            RoadGuard<small>道路维护工作台</small>
          </span>
        </Link>
        <p className="nav-label">工作区</p>
        <nav aria-label="主要导航">
          {pages.map((page) => (
            <NavLink
              key={page.path}
              to={page.path}
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              <span className="nav-number">{page.number}</span>
              {page.short}
              <span className="nav-arrow" aria-hidden="true">
                ↗
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="scope-dot" />
          Jurong East & West<p>课程模拟项目 · Group 7</p>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>维护运营 / 工作台</span>
          <span className="foundation-label">巡检、审核与任务已接入</span>
        </header>
        <DataSource />
        <HealthStatus />
        <main id="main-content" ref={mainRef} tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Navigate to="/tasks" replace />} />
            {pages.map((page) => (
              <Route
                key={page.path}
                path={page.path}
                element={
                  page.path === '/comparison' ? (
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
                    <WorkspacePage {...page} />
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
                  <Link className="button" to="/tasks">
                    返回任务工作区
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="page-footer">
          RoadGuard / AIS08FT<span>新加坡 · 课程模拟场景</span>
        </footer>
      </div>
    </div>
  )
}
