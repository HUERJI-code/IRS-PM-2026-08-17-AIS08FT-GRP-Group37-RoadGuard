import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiContext, type DataMode } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel, type Model } from '../api/contracts'
import planning from '../test/planning-fixtures.json'
import workflow from '../test/task-fixtures.json'
import CrewPage from './CrewPage'

const first = workflow.completed.before.task_id
const second = 'b'.repeat(32)
const other = 'c'.repeat(32)
function workspace() {
  const { plan_id, algorithm, input_revision, is_stale, planning_start_at, depot, settings, matrix_provider, matrix_is_simulated } = plan
  return { crew: crews.crews[0], input_revision: crews.input_revision, tasks: Object.values(tasks).filter((task) => task.task_id !== other), plan: { plan_id, algorithm, input_revision, is_stale, planning_start_at, depot, settings, matrix_provider, matrix_is_simulated, crew_routes: [plan.crew_routes[0]] } }
}
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const failure = (code: string, status = 409) => reply({ code, message: 'test' }, status)
let plan: Model<'RoutePlan'>
let crews: Model<'CrewList'>
let tasks: Record<string, Model<'TaskRecord'>>
let transport: ReturnType<typeof vi.fn<Transport>>
beforeEach(() => {
  crews = parseModel('CrewList', structuredClone(planning.crews))
  crews.input_revision = 2
  tasks = {
    [first]: parseModel('TaskRecord', structuredClone(workflow.completed.before)),
    [second]: parseModel('TaskRecord', { ...workflow.completed.before, task_id: second, damage_label: 'longitudinal_crack' }),
    [other]: parseModel('TaskRecord', { ...workflow.completed.before, task_id: other, damage_label: 'pothole_deep' }),
  }
  plan = parseModel('RoutePlan', structuredClone(planning.plans.ga))
  const base = plan.crew_routes[1]
  plan.crew_routes[0] = { ...base, crew_id: 'crew-01', stops: [
    { ...base.stops[0], sequence: 2, task_id: second },
    { ...base.stops[0], sequence: 1, task_id: first },
  ] }
  plan.crew_routes[1] = { ...base, stops: [{ ...base.stops[0], task_id: other }] }
  plan.metrics.assigned_task_count = 3
  parseModel('RoutePlan', plan)
  transport = vi.fn<Transport>().mockImplementation(async (url, init) => {
    if (url === '/api/v1/crew/workspace') return reply(workspace())
    if (url.includes('/route-plans/latest')) return reply({ ...plan, algorithm: url.includes('greedy') ? 'greedy' : 'ga' })
    const id = url.split('/').at(-1)!
    if (url.startsWith('/api/v1/tasks/') && tasks[id]) {
      if (init.method === 'PATCH') {
        tasks[id] = { ...tasks[id], status: 'completed', record_version: tasks[id].record_version + 1 }
        crews.input_revision += 1
        return reply({ ...workflow.completed.response, task: tasks[id], input_revision: crews.input_revision })
      }
      return reply(tasks[id])
    }
    return failure('not_found', 404)
  })
})
afterEach(() => vi.unstubAllGlobals())
function mount(path = '/crew?crew=crew-01', mode: DataMode = 'live') {
  return render(<ApiContext.Provider value={{ api: createApiClient(transport), mode, setMode: vi.fn(), imageUrl: (url) => url }}>
    <MemoryRouter initialEntries={[path]}><StrictMode><CrewPage /></StrictMode></MemoryRouter>
  </ApiContext.Provider>)
}
const patches = () => transport.mock.calls.filter(([, init]) => init.method === 'PATCH')
const current = () => screen.getByRole('region', { name: '当前维修任务' })
const loaded = () => screen.findByRole('button', { name: '✓ 标记为完成' })
it('opens the route from the task overview without changing or completing a task', async () => {
  mount()
  await loaded()
  const route = screen.getByRole('region', { name: '本队停靠顺序' })
  const scroll = vi.fn()
  Object.defineProperty(route, 'scrollIntoView', { value: scroll })
  await userEvent.click(screen.getByRole('button', { name: '查看 2 站路线 ↓' }))
  expect(route).toHaveFocus()
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: 'start', behavior: 'instant' })
  expect(patches()).toHaveLength(0)
  expect(within(current()).getByRole('heading', { name: '坑洞' })).toBeVisible()
})

