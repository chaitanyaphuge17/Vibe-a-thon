import { useState } from 'react'
import { BatchesPanel } from './components/BatchesPanel'
import { EventLog } from './components/EventLog'
import { MapView } from './components/MapView'
import { ShipmentsTable } from './components/ShipmentsTable'
import { SimulationPanel } from './components/SimulationPanel'
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
      {state ? <>
        <SimulationPanel state={state} refresh={refresh} />
        <div className="console-layout">
        <BatchesPanel state={state} now={now} refresh={refresh} />
        <MapView state={state} now={now} />
        <EventLog events={state.events} />
        <ShipmentsTable state={state} now={now} />
        </div>
      </> : <div className="loading-state">{loading ? 'Connecting to dispatch state…' : 'No state available'}</div>}
      <Toast />
    </main>
  )
}
