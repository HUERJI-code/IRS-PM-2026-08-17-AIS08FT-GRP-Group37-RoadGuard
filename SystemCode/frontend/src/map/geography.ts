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
  unknown_service_minutes: 'Unknown repair duration',
  unreachable_from_depot: 'Unreachable from depot',
  unreachable_to_depot: 'Cannot return to depot',
  no_available_crew: 'No available crews',
  exceeds_shift_limit: 'Exceeds shift limit',
  no_feasible_route_position: 'No feasible insertion position',
}
