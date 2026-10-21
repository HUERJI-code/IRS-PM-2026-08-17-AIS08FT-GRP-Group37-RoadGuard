export function formatMinutes(value: number | null | undefined): string {
  return value == null
    ? 'Not provided'
    : `${new Intl.NumberFormat('en-SG', { maximumFractionDigits: 2 }).format(value)} min`
}
export function formatRuntime(value: number | null | undefined): string {
  return value == null
    ? 'Not provided'
    : `${new Intl.NumberFormat('en-SG', { maximumFractionDigits: 2 }).format(value)} ms`
}
export function formatSingaporeTime(value: string | null | undefined): string {
  if (value == null) return 'Not provided'
  if (
    !/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ||
    !Number.isFinite(Date.parse(value))
  )
    return 'Invalid time'
  return (
    new Intl.DateTimeFormat('en-SG', {
      timeZone: 'Asia/Singapore',
      dateStyle: 'medium',
      timeStyle: 'short',
      hourCycle: 'h23',
    }).format(new Date(value)) + ' (Singapore)'
  )
}
export function stopTime(start: string, offsetMinutes: number | null): string {
  if (offsetMinutes === null) return 'Not provided'
  if (
    !Number.isFinite(offsetMinutes) ||
    offsetMinutes < 0 ||
    formatSingaporeTime(start) === 'Invalid time'
  )
    return 'Invalid time'
  return formatSingaporeTime(
    new Date(Date.parse(start) + offsetMinutes * 60000).toISOString(),
  )
}
