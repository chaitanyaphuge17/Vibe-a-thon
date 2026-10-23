import { useState } from 'react'
import { MapView } from './components/MapView'
import { Toast } from './components/Toast'
import { TopBar } from './components/TopBar'
import { useAppState } from './hooks/useAppState'
import { useNow } from './hooks/useNow'
import './styles.css'

export default function App(): JSX.Element {
  const { state, loading, connected, error, refresh } = useAppState()
  const now = useNow(state?.clock.now)
  const [activeView, setActiveView] = useState<'dashboard' | 'rider'>('dashboard')

  return (
    <main className="app-shell">
      <TopBar now={now} offsetMinutes={state?.clock.offsetMinutes ?? 0} connected={connected} activeView={activeView} onViewChange={setActiveView} refresh={refresh} />
      {error && <div className="error-strip" role="alert">{error}. Showing the last good state.</div>}
      {state ? <div className="console-layout">
        <aside className="side-panel batches-panel"><div className="panel-title"><div><p className="eyebrow">INVENTORY</p><h2>Batches</h2></div><strong>{state.batches.length}</strong></div><div className="placeholder-list"><p>Batch operations will appear here.</p><span>{state.batches.length} active records</span></div></aside>
        <MapView state={state} now={now} />
        <aside className="side-panel events-panel"><div className="panel-title"><div><p className="eyebrow">AUDIT STREAM</p><h2>Event log</h2></div><strong>{state.events.length}</strong></div><div className="placeholder-list"><p>Decision events will appear here.</p><span>{state.events.length} recorded events</span></div></aside>
        <section className="shipments-drawer"><div className="panel-title"><div><p className="eyebrow">DISPATCH QUEUE</p><h2>Shipments</h2></div><strong>{state.shipments.length}</strong></div><div className="drawer-placeholder">Shipment controls will appear here.</div></section>
      </div> : <div className="loading-state">{loading ? 'Connecting to dispatch state…' : 'No state available'}</div>}
      <Toast />
    </main>
  )
}
