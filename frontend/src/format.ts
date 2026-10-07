const ZONE = 'Asia/Phnom_Penh'

export function today() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONE }).format(new Date())
}

export function thisMonth() {
  return today().slice(0, 7)
}

export function formatDay(localDate: string) {
  const [year, month, day] = localDate.split('-').map(Number)
  if (!year || !month || !day) return localDate
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC',
    day: '2-digit',
    month: 'short',
  }).format(new Date(Date.UTC(year, month - 1, day)))
}

export function formatTime(timestamp: string | null) {
  if (!timestamp) return '—'
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return timestamp
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const hour = parts.find((part) => part.type === 'hour')?.value ?? '00'
  const minute = parts.find((part) => part.type === 'minute')?.value ?? '00'
  return `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
}

export function minutes(value: number) {
  if (!value) return '—'
  if (value < 60) return `${value} min`
  const rest = value % 60
  return rest ? `${Math.floor(value / 60)}h ${rest}m` : `${value / 60}h`
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    present: 'Present',
    late: 'Late',
    left_early: 'Left early',
    incomplete: 'Incomplete',
    absent: 'Absent',
    on_leave: 'On leave',
    holiday: 'Holiday',
    due: 'Not in yet',
  }
  return labels[status] ?? status
}

export function statusClass(status: string) {
  if (status === 'present' || status === 'approved' || status === 'active') return 'chip chip-good'
  if (status === 'absent' || status === 'rejected' || status === 'disabled') return 'chip chip-danger'
  if (status === 'late' || status === 'left_early' || status === 'incomplete' || status === 'pending') {
    return 'chip chip-warn'
  }
  if (status === 'on_leave' || status === 'holiday') return 'chip chip-neutral'
  return 'chip'
}

export function capitalize(value: string) {
  return value ? value[0]!.toUpperCase() + value.slice(1).replace(/_/g, ' ') : value
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  const first = parts[0]![0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]![0] ?? '') : (parts[0]![1] ?? '')
  return (first + last).toUpperCase()
}

function shiftDate(localDate: string, days: number) {
  const [year, month, day] = localDate.split('-').map(Number)
  const date = new Date(Date.UTC(year!, month! - 1, day! + days))
  return date.toISOString().slice(0, 10)
}

export function weekStart(localDate = today()) {
  const [year, month, day] = localDate.split('-').map(Number)
  const weekday = new Date(Date.UTC(year!, month! - 1, day!)).getUTCDay()
  return shiftDate(localDate, -((weekday + 6) % 7))
}

export function monthStart(localDate = today()) {
  return `${localDate.slice(0, 7)}-01`
}

export function shiftMonth(month: string, delta: number) {
  const [year, value] = month.split('-').map(Number)
  const date = new Date(Date.UTC(year!, value! - 1 + delta, 1))
  return date.toISOString().slice(0, 7)
}

export function monthLabel(month: string) {
  const [year, value] = month.split('-').map(Number)
  if (!year || !value) return month
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', month: 'long', year: 'numeric' }).format(
    new Date(Date.UTC(year, value - 1, 1)),
  )
}

export function dayCount(start: string, end: string) {
  const a = Date.parse(`${start}T00:00:00Z`)
  const b = Date.parse(`${end}T00:00:00Z`)
  if (Number.isNaN(a) || Number.isNaN(b)) return 0
  return Math.round((b - a) / 86_400_000) + 1
}

export function weekday(localDate: string) {
  const [year, month, day] = localDate.split('-').map(Number)
  if (!year || !month || !day) return ''
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', weekday: 'short' }).format(
    new Date(Date.UTC(year, month - 1, day)),
  )
}

export function roleLabel(role: string) {
  if (role === 'super_admin') return 'Super admin'
  if (role === 'admin') return 'Admin'
  if (role === 'employee') return 'Employee'
  return role
}
