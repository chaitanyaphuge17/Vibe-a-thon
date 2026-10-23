import { resetSimulation } from '../api'
import { formatClock } from '../utils/time'

interface TopBarProps {
  now: string
  offsetMinutes: number
  connected: boolean
  activeView: 'dashboard' | 'rider'
  onViewChange: (view: 'dashboard' | 'rider') => void
  refresh: () => Promise<void>
}

function LogoMark(): JSX.Element {
  return (
    <svg className="logo-mark" viewBox="0 0 48 48" role="img" aria-label="FreshRelay logo">
      <rect width="48" height="48" rx="12" fill="#16434a" />
      <circle cx="24" cy="24" r="14" fill="none" stroke="#F2A33A" strokeWidth="2.5" strokeDasharray="58 30" transform="rotate(-42 24 24)" />
      <path d="M13 29h7l5-10 5 7h8" fill="none" stroke="#F2A33A" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M31 25v9h8v-9l-4-4z" fill="none" stroke="#fffdf8" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}

export function TopBar({ now, offsetMinutes, connected, activeView, onViewChange, refresh }: TopBarProps): JSX.Element {
  const handleReset = async (): Promise<void> => {
    if (!window.confirm('Reset the simulated scenario and clock?')) return
    try {
      await resetSimulation()
      await refresh()
    } catch (error) {
      window.dispatchEvent(new CustomEvent('freshrelay:toast', { detail: { message: error instanceof Error ? error.message : 'Reset failed', tone: 'error' } }))
    }
  }

  return (
    <header className="topbar">
      <div className="brand">
        <LogoMark />
        <div>
          <p className="eyebrow">OPERATIONS CONSOLE</p>
          <h1>FreshRelay</h1>
        </div>
      </div>
      <div className="topbar-actions">
        <div className="sim-clock">
          <span className="sim-clock__label">SIMULATED CLOCK</span>
          <strong>{formatClock(now)}</strong>
          <span className="sim-clock__offset">+{offsetMinutes} min</span>
        </div>
        <div className="connection" aria-live="polite">
          <span className={`connection-dot ${connected ? 'connection-dot--up' : 'connection-dot--down'}`} aria-hidden="true" />
          <span>{connected ? 'Connected' : 'Backend unreachable'}</span>
        </div>
        <div className="view-switch" role="tablist" aria-label="Console view">
          <button className={activeView === 'dashboard' ? 'is-active' : ''} onClick={() => onViewChange('dashboard')} role="tab" aria-selected={activeView === 'dashboard'}>Dashboard</button>
          <button className={activeView === 'rider' ? 'is-active' : ''} onClick={() => onViewChange('rider')} role="tab" aria-selected={activeView === 'rider'}>Rider view</button>
        </div>
        <button className="button button--outline" onClick={() => void handleReset()}>Reset</button>
      </div>
    </header>
  )
}
