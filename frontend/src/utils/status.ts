export type StatusTone = 'safe' | 'caution' | 'danger' | 'neutral'

export function statusTone(status: string): StatusTone {
  if (['AVAILABLE', 'DELIVERED', 'FULLY_ASSIGNED', 'COMPLETED'].includes(status)) return 'safe'
  if (['AT_RISK', 'REROUTED', 'PARTIALLY_ASSIGNED', 'CLAIMED', 'PICKED_UP', 'IN_TRANSIT'].includes(status)) return 'caution'
  if (['SPOILED', 'EXPIRED_LEASE', 'UNRESPONSIVE'].includes(status)) return 'danger'
  return 'neutral'
}

export function statusLabel(status: string): string {
  return status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (letter: string) => letter.toUpperCase())
}
