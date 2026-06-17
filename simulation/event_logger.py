import threading
import uuid
from datetime import datetime, timezone

from game.state_context import state_lock
from storage import load, save
from simulation.event_importance import score_event_importance

EVENT_FILE = "events/event_log.json"

_event_buffer = []
_buffer_lock = threading.Lock()


def load_events():
    events = load(EVENT_FILE, [])
    return events if isinstance(events, list) else []


def all_events():
    """On-disk events plus buffered entries not yet flushed to disk."""
    with _buffer_lock:
        buffered = list(_event_buffer)
    with state_lock():
        return load_events() + buffered


def flush_events():
    global _event_buffer
    with _buffer_lock:
        if not _event_buffer:
            pending = []
        else:
            pending = _event_buffer
            _event_buffer = []
    if not pending:
        return
    with state_lock():
        events = load_events()
        events.extend(pending)
        save(EVENT_FILE, events)
    try:
        from simulation.event_archiver import maybe_archive_events
        maybe_archive_events()
    except Exception:
        pass


def log_event(event_type, actor, action, target=None, location=None, effects=None, tick=None):
    event = {
        "id": str(uuid.uuid4()),
        "tick_time": datetime.now(timezone.utc).isoformat(),
        "tick": tick,
        "type": event_type,
        "actor": actor,
        "action": action,
        "target": target,
        "location": location,
        "effects": effects or [],
        "importance": score_event_importance(
            event_type, action, effects=effects, target=target,
        ),
    }
    if not isinstance(event["effects"], list):
        event["effects"] = []
    with _buffer_lock:
        _event_buffer.append(event)
    return event
