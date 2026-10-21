import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import AssistantPage from './AssistantPage'
import { ApiContext, type DataMode } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import PlanningRunProvider from '../planning/PlanningRunProvider'
import answer from '../test/assistant-fixture.json'
import planning from '../test/planning-fixtures.json'

const status = { enabled: true, configured: true, model: 'test-double', max_output_tokens: 1200, max_calls_per_process: 20, calls_used: 0, read_only: true }
const reply = (body: unknown, code = 200) => new Response(JSON.stringify(body), { status: code })
function open(transport: Transport, mode: DataMode = 'live') {
  return render(<MemoryRouter><ApiContext.Provider value={{
    api: createApiClient(transport, 8000, { csrfToken: () => 'csrf-test', onUnauthorized: vi.fn() }),
    mode, setMode: vi.fn(), imageUrl: (p) => p,
  }}><PlanningRunProvider><AssistantPage /></PlanningRunProvider></ApiContext.Provider></MemoryRouter>)
}
async function ask() {
  const user = userEvent.setup()
  await screen.findByText('模型已配置')
  await user.type(screen.getByLabelText('你的问题'), '深坑洞维修多久')
  await user.click(screen.getByRole('button', { name: '查找依据并回答' }))
  return user
}

it('only queries after submission and renders verified extracts and provenance as text', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status : answer))
  open(transport)
  await screen.findByText('模型已配置')
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
  await ask()
  await screen.findByText('已选出引用证据')
  const [, init] = transport.mock.calls.at(-1)!
  expect(init.method).toBe('POST')
  expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-test')
  expect(JSON.parse(String(init.body))).toMatchObject({ scope: 'knowledge', plan_id: null })
  expect(screen.getByText(answer.selections[0].quote, { selector: '.assistant-quote pre' })).toBeVisible()
  expect(screen.getByRole('link', { name: /查看来源/ })).toHaveAttribute('href', '#assistant-source-0')
  expect(screen.getByText(/未修改业务数据/)).toBeVisible()
})

it('does not submit or fall back when unconfigured or in simulated data mode', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply({ ...status, configured: false, enabled: false }))
  const view = open(transport)
  await screen.findByText('模型尚未配置')
  expect(screen.getByRole('button', { name: '查找依据并回答' })).toBeDisabled()
  expect(transport).toHaveBeenCalledTimes(1)
  view.unmount(); transport.mockClear()
  open(transport, 'normal')
  expect(screen.getByText('模拟来源 · 问答未启用')).toBeVisible()
  expect(screen.getByRole('button', { name: '查找依据并回答' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
})

it('passes an explicit plan ID and clears prior evidence when inputs change', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status
    : url.includes('/route-plans/') ? planning.plans.ga : answer))
  open(transport)
  const user = userEvent.setup()
  await screen.findByText('模型已配置')
  await user.selectOptions(screen.getByLabelText('回答依据'), 'plan')
  await user.click(screen.getByRole('button', { name: '读取最新 GA 方案 ID' }))
  await waitFor(() => expect(screen.getByLabelText('方案 ID')).toHaveValue(planning.plans.ga.plan_id))
  await user.type(screen.getByLabelText('你的问题'), '总行程是多少')
  await user.click(screen.getByRole('button', { name: '查找依据并回答' }))
  await screen.findByText('已选出引用证据')
  expect(JSON.parse(String(transport.mock.calls.at(-1)![1].body))).toMatchObject({ scope: 'plan', plan_id: planning.plans.ga.plan_id })
  await user.type(screen.getByLabelText('你的问题'), '？')
  expect(screen.queryByText('已选出引用证据')).not.toBeInTheDocument()
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
})

it('shows model failure without retrying or reusing an old answer', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => url.endsWith('/status') ? reply(status)
    : reply({ code: 'assistant_provider_unavailable', message: 'Unavailable', details: null }, 503))
  open(transport); await ask()
  expect(await screen.findByRole('alert')).toHaveTextContent('The model service is unavailable')
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
  expect(screen.queryByText('已选出引用证据')).not.toBeInTheDocument()
})

it('cancels waiting and never shows a late answer', async () => {
  let resolve!: (response: Response) => void
  const transport = vi.fn<Transport>().mockImplementation(async (url) => url.endsWith('/status') ? reply(status)
    : new Promise<Response>((done) => { resolve = done }))
  open(transport); const user = await ask()
  await user.click(screen.getByRole('button', { name: '停止等待' }))
  expect(screen.getByRole('status')).toHaveTextContent('可能仍会完成并产生用量')
  expect(transport.mock.calls.at(-1)![1].signal?.aborted).toBe(true)
  await act(async () => resolve(reply(answer)))
  expect(screen.queryByText('已选出引用证据')).not.toBeInTheDocument()
})

it('displays insufficient evidence explicitly with no fabricated citations', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status
    : { ...answer, supported: false, status: 'insufficient_data', answer: '现有证据不足', selections: [], sources: [] }))
  open(transport); await ask()
  expect(await screen.findByText('现有证据不足')).toBeVisible()
  expect(screen.queryByRole('link', { name: /查看来源/ })).not.toBeInTheDocument()
})
