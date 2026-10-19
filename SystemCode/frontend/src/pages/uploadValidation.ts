import type { UploadMetadata } from '../api/contracts'

export async function validateImage(file: File): Promise<void> {
  if (!['image/jpeg', 'image/png'].includes(file.type))
    throw new Error('Select a JPEG or PNG image.')
  if (file.size === 0 || file.size > 8 * 1024 * 1024)
    throw new Error('The image must not be empty or exceed 8 MiB.')
  let image: ImageBitmap
  try {
    image = await createImageBitmap(file)
  } catch {
    throw new Error('Cannot decode the image. Select a valid JPEG or PNG.')
  }
  try {
    if (image.width * image.height > 20_000_000)
      throw new Error('The image must not exceed 20 MP. Reduce its resolution first.')
  } finally {
    image.close()
  }
}

export function uploadMetadata(
  mode: 'real' | 'demo',
  latitude: string,
  longitude: string,
  declared: boolean,
  scenario: string,
): UploadMetadata {
  if (!latitude.trim() || !longitude.trim())
    throw new Error('Enter the latitude and longitude where the photo was taken.')
  const lat = Number(latitude),
    lon = Number(longitude)
  if (
    !Number.isFinite(lat) ||
    lat < -90 ||
    lat > 90 ||
    !Number.isFinite(lon) ||
    lon < -180 ||
    lon > 180
  )
    throw new Error('Enter valid latitude and longitude.')
  if (!declared) throw new Error('Confirm that this location is an eligible public motor road.')
  const position = {
    latitude: lat,
    longitude: lon,
    road_type: 'public_motor_road' as const,
  }
  if (mode === 'real') return { ...position, mode }
  if (!scenario) throw new Error('Select a specific mock detection scenario.')
  return { ...position, mode, scenario_id: scenario }
}
