import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it } from 'vitest'
import fixtures from '../test/planning-fixtures.json'
import { parseModel, type Model } from '../api/contracts'
import {
  boundaryPoints,
  crewColor,
  makeProjection,
  referenceDepot,
} from '../map/geography'
import RouteMap from './RouteMap'
function plan(): Model<'RoutePlan'> {
  return parseModel('RoutePlan', structuredClone(fixtures.plans.ga))
}
function mount(
  value: Model<'RoutePlan'> | null = plan(),
  snapshot?: Model<'TaskSnapshot'>,
  revision?: number,
  readFailed = false,
) {
  return render(
    <MemoryRouter>
      <RouteMap
        plan={value}
        snapshot={snapshot}
        currentRevision={revision}
        readFailed={readFailed}
      />
    </MemoryRouter>,
  )
}
it('projects all frozen boundary vertices and outside depot within the default viewport', () => {
  const project = makeProjection([...boundaryPoints, referenceDepot])
  for (const point of [...boundaryPoints, referenceDepot]) {
    const [x, y] = project(point)
    expect(x).toBeGreaterThanOrEqual(20)
    expect(x).toBeLessThanOrEqual(880)
    expect(y).toBeGreaterThanOrEqual(20)
    expect(y).toBeLessThanOrEqual(540)
  }
  expect(project({ longitude: 103.77, latitude: 1.32 })[0]).toBeGreaterThan(
    project({ longitude: 103.7, latitude: 1.32 })[0],
  )
  expect(project({ longitude: 103.7, latitude: 1.34 })[1]).toBeLessThan(
    project({ longitude: 103.7, latitude: 1.3 })[1],
  )
})
it('keeps distinct stable colors for the four configured crews independent of order', () => {
  const ids = ['crew-01', 'crew-02', 'crew-03', 'crew-04']
  expect(new Set(ids.map(crewColor)).size).toBe(4)
  expect([...ids].reverse().map(crewColor).reverse()).toEqual(
    ids.map(crewColor),
  )
})
it('shows only boundaries and depot if no plan exists', () => {
  mount(null)
  expect(screen.getAllByTestId('boundary')).toHaveLength(2)
  expect(screen.getByText(/仅显示冻结服务区域和基地/)).toBeVisible()
  expect(screen.queryByTestId('route-crew-01')).not.toBeInTheDocument()
  expect(screen.getByText(/路线顺序示意，非道路导航/)).toBeVisible()
})
it('draws ordered depot-to-stops points and adds return only when saved settings require it', () => {
  const value = plan()
  const route = value.crew_routes.find((item) => item.stops.length)!
  const original = route.stops[0]
  route.stops = [
    { ...original, task_id: 'second', sequence: 2, latitude: 1.345 },
    { ...original, task_id: 'first', sequence: 1 },
  ]
  value.settings.return_to_depot = true
  const view = mount(value)
  const line = screen.getByTestId(`route-${route.crew_id}`)
  const coords = line.getAttribute('points')!.split(' ')
  const projection = makeProjection([
    ...boundaryPoints,
    referenceDepot,
    value.depot,
    ...route.stops,
  ])
  expect(coords).toEqual(
    [value.depot, route.stops[1], route.stops[0], value.depot].map((point) =>
      projection(point).join(','),
    ),
  )
  expect(
    value.crew_routes.find((item) => item.stops.length)!.stops[0].sequence,
  ).toBe(2)
  view.unmount()
  value.settings.return_to_depot = false
  mount(value)
  expect(
    screen
      .getByTestId(`route-${route.crew_id}`)
      .getAttribute('points')!
      .split(' '),
  ).toHaveLength(3)
})
it('links a keyboard-selected map stop to saved timing, crew and current task detail', async () => {
  const value = plan()
  const route = value.crew_routes.find((item) => item.stops.length)!
  const stop = route.stops[0]
  mount(value)
  fireEvent.keyDown(
    screen.getByRole('button', {
      name: `${route.crew_id} 第 ${stop.sequence} 站 ${stop.task_id}`,
    }),
    { key: 'Enter' },
  )
  const detail = screen.getByRole('region', { name: '选中停靠点' })
  expect(within(detail).getByText(/到达/)).toHaveTextContent('新加坡')
  expect(within(detail).getByRole('link')).toHaveAttribute(
    'href',
    `/tasks?task=${stop.task_id}`,
  )
  expect(screen.getByRole('region', { name: '选中队伍' })).toHaveTextContent(
    '返基地',
  )
  await userEvent.click(screen.getByRole('button', { name: '定位所选停靠点' }))
  expect(
    screen.getByRole('group', { name: 'Jurong 地理示意图，北朝上' }),
  ).not.toHaveAttribute('viewBox', '0 0 900 560')
  await userEvent.click(screen.getByRole('button', { name: '全域与基地' }))
  expect(
    screen.getByRole('group', { name: 'Jurong 地理示意图，北朝上' }),
  ).toHaveAttribute('viewBox', '0 0 900 560')
})
it('lets list selection highlight a stop even when map points overlap', async () => {
  const value = plan()
  const route = value.crew_routes.find((item) => item.stops.length)!
  const stop = route.stops[0]
  mount(value)
  await userEvent.click(
    screen.getByRole('button', { name: `${route.crew_id} · 已分配` }),
  )
  await userEvent.click(
    screen.getByRole('button', {
      name: `第 ${stop.sequence} 站：${stop.task_id}`,
    }),
  )
  expect(
    screen.getByRole('button', {
      name: `${route.crew_id} 第 ${stop.sequence} 站 ${stop.task_id}`,
    }),
  ).toHaveAttribute('aria-pressed', 'true')
})
it('retains unavailable and idle crews but draws no fictitious routes for them', () => {
  const value = plan()
  mount(value)
  for (const route of value.crew_routes.filter((item) => !item.stops.length))
    expect(
      screen.queryByTestId(`route-${route.crew_id}`),
    ).not.toBeInTheDocument()
  expect(
    within(screen.getByLabelText('队伍图例')).getAllByRole('button'),
  ).toHaveLength(4)
  expect(screen.getByRole('button', { name: 'crew-01 · 停用' })).toBeVisible()
})
it('lists all unassigned reasons without using coordinates from another revision', async () => {
  const value = parseModel('RoutePlan', fixtures.all_off_plans.ga)
  mount(
    value,
    parseModel('TaskSnapshot', fixtures.snapshot),
    fixtures.snapshot.input_revision,
  )
  const id = value.unassigned_tasks[0].task_id
  expect(
    screen.queryByRole('button', { name: `未分配 ${id}` }),
  ).not.toBeInTheDocument()
  expect(
    screen.getByRole('region', { name: '地图未分配任务' }),
  ).toHaveTextContent('无可用队伍')
  await userEvent.click(screen.getByRole('button', { name: id }))
  expect(
    screen.getByRole('region', { name: '选中未分配任务' }),
  ).toHaveTextContent('缺少同版本位置')
})
it('plots unassigned points only from a matching revision snapshot', () => {
  const value = parseModel('RoutePlan', fixtures.all_off_plans.ga)
  const snapshot = parseModel('TaskSnapshot', {
    ...fixtures.snapshot,
    input_revision: value.input_revision,
  })
  mount(value, snapshot)
  expect(
    screen.getByRole('button', {
      name: `未分配 ${value.unassigned_tasks[0].task_id}`,
    }),
  ).toBeVisible()
})
it('keeps stale and failed read warnings next to the map', () => {
  const value = plan()
  mount(value, undefined, value.input_revision + 1, true)
  expect(screen.getByRole('alert')).toHaveTextContent('未经重新验证')
  expect(screen.getByRole('status')).toHaveTextContent('已过期')
})
it('distinguishes external travel data in the collapsed summary and preserves full provenance', async () => {
  const value = plan()
  value.matrix_is_simulated = false
  value.matrix_provider = 'google_routes'
  mount(value)
  const source = screen.getByText(/外部行程数据.*查看来源/)
  expect(source).toBeVisible()
  expect(screen.getByText(/google_routes/)).not.toBeVisible()
  await userEvent.click(source)
  expect(screen.getByText(/google_routes/)).toBeVisible()
  expect(screen.getByText(value.plan_id)).toBeVisible()
  expect(screen.getByText(/非道路导航/)).toBeVisible()
})
it('displays null return time as unknown and zero as zero minutes', async () => {
  const value = plan()
  value.crew_routes[0].return_travel_minutes = null
  mount(value)
  await userEvent.click(screen.getByRole('button', { name: 'crew-01 · 停用' }))
  expect(screen.getByRole('region', { name: '选中队伍' })).toHaveTextContent(
    '返程行驶 未提供',
  )
  expect(screen.getByRole('region', { name: '选中队伍' })).toHaveTextContent(
    '行程 0 分钟',
  )
})
