import { useState } from 'react'
import { dispatchBatch } from '../api'
import type { Batch, DispatchResponse, Donor } from '../types'
import { StatusBadge } from './StatusBadge'
import { formatCountdown } from '../utils/time'

interface BatchCardProps {
  batch: Batch
  donors: Donor[]
  now: string
  refresh: () => Promise<void>
  rejections: DispatchResponse['rejections']
  onDispatchResult: (batchId: string, result: DispatchResponse) => void
}

function itemLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function notify(message: string, tone: 'success' | 'error'): void {
  window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message, tone } }))
}

export function BatchCard({ batch, donors, now, refresh, rejections, onDispatchResult }: BatchCardProps): JSX.Element {
  const [dispatching, setDispatching] = useState(false)
  const expired = new Date(batch.expiresAt).getTime() <= new Date(now).getTime()
  const secondsLeft = Math.floor((new Date(batch.expiresAt).getTime() - new Date(now).getTime()) / 1000)
  const countdownTone = expired || secondsLeft < 600 ? 'danger' : secondsLeft < 1200 ? 'caution' : 'safe'
  const disabled = dispatching || batch.status === 'SPOILED' || batch.status === 'COMPLETED'
  const donor = donors.find((item) => item.id === batch.donorId)

  const dispatch = async (): Promise<void> => {
    setDispatching(true)
    try {
      const result = await dispatchBatch(batch.id)
      onDispatchResult(batch.id, result)
      await refresh()
      notify(`${result.createdShipments.length} shipment${result.createdShipments.length === 1 ? '' : 's'} created.`, 'success')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Dispatch failed.', 'error')
    } finally {
      setDispatching(false)
    }
  }

  return <article className="batch-card">
    <div className="batch-card__top"><div><p className="batch-card__id">{batch.id}</p><h3>{itemLabel(batch.itemType)}</h3><span className="batch-card__donor">{donor?.name || batch.donorId}</span></div><StatusBadge status={expired ? 'SPOILED' : batch.status} /></div>
    <div className="batch-card__quantity"><span><strong>{batch.remainingQty}</strong> / {batch.totalQty} units</span><strong className={`expiry expiry--${countdownTone}`}>{expired ? 'SPOILED' : formatCountdown(batch.expiresAt, now)}</strong></div>
    <div className="progress-track" aria-label={`${batch.remainingQty} of ${batch.totalQty} units remaining`}><span style={{ width: `${Math.min(100, Math.max(0, (batch.remainingQty / batch.totalQty) * 100))}%` }} /></div>
    {batch.statusReason && <p className="batch-card__reason">{batch.statusReason}</p>}
    <button className="button button--dispatch" disabled={disabled} onClick={() => void dispatch()}>{dispatching ? 'Dispatching…' : 'Dispatch remaining'}</button>
    {rejections.length > 0 && <div className="rejection-list"><strong>Rejected matches</strong>{rejections.map((rejection, index) => <p key={`${rejection.reason}-${index}`}>{rejection.shelterId ? `${rejection.shelterId} excluded` : `${rejection.riderId || 'Match'} rejected`}: {rejection.reason}</p>)}</div>}
  </article>
}
