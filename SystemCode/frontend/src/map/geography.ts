import boundaryText from '../../../../Miscellaneous/geography/jurong-boundary-mp2025.geojson?raw'
import depotText from '../../../../Miscellaneous/geography/nus-iss-depot.geojson?raw'

export type Point = { longitude: number; latitude: number }
type Boundary = {
  type: 'FeatureCollection'
  features: {
    properties: { PLN_AREA_N: string }
    geometry: { type: 'Polygon'; coordinates: number[][][] }
  }[]
}
// Frozen repository files are the shared source; no runtime download or simplified boundary.
export const boundary = JSON.parse(boundaryText) as Boundary
const depotData = JSON.parse(depotText).features[0]
export const referenceDepot: Point = {
  longitude: depotData.geometry.coordinates[0],
  latitude: depotData.geometry.coordinates[1],
}
export const boundaryPoints = boundary.features.flatMap((feature) =>
  feature.geometry.coordinates.flatMap((ring) =>
    ring.map(([longitude, latitude]) => ({ longitude, latitude })),
  ),
)
const colors = ['#1565c0', '#a8490b', '#7b35a2', '#12734a']
export function crewColor(id: string) {
  const fixed = /^crew-0([1-4])$/.exec(id)
  if (fixed) return colors[Number(fixed[1]) - 1]
  let hash = 0
  for (const character of id) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  return colors[hash % colors.length]
}
export function makeProjection(points: Point[]) {
  const cos = Math.cos((referenceDepot.latitude * Math.PI) / 180)
  const xs = points.map((point) => point.longitude * cos),
    ys = points.map((point) => -point.latitude)
  const west = Math.min(...xs),
    east = Math.max(...xs),
    north = Math.min(...ys),
    south = Math.max(...ys)
  const scale = Math.min(
    840 / Math.max(east - west, 0.001),
    500 / Math.max(south - north, 0.001),
  )
  const centerX = (west + east) / 2,
    centerY = (north + south) / 2
  return (point: Point): [number, number] => [
    450 + (point.longitude * cos - centerX) * scale,
    280 + (-point.latitude - centerY) * scale,
  ]
}
export const unassignedReasons: Record<string, string> = {
  unknown_service_minutes: '维修时长未知',
  unreachable_from_depot: '从基地不可达',
  unreachable_to_depot: '无法返回基地',
  no_available_crew: '无可用队伍',
  exceeds_shift_limit: '超过班次限制',
  no_feasible_route_position: '无可行插入位置',
}
