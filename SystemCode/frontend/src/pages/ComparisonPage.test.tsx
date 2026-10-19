import { StrictMode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiContext, type DataMode } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel } from '../api/contracts'
import fixtures from '../test/planning-fixtures.json'
import { RunContext, type RunReceipt } from '../planning/runContext'
import ComparisonPage from './ComparisonPage'

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const receipt = () => parseModel('RecalculationResult', fixtures.calculation)
let transport: ReturnType<typeof vi.fn<Transport>>
beforeEach(() => {
  transport = vi.fn<Transport>().mockImplementation(async (url) => {
    if (url.endsWith('/health')) return reply({ status: 'ok', database: 'ok', api_version: 'v1', input_revision: fixtures.calculation.input_revision })
    return reply(url.includes('greedy') || url.endsWith(fixtures.plans.greedy.plan_id) ? fixtures.plans.greedy : fixtures.plans.ga)
  })
})
function mount(run: RunReceipt | null = receipt(), mode: DataMode = 'live') {
  return render(<ApiContext.Provider value={{ api: createApiClient(transport), mode, setMode: vi.fn(), imageUrl: (p) => p }}><RunContext.Provider value={{ run, rememberRun: vi.fn() }}><MemoryRouter><StrictMode><ComparisonPage /></StrictMode></MemoryRouter></RunContext.Provider></ApiContext.Provider>)
}
const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) })
it('reads the receipt IDs rather than latest, shows seeded GA and all metrics, and issues only GET', async () => {
  mount()
  await screen.findByText('Same-run plans verified')
  expect(transport.mock.calls.some(([url]) => url.includes('/latest'))).toBe(false)
  expect(screen.getByText(/GA \+ Greedy Initial solution/)).toBeVisible()
  expect(within(row('Total lateness')).getAllByText('Not calculable')).toHaveLength(3)
  expect(row('P1 Unassigned')).toHaveTextContent('0')
  expect(row('Algorithm runtime')).toHaveTextContent('ms')
  expect(screen.getByText(/single online result/)).toBeVisible()
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
})
it('shows matching latest values without percentages when the receipt is absent', async () => {
  mount(null)
  await screen.findByText('Comparability not verified')
  expect(row('Objective value')).toHaveTextContent('Not compared')
  expect(transport.mock.calls.some(([url]) => url.includes('/latest'))).toBe(true)
})
it('marks historical plans stale when current input has advanced', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => url.endsWith('/health') ? Promise.resolve(reply({ status: 'ok', database: 'ok', api_version: 'v1', input_revision: 99 })) : base(url, init))
  mount()
  expect(await screen.findByText(/The plan is stale and is shown for historical comparison only/)).toBeVisible()
  expect(screen.getByText('Same-run plans verified')).toBeVisible()
})
it('handles missing plans separately from zero tasks', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => url.includes('/route-plans') ? Promise.resolve(reply({ code: 'route_plan_not_found', message: 'missing' }, 404)) : base(url, init))
  mount()
  expect(await screen.findAllByText(/No saved plan found/)).toHaveLength(2)
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('clears unverified comparison on a failed read and retries only reads', async () => {
  mount(); await screen.findByText('Same-run plans verified')
  const base = transport.getMockImplementation()!
  transport.mockRejectedValue(new TypeError('offline'))
  await userEvent.click(screen.getByRole('button', { name: 'Reload comparison' }))
  await screen.findByRole('alert')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  transport.mockImplementation(base)
  await userEvent.click(screen.getByRole('button', { name: 'Reload comparison' }))
  await screen.findByText('Same-run plans verified')
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
})
it('rejects a response with the wrong saved ID', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => url.endsWith(fixtures.plans.ga.plan_id) ? Promise.resolve(reply({ ...fixtures.plans.ga, plan_id: 'wrong' })) : base(url, init))
  mount(); await screen.findByRole('alert')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})
it('loads without invented values and aborts on unmount', async () => {
  transport.mockReturnValue(new Promise(() => {}))
  const view = mount()
  expect(screen.getByRole('status')).toHaveTextContent('Loading')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  await waitFor(() => expect(transport).toHaveBeenCalled())
  const signal = transport.mock.calls.at(-1)![1].signal
  view.unmount(); expect(signal?.aborted).toBe(true)
})
it('labels mock data explicitly', async () => {
  mount(null, 'normal')
  expect(screen.getByText(/Read-only mock example/)).toBeVisible()
  await screen.findByText('Comparability not verified')
})

it('renders all-stopped crews and backend unassigned reasons without treating null as zero', async () => {
  const run = parseModel('RecalculationResult', fixtures.all_off)
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => url.includes('/route-plans/') ? Promise.resolve(reply(url.endsWith(fixtures.all_off_plans.greedy.plan_id) ? fixtures.all_off_plans.greedy : fixtures.all_off_plans.ga)) : base(url, init))
  mount(run)
  await screen.findByText('Same-run plans verified')
  expect(within(row('P2 Unassigned')).getAllByText('1')).toHaveLength(2)
  expect(within(row('Workload standard deviation')).getAllByText('Not calculable')).toHaveLength(3)
  expect(row('Objective value')).toHaveTextContent('Baseline is 0')
  expect(screen.getAllByText(/no_available_crew/)).toHaveLength(2)
})

it('shows a valid empty plan as zero tasks, distinct from no saved plan', async () => {
  const plans = { ga: parseModel('RoutePlan', structuredClone(fixtures.plans.ga)), greedy: parseModel('RoutePlan', structuredClone(fixtures.plans.greedy)) }
  const run = structuredClone(receipt())
  run.task_count = 0
  for (const p of Object.values(plans)) {
    for (const crew of p.crew_routes) {
      crew.stops = []; crew.status = crew.available ? 'idle' : 'unavailable'
      crew.travel_minutes = 0; crew.service_minutes = 0
      crew.total_work_minutes = 0; crew.end_minute = 0; crew.return_travel_minutes = null
    }
    p.metrics = { ...p.metrics, assigned_task_count: 0, workload_std_minutes: 0, priority_weighted_completion_minutes: null, total_service_minutes: 0, total_travel_minutes: 0, makespan_minutes: 0, objective_value: 0 }
    const summary = run.plans.find((s) => s.algorithm === p.algorithm)!
    summary.assigned_task_count = 0; summary.objective_value = 0
  }
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) => url.includes('/route-plans/') ? Promise.resolve(reply(url.endsWith(plans.greedy.plan_id) ? plans.greedy : plans.ga)) : base(url, init))
  mount(run)
  await screen.findByText('Same-run plans verified')
  expect(within(row('Assigned tasks')).getAllByText('0')).toHaveLength(2)
  expect(screen.queryByText(/No saved plan found/)).not.toBeInTheDocument()
  expect(row('Total travel')).toHaveTextContent('Baseline is 0')
})
