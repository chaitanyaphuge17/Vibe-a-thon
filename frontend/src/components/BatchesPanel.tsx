import { useState } from 'react'
import type { Batch, DispatchResponse, State } from '../types'
import { BatchCard } from './BatchCard'
import { BatchForm } from './BatchForm'

interface BatchesPanelProps { state: State; now: string; refresh: () => Promise<void> }

export function BatchesPanel({ state, now, refresh }: BatchesPanelProps): JSX.Element {
  const [rejections, setRejections] = useState<Record<string, DispatchResponse['rejections']>>({})
  const batches = [...state.batches].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  const onDispatchResult = (batchId: string, result: DispatchResponse): void => {
    setRejections((current) => ({ ...current, [batchId]: result.rejections }))
  }

  return <aside className="side-panel batches-panel">
    <div className="panel-title"><div><p className="eyebrow">INVENTORY</p><h2>Batches</h2></div><strong>{state.batches.length}</strong></div>
    <BatchForm donors={state.donors} refresh={refresh} />
    <div className="batch-list">
      {batches.length === 0 ? <div className="empty-state"><strong>No batches yet</strong><span>Create a batch to begin allocation.</span></div> : batches.map((batch: Batch) => <BatchCard key={batch.id} batch={batch} donors={state.donors} now={now} refresh={refresh} rejections={rejections[batch.id] || []} onDispatchResult={onDispatchResult} />)}
    </div>
  </aside>
}
