export function formatMinutes(value: number | null | undefined): string {
  return value == null
    ? '未提供'
    : `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)} 分钟`
}
export function formatRuntime(value: number | null | undefined): string {
  return value == null
    ? '未提供'
    : `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)} 毫秒`
}
export function formatSingaporeTime(value: string | null | undefined): string {
  if (value == null) return '未提供'
  if (
    !/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ||
    !Number.isFinite(Date.parse(value))
  )
    return '无效时间'
  return (
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Singapore',
      dateStyle: 'medium',
      timeStyle: 'short',
      hourCycle: 'h23',
    }).format(new Date(value)) + '（新加坡）'
  )
}
export function stopTime(start: string, offsetMinutes: number | null): string {
  if (offsetMinutes === null) return '未提供'
  if (
    !Number.isFinite(offsetMinutes) ||
    offsetMinutes < 0 ||
    formatSingaporeTime(start) === '无效时间'
  )
    return '无效时间'
  return formatSingaporeTime(
    new Date(Date.parse(start) + offsetMinutes * 60000).toISOString(),
  )
}
