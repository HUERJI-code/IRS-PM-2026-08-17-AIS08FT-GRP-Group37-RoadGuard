import type { Model } from '../api/contracts'
import { boundary, boundaryPoints, crewColor, makeProjection } from '../map/geography'

type Props = {
  plan: Pick<Model<'RoutePlan'>, 'depot' | 'settings'>
  route: Model<'RoutePlan'>['crew_routes'][number]
  selected: string
}

/** Coordinates and order come from the saved plan, never from live task edits. */
export default function CrewRouteMap({ plan, route, selected }: Props) {
  const stops = [...route.stops].sort((a, b) => a.sequence - b.sequence)
  const project = makeProjection([...boundaryPoints, plan.depot, ...stops])
  const color = crewColor(route.crew_id)
  const [x, y] = project(plan.depot)
  const points = [plan.depot, ...stops]
  if (plan.settings.return_to_depot) points.push(plan.depot)
  return (
    <details className="crew-map-details">
      <summary>查看本队路线示意图</summary>
      <p>编号对应下方停靠顺序。示意线连接保存的坐标，不是道路导航或实时位置。</p>
      <svg viewBox="0 0 900 560" role="img" aria-label={`${route.crew_id} 路线顺序示意图，北朝上`}>
        <rect width="900" height="560" rx="18" fill="#f1f6f5" />
        {boundary.features.map((feature) => (
          <path key={feature.properties.PLN_AREA_N}
            d={feature.geometry.coordinates.map((ring) => 'M ' + ring.map(([longitude, latitude]) => project({ longitude, latitude }).join(',')).join(' L ') + ' Z').join(' ')}
            fill="#d9e9e0" stroke="#9db9ac" fillRule="evenodd" strokeWidth="1.5">
            <title>{feature.properties.PLN_AREA_N}</title>
          </path>
        ))}
        <polyline points={points.map((point) => project(point).join(',')).join(' ')} fill="none" stroke={color} strokeWidth="3" strokeDasharray="8 6" />
        {stops.map((stop) => {
          const [sx, sy] = project(stop)
          return <g key={stop.task_id}>
            <title>{`第 ${stop.sequence} 站 · ${stop.task_id}`}</title>
            {stop.task_id === selected && <circle cx={sx} cy={sy} r="23" fill="none" stroke={color} strokeWidth="3" />}
            <circle cx={sx} cy={sy} r="16" fill={color} stroke="white" strokeWidth="3" />
            <text x={sx} y={sy + 6} textAnchor="middle" fill="white" fontSize="17" fontWeight="700">{stop.sequence}</text>
          </g>
        })}
        <rect x={x - 9} y={y - 9} width="18" height="18" rx="4" fill="#183c4c" />
        <text x={x - 12} y={y + 32} textAnchor="end" fill="#183c4c" fontSize="18">NUS-ISS 出发基地</text>
        <text x="865" y="38" textAnchor="middle" fill="#607c78" fontSize="18">↑ N</text>
      </svg>
    </details>
  )
}
