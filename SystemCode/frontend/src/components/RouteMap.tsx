import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Model } from '../api/contracts'
import { formatMinutes, formatSingaporeTime, stopTime } from '../api/format'
import {
  boundary,
  boundaryPoints,
  crewColor,
  makeProjection,
  referenceDepot,
  unassignedReasons,
} from '../map/geography'

type Props = {
  plan?: Model<'RoutePlan'> | null
  snapshot?: Model<'TaskSnapshot'>
  currentRevision?: number
  readFailed?: boolean
}
export default function RouteMap({
  plan,
  snapshot,
  currentRevision,
  readFailed,
}: Props) {
  const [selected, setSelected] = useState('')
  const [crew, setCrew] = useState('')
  const [zoom, setZoom] = useState(1)
  const [center, setCenter] = useState<[number, number]>([450, 280])
  const depot = plan?.depot ?? referenceDepot
  const routes = plan?.crew_routes ?? []
  const stops = routes.flatMap((route) =>
    route.stops.map((stop) => ({ ...stop, crew_id: route.crew_id })),
  )
  const sameSnapshot =
    !!plan && snapshot?.input_revision === plan.input_revision
  const unassigned = (plan?.unassigned_tasks ?? []).map((item) => ({
    ...item,
    point: sameSnapshot
      ? snapshot?.tasks.find((task) => task.task_id === item.task_id)
      : undefined,
  }))
  const project = makeProjection([
    ...boundaryPoints,
    referenceDepot,
    depot,
    ...stops,
    ...unassigned.flatMap((item) => (item.point ? [item.point] : [])),
  ])
  const selectedStop = stops.find((stop) => stop.task_id === selected)
  const selectedUnassigned = unassigned.find(
    (item) => item.task_id === selected,
  )
  const selectedRoute = routes.find((route) => route.crew_id === crew)
  const stale =
    !!plan &&
    (plan.is_stale ||
      (currentRevision !== undefined &&
        plan.input_revision !== currentRevision))
  function choose(task: string, id: string) {
    setSelected(task)
    setCrew(id)
  }
  function focusPoint(point: { longitude: number; latitude: number }) {
    setCenter(project(point))
    setZoom(2)
  }
  const [depotX, depotY] = project(depot)
  return (
    <section className="route-map-panel" aria-label="路线地图与详情">
      <h2>Jurong 与四队路线地图</h2>
      <p className="notice">
        路线顺序示意，非道路导航。线段连接保存的停靠点，不代表真实道路或可通行路径。
      </p>
      {readFailed && (
        <p role="alert">方案读取失败，当前地图保留旧快照，未经重新验证。</p>
      )}
      {stale && <p role="status">当前地图方案已过期，不能作为最新调度结果。</p>}
      {plan ? (
        <p>
          {plan.algorithm.toUpperCase()} · 方案{' '}
          <span className="record-id">{plan.plan_id}</span> · 输入版本{' '}
          {plan.input_revision} · 开始{' '}
          {formatSingaporeTime(plan.planning_start_at)} ·{' '}
          {plan.matrix_is_simulated ? '模拟行程矩阵' : '外部行程数据'}（
          {plan.matrix_provider}）
        </p>
      ) : (
        <p>尚无可展示方案；仅显示冻结服务区域和基地，不虚构任务或路线。</p>
      )}
      <div className="map-controls" aria-label="地图视野控制">
        <button
          onClick={() => setZoom((value) => Math.min(8, value * 1.5))}
          disabled={zoom >= 8}
        >
          放大
        </button>
        <button
          onClick={() => setZoom((value) => Math.max(1, value / 1.5))}
          disabled={zoom <= 1}
        >
          缩小
        </button>
        <button
          onClick={() => {
            setCenter([450, 280])
            setZoom(1)
          }}
        >
          全域与基地
        </button>
        <button
          aria-label="向西移动地图"
          onClick={() => setCenter(([x, y]) => [x - 100 / zoom, y])}
        >
          ←
        </button>
        <button
          aria-label="向北移动地图"
          onClick={() => setCenter(([x, y]) => [x, y - 100 / zoom])}
        >
          ↑
        </button>
        <button
          aria-label="向南移动地图"
          onClick={() => setCenter(([x, y]) => [x, y + 100 / zoom])}
        >
          ↓
        </button>
        <button
          aria-label="向东移动地图"
          onClick={() => setCenter(([x, y]) => [x + 100 / zoom, y])}
        >
          →
        </button>
      </div>
      <svg
        className="route-map"
        viewBox={`${center[0] - 450 / zoom} ${center[1] - 280 / zoom} ${900 / zoom} ${560 / zoom}`}
        role="group"
        aria-label="Jurong 地理示意图，北朝上"
      >
        <title>Jurong East、Jurong West 与 NUS-ISS 基地，北朝上</title>
        <rect
          x="-10000"
          y="-10000"
          width="20000"
          height="20000"
          fill="#f4f7f2"
        />
        {boundary.features.map((feature, index) => (
          <path
            key={feature.properties.PLN_AREA_N}
            data-testid="boundary"
            d={feature.geometry.coordinates
              .map(
                (ring) =>
                  'M ' +
                  ring
                    .map(([longitude, latitude]) =>
                      project({ longitude, latitude }).join(','),
                    )
                    .join(' L ') +
                  ' Z',
              )
              .join(' ')}
            fill={index ? '#cfe3ce' : '#deead0'}
            fillRule="evenodd"
            stroke="#6f856c"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          >
            <title>{feature.properties.PLN_AREA_N}</title>
          </path>
        ))}
        {boundary.features.map((feature) => {
          const points = feature.geometry.coordinates.flat()
          const xs = points.map((point) => point[0]),
            ys = points.map((point) => point[1])
          const [x, y] = project({
            longitude: (Math.min(...xs) + Math.max(...xs)) / 2,
            latitude: (Math.min(...ys) + Math.max(...ys)) / 2,
          })
          return (
            <text
              key={`name-${feature.properties.PLN_AREA_N}`}
              x={x}
              y={y}
              textAnchor="middle"
              fontSize="14"
              fill="#39503d"
              pointerEvents="none"
            >
              {feature.properties.PLN_AREA_N}
            </text>
          )
        })}
        {routes.map((route) => {
          const ordered = [...route.stops].sort(
            (a, b) => a.sequence - b.sequence,
          )
          if (!ordered.length) return null
          const points = [
            depot,
            ...ordered,
            ...(plan?.settings.return_to_depot ? [depot] : []),
          ]
          return (
            <polyline
              key={route.crew_id}
              data-testid={`route-${route.crew_id}`}
              points={points.map((point) => project(point).join(',')).join(' ')}
              fill="none"
              stroke={crewColor(route.crew_id)}
              strokeWidth={crew === route.crew_id ? 4 : 2}
              strokeDasharray="7 5"
              opacity={!crew || crew === route.crew_id ? 1 : 0.3}
              vectorEffect="non-scaling-stroke"
            >
              <title>
                {route.crew_id} 按保存顺序的示意线
                {plan?.settings.return_to_depot ? '，包含返程' : ''}
              </title>
            </polyline>
          )
        })}
        {stops.map((stop) => {
          const [x, y] = project(stop)
          return (
            <g
              key={stop.task_id}
              role="button"
              tabIndex={0}
              aria-label={`${stop.crew_id} 第 ${stop.sequence} 站 ${stop.task_id}`}
              aria-pressed={selected === stop.task_id}
              onClick={() => choose(stop.task_id, stop.crew_id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  choose(stop.task_id, stop.crew_id)
                }
              }}
              className="map-marker"
            >
              <circle
                cx={x}
                cy={y}
                r={selected === stop.task_id ? 13 : 10}
                fill={crewColor(stop.crew_id)}
                stroke="white"
                strokeWidth="2"
              />
              <text
                x={x}
                y={y + 4}
                textAnchor="middle"
                fill="white"
                fontSize="11"
              >
                {stop.sequence}
              </text>
              <title>
                {stop.task_id} · {stop.priority}
              </title>
            </g>
          )
        })}
        {unassigned.map((item) => {
          if (!item.point) return null
          const [x, y] = project(item.point)
          return (
            <g
              key={item.task_id}
              role="button"
              tabIndex={0}
              aria-label={`未分配 ${item.task_id}`}
              onClick={() => choose(item.task_id, '')}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  choose(item.task_id, '')
                }
              }}
              className="map-marker"
            >
              <rect
                x={x - 8}
                y={y - 8}
                width="16"
                height="16"
                fill="#555"
                stroke="white"
                strokeWidth="2"
              />
              <text
                x={x}
                y={y + 4}
                textAnchor="middle"
                fill="white"
                fontSize="11"
              >
                !
              </text>
            </g>
          )
        })}
        <g>
          <path
            d={`M ${depotX} ${depotY - 12} L ${depotX + 12} ${depotY} L ${depotX} ${depotY + 12} L ${depotX - 12} ${depotY} Z`}
            fill="#202b26"
          />
          <text x={depotX - 8} y={depotY + 28} textAnchor="end" fontSize="13">
            NUS-ISS 基地
          </text>
        </g>
      </svg>
      <p className="field-note">
        北 ↑ · 绿色区域：Jurong East /
        West；菱形：基地；彩色圆点：队伍停靠序号；灰色方点：未分配任务。重合点可用下方任务列表逐一选择。
      </p>
      <p>
        边界：URA Master Plan 2025，冻结版本 jurong-je-jw-mp2025-v1，获取于
        2026-10-12。
        <a href="https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view">
          数据来源
        </a>{' '}
        ·{' '}
        <a href="https://data.gov.sg/open-data-licence">
          Singapore Open Data Licence
        </a>
        。规划边界不代表道路维修权限。基地为 NUS-ISS
        建筑参考点，模拟调度用途，不是已验证驾驶入口。
      </p>
      <div className="map-legend" aria-label="队伍图例">
        {routes.map((route) => (
          <button
            key={route.crew_id}
            aria-pressed={crew === route.crew_id}
            onClick={() => {
              setCrew(crew === route.crew_id ? '' : route.crew_id)
              setSelected('')
            }}
          >
            <span style={{ background: crewColor(route.crew_id) }} />
            {route.crew_id} ·{' '}
            {
              { assigned: '已分配', idle: '闲置', unavailable: '停用' }[
                route.status
              ]
            }
          </button>
        ))}
      </div>
      {selectedRoute && (
        <section className="notice" aria-label="选中队伍">
          <h3>{selectedRoute.crew_id} 路线详情</h3>
          <p>
            行程 {formatMinutes(selectedRoute.travel_minutes)} · 维修{' '}
            {formatMinutes(selectedRoute.service_minutes)} · 总工作{' '}
            {formatMinutes(selectedRoute.total_work_minutes)}
          </p>
          <p>
            返基地：
            {plan?.settings.return_to_depot
              ? '本方案要求返程'
              : '本方案不要求返程'}{' '}
            · 返程行驶{' '}
            {selectedRoute.return_travel_minutes === null
              ? '未提供'
              : formatMinutes(selectedRoute.return_travel_minutes)}{' '}
            · 结束{' '}
            {plan && stopTime(plan.planning_start_at, selectedRoute.end_minute)}
          </p>
        </section>
      )}
      {selectedStop && plan && (
        <section className="notice" aria-label="选中停靠点">
          <h3>
            第 {selectedStop.sequence} 站 · {selectedStop.crew_id}
          </h3>
          <p>
            {selectedStop.task_id} · {selectedStop.priority} · 位置{' '}
            {selectedStop.latitude}, {selectedStop.longitude}
          </p>
          <p>
            上一点至本站{' '}
            {formatMinutes(selectedStop.travel_minutes_from_previous)} · 维修{' '}
            {formatMinutes(selectedStop.service_minutes)}
          </p>
          <p>
            到达 {stopTime(plan.planning_start_at, selectedStop.arrival_minute)}{' '}
            · 完成{' '}
            {stopTime(plan.planning_start_at, selectedStop.completion_minute)}
          </p>
          <Link to={`/tasks?task=${selectedStop.task_id}`}>
            查看当前任务详情
          </Link>
          <p>地图时间与位置来自保存方案；当前任务可能已发生修改。</p>
          <button onClick={() => focusPoint(selectedStop)}>
            定位所选停靠点
          </button>
        </section>
      )}
      {selectedUnassigned && (
        <section className="notice" aria-label="选中未分配任务">
          <h3>未分配任务</h3>
          <p>
            {selectedUnassigned.task_id}：
            {unassignedReasons[selectedUnassigned.reason] ??
              selectedUnassigned.reason}
          </p>
          <Link to={`/tasks?task=${selectedUnassigned.task_id}`}>
            查看当前任务详情
          </Link>
          {selectedUnassigned.point ? (
            <button onClick={() => focusPoint(selectedUnassigned.point!)}>
              定位未分配任务
            </button>
          ) : (
            <p>缺少同版本位置，未在地图上标点。</p>
          )}
        </section>
      )}
      {routes.map((route) => (
        <details key={route.crew_id} open={crew === route.crew_id}>
          <summary>
            {route.crew_id} 保存的停靠顺序（{route.stops.length} 站）
          </summary>
          {!route.stops.length ? (
            <p>
              {route.available
                ? '该队闲置，没有路线。'
                : '该队停用，没有路线。'}
            </p>
          ) : (
            <ol>
              {[...route.stops]
                .sort((a, b) => a.sequence - b.sequence)
                .map((stop) => (
                  <li key={stop.task_id} value={stop.sequence}>
                    <button
                      className="text-button"
                      aria-pressed={selected === stop.task_id}
                      onClick={() => choose(stop.task_id, route.crew_id)}
                    >
                      第 {stop.sequence} 站：{stop.task_id}
                    </button>{' '}
                    · {stop.priority}
                  </li>
                ))}
            </ol>
          )}
        </details>
      ))}
      <section aria-label="地图未分配任务">
        <h3>未分配任务（{unassigned.length}）</h3>
        {unassigned.length > 0 && !sameSnapshot && (
          <p>
            方案未保存未分配任务坐标，当前快照版本不一致或不可用；全部任务仍列出，但不混用新坐标标点。
          </p>
        )}
        <ul>
          {unassigned.map((item) => (
            <li key={item.task_id}>
              <button
                className="text-button"
                onClick={() => choose(item.task_id, '')}
              >
                {item.task_id}
              </button>
              ：{unassignedReasons[item.reason] ?? item.reason}
              {!item.point ? ' · 位置不可用' : ''}
            </li>
          ))}
        </ul>
      </section>
    </section>
  )
}
