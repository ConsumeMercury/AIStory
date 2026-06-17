import json
import os
import uuid
from datetime import datetime, timezone

from storage import load, save
from simulation.event_importance import score_event_importance

EVENT_FILE = "events/event_log.json"

_event_buffer = []


def load_events():
    events = load(EVENT_FILE, [])
    return events if isinstance(events, list) else []


def all_events():
    """On-disk events plus buffered entries not yet flushed to disk."""
    return load_events() + list(_event_buffer)


def flush_events():
    global _event_buffer
    if not _event_buffer:
        return
    events = load_events()
    events.extend(_event_buffer)
    save(EVENT_FILE, events)
    _event_buffer = []


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
    _event_buffer.append(event)
    return event
