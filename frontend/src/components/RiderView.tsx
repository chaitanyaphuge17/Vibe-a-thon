import { useEffect, useMemo, useState } from 'react'
import { claimShipment, deliverShipment, heartbeatRider, pickupShipment } from '../api'
import type { Rider, Shipment, State } from '../types'
import { StatusBadge } from './StatusBadge'
import { formatCountdown } from '../utils/time'

interface RiderViewProps { state: State; now: string; refresh: () => Promise<void> }
type Action = 'claim' | 'pickup' | 'deliver' | 'heartbeat' | null

function notify(message: string, tone: 'success' | 'error' | 'info'): void {
  window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message, tone } }))
}

function actionLabel(status: Shipment['status']): string {
  if (status === 'CREATED') return 'Claim'
  if (status === 'CLAIMED') return 'Pick up'
  if (status === 'IN_TRANSIT') return 'Deliver'
  return 'No action'
}

export function RiderView({ state, now, refresh }: RiderViewProps): JSX.Element {
  const [riderId, setRiderId] = useState(state.riders[0]?.id || '')
  const [autoHeartbeat, setAutoHeartbeat] = useState(false)
  const [action, setAction] = useState<Action>(null)
  const rider = state.riders.find((item) => item.id === riderId)
  const shipments = useMemo(() => state.shipments.filter((shipment) => shipment.riderId === riderId), [state.shipments, riderId])
  const destinations = new Map(state.shelters.map((shelter) => [shelter.id, shelter.name]))

  useEffect(() => {
    if (!autoHeartbeat || !rider) return
    const interval = window.setInterval(() => {
      void sendHeartbeat(rider)
    }, 10000)
    return () => window.clearInterval(interval)
  }, [autoHeartbeat, riderId, rider?.location.lat, rider?.location.lng])

  const run = async (nextAction: Exclude<Action, null>, operation: () => Promise<unknown>, message: string): Promise<void> => {
    setAction(nextAction)
    try {
      await operation()
      await refresh()
      notify(message, 'success')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Rider action failed.', 'error')
    } finally {
      setAction(null)
    }
  }

  const sendHeartbeat = async (selectedRider: Rider): Promise<void> => {
    if (action === 'heartbeat') return
    await run('heartbeat', () => heartbeatRider(selectedRider.id, selectedRider.location), 'Heartbeat sent.')
  }

  const actOnShipment = (shipment: Shipment): void => {
    if (shipment.status === 'CREATED') void run('claim', () => claimShipment(shipment.id), `${shipment.id} claimed.`)
    if (shipment.status === 'CLAIMED') void run('pickup', () => pickupShipment(shipment.id), `${shipment.id} picked up.`)
    if (shipment.status === 'IN_TRANSIT') void run('deliver', () => deliverShipment(shipment.id), `${shipment.id} delivered.`)
  }

  return <section className="rider-view" aria-label="Rider view">
    <div className="rider-view__header"><div><p className="eyebrow">FIELD OPERATIONS</p><h2>Rider view</h2><span>Operate one rider's active delivery queue.</span></div><label className="rider-select">Rider<select value={riderId} onChange={(event) => { setRiderId(event.target.value); setAutoHeartbeat(false) }} aria-label="Select rider">{state.riders.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.status}</option>)}</select></label></div>
    {!rider ? <div className="empty-state empty-state--wide"><strong>No riders available</strong><span>Rider assignments will appear when the backend provides them.</span></div> : <>
      {rider.status === 'UNRESPONSIVE' && <div className="rider-banner rider-banner--danger" role="alert"><strong>Rider unresponsive</strong><span>Heartbeats may be ignored until this rider is restored.</span></div>}
      <div className="rider-controls"><StatusBadge status={rider.status} /><button className="button button--outline" disabled={action !== null} onClick={() => void sendHeartbeat(rider)}>{action === 'heartbeat' ? 'Sending…' : 'Send heartbeat'}</button><label className="heartbeat-toggle"><input type="checkbox" checked={autoHeartbeat} disabled={action !== null} onChange={(event) => setAutoHeartbeat(event.target.checked)} /> Auto heartbeat every 10 s</label></div>
      <div className="rider-shipment-list">{shipments.length === 0 ? <div className="empty-state"><strong>No shipments assigned</strong><span>This rider has no shipment queue.</span></div> : shipments.map((shipment) => {
        const shelterName = destinations.get(shipment.shelterId) || shipment.shelterId
        const leaseSeconds = shipment.leaseExpiresAt ? Math.floor((new Date(shipment.leaseExpiresAt).getTime() - new Date(now).getTime()) / 1000) : null
        const leaseVisible = leaseSeconds !== null && !['DELIVERED', 'SPOILED'].includes(shipment.status)
        return <article className="rider-shipment" key={shipment.id}>
          {rider.status === 'UNRESPONSIVE' && <div className="rider-banner rider-banner--danger"><strong>Heartbeat required</strong><span>Lease may expire while the rider is unresponsive.</span></div>}
          {shipment.status === 'REROUTED' && <div className="rider-banner rider-banner--warning"><strong>Shipment rerouted</strong><span>New destination: {shelterName}</span></div>}
          <div className="rider-shipment__top"><div><code>{shipment.id}</code><h3>{shelterName}</h3><span>{shipment.qty} units · {shipment.batchId}</span></div><StatusBadge status={shipment.status} /></div>
          {leaseVisible && <div className={`lease-countdown ${leaseSeconds < 60 ? 'lease-countdown--urgent' : ''}`}><span>LEASE TIME REMAINING</span><strong>{formatCountdown(shipment.leaseExpiresAt as string, now)}</strong></div>}
          <button className="button button--primary rider-action" disabled={action !== null || !['CREATED', 'CLAIMED', 'IN_TRANSIT'].includes(shipment.status)} onClick={() => actOnShipment(shipment)}>{action === 'claim' || action === 'pickup' || action === 'deliver' ? 'Updating…' : actionLabel(shipment.status)}</button>
        </article>
      })}</div>
    </>}
  </section>
}
