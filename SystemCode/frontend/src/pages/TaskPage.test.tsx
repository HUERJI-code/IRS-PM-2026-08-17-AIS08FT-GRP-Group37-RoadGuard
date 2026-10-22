import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import fixtures from '../test/task-fixtures.json'
import { ApiContext, type ApiContextValue } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel } from '../api/contracts'
import { mockFixtures } from '../api/mock/transport'
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
    const pane = screen.getByLabelText('Task details workspace')
    const scroll = vi.fn()
    Object.defineProperty(pane, 'scrollIntoView', { value: scroll })
    const button = await screen.findByRole('button', { name: new RegExp(`P[123].*Active.*${fixture.before.task_id}`) })
    await userEvent.click(button)
    expect(pane).toHaveFocus()
    expect(scroll).not.toHaveBeenCalled()
    await act(async () => resolveDetail(reply(fixture.before)))
    expect(await screen.findByRole('heading', { name: 'Task details' })).toBeVisible()
    expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: 'start', behavior: 'instant' })
    expect(button).toHaveAttribute('aria-current', 'true')
    transport.mockImplementation(async (url) => reply(url.includes('?') ? list : fixture.before))
    await userEvent.click(screen.getByRole('button', { name: 'Reload and check' }))
    await screen.findByRole('heading', { name: 'Task details' })
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
    await user.selectOptions(await screen.findByLabelText('Task action'), action)
    if (action === 'label')
      await user.selectOptions(
        screen.getByLabelText('New damage label'),
        'pothole_deep',
      )
    if (action === 'location') {
      await user.clear(screen.getByLabelText('Latitude'))
      await user.type(screen.getByLabelText('Latitude'), '1.3406')
      await user.click(screen.getByRole('checkbox'))
    }
    await user.click(screen.getByRole('button', { name: 'Save task changes' }))
    expect(await screen.findByText('Task saved')).toBeVisible()
    expect(JSON.parse(writes()[0][1].body as string)).toEqual({
      ...sample.request,
      request_id: expect.any(String),
    })
    expect(screen.getByText(/Existing routes may be stale/)).toBeVisible()
    expect(
      transport.mock.calls.some(([url]) => url.includes('recalculate')),
    ).toBe(false)
    if (action === 'completed' || action === 'cancelled') {
      expect(screen.getByText(/Final-state tasks are read-only/)).toBeVisible()
      expect(screen.queryByLabelText('Task action')).not.toBeInTheDocument()
    }
  },
)
it('requires coordinates and road declaration', async () => {
  mount()
  const user = userEvent.setup()
  await user.selectOptions(await screen.findByLabelText('Task action'), 'location')
  await user.clear(screen.getByLabelText('Latitude'))
  await user.click(screen.getByRole('button', { name: 'Save task changes' }))
  expect(writes()).toHaveLength(0)
  expect(screen.getByLabelText('Latitude')).toBeInvalid()
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
  await user.click(await screen.findByRole('button', { name: 'Save task changes' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The record has changed')
  expect(screen.getByRole('button', { name: 'Save task changes' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Reload and check' }))
  await user.click(await screen.findByRole('button', { name: 'Save task changes' }))
  await screen.findByText('Task saved')
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
  await user.click(await screen.findByRole('button', { name: 'Save task changes' }))
  const retry = await screen.findByRole('button', {
    name: 'Retry task with original request',
  })
  expect(screen.getByLabelText('Task action')).toBeDisabled()
  expect(screen.getByLabelText('Status filter')).toBeDisabled()
  await user.click(retry)
  await screen.findByText('Original request result recovered')
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
    await screen.findByRole('button', { name: 'Save task changes' })
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
    expect(await screen.findByText(/Final-state tasks are read-only/)).toBeVisible()
    expect(screen.queryByLabelText('Task action')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Task history' })).toBeVisible()
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
  expect(await screen.findByText('Unknown')).toBeVisible()
  expect(screen.getByText('Not set')).toBeVisible()
  expect(screen.queryByLabelText('Priority')).not.toBeInTheDocument()
})
it('prohibits mock writes', async () => {
  mount(fixture.before.task_id, 'normal')
  expect(
    await screen.findByRole('button', { name: 'Save task changes' }),
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
  await user.click(await screen.findByRole('button', { name: 'Next page' }))
  await screen.findByText('Page 2')
  await user.selectOptions(screen.getByLabelText('Status filter'), 'cancelled')
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
    await screen.findByRole('button', { name: 'Save task changes' }),
  )
  expect(await screen.findByText('Task saved')).toBeVisible()
  expect(await screen.findByText(/Previous list retained/)).toBeVisible()
})
it('does not present a read failure as empty', async () => {
  transport.mockResolvedValue(
    reply({ code: 'database_unavailable', message: 'failed' }, 503),
  )
  mount('')
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.queryByText('No tasks match this filter.')).not.toBeInTheDocument()
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
  await user.selectOptions(await screen.findByLabelText('Task action'), 'label')
  await user.selectOptions(
    screen.getByLabelText('New damage label'),
    fixtures.noop.before.damage_label,
  )
  await user.click(screen.getByRole('button', { name: 'Save task changes' }))
  expect(await screen.findByText(/Planning inputs are unchanged/)).toBeVisible()
})

it('loads the source inspection photo only when the photo section is opened', async () => {
  const inspection = {
    ...mockFixtures.normal['/inspections'].items[0],
    inspection_id: fixture.before.inspection_id,
  }
  transport.mockImplementation(async (url, init) =>
    reply(
      url.includes('/inspections/')
        ? inspection
        : init.method === 'PATCH'
          ? fixture.response
          : url.includes('?')
            ? list
            : fixture.before,
    ),
  )
  mount()
  const summary = await screen.findByText('View road photo')
  const inspectionReads = () =>
    transport.mock.calls.filter(([url]) => url.includes('/inspections/'))
  expect(inspectionReads()).toHaveLength(0)
  await userEvent.setup().click(summary)
  expect(
    await screen.findByAltText('Server-normalised inspection photo'),
  ).toHaveAttribute('src', inspection.image_url)
  expect(inspectionReads()[0][0]).toContain(fixture.before.inspection_id)
})
