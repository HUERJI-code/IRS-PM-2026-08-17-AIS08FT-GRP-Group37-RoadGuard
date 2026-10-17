import { StrictMode } from 'react'
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'
import fixtures from '../test/planning-fixtures.json'
import { ApiContext, type ApiContextValue } from '../api/context'
import { createApiClient, type Transport } from '../api/client'
import { parseModel } from '../api/contracts'
import RoutesPage from './RoutesPage'
import PlanningRunProvider from '../planning/PlanningRunProvider'
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
const failure = (code: string, status = 409) =>
  reply({ code, message: 'test' }, status)
let transport: ReturnType<typeof vi.fn<Transport>>
let changed: boolean
beforeEach(() => {
  changed = false
  transport = vi.fn<Transport>().mockImplementation(async (url, init) => {
    if (init.method === 'PATCH') {
      changed = true
      return reply(fixtures.mutation)
    }
    if (init.method === 'POST')
      return reply({
        ...fixtures.calculation,
        input_revision: changed
          ? fixtures.after_snapshot.input_revision
          : fixtures.snapshot.input_revision,
      })
    if (url === '/api/v1/crews')
      return reply(changed ? fixtures.after_crews : fixtures.crews)
    if (url.startsWith('/api/v1/tasks/snapshot'))
      return reply(changed ? fixtures.after_snapshot : fixtures.snapshot)
    if (url.includes('/latest'))
      return reply(fixtures.stale[url.includes('greedy') ? 'greedy' : 'ga'])
    const plan = Object.values(fixtures.plans).find((p) =>
      url.endsWith(p.plan_id),
    )
    return plan ? reply(plan) : failure('not_found', 404)
  })
})
function mount(mode: ApiContextValue['mode'] = 'live') {
  return render(
    <ApiContext.Provider
      value={{
        api: createApiClient(transport),
        mode,
        setMode: vi.fn(),
        imageUrl: (path) => path,
      }}
    >
      <MemoryRouter>
        <StrictMode>
          <PlanningRunProvider><RoutesPage /></PlanningRunProvider>
        </StrictMode>
      </MemoryRouter>
    </ApiContext.Provider>,
  )
}
const writes = (method: string) =>
  transport.mock.calls.filter(([, init]) => init.method === method)
