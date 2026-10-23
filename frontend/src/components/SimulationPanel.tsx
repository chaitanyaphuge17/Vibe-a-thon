import { useState } from 'react'
import { advanceClock, createHandoutScenario, createIncompatibleScenario, createTightExpiryScenario, setRiderUnresponsive, updateShelter } from '../api'
import type { ShelterUpdateResponse, State } from '../types'

interface SimulationPanelProps { state: State; refresh: () => Promise<void> }
type Action = 'clock-5' | 'clock-10' | 'clock-30' | 'rider' | 'shelter-close' | 'shelter-open' | 'shelter-demand' | 'handout' | 'tight' | 'incompatible' | null

function notify(message: string, tone: 'info' | 'success' | 'warning' | 'error'): void {
  window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message, tone } }))
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

export function SimulationPanel({ state, refresh }: SimulationPanelProps): JSX.Element {
  const [collapsed, setCollapsed] = useState(false)
  const [riderId, setRiderId] = useState(state.riders[0]?.id || '')
  const [shelterId, setShelterId] = useState(state.shelters[0]?.id || '')
  const [shelterResult, setShelterResult] = useState<ShelterUpdateResponse | null>(null)
  const [action, setAction] = useState<Action>(null)
  const rider = state.riders.find((item) => item.id === riderId)
  const shelter = state.shelters.find((item) => item.id === shelterId)
  const busy = action !== null

  const run = async <T,>(name: Exclude<Action, null>, operation: () => Promise<T>, onSuccess: (result: T) => void, successMessage?: string): Promise<void> => {
    setAction(name)
    try {
      const result = await operation()
      onSuccess(result)
      await refresh()
      if (successMessage) notify(successMessage, 'success')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Simulation action failed.', 'error')
    } finally {
      setAction(null)
    }
  }

  const runClock = (minutes: number): void => {
    const name = `clock-${minutes}` as Exclude<Action, null>
    void run(name, () => advanceClock({ advanceMinutes: minutes }), (result) => {
      const { leasesExpired, reassigned, spoiled } = result.tickSummary
      const summary = [leasesExpired > 0 && plural(leasesExpired, 'lease expired'), reassigned > 0 && plural(reassigned, 'reassigned'), spoiled > 0 && plural(spoiled, 'spoiled')].filter(Boolean).join(', ')
      notify(summary || 'No lease, reassignment or spoilage changes.', summary ? 'warning' : 'info')
    })
  }

  const toggleRider = (): void => {
    if (!riderId) return
    const makeUnresponsive = rider?.status !== 'UNRESPONSIVE'
    void run('rider', () => setRiderUnresponsive(riderId, { unresponsive: makeUnresponsive }), () => undefined, makeUnresponsive ? 'Rider marked unresponsive.' : 'Rider restored.')
  }

  const updateSelectedShelter = (update: 'close' | 'open' | 'demand'): void => {
    if (!shelterId) return
    const name = `shelter-${update}` as Exclude<Action, null>
    const body = update === 'close' ? { isOpen: false } : update === 'open' ? { isOpen: true } : { demandRemaining: 0 }
    void run(name, () => updateShelter(shelterId, body), (result) => setShelterResult(result), `Shelter ${update === 'demand' ? 'demand set to 0' : `${update}ed`}.`)
  }

  const createScenario = (type: 'handout' | 'tight' | 'incompatible'): void => {
    const operation = type === 'handout' ? createHandoutScenario : type === 'tight' ? createTightExpiryScenario : createIncompatibleScenario
    void run(type, operation, (result) => {
      window.dispatchEvent(new CustomEvent('freshrelay:highlight-batch', { detail: { batchId: result.batch.id } }))
    }, 'Scenario created. New batch highlighted.')
  }

  return <section className={`simulation-panel ${collapsed ? 'simulation-panel--collapsed' : ''}`} aria-label="Simulation controls">
    <div className="simulation-heading"><div><p className="eyebrow">JUDGE CONTROLS</p><h2>Simulation panel</h2><span>Drive failures and recovery from one place.</span></div><button className="simulation-collapse" onClick={() => setCollapsed((value) => !value)} aria-expanded={!collapsed}>{collapsed ? 'Expand controls' : 'Collapse'}</button></div>
    {!collapsed && <div className="simulation-groups">
      <div className="simulation-group"><h3>Time</h3><div className="simulation-actions">{[5, 10, 30].map((minutes) => <button className="button button--sim" disabled={busy} onClick={() => runClock(minutes)} key={minutes}>{action === `clock-${minutes}` ? 'Advancing…' : `Fast-forward +${minutes} min`}</button>)}</div></div>
      <div className="simulation-group"><h3>Riders</h3><select value={riderId} onChange={(event) => setRiderId(event.target.value)} disabled={busy} aria-label="Select rider">{state.riders.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.status}</option>)}</select><button className="button button--sim" disabled={busy || !riderId} onClick={toggleRider}>{action === 'rider' ? 'Updating…' : rider?.status === 'UNRESPONSIVE' ? 'Restore rider' : 'Make unresponsive'}</button></div>
      <div className="simulation-group"><h3>Shelters</h3><select value={shelterId} onChange={(event) => setShelterId(event.target.value)} disabled={busy} aria-label="Select shelter">{state.shelters.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.isOpen ? 'OPEN' : 'CLOSED'}</option>)}</select><div className="simulation-actions simulation-actions--compact"><button className="button button--sim button--danger" disabled={busy || !shelterId} onClick={() => updateSelectedShelter('close')}>{action === 'shelter-close' ? 'Closing…' : 'Close'}</button><button className="button button--sim" disabled={busy || !shelterId} onClick={() => updateSelectedShelter('open')}>{action === 'shelter-open' ? 'Reopening…' : 'Reopen'}</button><button className="button button--sim button--warning" disabled={busy || !shelterId} onClick={() => updateSelectedShelter('demand')}>{action === 'shelter-demand' ? 'Updating…' : 'Set demand to 0'}</button></div>{shelterResult && <div className="simulation-result"><strong>{shelter?.name || shelterId} update result</strong><span>{shelterResult.rerouted.length ? `${plural(shelterResult.rerouted.length, 'shipment')} rerouted` : 'No shipments rerouted'}</span>{shelterResult.rerouted.map((item) => <span key={item.shipmentId}>{item.shipmentId}: {item.fromShelterId} → {item.toShelterId}</span>)}{shelterResult.atRisk.length ? <span className="simulation-result__risk">{plural(shelterResult.atRisk.length, 'shipment')} at risk</span> : <span>No shipments at risk</span>}{shelterResult.atRisk.map((item) => <span key={item.shipmentId}>{item.shipmentId}: {item.reason}</span>)}</div>}</div>
      <div className="simulation-group simulation-group--scenarios"><h3>Scenarios</h3><button className="button button--scenario" disabled={busy} onClick={() => createScenario('handout')}>{action === 'handout' ? 'Creating…' : 'Handout scenario (180 meals)'}</button><button className="button button--scenario" disabled={busy} onClick={() => createScenario('tight')}>{action === 'tight' ? 'Creating…' : 'Tight expiry batch'}</button><button className="button button--scenario" disabled={busy} onClick={() => createScenario('incompatible')}>{action === 'incompatible' ? 'Creating…' : 'Incompatible shipment'}</button></div>
    </div>}
  </section>
}
