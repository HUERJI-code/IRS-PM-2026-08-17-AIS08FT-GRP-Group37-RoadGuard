import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import ChangePanel from './ChangePanel'
import { ApiContext, type DataMode } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import PlanningRunProvider from '../planning/PlanningRunProvider'
import fixtures from '../test/change-fixtures.json'

const pending = { ...fixtures.pending, expires_at: '2099-01-01T00:00:00Z' }
const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
function open(transport: Transport, mode: DataMode = 'live') {
  return render(<MemoryRouter><ApiContext.Provider value={{ mode, setMode: vi.fn(),
    api: createApiClient(transport, 8000, { csrfToken: () => 'test-csrf', onUnauthorized: vi.fn() }),
    imageUrl: (p) => p }}><PlanningRunProvider><ChangePanel /></PlanningRunProvider></ApiContext.Provider></MemoryRouter>)
}
async function preview() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Availability plan ID'), pending.based_on_plan_id)
  await user.type(screen.getByLabelText('Availability instruction'), 'disable crew-02')
  await user.click(screen.getByRole('button', { name: 'Preview availability change' }))
  await screen.findByRole('heading', { name: 'crew-02: available → unavailable' })
  return user
}

it('requires a checked preview before confirmation and a separate click before recalculation', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) =>
    reply(url.endsWith('/confirm') ? fixtures.confirmed : url.endsWith('/replan') ? fixtures.completed : pending))
  open(transport)
  expect(transport).not.toHaveBeenCalled()
  const user = await preview()
  const confirm = screen.getByRole('button', { name: 'Confirm crew availability' })
  expect(confirm).toBeDisabled()
  expect(transport).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('checkbox'))
  await user.click(confirm)
  await screen.findByText('Crew availability saved')
  expect(transport.mock.calls.some(([url]) => url.endsWith('/replan'))).toBe(false)
  await user.click(screen.getByRole('button', { name: 'Recalculate GA and Greedy from saved availability' }))
  await screen.findByRole('link', { name: 'Compare these plans' })
  expect(transport.mock.calls.map(([url]) => url)).toEqual([
    '/api/v1/assistant/change-requests',
    `/api/v1/assistant/change-requests/${pending.change_id}/confirm`,
    `/api/v1/assistant/change-requests/${pending.change_id}/replan`,
  ])
  for (const [, init] of transport.mock.calls) expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('test-csrf')
})

it('cancels a preview without any confirm or replan call', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/cancel') ? { ...pending, status: 'cancelled' } : pending))
  open(transport); const user = await preview()
  await user.click(screen.getByRole('button', { name: 'Cancel availability preview' }))
  await screen.findByText('Cancelled')
  expect(screen.queryByRole('button', { name: 'Confirm crew availability' })).not.toBeInTheDocument()
  expect(transport.mock.calls).toHaveLength(2)
})

it('retains the same preview idempotency key after a network failure', async () => {
  const transport = vi.fn<Transport>().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValue(reply(pending))
  open(transport)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Availability plan ID'), pending.based_on_plan_id)
  await user.type(screen.getByLabelText('Availability instruction'), 'disable crew-02')
  await user.click(screen.getByRole('button', { name: 'Preview availability change' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The outcome is uncertain')
  await user.click(screen.getByRole('button', { name: 'Preview availability change' }))
  await screen.findByText('Awaiting confirmation')
  const bodies = transport.mock.calls.map(([, init]) => JSON.parse(String(init.body)))
  expect(bodies[0].request_id).toBe(bodies[1].request_id)
})

it('recovers an existing confirmed record using only reads', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) =>
    reply(url.endsWith('/change-requests') ? { items: [fixtures.confirmed] } : fixtures.confirmed))
  open(transport); const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Read my recent availability changes' }))
  await user.click(await screen.findByRole('button', { name: /disable crew-02 · Crew availability saved/ }))
  await screen.findByRole('button', { name: 'Recalculate GA and Greedy from saved availability' })
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
})

it('shows failed replanning as saved availability and requires manual recovery', async () => {
  const failed = { ...fixtures.confirmed, replan_status: 'failed', replan_error_code: 'travel_matrix_unavailable' }
  const transport = vi.fn<Transport>().mockResolvedValue(reply(failed))
  open(transport); const user = userEvent.setup()
  await user.type(screen.getByLabelText('Availability change ID'), pending.change_id)
  await user.click(screen.getByRole('button', { name: 'Recover availability change' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Availability is saved.')
  expect(screen.getByRole('button', { name: 'Retry or recover recalculation' })).toBeEnabled()
  expect(transport).toHaveBeenCalledTimes(1)
})

it('never writes in simulated mode and does not confirm expired previews', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply({ ...pending, status: 'expired' }))
  const view = open(transport, 'normal')
  expect(screen.getByRole('button', { name: 'Preview availability change' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
  view.unmount(); open(transport)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Availability change ID'), pending.change_id)
  await user.click(screen.getByRole('button', { name: 'Recover availability change' }))
  await waitFor(() => expect(screen.getByText('Preview expired')).toBeVisible())
  expect(screen.queryByRole('button', { name: 'Confirm crew availability' })).not.toBeInTheDocument()
})
