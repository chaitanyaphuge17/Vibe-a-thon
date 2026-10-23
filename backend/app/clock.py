from datetime import datetime, timedelta, timezone
from threading import RLock


state_lock = RLock()
_offset_minutes = 0


def now() -> datetime:
    with state_lock:
        return datetime.now(timezone.utc) + timedelta(minutes=_offset_minutes)


def advance(minutes: int) -> None:
    global _offset_minutes
    with state_lock:
        _offset_minutes += minutes


def reset() -> None:
    global _offset_minutes
    with state_lock:
        _offset_minutes = 0


def offset_minutes() -> int:
    with state_lock:
        return _offset_minutes
