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
    const menu = await screen.findByRole('button', { name: '菜单 ☰' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(menu).toHaveAttribute('aria-controls', 'workspace-navigation')
    await user.click(menu)
    expect(menu).toHaveAttribute('aria-expanded', 'true')
    const navigation = screen.getByRole('navigation', { name: '主要导航' })
    expect(within(navigation).queryByRole('link', { name: /上传巡检|施工队工作台/ })).not.toBeInTheDocument()
    await user.click(within(navigation).getByRole('link', { name: /四队路线/ }))
    expect(screen.getByRole('heading', { name: '四队路线', level: 1 })).toBeVisible()
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('explains automatic acceptance and manual review, and navigates without writes', async () => {
    open('/tasks')
    const user = userEvent.setup()
    await user.click(await screen.findByText('操作说明与流程'))
    expect(await screen.findByRole('complementary', { name: '当前步骤指引' })).toHaveTextContent('这里管理要做什么')
    await user.click(screen.getByText('查看完整流程'))
    const guide = screen.getByRole('complementary', { name: '当前步骤指引' })
    expect(within(guide).getByText(/自动接受的巡检可直接进入任务/)).toBeVisible()
    expect(within(guide).queryByRole('link', { name: '上传巡检' })).not.toBeInTheDocument()
    await user.click(within(guide).getByRole('link', { name: '处理待审' }))
    expect(screen.getByRole('heading', { level: 1, name: '人工审核' })).toBeVisible()
    expect(fetchMock.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true)
  })

  it('opens the task workspace and reads tasks without business writes', async () => {
    open()
    expect(
      await screen.findByRole('heading', { name: '任务工作区', level: 1 }),
    ).toBeVisible()
    expect(
      await screen.findByText(/应用与数据库已连接 · 输入版本 7/),
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
    await screen.findByText(/输入版本 7/)
    for (const [label, heading] of [
      ['人工审核', '人工审核'],
      ['维修任务', '任务工作区'],
      ['四队路线', '四队路线'],
      ['算法比较', '算法比较'],
      ['路线助手', '路线助手'],
    ]) {
      await user.click(
        within(screen.getByRole('navigation', { name: '主要导航' })).getByRole('link', {
          name: new RegExp(label),
        }),
      )
      expect(
        screen.getByRole('heading', { name: heading, level: 1 }),
      ).toBeVisible()
      expect(
        within(screen.getByRole('navigation', { name: '主要导航' })).getByRole('link', {
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
      await screen.findByRole('heading', { name: '算法比较', level: 1 }),
    ).toBeVisible()
    first.unmount()
    open('/missing')
    expect(await screen.findByRole('heading', { name: '页面不存在' })).toBeVisible()
    await userEvent.click(screen.getByRole('link', { name: '返回工作区' }))
    expect(
      screen.getByRole('heading', { name: '任务工作区', level: 1 }),
    ).toBeVisible()
  })
})

describe('service connection', () => {
  it('shows loading instead of a false empty or connected state', () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    render(<HealthStatus />)
    expect(screen.getByRole('status')).toHaveTextContent('正在检查服务')
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('can recover from a connection error through an explicit retry', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('offline'))
    render(<HealthStatus />)
    expect(await screen.findByText(/暂时无法连接服务/)).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '重新检查连接' }))
    expect(await screen.findByText(/输入版本 7/)).toBeVisible()
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
    expect(await screen.findByText(/暂时无法连接服务/)).toBeVisible()
    expect(screen.queryByText(/已连接/)).not.toBeInTheDocument()
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
    expect(screen.getByRole('status')).toHaveTextContent('暂时无法连接服务')
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
  const calculate = await screen.findByRole('button', { name: '重算 GA 与 Greedy' })
  await waitFor(() => expect(calculate).toBeEnabled())
  await user.click(calculate)
  await user.click(await screen.findByRole('link', { name: '比较本次 GA 与 Greedy' }))
  await screen.findByText('同轮方案已核对')
  await user.click(within(screen.getByRole('navigation', { name: '主要导航' })).getByRole('link', { name: /路线助手/ }))
  await user.click(within(screen.getByRole('navigation', { name: '主要导航' })).getByRole('link', { name: /算法比较/ }))
  await screen.findByText('同轮方案已核对')
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  await user.selectOptions(screen.getByRole('combobox', { name: '数据来源' }), 'normal')
  await screen.findByText('暂不能确认可比')
  await user.selectOptions(screen.getByRole('combobox', { name: '数据来源' }), 'live')
  await screen.findByText('暂不能确认可比')
  expect(screen.queryByText('同轮方案已核对')).not.toBeInTheDocument()
})
