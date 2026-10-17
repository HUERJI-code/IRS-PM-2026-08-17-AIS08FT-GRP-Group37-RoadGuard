import type { UploadMetadata } from '../api/contracts'

export async function validateImage(file: File): Promise<void> {
  if (!['image/jpeg', 'image/png'].includes(file.type))
    throw new Error('请选择 JPEG 或 PNG 图片。')
  if (file.size === 0 || file.size > 8 * 1024 * 1024)
    throw new Error('图片不能为空，且不能超过 8 MiB。')
  let image: ImageBitmap
  try {
    image = await createImageBitmap(file)
  } catch {
    throw new Error('无法解码图片，请重新选择有效的 JPEG 或 PNG。')
  }
  try {
    if (image.width * image.height > 20_000_000)
      throw new Error('图片不能超过 20 MP，请先缩小分辨率。')
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
    throw new Error('请填写照片拍摄位置的纬度和经度。')
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
    throw new Error('请输入有效的经纬度。')
  if (!declared) throw new Error('请确认该位置属于允许的公共机动车道路。')
  const position = {
    latitude: lat,
    longitude: lon,
    road_type: 'public_motor_road' as const,
  }
  if (mode === 'real') return { ...position, mode }
  if (!scenario) throw new Error('请选择明确的模拟检测案例。')
  return { ...position, mode, scenario_id: scenario }
}
