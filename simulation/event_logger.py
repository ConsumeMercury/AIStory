import json
import os
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENT_FILE = os.path.join(BASE_DIR, "events", "event_log.json")

_event_buffer = []


def load_events():
    if not os.path.exists(EVENT_FILE):
        return []

    try:
        with open(EVENT_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        # FIX: corrupted log recovery safety
        return []


def flush_events():
    """Persist buffered events once per tick."""
    global _event_buffer

    if not _event_buffer:
        return

    events = load_events()

    # FIX: ensure event list integrity
    if not isinstance(events, list):
        events = []

    events.extend(_event_buffer)

    with open(EVENT_FILE, "w") as f:
        json.dump(events, f, indent=2)

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
        "effects": effects or []
    }

    # FIX: enforce consistent schema types early
    if not isinstance(event["effects"], list):
        event["effects"] = []

    _event_buffer.append(event)
    return event