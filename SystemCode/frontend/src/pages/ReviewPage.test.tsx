import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import fixtures from '../test/review-fixtures.json'
import { ApiContext, type ApiContextValue } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel } from '../api/contracts'
import ReviewPage from './ReviewPage'

const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
let transport: ReturnType<typeof vi.fn<Transport>>
const fixture = fixtures.confirm
function mount(
  id = fixture.before.inspection_id,
  mode: ApiContextValue['mode'] = 'live',
) {
  const value: ApiContextValue = {
    mode,
    setMode: vi.fn(),
    api: createApiClient(transport),
    imageUrl: (path) => path,
  }
  return render(
    <ApiContext.Provider value={value}>
      <MemoryRouter
        initialEntries={[id ? '/reviews?inspection=' + id : '/reviews']}
      >
        <ReviewPage />
      </MemoryRouter>
    </ApiContext.Provider>,
  )
}
beforeEach(() => {
  let saved = false
  transport = vi.fn<Transport>().mockImplementation(async (url, init) => {
    if (init.method === 'POST') {
      saved = true
      return reply(fixture.response)
    }
    if (url.includes('?'))
      return reply({
        items: saved ? [] : [fixture.before],
        total: saved ? 0 : 1,
        limit: 20,
        offset: 0,
      })
    return reply(saved ? fixture.response.inspection : fixture.before)
  })
})
afterEach(() => vi.unstubAllGlobals())

it('validates all backend-generated review and replay fixtures', () => {
  for (const value of Object.values(fixtures)) {
    expect(() => parseModel('InspectionResponse', value.before)).not.toThrow()
    expect(() =>
      parseModel('InspectionMutationResponse', value.response),
    ).not.toThrow()
    expect(() =>
      parseModel('InspectionMutationResponse', value.replay),
    ).not.toThrow()
  }
})

it('loads the queue and fresh detail before confirmation, then refreshes the queue', async () => {
  mount()
  const button = await screen.findByRole('button', { name: '保存审核决定' })
  await userEvent.click(button)
  expect(
    await screen.findByRole('heading', { name: '审核已保存' }),
  ).toBeVisible()
  expect(await screen.findByText('当前没有待审核巡检。')).toBeVisible()
  expect(screen.getByText(/已有路线需要重新规划/)).toBeVisible()
  expect(screen.getByText(/当前为只读/)).toBeVisible()
  const request = transport.mock.calls.find(
    ([, init]) => init.method === 'POST',
  )!
  expect(JSON.parse(request[1].body as string)).toMatchObject({
    action: 'confirm',
    expected_version: fixture.before.record_version,
    detection_id: fixture.before.detections[0].detection_id,
  })
  expect(JSON.parse(request[1].body as string)).not.toHaveProperty(
    'damage_label',
  )
  expect(
    transport.mock.calls.some(([url]) => url.includes('recalculate')),
  ).toBe(false)
})

it.each(['correct', 'dismiss'] as const)(
  'sends only the allowed fields for %s',
  async (action) => {
    const sample = fixtures[action]
    transport.mockImplementation(async (url, init) => {
      if (init.method === 'POST') return reply(sample.response)
      if (url.includes('?'))
        return reply({ items: [sample.before], total: 1, limit: 20, offset: 0 })
      return reply(sample.before)
    })
    mount(sample.before.inspection_id)
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('操作'), action)
    if (action === 'correct') {
      const selector = screen.getByLabelText('纠正后的标签')
      expect(within(selector).getAllByRole('option')).toHaveLength(9)
      await user.selectOptions(selector, 'pothole_deep')
    }
    await user.type(screen.getByLabelText(/审核备注/), 'Checked photo')
    await user.click(screen.getByRole('button', { name: '保存审核决定' }))
    await screen.findByRole('heading', { name: '审核已保存' })
    const request = JSON.parse(
      transport.mock.calls.find(([, init]) => init.method === 'POST')![1]
        .body as string,
    )
    expect(request.action).toBe(action)
    expect(request.note).toBe('Checked photo')
    if (action === 'correct')
      expect(request).toMatchObject({
        damage_label: 'pothole_deep',
        detection_id: sample.before.detections[0].detection_id,
      })
    else {
      expect(request).not.toHaveProperty('damage_label')
      expect(request).not.toHaveProperty('detection_id')
      expect(screen.getByText('本次结果没有关联任务。')).toBeVisible()
    }
  },
)

