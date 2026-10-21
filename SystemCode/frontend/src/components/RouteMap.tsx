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
    <section className="route-map-panel" aria-label="Route map and details">
      <h2>Jurong and four-crew route map</h2>
      <p className="notice">
        Route order diagram, not road navigation. Lines connect saved stops and do not represent actual roads or accessible paths.
      </p>
      {readFailed && (
        <p role="alert">Plan loading failed. The map retains an old snapshot that has not been revalidated.</p>
      )}
      {stale && <p role="status">The displayed plan is stale and cannot be used as the latest dispatch result.</p>}
      {plan ? (
        <details className="map-provenance">
          <summary>{plan.algorithm.toUpperCase()} · Input revision {plan.input_revision} · {plan.matrix_is_simulated ? 'Simulated travel matrix' : 'External travel data'} · View source</summary>
          <p>Plan{' '}
          <span className="record-id">{plan.plan_id}</span> · Input revision{' '}
          {plan.input_revision} · Start{' '}
          {formatSingaporeTime(plan.planning_start_at)} ·{' '}
          {plan.matrix_is_simulated ? 'Simulated travel matrix' : 'External travel data'} (
          {plan.matrix_provider})
          </p>
        </details>
      ) : (
        <p>No plan is available to display. Only the frozen service area and depot are shown; no tasks or routes are invented.</p>
      )}
      {plan && <div className="plan-at-a-glance" aria-label="Selected plan overview">
        <div><span>Assigned tasks</span><strong>{plan.metrics.assigned_task_count}<small> {plan.metrics.assigned_task_count === 1 ? 'task' : 'tasks'}</small></strong></div>
        <div><span>Unassigned tasks</span><strong>{plan.metrics.unassigned_task_count}<small> {plan.metrics.unassigned_task_count === 1 ? 'task' : 'tasks'}</small></strong></div>
        <div><span>Total travel</span><strong>{formatMinutes(plan.metrics.total_travel_minutes)}</strong></div>
      </div>}
      <div className="map-controls" aria-label="Map view controls">
        <button
          onClick={() => setZoom((value) => Math.min(8, value * 1.5))}
          disabled={zoom >= 8}
        >
          Zoom in
        </button>
        <button
          onClick={() => setZoom((value) => Math.max(1, value / 1.5))}
          disabled={zoom <= 1}
        >
          Zoom out
        </button>
        <button
          onClick={() => {
            setCenter([450, 280])
            setZoom(1)
          }}
        >
          Full area and depot
        </button>
        <button
          aria-label="Pan map west"
          onClick={() => setCenter(([x, y]) => [x - 100 / zoom, y])}
        >
          ←
        </button>
        <button
          aria-label="Pan map north"
          onClick={() => setCenter(([x, y]) => [x, y - 100 / zoom])}
        >
          ↑
        </button>
        <button
          aria-label="Pan map south"
          onClick={() => setCenter(([x, y]) => [x, y + 100 / zoom])}
        >
          ↓
        </button>
        <button
          aria-label="Pan map east"
          onClick={() => setCenter(([x, y]) => [x + 100 / zoom, y])}
        >
          →
        </button>
      </div>
      <svg
        className="route-map"
        viewBox={`${center[0] - 450 / zoom} ${center[1] - 280 / zoom} ${900 / zoom} ${560 / zoom}`}
        role="group"
        aria-label="Jurong Geographic diagram, north up"
      >
        <title>Jurong East, Jurong West and NUS-ISS depot, north up</title>
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
                {route.crew_id} Diagram lines in saved order
                {plan?.settings.return_to_depot ? ', Includes return journey' : ''}
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
              aria-label={`${stop.crew_id} Stop ${stop.sequence} ${stop.task_id}`}
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
              aria-label={`Unassigned ${item.task_id}`}
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
            NUS-ISS Depot
          </text>
        </g>
      </svg>
      <p className="field-note">
        N ↑ · Green area: Jurong East /
        West; Diamond: depot; coloured circles: crew stop numbers; grey squares: unassigned tasks. Select overlapping points individually from the task list below.
      </p>
      <details className="map-provenance"><summary>Map coverage, depot and data sources</summary><p>
        Boundary: URA Master Plan 2025, frozen version jurong-je-jw-mp2025-v1, retrieved
        2026-10-12.
        <a href="https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view">
          Data source
        </a>{' '}
        ·{' '}
        <a href="https://data.gov.sg/open-data-licence">
          Singapore Open Data Licence
        </a>
        . Planning boundaries do not establish road maintenance authority. The depot is the NUS-ISS
        building reference point for simulated dispatch, not a verified vehicle entrance.
      </p></details>
      <div className="map-legend" aria-label="Crew legend">
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
              { assigned: 'Assigned', idle: 'Idle', unavailable: 'Unavailable' }[
                route.status
              ]
            }
          </button>
        ))}
      </div>
      {selectedRoute && (
        <section className="notice" aria-label="Selected crew">
          <h3>{selectedRoute.crew_id} Route details</h3>
          <p>
            Travel {formatMinutes(selectedRoute.travel_minutes)} · Repair{' '}
            {formatMinutes(selectedRoute.service_minutes)} · Total work{' '}
            {formatMinutes(selectedRoute.total_work_minutes)}
          </p>
          <p>
            Return to depot:
            {plan?.settings.return_to_depot
              ? 'Return required by this plan'
              : 'Return not required by this plan'}{' '}
            · Return travel{' '}
            {selectedRoute.return_travel_minutes === null
              ? 'Not provided'
              : formatMinutes(selectedRoute.return_travel_minutes)}{' '}
            · End{' '}
            {plan && stopTime(plan.planning_start_at, selectedRoute.end_minute)}
          </p>
        </section>
      )}
      {selectedStop && plan && (
        <section className="notice" aria-label="Selected stop">
          <h3>
            Stop {selectedStop.sequence} · {selectedStop.crew_id}
          </h3>
          <p>
            {selectedStop.task_id} · {selectedStop.priority} · Location{' '}
            {selectedStop.latitude}, {selectedStop.longitude}
          </p>
          <p>
            Travel from previous stop{' '}
            {formatMinutes(selectedStop.travel_minutes_from_previous)} · Repair{' '}
            {formatMinutes(selectedStop.service_minutes)}
          </p>
          <p>
            Arrival {stopTime(plan.planning_start_at, selectedStop.arrival_minute)}{' '}
            · Completion{' '}
            {stopTime(plan.planning_start_at, selectedStop.completion_minute)}
          </p>
          <Link to={`/tasks?task=${selectedStop.task_id}`}>
            View current task details
          </Link>
          <p>Map times and locations come from the saved plan. Current tasks may have changed.</p>
          <button onClick={() => focusPoint(selectedStop)}>
            Focus selected stop
          </button>
        </section>
      )}
      {selectedUnassigned && (
        <section className="notice" aria-label="Selected unassigned task">
          <h3>Unassigned tasks</h3>
          <p>
            {selectedUnassigned.task_id}:
            {unassignedReasons[selectedUnassigned.reason] ??
              selectedUnassigned.reason}
          </p>
          <Link to={`/tasks?task=${selectedUnassigned.task_id}`}>
            View current task details
          </Link>
          {selectedUnassigned.point ? (
            <button onClick={() => focusPoint(selectedUnassigned.point!)}>
              Focus unassigned task
            </button>
          ) : (
            <p>No location from the same revision; not plotted on the map.</p>
          )}
        </section>
      )}
      {routes.map((route) => (
        <details key={route.crew_id} open={crew === route.crew_id}>
          <summary>
            {route.crew_id} Saved stop order (Stops: {route.stops.length})
          </summary>
          {!route.stops.length ? (
            <p>
              {route.available
                ? 'This crew is idle and has no route.'
                : 'This crew is unavailable and has no route.'}
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
                      Stop {stop.sequence}: {stop.task_id}
                    </button>{' '}
                    · {stop.priority}
                  </li>
                ))}
            </ol>
          )}
        </details>
      ))}
      <section aria-label="Unassigned map tasks">
        <h3>Unassigned tasks ({unassigned.length})</h3>
        {unassigned.length > 0 && !sameSnapshot && (
          <p>
            The plan has no saved coordinates for unassigned tasks, and the current snapshot is unavailable or has a different revision. All tasks remain listed; newer coordinates are not mixed into this map.
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
              : {unassignedReasons[item.reason] ?? item.reason}
              {!item.point ? ' · Location unavailable' : ''}
            </li>
          ))}
        </ul>
      </section>
    </section>
  )
}
