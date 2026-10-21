import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import planning from './test/planning-fixtures.json'
import HealthStatus from './components/HealthStatus'

const session = { user: { user_id: 'dispatcher-1', username: 'c', display_name: 'Dispatcher C', role: 'dispatcher', crew_id: null }, csrf_token: 'csrf-test', expires_at: Math.floor(Date.now() / 1000) + 3600 }
const health = {
  status: 'ok',
  database: 'ok',
  api_version: 'v1',
  input_revision: 7,
}
const fetchMock = vi.fn<typeof fetch>()
function open(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockImplementation(async (url) => new Response(JSON.stringify(String(url).endsWith('/auth/session') ? session : health)))
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  fetchMock.mockReset()
})

describe('workspace navigation', () => {
  it('opens the workspace menu and closes it after an authorized destination is selected', async () => {
    const user = userEvent.setup()
    open('/tasks')
    const menu = await screen.findByRole('button', { name: 'Menu ☰' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(menu).toHaveAttribute('aria-controls', 'workspace-navigation')
    await user.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    const navigation = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(navigation).queryByRole('link', { name: /Upload inspection|Crew workspace/ })).not.toBeInTheDocument()
    await user.click(within(navigation).getByRole('link', { name: /Four-crew routes/ }))
    expect(screen.getByRole('heading', { name: 'Four-crew routes', level: 1 })).toBeVisible()
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('explains automatic acceptance and manual review, and navigates without writes', async () => {
    open('/tasks')
    const user = userEvent.setup()
    await user.click(await screen.findByText('Instructions and workflow'))
    expect(await screen.findByRole('complementary', { name: 'Current step guide' })).toHaveTextContent('Manage the work here')
    await user.click(screen.getByText('View the full workflow'))
    const guide = screen.getByRole('complementary', { name: 'Current step guide' })
    expect(within(guide).getByText(/Automatically accepted inspections enter the task queue/)).toBeVisible()
    expect(within(guide).queryByRole('link', { name: 'Upload inspection' })).not.toBeInTheDocument()
    await user.click(within(guide).getByRole('link', { name: 'Review pending' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Manual review' })).toBeVisible()
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('opens the task workspace and reads tasks without business writes', async () => {
    open()
    expect(
      await screen.findByRole('heading', { name: 'Task workspace', level: 1 }),
    ).toBeVisible()
    expect(
      await screen.findByText(/Application and database connected · Input revision 7/),
    ).toBeVisible()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/health',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/tasks?status=active&limit=20&offset=0',
      expect.anything(),
    )
    expect(
      fetchMock.mock.calls.every(
        ([, options]) => !options?.method || options.method === 'GET',
      ),
    ).toBe(true)
  })

  it('supports all five dispatcher navigation destinations without issuing business writes', async () => {
    const user = userEvent.setup()
    open('/tasks')
    await screen.findByText(/Input revision 7/)
    for (const [label, heading] of [
      ['Manual review', 'Manual review'],
      ['Repair tasks', 'Task workspace'],
      ['Four-crew routes', 'Four-crew routes'],
      ['Algorithm comparison', 'Algorithm comparison'],
      ['Route assistant', 'Route assistant'],
    ]) {
      await user.click(
        within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', {
          name: new RegExp(label),
        }),
      )
      expect(
        screen.getByRole('heading', { name: heading, level: 1 }),
      ).toBeVisible()
      expect(
        within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', {
          name: new RegExp(label),
        }),
      ).toHaveAttribute('aria-current', 'page')
      expect(document.title).toBe(`${heading} · RoadGuard`)
      expect(screen.getByRole('main')).toHaveFocus()
    }
    expect(
      fetchMock.mock.calls.every(
        ([, options]) => !options?.method || options.method === 'GET',
      ),
    ).toBe(true)
  })

  it('handles a direct page URL and an unknown URL with a return link', async () => {
    const first = open('/comparison')
    expect(
      await screen.findByRole('heading', { name: 'Algorithm comparison', level: 1 }),
    ).toBeVisible()
    first.unmount()
    open('/missing')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeVisible()
    await userEvent.click(screen.getByRole('link', { name: 'Return to workspace' }))
    expect(
      screen.getByRole('heading', { name: 'Task workspace', level: 1 }),
    ).toBeVisible()
  })
})

describe('service connection', () => {
  it('shows loading instead of a false empty or connected state', () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    render(<HealthStatus />)
    expect(screen.getByRole('status')).toHaveTextContent('Checking service')
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('can recover from a connection error through an explicit retry', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    render(<HealthStatus />)
    expect(await screen.findByText(/Cannot connect to the service/)).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Check connection again' }))
    expect(await screen.findByText(/Input revision 7/)).toBeVisible()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['HTTP failure', () => new Response('{}', { status: 503 })],
    ['HTML response', () => new Response('<html>fallback</html>')],
    [
      'invalid contract',
      () => new Response(JSON.stringify({ ...health, input_revision: '7' })),
    ],
  ])('rejects %s without pretending to be connected', async (_, response) => {
    fetchMock.mockResolvedValue(response())
    render(<HealthStatus />)
    expect(await screen.findByText(/Cannot connect to the service/)).toBeVisible()
    expect(screen.queryByText(/Connected/)).not.toBeInTheDocument()
  })

  it('ends a stalled request after eight seconds', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url, options) =>
        new Promise((_, reject) => {
          options?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    render(<HealthStatus />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })
    expect(screen.getByRole('status')).toHaveTextContent('Cannot connect to the service')
  })

  it('aborts an outstanding request on unmount', async () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    const view = render(<HealthStatus />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const signal = fetchMock.mock.calls[0][1]?.signal
    view.unmount()
    expect(signal?.aborted).toBe(true)
  })
})


it('preserves the actual recalculation pair across navigation and clears it on source change', async () => {
  fetchMock.mockImplementation(async (url, init) => {
    const path = String(url)
    const body = path.endsWith('/auth/session') ? session : path.endsWith('/health') ? { ...health, input_revision: planning.calculation.input_revision }
      : path.endsWith('/crews') ? planning.after_crews
      : path.includes('/tasks/snapshot') ? planning.after_snapshot
      : init?.method === 'POST' ? planning.calculation
      : path.includes('greedy') || path.endsWith(planning.plans.greedy.plan_id) ? planning.plans.greedy
      : planning.plans.ga
    return new Response(JSON.stringify(body))
  })
  open('/routes')
  const user = userEvent.setup()
  const calculate = await screen.findByRole('button', { name: 'Recalculate GA and Greedy' })
  await waitFor(() => expect(calculate).toBeEnabled())
  await user.click(calculate)
  await user.click(await screen.findByRole('link', { name: 'Compare this GA and Greedy run' }))
  await screen.findByText('Same-run plans verified')
  await user.click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: /Route assistant/ }))
  await user.click(within(screen.getByRole('navigation', { name: 'Main navigation' })).getByRole('link', { name: /Algorithm comparison/ }))
  await screen.findByText('Same-run plans verified')
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  await user.selectOptions(screen.getByRole('combobox', { name: 'Data source' }), 'normal')
  await screen.findByText('Comparability not verified')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Data source' }), 'live')
  await screen.findByText('Comparability not verified')
  expect(screen.queryByText('Same-run plans verified')).not.toBeInTheDocument()
})
