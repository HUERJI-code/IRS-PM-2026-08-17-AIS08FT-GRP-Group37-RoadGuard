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
const current = () => screen.getByRole('region', { name: 'Current repair task' })
const loaded = () => screen.findByRole('button', { name: '✓ Mark as complete' })
it('opens the route from the task overview without changing or completing a task', async () => {
  mount()
  await loaded()
  const route = screen.getByRole('region', { name: 'Crew stop order' })
  const scroll = vi.fn()
  Object.defineProperty(route, 'scrollIntoView', { value: scroll })
  await userEvent.click(screen.getByRole('button', { name: 'View 2-stop route ↓' }))
  expect(route).toHaveFocus()
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: 'start', behavior: 'instant' })
  expect(patches()).toHaveLength(0)
  expect(within(current()).getByRole('heading', { name: 'Pothole' })).toBeVisible()
})

async function confirm() {
  await userEvent.click(await loaded())
  await userEvent.click(screen.getByRole('button', { name: 'Confirm completion' }))
}

it('reads only the selected crew tasks in sequence, with a crew-scoped map and no writes', async () => {
  mount()
  await loaded()
  expect(within(current()).getByRole('heading', { name: 'Pothole' })).toBeVisible()
  const stops = within(screen.getByRole('region', { name: 'Crew stop order' })).getAllByRole('button')
  expect(stops.map((item) => item.getAttribute('aria-label'))).toEqual(['Stop 1 Pothole Pending', 'Stop 2 Longitudinal crack Pending'])
  expect(transport.mock.calls.some(([url]) => url.endsWith(other))).toBe(false)
  await userEvent.click(screen.getByText('View crew route diagram'))
  expect(screen.getByRole('img', { name: 'crew-01 route order diagram, north up' })).toBeVisible()
  expect(patches()).toHaveLength(0)
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Dispatch overview|Full task/ })).not.toBeInTheDocument()
})

it('requires confirmation, saves versioned completion, keeps history progress and does not replan', async () => {
  mount()
  await userEvent.click(await loaded())
  expect(patches()).toHaveLength(0)
  await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
  expect(patches()).toHaveLength(0)
  await confirm()
  expect(await screen.findByText(/Completion saved/)).toBeVisible()
  expect(JSON.parse(patches()[0][1].body as string)).toEqual({ expected_version: 1, status: 'completed', request_id: expect.any(String) })
  expect(patches()[0][0]).toBe(`/api/v1/tasks/${first}`)
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '1')
  expect(screen.getByText(/The route snapshot is stale/)).toBeVisible()
  expect(transport.mock.calls.some(([, init]) => init.method === 'POST')).toBe(false)
  await userEvent.click(screen.getByRole('button', { name: 'View next pending task →' }))
  expect(within(current()).getByRole('heading', { name: 'Longitudinal crack' })).toBeVisible()
  expect(await loaded()).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: 'Refresh workspace' }))
  await loaded()
  expect(screen.getByRole('progressbar')).toHaveAttribute('value', '1')
  expect(screen.getByRole('button', { name: 'Stop 1 Pothole Completed' })).toBeVisible()
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
  expect(await screen.findByText(/The submission outcome is uncertain/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Refresh workspace' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Stop 2 Longitudinal crack Pending' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Retry original request' }))
  await screen.findByText(/Completion saved/)
  expect(patches()).toHaveLength(2)
  expect(patches()[0][1].body).toBe(patches()[1][1].body)
  expect(screen.getByRole('button', { name: 'Refresh workspace' })).toBeEnabled()
})

it('blocks duplicate submission while a request is pending', async () => {
  let resolve!: (response: Response) => void
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => init.method === 'PATCH' ? new Promise((done) => { resolve = done }) : base(url, init))
  mount()
  await loaded()
  await userEvent.click(screen.getByRole('button', { name: '✓ Mark as complete' }))
  const button = screen.getByRole('button', { name: 'Confirm completion' })
  fireEvent.click(button); fireEvent.click(button)
  expect(patches()).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Submitting…' })).toBeDisabled()
  resolve(reply(workflow.completed.response))
  await screen.findByText(/Completion saved/)
})

