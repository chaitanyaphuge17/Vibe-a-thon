import { useEffect, useRef, useState } from 'react'
import type { Event, EventSeverity } from '../types'
import { formatClock } from '../utils/time'

interface EventLogProps { events: Event[] }
type Filter = 'all' | 'alerts'

const severityIcon: Record<EventSeverity, string> = { info: 'i', success: '✓', warning: '!', error: '×' }

export function EventLog({ events }: EventLogProps): JSX.Element {
  const [filter, setFilter] = useState<Filter>('all')
  const [newEventIds, setNewEventIds] = useState<string[]>([])
  const seenIds = useRef(new Set<string>())
  const initialized = useRef(false)
  const listRef = useRef<HTMLDivElement>(null)
  const newestFirst = [...events].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
  const visibleEvents = filter === 'all' ? newestFirst : newestFirst.filter((event) => event.severity === 'warning' || event.severity === 'error')

  useEffect(() => {
    const incoming = initialized.current ? events.filter((event) => !seenIds.current.has(event.id)).map((event) => event.id) : []
    events.forEach((event) => seenIds.current.add(event.id))
    initialized.current = true
    if (incoming.length === 0) return
    setNewEventIds(incoming)
    const timer = window.setTimeout(() => setNewEventIds([]), 1800)
    listRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    return () => window.clearTimeout(timer)
  }, [events])

  return <aside className="side-panel events-panel">
    <div className="panel-title"><div><p className="eyebrow">AUDIT STREAM</p><h2>Event log</h2></div><strong>{events.length}</strong></div>
    <div className="event-filters" role="group" aria-label="Event filters">
      <button className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>All</button>
      <button className={filter === 'alerts' ? 'is-active' : ''} onClick={() => setFilter('alerts')}>Warnings &amp; errors</button>
    </div>
    <div className="event-list" ref={listRef}>
      {visibleEvents.length === 0 ? <div className="empty-state"><strong>No matching events</strong><span>The event stream is clear.</span></div> : visibleEvents.map((event) => <article className={`event-item event-item--${event.severity} ${newEventIds.includes(event.id) ? 'event-item--new' : ''}`} key={event.id}>
        <span className="event-icon" aria-label={event.severity}>{severityIcon[event.severity]}</span><div className="event-content"><div className="event-meta"><time dateTime={event.at}>{formatClock(event.at)}</time><span>{event.type.replace(/_/g, ' ')}</span></div><p>{event.message}</p></div>
      </article>)}
    </div>
  </aside>
}
