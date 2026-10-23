from threading import RLock

from app import clock
from app.models import Event, EventSeverity, EventType


events: list[Event] = []
_next_event_id = 1
_lock: RLock = clock.state_lock


def log_event(
    type: EventType,
    severity: EventSeverity,
    message: str,
    refs: dict[str, str] | None = None,
) -> Event:
    global _next_event_id
    with _lock:
        event = Event(
            id=f"evt_{_next_event_id}",
            at=clock.now(),
            type=type,
            severity=severity,
            message=message,
            refs=refs or {},
        )
        _next_event_id += 1
        events.append(event)
        del events[:-100]
        return event


def reset_events() -> None:
    global _next_event_id
    with _lock:
        events.clear()
        _next_event_id = 1
