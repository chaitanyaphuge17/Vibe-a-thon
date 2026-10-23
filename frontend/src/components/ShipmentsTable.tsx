import { useMemo } from 'react'
import type { Shipment, State } from '../types'
import { StatusBadge } from './StatusBadge'
import { formatClock, formatCountdown } from '../utils/time'

interface ShipmentsTableProps {
  state: State
  now: string
}

const failureStatuses: Shipment['status'][] = ['EXPIRED_LEASE', 'REROUTED', 'AT_RISK', 'SPOILED']
const activeStatuses: Shipment['status'][] = ['CREATED', 'CLAIMED', 'PICKED_UP', 'IN_TRANSIT', 'AT_RISK', 'REROUTED', 'EXPIRED_LEASE']

function sortShipments(shipments: Shipment[]): Shipment[] {
  return [...shipments].sort((a, b) => {
    const activeDifference = Number(activeStatuses.includes(b.status)) - Number(activeStatuses.includes(a.status))
    return activeDifference || new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  })
}

export function ShipmentsTable({ state, now }: ShipmentsTableProps): JSX.Element {
  const shipments = useMemo(() => sortShipments(state.shipments), [state.shipments])
  return <section className="shipments-drawer" aria-label="Shipment dispatch queue">
    <div className="panel-title"><div><p className="eyebrow">DISPATCH QUEUE</p><h2>Shipments</h2></div><strong>{state.shipments.length}</strong></div>
    {shipments.length === 0 ? <div className="empty-state empty-state--wide"><strong>No shipments yet</strong><span>Dispatch a batch to create the first route.</span></div> : <div className="shipment-table-wrap">
      <table className="shipment-table">
        <thead><tr><th>Shipment</th><th>Batch</th><th>Rider</th><th>Destination shelter</th><th>Qty</th><th>Status</th><th>Lease</th><th>ETA delivery</th></tr></thead>
        <tbody>{shipments.map((shipment) => {
          const shelter = state.shelters.find((item) => item.id === shipment.shelterId)
          const rider = state.riders.find((item) => item.id === shipment.riderId)
          const leaseSeconds = shipment.leaseExpiresAt ? Math.floor((new Date(shipment.leaseExpiresAt).getTime() - new Date(now).getTime()) / 1000) : null
          const leaseDanger = leaseSeconds !== null && leaseSeconds < 60
          return <tr className={failureStatuses.includes(shipment.status) ? `shipment-row--${shipment.status.toLowerCase()}` : ''} key={shipment.id}>
            <td><code>{shipment.id}</code></td><td><code>{shipment.batchId}</code></td><td>{rider?.name || shipment.riderId || 'Unassigned'}</td>
            <td>{shelter?.name || shipment.shelterId}{shipment.status === 'REROUTED' && shipment.originalShelterId && <span className="reroute-note">was {state.shelters.find((item) => item.id === shipment.originalShelterId)?.name || shipment.originalShelterId}</span>}</td>
            <td>{shipment.qty}</td><td><StatusBadge status={shipment.status} /></td>
            <td className={leaseDanger ? 'lease--danger' : ''}>{shipment.leaseExpiresAt && !['DELIVERED', 'SPOILED'].includes(shipment.status) ? formatCountdown(shipment.leaseExpiresAt, now) : '—'}</td><td>{formatClock(shipment.etaDeliveryAt)}</td>
          </tr>
        })}</tbody>
      </table>
    </div>}
  </section>
}
