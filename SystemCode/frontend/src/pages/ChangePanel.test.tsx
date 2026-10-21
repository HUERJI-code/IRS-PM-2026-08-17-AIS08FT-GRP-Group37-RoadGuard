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
  await user.type(screen.getByLabelText('调整依据方案 ID'), pending.based_on_plan_id)
  await user.type(screen.getByLabelText('调整指令'), '停用 crew-02')
  await user.click(screen.getByRole('button', { name: '生成调整预览' }))
  await screen.findByRole('heading', { name: 'crew-02：可用 → 不可用' })
  return user
}

it('requires a checked preview before confirmation and a separate click before recalculation', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) =>
    reply(url.endsWith('/confirm') ? fixtures.confirmed : url.endsWith('/replan') ? fixtures.completed : pending))
  open(transport)
  expect(transport).not.toHaveBeenCalled()
  const user = await preview()
  const confirm = screen.getByRole('button', { name: '确认保存队伍状态' })
  expect(confirm).toBeDisabled()
  expect(transport).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('checkbox'))
  await user.click(confirm)
  await screen.findByText('队伍状态已保存')
  expect(transport.mock.calls.some(([url]) => url.endsWith('/replan'))).toBe(false)
  await user.click(screen.getByRole('button', { name: '按已保存状态重算 GA 与 Greedy' }))
  await screen.findByRole('link', { name: '查看本次方案比较' })
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
  await user.click(screen.getByRole('button', { name: '取消此预览' }))
  await screen.findByText('已取消')
  expect(screen.queryByRole('button', { name: '确认保存队伍状态' })).not.toBeInTheDocument()
  expect(transport.mock.calls).toHaveLength(2)
})

it('retains the same preview idempotency key after a network failure', async () => {
  const transport = vi.fn<Transport>().mockRejectedValueOnce(new TypeError('offline')).mockResolvedValue(reply(pending))
  open(transport)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('调整依据方案 ID'), pending.based_on_plan_id)
  await user.type(screen.getByLabelText('调整指令'), '停用 crew-02')
  await user.click(screen.getByRole('button', { name: '生成调整预览' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The outcome is uncertain')
  await user.click(screen.getByRole('button', { name: '生成调整预览' }))
  await screen.findByText('等待确认')
  const bodies = transport.mock.calls.map(([, init]) => JSON.parse(String(init.body)))
  expect(bodies[0].request_id).toBe(bodies[1].request_id)
})

it('recovers an existing confirmed record using only reads', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) =>
    reply(url.endsWith('/change-requests') ? { items: [fixtures.confirmed] } : fixtures.confirmed))
  open(transport); const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '读取我的最近调整' }))
  await user.click(await screen.findByRole('button', { name: /停用 crew-02 · 队伍状态已保存/ }))
  await screen.findByRole('button', { name: '按已保存状态重算 GA 与 Greedy' })
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
})

it('shows failed replanning as saved availability and requires manual recovery', async () => {
  const failed = { ...fixtures.confirmed, replan_status: 'failed', replan_error_code: 'travel_matrix_unavailable' }
  const transport = vi.fn<Transport>().mockResolvedValue(reply(failed))
  open(transport); const user = userEvent.setup()
  await user.type(screen.getByLabelText('按调整 ID 查询'), pending.change_id)
  await user.click(screen.getByRole('button', { name: '查询指定调整' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('队伍状态已经保存')
  expect(screen.getByRole('button', { name: '重试或恢复重算' })).toBeEnabled()
  expect(transport).toHaveBeenCalledTimes(1)
})

it('never writes in simulated mode and does not confirm expired previews', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply({ ...pending, status: 'expired' }))
  const view = open(transport, 'normal')
  expect(screen.getByRole('button', { name: '生成调整预览' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
  view.unmount(); open(transport)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('按调整 ID 查询'), pending.change_id)
  await user.click(screen.getByRole('button', { name: '查询指定调整' }))
  await waitFor(() => expect(screen.getByText('预览已过期')).toBeVisible())
  expect(screen.queryByRole('button', { name: '确认保存队伍状态' })).not.toBeInTheDocument()
})