async function loaded() {
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '停用 Crew 02' })).toBeEnabled(),
  )
}
it('validates actual backend fixtures', () => {
  expect(() => parseModel('CrewMutation', fixtures.mutation)).not.toThrow()
  expect(() => parseModel('CrewMutation', fixtures.replay)).not.toThrow()
  expect(() =>
    parseModel('RecalculationResult', fixtures.calculation),
  ).not.toThrow()
  for (const plan of Object.values(fixtures.plans))
    expect(() => parseModel('RoutePlan', plan)).not.toThrow()
})
it('shows all configured crews and checks a complete task snapshot without writes', async () => {
  mount()
  await loaded()
  expect(
    within(screen.getByRole('region', { name: '工程队管理' })).getAllByRole(
      'button',
    ),
  ).toHaveLength(4)
  expect(
    transport.mock.calls.some(
      ([url]) =>
        url ===
        `/api/v1/tasks/snapshot?expected_revision=${fixtures.crews.input_revision}`,
    ),
  ).toBe(true)
  expect(writes('PATCH')).toHaveLength(0)
  expect(writes('POST')).toHaveLength(0)
})
it('saves availability then explicitly recalculates using the returned revision', async () => {
  mount()
  await loaded()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '停用 Crew 01' }))
  await screen.findByText('队伍状态已保存')
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
    ).toBeEnabled(),
  )
  expect(writes('POST')).toHaveLength(0)
  expect(JSON.parse(writes('PATCH')[0][1].body as string)).toEqual({
    request_id: expect.any(String),
    expected_version: 1,
    available: false,
  })
  await user.click(screen.getByRole('button', { name: '重算 GA 与 Greedy' }))
  await screen.findByText('本次重算已完成')
  expect(JSON.parse(writes('POST')[0][1].body as string)).toEqual({
    expected_revision: fixtures.mutation.input_revision,
  })
  expect(screen.getByText(/以上两个方案 ID 来自同一次/)).toBeVisible()
  await waitFor(() =>
    expect(
      transport.mock.calls.some(([url]) =>
        url.endsWith(fixtures.plans.ga.plan_id),
      ),
    ).toBe(true),
  )
})
it('retains saved availability when matrix fails and retry never repeats PATCH', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'POST'
      ? Promise.resolve(failure('travel_matrix_unavailable', 503))
      : base(url, init),
  )
  mount()
  await loaded()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '停用 Crew 01' }))
  await screen.findByText('队伍状态已保存')
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
    ).toBeEnabled(),
  )
  await user.click(screen.getByRole('button', { name: '重算 GA 与 Greedy' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('行程数据暂不可用')
  expect(screen.getByRole('button', { name: '启用 Crew 01' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: '重算 GA 与 Greedy' }))
  expect(writes('PATCH')).toHaveLength(1)
  expect(writes('POST')).toHaveLength(2)
})
it('retries an unknown crew write with the identical request and locks recalculation', async () => {
  const base = transport.getMockImplementation()!
  let first = true
  transport.mockImplementation(async (url, init) => {
    if (init.method === 'PATCH') {
      if (first) {
        first = false
        throw new TypeError('offline')
      }
      changed = true
      return reply(fixtures.replay)
    }
    return base(url, init)
  })
  mount()
  await loaded()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '停用 Crew 01' }))
  const retry = await screen.findByRole('button', {
    name: '使用原请求重试队伍修改',
  })
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  await user.click(retry)
  await screen.findByText('已恢复队伍修改结果')
  expect(writes('PATCH')[1][1].body).toBe(writes('PATCH')[0][1].body)
})
it('requires rereading after crew version conflict without automatic retry', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'PATCH'
      ? Promise.resolve(failure('stale_record_version'))
      : base(url, init),
  )
  mount()
  await loaded()
  await userEvent.click(screen.getByRole('button', { name: '停用 Crew 01' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: '停用 Crew 01' })).toBeDisabled()
  expect(writes('PATCH')).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: '刷新输入与方案' }))
  await loaded()
  expect(writes('PATCH')).toHaveLength(1)
})
it('blocks recalculation when snapshot revision has changed', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    url.includes('/tasks/snapshot')
      ? Promise.resolve(failure('stale_input_revision'))
      : base(url, init),
  )
  mount()
  expect(await screen.findByRole('alert')).toHaveTextContent('任务或队伍已变化')
  expect(
    screen.queryByRole('button', { name: '重算 GA 与 Greedy' }),
  ).not.toBeInTheDocument()
  expect(writes('POST')).toHaveLength(0)
})
it('requires refresh after recalculation revision conflict', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'POST'
      ? Promise.resolve(failure('stale_input_revision'))
      : base(url, init),
  )
  mount()
  await loaded()
  await userEvent.click(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  )
  await screen.findByRole('alert')
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  expect(writes('POST')).toHaveLength(1)
})
it('unknown recalculation requires a read-only check and explicit new-calculation acknowledgement', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'POST'
      ? Promise.reject(new TypeError('offline'))
      : base(url, init),
  )
  mount()
  await loaded()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '重算 GA 与 Greedy' }))
  await screen.findByText('重算结果尚不确定')
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  await user.click(screen.getByRole('button', { name: '核对输入与已保存方案' }))
  const checkbox = await screen.findByRole('checkbox')
  expect(writes('POST')).toHaveLength(1)
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  await user.click(checkbox)
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeEnabled()
})
it('keeps successful calculation if detail read fails and query refresh does not POST', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    url.includes('/route-plans/plan-')
      ? Promise.resolve(failure('database_unavailable', 503))
      : base(url, init),
  )
  changed = true
  mount()
  await loaded()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '重算 GA 与 Greedy' }))
  await screen.findByText('本次重算已完成')
  expect(
    await within(screen.getByRole('region', { name: '已保存方案' })).findByText(
      /方案读取失败/,
    ),
  ).toBeVisible()
  await user.click(screen.getByRole('button', { name: '刷新输入与方案' }))
  expect(writes('POST')).toHaveLength(1)
})
it('prevents duplicate calculation while pending', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    init.method === 'POST' ? new Promise(() => {}) : base(url, init),
  )
  mount()
  await loaded()
  const button = screen.getByRole('button', { name: '重算 GA 与 Greedy' })
  fireEvent.click(button)
  fireEvent.click(button)
  expect(writes('POST')).toHaveLength(1)
})
it('distinguishes missing plans from valid empty plans and prohibits mock writes', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    url.includes('/latest')
      ? Promise.resolve(failure('route_plan_not_found', 404))
      : base(url, init),
  )
  mount('normal')
  expect(
    await screen.findAllByText('尚未生成方案（不等于空任务方案）。'),
  ).toHaveLength(2)
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  expect(screen.getByRole('button', { name: '停用 Crew 01' })).toBeDisabled()
})
it('shows all stopped crews and backend unassigned reasons without inventing assignments', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    url.includes('/latest')
      ? Promise.resolve(
          reply(
            fixtures.all_off_plans[url.includes('greedy') ? 'greedy' : 'ga'],
          ),
        )
      : base(url, init),
  )
  mount()
  await loaded()
  expect(await screen.findAllByText(/no_available_crew/)).toHaveLength(2)
  expect(screen.getAllByText(/crew-01：停用/)).toHaveLength(2)
})