async function confirm() {
  await userEvent.click(await loaded())
  await userEvent.click(screen.getByRole('button', { name: '确认完成' }))
}

it('reads only the selected crew tasks in sequence, with a crew-scoped map and no writes', async () => {
  mount()
  await loaded()
  expect(within(current()).getByRole('heading', { name: '坑洞' })).toBeVisible()
  const stops = within(screen.getByRole('region', { name: '本队停靠顺序' })).getAllByRole('button')
  expect(stops.map((item) => item.getAttribute('aria-label'))).toEqual(['第 1 站 坑洞 待完成', '第 2 站 纵向裂缝 待完成'])
  expect(transport.mock.calls.some(([url]) => url.endsWith(other))).toBe(false)
  await userEvent.click(screen.getByText('查看本队路线示意图'))
  expect(screen.getByRole('img', { name: 'crew-01 路线顺序示意图，北朝上' })).toBeVisible()
  expect(patches()).toHaveLength(0)
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /调度总览|完整任务/ })).not.toBeInTheDocument()
})

it('requires confirmation, saves versioned completion, keeps history progress and does not replan', async () => {
  mount()
  await userEvent.click(await loaded())
  expect(patches()).toHaveLength(0)
  await userEvent.click(screen.getByRole('button', { name: '暂不提交' }))
  expect(patches()).toHaveLength(0)
  await confirm()
  expect(await screen.findByText(/完成状态已保存/)).toBeVisible()
  expect(JSON.parse(patches()[0][1].body as string)).toEqual({ expected_version: 1, status: 'completed', request_id: expect.any(String) })
  expect(patches()[0][0]).toBe(`/api/v1/tasks/${first}`)
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '1')
  expect(screen.getByText(/路线快照已过期/)).toBeVisible()
  expect(transport.mock.calls.some(([, init]) => init.method === 'POST')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: '查看下一项待完成任务 →' }))
  expect(within(current()).getByRole('heading', { name: '纵向裂缝' })).toBeVisible()
  expect(await loaded()).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '刷新工作台' }))
  await loaded()
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '1')
  expect(screen.getByRole('button', { name: '第 1 站 坑洞 已完成' })).toBeVisible()
})

it('retains identical request after uncertain network result and blocks changing crew or task', async () => {
  const base = transport.getMockImplementation()!
  let uncertain = true
  transport.mockImplementation((url, init) => {
    if (init.method === 'PATCH' && uncertain) { uncertain = false; return Promise.reject(new TypeError('lost reply')) }
    return base(url, init)
  })
  mount()
  await confirm()
  expect(await screen.findByText(/提交结果尚不确定/)).toBeVisible()
  expect(screen.getByRole('button', { name: '刷新工作台' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '第 2 站 纵向裂缝 待完成' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '用原请求重试' }))
  await screen.findByText(/完成状态已保存/)
  expect(patches()).toHaveLength(2)
  expect(patches()[0][1].body).toBe(patches()[1][1].body)
  expect(screen.getByRole('button', { name: '刷新工作台' })).toBeEnabled()
})

it('blocks duplicate submission while a request is pending', async () => {
  let resolve!: (response: Response) => void
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => init.method === 'PATCH' ? new Promise((done) => { resolve = done }) : base(url, init))
  mount()
  await loaded()
  await userEvent.click(screen.getByRole('button', { name: '✓ 标记为完成' }))
  const button = screen.getByRole('button', { name: '确认完成' })
  fireEvent.click(button); fireEvent.click(button)
  expect(patches()).toHaveLength(1)
  expect(screen.getByRole('button', { name: '正在提交…' })).toBeDisabled()
  resolve(reply(workflow.completed.response))
  await screen.findByText(/完成状态已保存/)
})

