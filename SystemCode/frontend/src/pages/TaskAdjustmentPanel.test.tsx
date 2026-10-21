import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import TaskAdjustmentPanel from './TaskAdjustmentPanel'
import { ApiContext, type DataMode } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import PlanningRunProvider from '../planning/PlanningRunProvider'
import planning from '../test/planning-fixtures.json'

const plan = { ...planning.plans.ga, crew_routes: planning.plans.ga.crew_routes.map(route => ({ ...route, shift_remaining_minutes: 123, stops: route.stops.map(stop => ({ ...stop, damage_label: 'deep_pothole', locked_crew_id: null })) })) }
const task = plan.crew_routes.flatMap(route => route.stops)[0]
const source = plan.crew_routes.find(route => route.stops.some(stop => stop.task_id === task.task_id))!
const target = plan.crew_routes.find(route => route.crew_id !== source.crew_id && route.available)!
const pending = { contract_version: 'c-assistant-task-change-v1', change_id: 'task-change-' + 'a'.repeat(32), actor_id: 'dispatcher', client_key: '11111111-1111-4111-8111-111111111111', based_on_plan_id: plan.plan_id, input_revision: plan.input_revision, planning_config_fingerprint: 'x', action: 'reassign', task_id: task.task_id, task_record_version: 1, source_crew_id: source.crew_id, target_crew_id: target.crew_id, status: 'pending', record_version: 1, created_at: '2026-10-21T00:00:00Z', expires_at: '2099-01-01T00:00:00Z', applied_revision: null, before_routes: plan.crew_routes, after_routes: plan.crew_routes, shift_limit_minutes: 480, return_to_depot: true, replan_status: 'not_requested', replan_attempts: [], replan_attempt_id: null, replan_lease_until: null, replan_error_code: null, result: null }
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
function open(transport: Transport, mode: DataMode = 'live') {
  render(<MemoryRouter><ApiContext.Provider value={{ mode, setMode: vi.fn(), api: createApiClient(transport, 8000, { csrfToken: () => 'csrf', onUnauthorized: vi.fn() }), imageUrl: p => p }}><PlanningRunProvider><TaskAdjustmentPanel /></PlanningRunProvider></ApiContext.Provider></MemoryRouter>)
}
async function choose() {
  const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Load latest GA plan' }))
  await screen.findByText(`Loaded plan`, { exact: false })
  await user.selectOptions(screen.getByLabelText('Task to adjust'), task.task_id)
  await user.selectOptions(screen.getByLabelText('Target crew'), target.crew_id)
  return user
}
it('loads route facts and requires explicit preview acknowledgement and confirmation', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async url => reply(url.includes('/route-plans') ? plan : url.endsWith('/confirm') ? { ...pending, status: 'confirmed', record_version: 2, applied_revision: 20 } : pending))
  open(transport); const user = await choose()
  expect(screen.getAllByText('Shift remaining: 123 min')).toHaveLength(plan.crew_routes.length)
  await user.click(screen.getByRole('button', { name: 'Preview task change' }))
  const confirm = await screen.findByRole('button', { name: 'Confirm task change' }); expect(confirm).toBeDisabled()
  await user.click(screen.getByRole('checkbox')); await user.click(confirm)
  await screen.findByRole('button', { name: 'Recalculate saved task change' })
  expect(screen.queryByText('Loaded plan', { exact: false })).not.toBeInTheDocument()
  expect(transport.mock.calls.some(([url]) => url.endsWith('/replan'))).toBe(false)
  const write = transport.mock.calls.find(([url]) => url.endsWith('/confirm'))!
  expect(new Headers(write[1].headers).get('X-CSRF-Token')).toBe('csrf')
})
it('clears mismatching route data immediately when the plan ID is edited', async () => {
  open(vi.fn<Transport>().mockResolvedValue(reply(plan))); const user = await choose()
  await user.type(screen.getByLabelText('Task adjustment plan ID'), 'x')
  expect(screen.queryByLabelText('Task to adjust')).not.toBeInTheDocument()
})
it('displays server overtime detail and retains preview request ID after retry', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async url => url.includes('/route-plans') ? reply(plan) : reply({ code: 'task_change_infeasible', message: 'crew-02 needs 520 minutes including return travel; shift 480 minutes.', details: { shift_limit_minutes: 480, return_to_depot: true } }, 409))
  open(transport); const user = await choose()
  await user.click(screen.getByRole('button', { name: 'Preview task change' }))
  expect(await screen.findByText(/crew-02 needs 520/)).toBeVisible()
  expect(screen.getByText('Shift limit: 480 min. Depot return included.')).toBeVisible()
  expect(screen.queryByText(/Check the saved change record after a connection failure/)).not.toBeInTheDocument()
  expect(document.body).not.toHaveTextContent('shift_limit_minutes')
  await user.click(screen.getByRole('button', { name: 'Preview task change' }))
  const writes = transport.mock.calls.filter(([url]) => url.endsWith('/preview')).map(([, init]) => JSON.parse(String(init.body)))
  expect(writes[0].request_id).toBe(writes[1].request_id)
  expect(screen.queryByRole('button', { name: 'Confirm task change' })).not.toBeInTheDocument()
})
it('supports cancellation of an unassigned active task without a destination crew', async () => {
  const unassigned = { ...plan, unassigned_tasks: [{ task_id: 'unassigned-test', reason: 'exceeds_shift_limit' }] }
  const transport = vi.fn<Transport>().mockImplementation(async url => reply(url.includes('/route-plans') ? unassigned : { ...pending, action: 'cancel_task', task_id: 'unassigned-test', source_crew_id: null, target_crew_id: null }))
  open(transport); const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Load latest GA plan' }))
  await user.selectOptions(await screen.findByLabelText('Task action'), 'cancel_task')
  await user.selectOptions(screen.getByLabelText('Task to adjust'), 'unassigned-test')
  await user.click(screen.getByRole('button', { name: 'Preview task change' }))
  await screen.findByRole('button', { name: 'Discard task preview' })
  const payload = JSON.parse(String(transport.mock.calls.at(-1)![1].body))
  expect(payload).toMatchObject({ action: 'cancel_task', target_crew_id: null, task_id: 'unassigned-test' })
  expect(screen.queryByLabelText('Target crew')).not.toBeInTheDocument()
})
it('blocks mock writes and stale plan changes', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply({ ...plan, is_stale: true }))
  open(transport); const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Load latest GA plan' }))
  expect(await screen.findByLabelText('Task action')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Preview task change' })).toBeDisabled()
})
it('does not load or mutate plans in mock mode', () => {
  const transport = vi.fn<Transport>()
  open(transport, 'normal')
  expect(screen.getByRole('button', { name: 'Load latest GA plan' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
})
it('shows persistent crew locks from backend route facts', async () => {
  const locked = { ...plan, crew_routes: plan.crew_routes.map(route => ({ ...route, stops: route.stops.map(stop => ({ ...stop, locked_crew_id: route.crew_id })) })) }
  open(vi.fn<Transport>().mockResolvedValue(reply(locked)))
  const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Load latest GA plan' }))
  expect(await screen.findByText(`Locked to ${source.crew_id} for future recalculations`)).toBeVisible()
})
it('formats server duration values without exposing binary floating-point artifacts', async () => {
  const rounded = { ...plan, crew_routes: plan.crew_routes.map(route => ({ ...route, travel_minutes: 62.900000000000006, service_minutes: 360.00000000000006, total_work_minutes: 422.90000000000003, return_travel_minutes: 14.100000000000001, shift_remaining_minutes: 57.10000000000002, stops: route.stops.map(stop => ({ ...stop, travel_minutes_from_previous: 24.700000000000003, service_minutes: 120.00000000000001, completion_minute: 144.70000000000002 })) })) }
  const transport = vi.fn<Transport>().mockResolvedValue(reply(rounded)); open(transport)
  const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Load latest GA plan' }))
  expect((await screen.findAllByText('Shift remaining: 57.1 min'))[0]).toBeVisible()
  expect(screen.getAllByText('Travel 62.9 min (depot return 14.1 min) · Service 360 min · Total 422.9 min')[0]).toBeVisible()
  expect(screen.getByText('Travel 24.7 min · Service 120 min · Completion offset 144.7 min')).toBeVisible()
  expect(document.body).not.toHaveTextContent('00000000000')
  expect(rounded.crew_routes[0].travel_minutes).toBe(62.900000000000006)
})