it('preserves crew save and blocks new actions if snapshot read after save fails', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    changed && url.includes('/tasks/snapshot')
      ? Promise.resolve(failure('database_unavailable', 503))
      : base(url, init),
  )
  mount()
  await loaded()
  await userEvent.click(screen.getByRole('button', { name: '停用 Crew 01' }))
  expect(await screen.findByText('队伍状态已保存')).toBeVisible()
  expect(await screen.findByRole('alert')).toHaveTextContent('数据库暂不可用')
  expect(screen.getByRole('button', { name: '启用 Crew 01' })).toBeDisabled()
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeDisabled()
  expect(writes('PATCH')).toHaveLength(1)
})
it('does not fabricate tasks when the snapshot is empty', async () => {
  const base = transport.getMockImplementation()!
  transport.mockImplementation((url, init) =>
    url.includes('/tasks/snapshot')
      ? Promise.resolve(reply({ ...fixtures.snapshot, tasks: [], total: 0 }))
      : base(url, init),
  )
  mount()
  await loaded()
  expect(screen.getByText(/活动任务 0 项/)).toBeVisible()
  expect(
    screen.getByRole('button', { name: '重算 GA 与 Greedy' }),
  ).toBeEnabled()
  expect(writes('POST')).toHaveLength(0)
})

it('switches map algorithms without mixing saved plan IDs or causing writes', async () => {
  mount()
  await loaded()
  const map = screen.getByRole('region', { name: '路线地图与详情' })
  expect(map).toHaveTextContent(fixtures.stale.ga.plan_id)
  await userEvent.selectOptions(screen.getByLabelText('地图方案'), 'greedy')
  expect(
    screen.getByRole('region', { name: '路线地图与详情' }),
  ).toHaveTextContent(fixtures.stale.greedy.plan_id)
  expect(
    screen.getByRole('region', { name: '路线地图与详情' }),
  ).not.toHaveTextContent(fixtures.stale.ga.plan_id)
  expect(writes('PATCH')).toHaveLength(0)
  expect(writes('POST')).toHaveLength(0)
})
