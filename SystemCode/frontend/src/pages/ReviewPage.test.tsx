import {
  act,
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

it('scrolls mobile review detail after loading and does not jump again on retry', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  let resolveDetail!: (value: Response) => void
  const deferred = new Promise<Response>((resolve) => { resolveDetail = resolve })
  const queue = { items: [fixture.before], total: 1, limit: 20, offset: 0 }
  transport.mockImplementation(async (url) => url.includes('?') ? reply(queue) : deferred)
  mount('')
  const pane = screen.getByLabelText('Review details workspace')
  const scroll = vi.fn()
  Object.defineProperty(pane, 'scrollIntoView', { value: scroll })
  await userEvent.click(await screen.findByRole('button', { name: new RegExp(`Pending review.*${fixture.before.inspection_id}`) }))
  expect(pane).toHaveFocus()
  expect(scroll).not.toHaveBeenCalled()
  await act(async () => resolveDetail(reply(fixture.before)))
  expect(await screen.findByRole('heading', { name: 'Inspection details' })).toBeVisible()
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: 'start', behavior: 'instant' })
  transport.mockImplementation(async (url) => reply(url.includes('?') ? queue : fixture.before))
  await userEvent.click(screen.getByRole('button', { name: 'Reload and check' }))
  await screen.findByRole('heading', { name: 'Inspection details' })
  expect(scroll).toHaveBeenCalledTimes(1)
  expect(transport.mock.calls.some(([, init]) => init.method === 'POST')).toBe(false)
})

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
  const button = await screen.findByRole('button', { name: 'Save review decision' })
  await userEvent.click(button)
  expect(
    await screen.findByRole('heading', { name: 'Review saved' }),
  ).toBeVisible()
  expect(await screen.findByText('No inspections are awaiting review.')).toBeVisible()
  expect(screen.getByText(/Route recalculation status was not provided/)).toBeVisible()
  expect(screen.getByText(/Read-only/)).toBeVisible()
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
    await user.selectOptions(await screen.findByLabelText('Action'), action)
    if (action === 'correct') {
      const selector = screen.getByLabelText('Corrected label')
      expect(within(selector).getAllByRole('option')).toHaveLength(9)
      await user.selectOptions(selector, 'pothole_deep')
    }
    await user.type(screen.getByLabelText(/Review notes/), 'Checked photo')
    await user.click(screen.getByRole('button', { name: 'Save review decision' }))
    await screen.findByRole('heading', { name: 'Review saved' })
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
      expect(screen.getByText('No task is linked to this result.')).toBeVisible()
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
  await user.click(await screen.findByRole('button', { name: 'Save review decision' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The record has changed')
  expect(screen.getByRole('button', { name: 'Save review decision' })).toBeDisabled()
  expect(
    transport.mock.calls.filter(([, init]) => init.method === 'POST'),
  ).toHaveLength(1)
  await user.click(screen.getByRole('button', { name: 'Reload and check' }))
  await user.click(await screen.findByRole('button', { name: 'Save review decision' }))
  await screen.findByRole('heading', { name: 'Review saved' })
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
  await user.click(await screen.findByRole('button', { name: 'Save review decision' }))
  const retry = await screen.findByRole('button', {
    name: 'Retry review with original request',
  })
  expect(screen.getByLabelText('Action')).toBeDisabled()
  await user.click(retry)
  expect(
    await screen.findByRole('heading', { name: 'Original request result recovered' }),
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
    await screen.findByRole('button', { name: 'Save review decision' })
  ).closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  await waitFor(() =>
    expect(
      transport.mock.calls.filter(([, init]) => init.method === 'POST'),
    ).toHaveLength(1),
  )
  expect(screen.getByRole('button', { name: 'Saving review…' })).toBeDisabled()
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
  expect(await screen.findByText(/Read-only/)).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Save review decision' }),
  ).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Review history' })).toBeVisible()
})

it('prevents writes in mock mode', async () => {
  mount(fixture.before.inspection_id, 'normal')
  expect(
    await screen.findByRole('button', { name: 'Save review decision' }),
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
  expect(await screen.findByRole('alert')).toHaveTextContent('The database is temporarily unavailable')
  expect(screen.queryByText('No inspections are awaiting review.')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Refresh review queue' })).toBeEnabled()
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
  await user.click(await screen.findByRole('button', { name: 'Next page' }))
  await screen.findByText('No pending records remain on this page. Go to the previous page.')
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
    await screen.findByRole('button', { name: 'Save review decision' }),
  )
  expect(
    await screen.findByRole('heading', { name: 'Review saved' }),
  ).toBeVisible()
  expect(await screen.findByText(/Previous list retained/)).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Save review decision' }),
  ).not.toBeInTheDocument()
})

it.each(['completed', 'failed', 'not_needed'] as const)('shows %s route feedback and retains the saved task without another write', async (status) => {
  const original = transport.getMockImplementation()!
  transport.mockImplementation(async (url, init) => {
    const response = await original(url, init)
    if (init.method === 'POST') response.headers.set('X-RoadGuard-Replanning', status)
    return response
  })
  mount()
  await userEvent.click(await screen.findByRole('button', { name: 'Save review decision' }))
  const result = await screen.findByRole('region', { name: 'Review result' })
  expect(within(result).getByText(/Linked task:/)).toBeVisible()
  expect(within(result).getByText(status === 'failed' ? /Task saved; automatic route recalculation failed/ : status === 'completed' ? /Automatic GA and Greedy route recalculation completed/ : /No additional route recalculation was needed/)).toBeVisible()
  expect(transport.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1)
})
