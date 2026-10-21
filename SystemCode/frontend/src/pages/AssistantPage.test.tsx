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
  await screen.findByText('Model configured')
  await user.type(screen.getByLabelText('Your question'), 'How long does a deep pothole repair take?')
  await user.click(screen.getByRole('button', { name: 'Ask assistant' }))
  return user
}

it('shows the answer first and hides original evidence until sources are opened', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status : answer))
  open(transport)
  await screen.findByText('Model configured')
  expect(transport.mock.calls.every(([, init]) => !init.method || init.method === 'GET')).toBe(true)
  const user = await ask()
  await screen.findByRole('heading', { name: 'Answer' })
  const [, init] = transport.mock.calls.at(-1)!
  expect(init.method).toBe('POST')
  expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf-test')
  expect(JSON.parse(String(init.body))).toMatchObject({ scope: 'knowledge', plan_id: null })
  expect(screen.getByText(answer.answer.split('\n\n')[0])).toBeVisible()
  const sourceToggle = screen.getByText('View sources', { selector: 'summary' })
  expect(sourceToggle.parentElement).not.toHaveAttribute('open')
  const quote = screen.getByText((_, element) => element?.textContent === answer.selections[0].quote,
    { selector: '.assistant-quote pre' })
  expect(quote).not.toBeVisible()
  await user.click(sourceToggle)
  expect(quote).toBeVisible()
  await user.click(sourceToggle)
  expect(quote).not.toBeVisible()
  expect(screen.getByText(/Business data unchanged/)).toBeVisible()
})

it('does not automatically submit and keeps questions disabled in simulated data mode', async () => {
  const transport = vi.fn<Transport>().mockResolvedValue(reply({ ...status, configured: false, enabled: false }))
  const view = open(transport)
  await screen.findByText('Model not configured')
  expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeDisabled()
  expect(transport).toHaveBeenCalledTimes(1)
  view.unmount(); transport.mockClear()
  open(transport, 'normal')
  expect(screen.getByText('Mock source · Questions unavailable')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeDisabled()
  expect(transport).not.toHaveBeenCalled()
})

it('allows configuration questions without a configured provider and does not invent citations', async () => {
  const modelInfo = { ...answer, status: 'model_info', answer_mode: 'server_configuration',
    answer: 'The assistant model configured on this server is fixture-model.', model: 'fixture-model',
    model_called: false, package_version: null, manifest_sha256: null, plan: null, sources: [], selections: [] }
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status')
    ? { ...status, configured: false, enabled: false } : modelInfo))
  open(transport)
  await screen.findByText('Model not configured')
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Your question'), 'What model are you?')
  expect(screen.getByRole('button', { name: 'Ask assistant' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: 'Ask assistant' }))
  expect(await screen.findByText('Server configuration')).toBeVisible()
  expect(screen.getByText(modelInfo.answer)).toBeVisible()
  expect(screen.getByText('Server response · No model call or retrieval')).toBeVisible()
  expect(screen.queryByText('Based on selected evidence')).not.toBeInTheDocument()
  expect(screen.queryByText('View sources', { selector: 'summary' })).not.toBeInTheDocument()
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
})

it('shows friendly scope guidance instead of an evidence-validation error', async () => {
  const guidance = { ...answer, status: 'out_of_scope', supported: false, answer_mode: 'scope_guidance',
    answer: 'I can help with RoadGuard repair rules and saved routes. Try asking about a deep pothole.',
    model: null, model_called: false, package_version: null, manifest_sha256: null, plan: null, sources: [], selections: [] }
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status : guidance))
  open(transport)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Your question'), 'Who won the World Cup?')
  await user.click(screen.getByRole('button', { name: 'Ask assistant' }))
  expect(await screen.findByRole('heading', { name: 'How I can help' })).toBeVisible()
  expect(screen.getByText(guidance.answer)).toBeVisible()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.queryByText('View sources', { selector: 'summary' })).not.toBeInTheDocument()
})

