import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import fixtures from '../test/task-fixtures.json'
import { ApiContext, type ApiContextValue } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel } from '../api/contracts'
import TaskPage from './TaskPage'
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
let transport: ReturnType<typeof vi.fn<Transport>>
const fixture = fixtures.completed
const list = {
  items: [fixture.before],
  total: 1,
  limit: 20,
  offset: 0,
  input_revision: 1,
}
function mount(
  id = fixture.before.task_id,
  mode: ApiContextValue['mode'] = 'live',
) {
  return render(
    <ApiContext.Provider
      value={{
        mode,
        setMode: vi.fn(),
        api: createApiClient(transport),
        imageUrl: (path) => path,
      }}
    >
      <MemoryRouter initialEntries={[id ? '/tasks?task=' + id : '/tasks']}>
        <TaskPage />
      </MemoryRouter>
    </ApiContext.Provider>,
  )
}
const writes = () =>
  transport.mock.calls.filter(([, init]) => init.method === 'PATCH')
beforeEach(() => {
  transport = vi
    .fn<Transport>()
    .mockImplementation(async (url, init) =>
      reply(
        init.method === 'PATCH'
          ? fixture.response
          : url.includes('?')
            ? list
            : fixture.before,
      ),
    )
})
it('validates generated task mutations and replays', () => {
  for (const value of Object.values(fixtures)) {
    expect(() => parseModel('TaskRecord', value.before)).not.toThrow()
    expect(() => parseModel('TaskMutation', value.response)).not.toThrow()
    expect(() => parseModel('TaskMutation', value.replay)).not.toThrow()
  }
})
it('reveals a mobile selection after its asynchronous detail loads, only once', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  try {
    let resolveDetail!: (value: Response) => void
    const deferred = new Promise<Response>((resolve) => { resolveDetail = resolve })
    transport.mockImplementation(async (url) => url.includes('?') ? reply(list) : deferred)
    mount('')
    const pane = screen.getByLabelText('任务详情工作区')
    const scroll = vi.fn()
    Object.defineProperty(pane, 'scrollIntoView', { value: scroll })
    const button = await screen.findByRole('button', { name: new RegExp(`P[123].*活动.*${fixture.before.task_id}`) })
    await userEvent.click(button)
    expect(pane).toHaveFocus()
    expect(scroll).not.toHaveBeenCalled()
    await act(async () => resolveDetail(reply(fixture.before)))
    expect(await screen.findByRole('heading', { name: '任务详情' })).toBeVisible()
    expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: 'start', behavior: 'instant' })
    expect(button).toHaveAttribute('aria-current', 'true')
    transport.mockImplementation(async (url) => reply(url.includes('?') ? list : fixture.before))
    await userEvent.click(screen.getByRole('button', { name: '重新读取并检查' }))
    await screen.findByRole('heading', { name: '任务详情' })
    expect(scroll).toHaveBeenCalledTimes(1)
    expect(writes()).toHaveLength(0)
  } finally {
    vi.unstubAllGlobals()
  }
})
it.each(['completed', 'cancelled', 'label', 'location'] as const)(
  'sends only allowed fields for %s',
  async (action) => {
    const sample = fixtures[action]
    transport.mockImplementation(async (url, init) =>
      reply(
        init.method === 'PATCH'
          ? sample.response
          : url.includes('?')
            ? list
            : sample.before,
      ),
    )
    mount(sample.before.task_id)
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('任务操作'), action)
    if (action === 'label')
      await user.selectOptions(
        screen.getByLabelText('新的损伤标签'),
        'pothole_deep',
      )
    if (action === 'location') {
      await user.clear(screen.getByLabelText('纬度'))
      await user.type(screen.getByLabelText('纬度'), '1.3406')
      await user.click(screen.getByRole('checkbox'))
    }
    await user.click(screen.getByRole('button', { name: '保存任务修改' }))
    expect(await screen.findByText('任务已保存')).toBeVisible()
    expect(JSON.parse(writes()[0][1].body as string)).toEqual({
      ...sample.request,
      request_id: expect.any(String),
    })
    expect(screen.getByText(/已有路线可能过期/)).toBeVisible()
    expect(
      transport.mock.calls.some(([url]) => url.includes('recalculate')),
    ).toBe(false)
    if (action === 'completed' || action === 'cancelled') {
      expect(screen.getByText(/终态任务只读/)).toBeVisible()
      expect(screen.queryByLabelText('任务操作')).not.toBeInTheDocument()
    }
  },
)
it('requires coordinates and road declaration', async () => {
  mount()
  const user = userEvent.setup()
  await user.selectOptions(await screen.findByLabelText('任务操作'), 'location')
  await user.clear(screen.getByLabelText('纬度'))
  await user.click(screen.getByRole('button', { name: '保存任务修改' }))
  expect(writes()).toHaveLength(0)
  expect(screen.getByLabelText('纬度')).toBeInvalid()
  expect(screen.getByRole('checkbox')).toBeInvalid()
})
it('reloads after conflict without replaying old intent', async () => {
  let attempted = false
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'PATCH') {
      if (!attempted) {
        attempted = true
        return reply({ code: 'stale_record_version', message: 'changed' }, 409)
      }
      return reply(fixture.response)
    }
    return reply(
      url.includes('?')
        ? list
        : { ...fixture.before, record_version: attempted ? 2 : 1 },
    )
  })
  mount()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '保存任务修改' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('记录已被修改')
  expect(screen.getByRole('button', { name: '保存任务修改' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '重新读取并检查' }))
  await user.click(await screen.findByRole('button', { name: '保存任务修改' }))
  await screen.findByText('任务已保存')
  const bodies = writes().map(([, init]) => JSON.parse(init.body as string))
  expect(bodies).toHaveLength(2)
  expect(bodies[1].expected_version).toBe(2)
  expect(bodies[1].request_id).not.toBe(bodies[0].request_id)
})
it('locks editing and retries the exact original operation after unknown outcome', async () => {
  let first = true
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'PATCH') {
      if (first) {
        first = false
        throw new TypeError('offline')
      }
      return reply(fixture.replay)
    }
    return reply(url.includes('?') ? list : fixture.before)
  })
  mount()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '保存任务修改' }))
  const retry = await screen.findByRole('button', {
    name: '使用原请求重试任务',
  })
  expect(screen.getByLabelText('任务操作')).toBeDisabled()
  expect(screen.getByLabelText('状态筛选')).toBeDisabled()
  await user.click(retry)
  await screen.findByText('已恢复原请求结果')
  expect(writes()).toHaveLength(2)
  expect(writes()[1][1].body).toBe(writes()[0][1].body)
})
it('blocks duplicate submission', async () => {
  transport.mockImplementation((url, init) =>
    init.method === 'PATCH'
      ? new Promise(() => {})
      : Promise.resolve(reply(url.includes('?') ? list : fixture.before)),
  )
  mount()
  const form = (
    await screen.findByRole('button', { name: '保存任务修改' })
  ).closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  await waitFor(() => expect(writes()).toHaveLength(1))
})
it.each(['completed', 'cancelled'] as const)(
  'shows %s history read-only on direct entry',
  async (status) => {
    transport.mockImplementation(async (url) =>
      reply(url.includes('?') ? list : fixtures[status].response.task),
    )
    mount()
    expect(await screen.findByText(/终态任务只读/)).toBeVisible()
    expect(screen.queryByLabelText('任务操作')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '任务历史' })).toBeVisible()
  },
)
it('renders unknown time and unset due date', async () => {
  transport.mockImplementation(async (url) =>
    reply(
      url.includes('?')
        ? list
        : { ...fixture.before, service_minutes: null, due_at: null },
    ),
  )
  mount()
  expect(await screen.findByText('未知')).toBeVisible()
  expect(screen.getByText('未设置')).toBeVisible()
  expect(screen.queryByLabelText('优先级')).not.toBeInTheDocument()
})
it('prohibits mock writes', async () => {
  mount(fixture.before.task_id, 'normal')
  expect(
    await screen.findByRole('button', { name: '保存任务修改' }),
  ).toBeDisabled()
})
it('resets server pagination when changing status', async () => {
  transport.mockImplementation(async (url) =>
    reply({
      ...list,
      total: 21,
      offset: Number(new URL(url, 'http://test').searchParams.get('offset')),
    }),
  )
  mount('')
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '下一页' }))
  await screen.findByText('第 2 页')
  await user.selectOptions(screen.getByLabelText('状态筛选'), 'cancelled')
  await waitFor(() =>
    expect(
      transport.mock.calls.some(
        ([url]) => url === '/api/v1/tasks?status=cancelled&limit=20&offset=0',
      ),
    ).toBe(true),
  )
})
it('preserves saved result if list refresh fails', async () => {
  let saved = false
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'PATCH') {
      saved = true
      return reply(fixture.response)
    }
    if (url.includes('?'))
      return saved
        ? reply({ code: 'database_unavailable', message: 'failed' }, 503)
        : reply(list)
    return reply(fixture.before)
  })
  mount()
  await userEvent.click(
    await screen.findByRole('button', { name: '保存任务修改' }),
  )
  expect(await screen.findByText('任务已保存')).toBeVisible()
  expect(await screen.findByText(/保留上次列表/)).toBeVisible()
})
it('does not present a read failure as empty', async () => {
  transport.mockResolvedValue(
    reply({ code: 'database_unavailable', message: 'failed' }, 503),
  )
  mount('')
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.queryByText('当前筛选下没有任务。')).not.toBeInTheDocument()
})
it('shows no input change for an acknowledged no-op', async () => {
  transport.mockImplementation(async (url, init) =>
    reply(
      init.method === 'PATCH'
        ? fixtures.noop.response
        : url.includes('?')
          ? list
          : fixtures.noop.before,
    ),
  )
  mount(fixtures.noop.before.task_id)
  const user = userEvent.setup()
  await user.selectOptions(await screen.findByLabelText('任务操作'), 'label')
  await user.selectOptions(
    screen.getByLabelText('新的损伤标签'),
    fixtures.noop.before.damage_label,
  )
  await user.click(screen.getByRole('button', { name: '保存任务修改' }))
  expect(await screen.findByText(/本次未改变规划输入/)).toBeVisible()
})
