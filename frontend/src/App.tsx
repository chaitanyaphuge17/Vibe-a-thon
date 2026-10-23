import { StatusBadge } from './components/StatusBadge'
import { Toast } from './components/Toast'
import { useAppState } from './hooks/useAppState'
import { useNow } from './hooks/useNow'
import { formatClock } from './utils/time'
import './styles.css'

export default function App(): JSX.Element {
  const { state, loading, connected, error } = useAppState()
  const now = useNow(state?.clock.now)

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">FRESHRELAY / OPERATIONS</p>
          <h1>Dispatch control room</h1>
        </div>
        <div className="connection" aria-live="polite">
          <span className={`connection-dot ${connected ? 'connection-dot--up' : 'connection-dot--down'}`} aria-hidden="true" />
          <span>{connected ? 'Connected' : 'Backend unreachable'}</span>
          {state && <time dateTime={now}>Simulated {formatClock(now)} UTC</time>}
        </div>
      </header>
      {error && <div className="error-strip" role="alert">{error}. Showing the last good state.</div>}
      <section className="summary-grid" aria-label="Network summary">
        <article className="metric"><span>Batches</span><strong>{loading && !state ? '—' : state?.batches.length ?? 0}</strong></article>
        <article className="metric"><span>Shipments</span><strong>{loading && !state ? '—' : state?.shipments.length ?? 0}</strong></article>
        <article className="metric"><span>Riders</span><strong>{loading && !state ? '—' : state?.riders.length ?? 0}</strong></article>
        <article className="metric"><span>Shelters</span><strong>{loading && !state ? '—' : state?.shelters.length ?? 0}</strong></article>
      </section>
      {state && <section className="state-panel">
        <div className="panel-heading"><div><p className="eyebrow">LIVE STATE</p><h2>Current dispatch picture</h2></div><StatusBadge status={state.batches[0]?.status || 'OPEN'} /></div>
        <p>{state.batches[0]?.itemType.replace(/_/g, ' ') || 'No active batches'} · {state.batches[0]?.remainingQty ?? 0} units remaining</p>
      </section>}
      <Toast />
    </main>
  )
}