it('still hides unverifiable RAG output instead of treating it as scope guidance', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => url.endsWith('/status') ? reply(status)
    : reply({ code: 'assistant_invalid_response', message: 'Unverifiable evidence', details: null }, 502))
  open(transport); await ask()
  expect(await screen.findByRole('alert')).toHaveTextContent('The model evidence failed validation')
  expect(screen.queryByRole('heading', { name: 'Answer' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'How I can help' })).not.toBeInTheDocument()
})

it('passes an explicit plan ID and clears prior evidence when inputs change', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status
    : url.includes('/route-plans/') ? planning.plans.ga : answer))
  open(transport)
  const user = userEvent.setup()
  await screen.findByText('Model configured')
  await user.selectOptions(screen.getByLabelText('Answer scope'), 'plan')
  await user.click(screen.getByRole('button', { name: 'Read latest GA plan ID' }))
  await waitFor(() => expect(screen.getByLabelText('Plan ID')).toHaveValue(planning.plans.ga.plan_id))
  await user.type(screen.getByLabelText('Your question'), 'What is the total travel?')
  await user.click(screen.getByRole('button', { name: 'Ask assistant' }))
  await screen.findByRole('heading', { name: 'Answer' })
  expect(JSON.parse(String(transport.mock.calls.at(-1)![1].body))).toMatchObject({ scope: 'plan', plan_id: planning.plans.ga.plan_id })
  await user.type(screen.getByLabelText('Your question'), '?')
  expect(screen.queryByRole('heading', { name: 'Answer' })).not.toBeInTheDocument()
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
})

it('shows model failure without retrying or reusing an old answer', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => url.endsWith('/status') ? reply(status)
    : reply({ code: 'assistant_provider_unavailable', message: 'Unavailable', details: null }, 503))
  open(transport); await ask()
  expect(await screen.findByRole('alert')).toHaveTextContent('The model service is unavailable')
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
  expect(screen.queryByRole('heading', { name: 'Answer' })).not.toBeInTheDocument()
})

it('cancels waiting and never shows a late answer', async () => {
  let resolve!: (response: Response) => void
  const transport = vi.fn<Transport>().mockImplementation(async (url) => url.endsWith('/status') ? reply(status)
    : new Promise<Response>((done) => { resolve = done }))
  open(transport); const user = await ask()
  await user.click(screen.getByRole('button', { name: 'Stop waiting' }))
  expect(screen.getByRole('status')).toHaveTextContent('may still complete and use quota')
  expect(transport.mock.calls.at(-1)![1].signal?.aborted).toBe(true)
  await act(async () => resolve(reply(answer)))
  expect(screen.queryByRole('heading', { name: 'Answer' })).not.toBeInTheDocument()
})

it('displays insufficient evidence explicitly with no fabricated citations', async () => {
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status
    : { ...answer, supported: false, status: 'insufficient_data', answer: 'Insufficient evidence', selections: [], sources: [] }))
  open(transport); await ask()
  expect(await screen.findByText('Insufficient evidence')).toBeVisible()
  expect(screen.queryByText('View sources', { selector: 'summary' })).not.toBeInTheDocument()
})

it('renders model content as plain text and folds sources again for a new answer', async () => {
  const text = '<img src=x onerror=alert(1)>\n\nA second paragraph.'
  const transport = vi.fn<Transport>().mockImplementation(async (url) => reply(url.endsWith('/status') ? status
    : { ...answer, answer: text }))
  const view = open(transport)
  const user = await ask()
  expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeVisible()
  expect(screen.getByText('A second paragraph.')).toBeVisible()
  expect(view.container.querySelector('.assistant-response img')).toBeNull()
  await user.click(screen.getByText('View sources', { selector: 'summary' }))
  await user.type(screen.getByLabelText('Your question'), '?')
  await user.click(screen.getByRole('button', { name: 'Ask assistant' }))
  await screen.findByRole('heading', { name: 'Answer' })
  expect(screen.getByText('View sources', { selector: 'summary' }).parentElement).not.toHaveAttribute('open')
})