it('does not repeat a decision after a version conflict; reload uses the new version and ID', async () => {
  let attempted = false
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'POST') {
      if (!attempted) {
        attempted = true
        return reply({ code: 'stale_record_version', message: 'changed' }, 409)
      }
      return reply(fixture.response)
    }
    if (url.includes('?'))
      return reply({ items: [fixture.before], total: 1, limit: 20, offset: 0 })
    return reply({ ...fixture.before, record_version: attempted ? 2 : 1 })
  })
  mount()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '保存审核决定' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('记录已被修改')
  expect(screen.getByRole('button', { name: '保存审核决定' })).toBeDisabled()
  expect(
    transport.mock.calls.filter(([, init]) => init.method === 'POST'),
  ).toHaveLength(1)
  await user.click(screen.getByRole('button', { name: '重新读取并检查' }))
  await user.click(await screen.findByRole('button', { name: '保存审核决定' }))
  await screen.findByRole('heading', { name: '审核已保存' })
  const bodies = transport.mock.calls
    .filter(([, init]) => init.method === 'POST')
    .map(([, init]) => JSON.parse(init.body as string))
  expect(bodies[1].expected_version).toBe(2)
  expect(bodies[0].request_id).not.toBe(bodies[1].request_id)
})

it('retries an uncertain response using the same request ID and payload', async () => {
  let first = true
  const base = transport.getMockImplementation()!
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'POST') {
      if (first) {
        first = false
        throw new TypeError('offline')
      }
      return reply(fixture.replay)
    }
    return base(url, init)
  })
  mount()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '保存审核决定' }))
  const retry = await screen.findByRole('button', {
    name: '使用原请求重试审核',
  })
  expect(screen.getByLabelText('操作')).toBeDisabled()
  await user.click(retry)
  expect(
    await screen.findByRole('heading', { name: '已恢复原请求结果' }),
  ).toBeVisible()
  const bodies = transport.mock.calls
    .filter(([, init]) => init.method === 'POST')
    .map(([, init]) => init.body)
  expect(bodies).toHaveLength(2)
  expect(bodies[0]).toBe(bodies[1])
})

it('blocks double submission while the response is pending', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'POST' ? new Promise(() => {}) : base(url, init),
  )
  mount()
  const form = (
    await screen.findByRole('button', { name: '保存审核决定' })
  ).closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  await waitFor(() =>
    expect(
      transport.mock.calls.filter(([, init]) => init.method === 'POST'),
    ).toHaveLength(1),
  )
  expect(screen.getByRole('button', { name: '正在保存审核…' })).toBeDisabled()
})

it('renders already processed records without editable actions', async () => {
  transport.mockImplementation(async (url) =>
    reply(
      url.includes('?')
        ? { items: [], total: 0, limit: 20, offset: 0 }
        : fixture.response.inspection,
    ),
  )
  mount()
  expect(await screen.findByText(/当前为只读/)).toBeVisible()
  expect(
    screen.queryByRole('button', { name: '保存审核决定' }),
  ).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '审核历史' })).toBeVisible()
})

it('prevents writes in mock mode', async () => {
  mount(fixture.before.inspection_id, 'normal')
  expect(
    await screen.findByRole('button', { name: '保存审核决定' }),
  ).toBeDisabled()
  expect(transport.mock.calls.some(([, init]) => init.method === 'POST')).toBe(
    false,
  )
})

it('shows queue read errors without claiming there are no pending inspections', async () => {
  transport.mockResolvedValue(
    reply({ code: 'database_unavailable', message: 'failed' }, 503),
  )
  mount('')
  expect(await screen.findByRole('alert')).toHaveTextContent('数据库暂不可用')
  expect(screen.queryByText('当前没有待审核巡检。')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '刷新待审队列' })).toBeEnabled()
})

it('paginates using pending_review and never fetches other statuses', async () => {
  transport.mockImplementation(async (url) => {
    const offset = Number(
      new URL(url, 'http://test').searchParams.get('offset') ?? 0,
    )
    return reply({
      items: offset ? [] : [fixture.before],
      total: 21,
      limit: 20,
      offset,
    })
  })
  mount('')
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '下一页' }))
  await screen.findByText('当前页已无待审记录，请返回上一页。')
  expect(transport.mock.calls[1][0]).toContain(
    'status=pending_review&limit=20&offset=20',
  )
})

it('preserves a successful review when queue refresh fails', async () => {
  let saved = false
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'POST') {
      saved = true
      return reply(fixture.response)
    }
    if (url.includes('?'))
      return saved
        ? reply(
            { code: 'database_unavailable', message: 'failed refresh' },
            503,
          )
        : reply({ items: [fixture.before], total: 1, limit: 20, offset: 0 })
    return reply(fixture.before)
  })
  mount()
  await userEvent.click(
    await screen.findByRole('button', { name: '保存审核决定' }),
  )
  expect(
    await screen.findByRole('heading', { name: '审核已保存' }),
  ).toBeVisible()
  expect(await screen.findByText(/保留上次列表/)).toBeVisible()
  expect(
    screen.queryByRole('button', { name: '保存审核决定' }),
  ).not.toBeInTheDocument()
})