it('requires rereading a conflicted record before a new completion request', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => init.method === 'PATCH' ? Promise.resolve(failure('stale_record_version')) : base(url, init))
  mount()
  await confirm()
  expect(await screen.findByText(/The task has changed. Reload/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Confirm completion' })).toBeDisabled()
  tasks[first] = { ...tasks[first], status: 'completed', record_version: 2 }
  await userEvent.click(screen.getByRole('button', { name: 'Reload task status' }))
  await screen.findByRole('button', { name: 'View next pending task →' })
  expect(screen.queryByRole('button', { name: '✓ Mark as complete' })).not.toBeInTheDocument()
  expect(patches()).toHaveLength(1)
})

it('does not offer completion for cancelled tasks or mark missing records as completed', async () => {
  tasks[first].status = 'cancelled'
  delete tasks[second]
  mount()
  await screen.findByText('Completed 0 / 2')
  expect(screen.getByText('Pending 0 · Cancelled 1 · Unknown 1')).toBeVisible()
  expect(screen.queryByRole('button', { name: '✓ Mark as complete' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Stop 2 Task loading failed Status unknown' }))
  expect(within(current()).getByRole('alert')).toHaveTextContent('This record is unavailable')
  expect(patches()).toHaveLength(0)
})

it.each(['normal', 'empty'] as const)('keeps completion disabled for explicit %s mock mode', async (mode) => {
  mount('/crew?crew=crew-01', mode)
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/This is read-only mock data/)).toBeVisible()
  expect(patches()).toHaveLength(0)
})

it('blocks stopped crews and ignores tampered crew or algorithm URL parameters', async () => {
  crews.crews[0].available = false
  mount('/crew?crew=crew-04&algorithm=greedy')
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/This crew is unavailable/)).toBeVisible()
  expect(screen.getByText('crew-01 / GA')).toBeVisible()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

it('blocks completion when a refreshed workspace has a different route', async () => {
  mount(); await loaded()
  plan.plan_id = 'plan-' + 'a'.repeat(32)
  await userEvent.click(screen.getByRole('button', { name: 'Reload task status' }))
  expect(await loaded()).toBeDisabled()
  expect(screen.getByText(/Dispatch has updated the route/)).toBeVisible()
})

it('distinguishes an idle route, no saved plan, and an unavailable service', async () => {
  const base = transport.getMockImplementation()!
  plan.crew_routes[0].stops = []
  const idle = mount()
  expect(await screen.findByRole('heading', { name: 'No tasks assigned in this plan' })).toBeVisible()
  idle.unmount()
  transport.mockImplementation((url, init) => url.endsWith('/crew/workspace') ? Promise.resolve(reply({ ...workspace(), plan: null, tasks: [] })) : base(url, init))
  const empty = mount()
  expect(await screen.findByRole('heading', { name: 'No route assigned yet' })).toBeVisible()
  expect(screen.queryByRole('link', { name: 'Go to four-crew routes' })).not.toBeInTheDocument()
  empty.unmount()
  transport.mockImplementation(async () => failure('database_unavailable', 503))
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('The database is temporarily unavailable')
  expect(screen.queryByText('No route assigned yet')).not.toBeInTheDocument()
})

it('flags stale plans and changed task coordinates while preserving the saved map', async () => {
  crews.input_revision = 3
  tasks[first].latitude = 1.35
  mount()
  await loaded()
  expect(screen.getByText(/The route snapshot is stale/)).toBeVisible()
  expect(screen.getByText(/Task location, duration or priority differs from the route snapshot/)).toBeVisible()
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
    await userEvent.click(screen.getByRole('button', { name: 'Stop 2 Longitudinal crack Pending' }))
    expect(current()).toHaveFocus()
    expect(scroll).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Stop 2 Longitudinal crack Pending' }))
    expect(scroll).toHaveBeenCalledTimes(2)
    await userEvent.click(screen.getByRole('button', { name: 'Reload task status' }))
    await loaded()
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(2))
  } finally { HTMLElement.prototype.scrollIntoView = previous }
})
it('explains that a revoked stale route requires dispatcher recalculation before completion', async () => {
  transport.mockImplementation(async () => {
    const data = workspace()
    return reply({ ...data, tasks: [], plan: { ...data.plan, is_stale: true, crew_routes: [] } })
  })
  mount()
  expect(await screen.findByText(/Your saved route is stale and no longer available/)).toHaveTextContent('Ask the dispatcher to recalculate')
  expect(screen.queryByRole('region', { name: 'Current repair task' })).not.toBeInTheDocument()
  expect(patches()).toHaveLength(0)
})
