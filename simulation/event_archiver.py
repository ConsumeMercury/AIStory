"""
Event log archiver — roll cold low-importance events into summaries.

Hot window stays in events/event_log.json; batches move to events/event_archive.json.
"""

import os
import uuid

from game.state_context import state_lock
from storage import load, save

EVENT_FILE = "events/event_log.json"
ARCHIVE_FILE = "events/event_archive.json"
RUMOR_FILE = "rumors/rumors.json"


def _hot_cap():
    raw = os.environ.get("AISTORY_EVENT_HOT_CAP", "2500")
    try:
        return max(100, min(10000, int(raw)))
    except ValueError:
        return 2500


def _archive_cap():
    raw = os.environ.get("AISTORY_EVENT_ARCHIVE_CAP", "200")
    try:
        return max(20, min(1000, int(raw)))
    except ValueError:
        return 200


def archive_enabled():
    return os.environ.get("AISTORY_SKIP_EVENT_ARCHIVE", "").lower() not in ("1", "true", "yes")


def _protected_event_ids(rumors):
    protected = set()
    for rumor in rumors or []:
        eid = rumor.get("source_event_id")
        if eid:
            protected.add(eid)
    return protected


def _summarize_batch(events):
    """One-line summary for archived batch."""
    if not events:
        return ""
    types = {}
    for e in events:
        t = e.get("type") or "event"
        types[t] = types.get(t, 0) + 1
    top = sorted(types.items(), key=lambda x: x[1], reverse=True)[:4]
    parts = [f"{count} {name}" for name, count in top]
    sample_actions = []
    for e in sorted(events, key=lambda x: int(x.get("importance") or 0), reverse=True)[:3]:
        act = (e.get("action") or "")[:60].strip()
        if act:
            sample_actions.append(act)
    summary = f"Archived {len(events)} events ({', '.join(parts)})."
    if sample_actions:
        summary += " Notable: " + "; ".join(sample_actions)
    return summary[:400]


def maybe_archive_events(*, tick=None, force=False):
    """
    Archive oldest low-importance events when log exceeds hot cap.
    Returns stats dict; never raises.
    """
    if not archive_enabled() and not force:
        return {"archived": 0, "skipped": "disabled"}

    try:
        from simulation.event_logger import flush_events
        flush_events()
    except Exception:
        pass

    with state_lock():
        events = load(EVENT_FILE, [])
        if not isinstance(events, list):
            events = []

        cap = _hot_cap()
        overflow = max(0, len(events) - cap)
        if overflow <= 0 and not force:
            return {"archived": 0, "remaining": len(events)}

        rumors = load(RUMOR_FILE, [])
        protected = _protected_event_ids(rumors)

        from simulation.importance_router import score_event

        player = load("player/player.json", {})
        candidates = []
        for idx, event in enumerate(events):
            eid = event.get("id")
            if eid and eid in protected:
                continue
            imp = score_event(event, player=player if player else None)
            candidates.append((imp, idx, event))

        candidates.sort(key=lambda row: (row[0], row[1]))

        remove_indices = set()
        archived_events = []
        for imp, idx, event in candidates:
            if len(archived_events) >= overflow:
                break
            remove_indices.add(idx)
            archived_events.append(event)

        if not archived_events:
            return {
                "archived": 0,
                "remaining": len(events),
                "skipped": "nothing_archivable",
            }

        ticks = [e.get("tick") for e in archived_events if e.get("tick") is not None]
        batch = {
            "id": str(uuid.uuid4())[:12],
            "archived_at_tick": tick,
            "tick_from": min(ticks) if ticks else None,
            "tick_to": max(ticks) if ticks else None,
            "count": len(archived_events),
            "importance_max": max(int(e.get("importance") or 0) for e in archived_events),
            "summary": _summarize_batch(archived_events),
            "event_ids": [e.get("id") for e in archived_events if e.get("id")][:80],
        }

        archive = load(ARCHIVE_FILE, [])
        if not isinstance(archive, list):
            archive = []
        archive.append(batch)
        archive = archive[-_archive_cap():]

        remaining = [e for i, e in enumerate(events) if i not in remove_indices]
        save(EVENT_FILE, remaining)
        save(ARCHIVE_FILE, archive)

        return {
            "archived": len(archived_events),
            "remaining": len(remaining),
            "batch_id": batch["id"],
        }


def archive_stats():
    """Size stats for health reports."""
    events = load(EVENT_FILE, [])
    archive = load(ARCHIVE_FILE, [])
    if not isinstance(events, list):
        events = []
    if not isinstance(archive, list):
        archive = []
    archived_events = sum(int(b.get("count") or 0) for b in archive)
    return {
        "hot_events": len(events),
        "hot_cap": _hot_cap(),
        "archive_batches": len(archive),
        "archived_events_total": archived_events,
    }