it('requires rereading a conflicted record before a new completion request', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => init.method === 'PATCH' ? Promise.resolve(failure('stale_record_version')) : base(url, init))
  mount()
  await confirm()
  expect(await screen.findByText(/任务已被修改，请重新读取/)).toBeVisible()
  expect(screen.getByRole('button', { name: '确认完成' })).toBeDisabled()
  tasks[first] = { ...tasks[first], status: 'completed', record_version: 2 }
  await userEvent.click(screen.getByRole('button', { name: '重新读取任务状态' }))
  await screen.findByRole('button', { name: '查看下一项待完成任务 →' })
  expect(screen.queryByRole('button', { name: '✓ 标记为完成' })).not.toBeInTheDocument()
  expect(patches()).toHaveLength(1)
})

it('does not offer completion for cancelled tasks or mark missing records as completed', async () => {
  tasks[first].status = 'cancelled'
  delete tasks[second]
  mount()
  await screen.findByText('已完成 0 / 2')
  expect(screen.getByText('待完成 0 · 已取消 1 · 未知 1')).toBeVisible()
  expect(screen.queryByRole('button', { name: '✓ 标记为完成' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '第 2 站 任务读取失败 状态未知' }))
  expect(within(current()).getByRole('alert')).toHaveTextContent('记录不存在')
  expect(patches()).toHaveLength(0)
})

it.each(['normal', 'empty'] as const)('keeps completion disabled for explicit %s mock mode', async (mode) => {
  mount('/crew?crew=crew-01', mode)
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/当前为只读模拟数据/)).toBeVisible()
  expect(patches()).toHaveLength(0)
})

it('blocks stopped crews and ignores tampered crew or algorithm URL parameters', async () => {
  crews.crews[0].available = false
  mount('/crew?crew=crew-04&algorithm=greedy')
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/该队伍已停用/)).toBeVisible()
  expect(screen.getByText('crew-01 / GA')).toBeVisible()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

it('blocks completion when a refreshed workspace has a different route', async () => {
  mount(); await loaded()
  plan.plan_id = 'plan-' + 'a'.repeat(32)
  await userEvent.click(screen.getByRole('button', { name: '重新读取任务状态' }))
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/调度已更新路线/)).toBeVisible()
})

it('distinguishes an idle route, no saved plan, and an unavailable service', async () => {
  const base = transport.getMockImplementation()!
  plan.crew_routes[0].stops = []
  const idle = mount()
  expect(await screen.findByRole('heading', { name: '本方案没有安排任务' })).toBeVisible()
  idle.unmount()
  transport.mockImplementation((url, init) => url.endsWith('/crew/workspace') ? Promise.resolve(reply({ ...workspace(), plan: null, tasks: [] })) : base(url, init))
  const empty = mount()
  expect(await screen.findByRole('heading', { name: '还没有路线安排' })).toBeVisible()
  expect(screen.queryByRole('link', { name: '前往四队路线' })).not.toBeInTheDocument()
  empty.unmount()
  transport.mockImplementation(async () => failure('database_unavailable', 503))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('数据库暂不可用')
  expect(screen.queryByText('还没有路线安排')).not.toBeInTheDocument()
})

it('flags stale plans and changed task coordinates while preserving the saved map', async () => {
  crews.input_revision = 3
  tasks[first].latitude = 1.35
  mount()
  await loaded()
  expect(screen.getByText(/路线快照已过期/)).toBeVisible()
  expect(screen.getByText(/任务位置、工时或优先级与路线快照不同/)).toBeVisible()
  expect(screen.getByText('1.350000, 103.706000')).toBeVisible()
  expect(screen.getByText('crew-01 / GA')).toBeVisible()
})

it('focuses selected task on mobile and keeps focus stable after rereading', async () => {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))
  const scroll = vi.fn()
  const previous = HTMLElement.prototype.scrollIntoView
  HTMLElement.prototype.scrollIntoView = scroll
  try {
    mount()
    await loaded()
    expect(scroll).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: '第 2 站 纵向裂缝 待完成' }))
    expect(current()).toHaveFocus()
    expect(scroll).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: '第 2 站 纵向裂缝 待完成' }))
    expect(scroll).toHaveBeenCalledTimes(2)
    await userEvent.click(screen.getByRole('button', { name: '重新读取任务状态' }))
    await loaded()
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(2))
  } finally { HTMLElement.prototype.scrollIntoView = previous }
})
