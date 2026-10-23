export function formatClock(iso: string): string {
  return new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'UTC' }).format(new Date(iso))
}

export function formatCountdown(target: string, now: string): string {
  const seconds = Math.max(0, Math.floor((new Date(target).getTime() - new Date(now).getTime()) / 1000))
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export function minutesAgo(iso: string, now: string): string {
  const minutes = Math.max(0, Math.floor((new Date(now).getTime() - new Date(iso).getTime()) / 60000))
  return `${minutes}m ago`
}
