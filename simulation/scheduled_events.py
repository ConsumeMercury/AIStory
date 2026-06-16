"""
Plot events promised in narration or dialogue — scheduled to fire at a real hour.
Distinct from npc_schedule.py (NPC daily routines).
"""

import re

# (pattern, event_id, hours_from_now, human label)
_EVENT_PROMISES = (
    (re.compile(r"\b(?:wait for|at|until)\s+(?:the\s+)?third\s+(?:toll|bell)\b", re.I),
     "third_toll", 3, "the third toll of the bell"),
    (re.compile(r"\bthird\s+(?:toll|bell)\s+of\s+the\s+bell\b", re.I),
     "third_toll", 3, "the third toll of the bell"),
    (re.compile(r"\b(?:wait for|at|until)\s+(?:the\s+)?second\s+(?:toll|bell)\b", re.I),
     "second_toll", 2, "the second toll"),
    (re.compile(r"\b(?:wait for|at|until)\s+(?:the\s+)?first\s+(?:toll|bell)\b", re.I),
     "first_toll", 1, "the first toll"),
    (re.compile(r"\b(?:auction|buyers?|bid)\b.*\b(?:third|3rd)\s+(?:toll|bell)\b", re.I),
     "third_toll_auction", 3, "the third toll (underground bid)"),
)

_WAIT_FOR_EVENT = re.compile(
    r"\b(?:wait|watch|keep watch|stake out)\s+(?:for|until)\s+(?:the\s+)?(.+?)(?:\s*$|\.|,)",
    re.I,
)


def _area_store(player, area_id):
    if not area_id:
        return {}
    return player.setdefault("scheduled_events", {}).setdefault(area_id, {})


def extract_event_promises(text):
    """Find schedulable event promises in prose or dialogue."""
    if not text:
        return []
    found = []
    seen = set()
    for pattern, eid, delta, label in _EVENT_PROMISES:
        if not pattern.search(text):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        found.append({"id": eid, "label": label, "hours_from_now": delta})
    return found


def record_scheduled_events(player, scene, area_id, world):
    """Promote narrator/dialogue event promises into player state."""
    if not scene or not area_id:
        return False
    promises = extract_event_promises(scene)
    if not promises:
        return False
    hc = world.get("hour_count", 0)
    store = _area_store(player, area_id)
    changed = False
    for p in promises:
        eid = p["id"]
        if store.get(eid, {}).get("fired"):
            continue
        if eid not in store:
            store[eid] = {
                "id": eid,
                "label": p["label"],
                "fires_at_hour": hc + p["hours_from_now"],
                "fired": False,
                "source": "narration",
            }
            changed = True
        else:
            rec = store[eid]
            if not rec.get("fired") and rec.get("fires_at_hour", hc) <= hc:
                rec["fires_at_hour"] = hc + p["hours_from_now"]
                changed = True
    return changed


def list_pending_events(player, area_id):
    store = _area_store(player, area_id)
    return [e for e in store.values() if not e.get("fired")]


def parse_wait_for_event(action, player, area_id):
    """Match a wait-for action to a pending scheduled event."""
    if not action or not area_id:
        return None
    text = action.lower()
    if not re.search(r"\bwait\s+(?:for|until)\b", text):
        return None
    store = _area_store(player, area_id)
    m = _WAIT_FOR_EVENT.search(action.strip())
    query = (m.group(1) if m else "").lower().strip()
    for event in store.values():
        if event.get("fired"):
            continue
        label = (event.get("label") or "").lower()
        eid = event.get("id", "")
        if query and (query in label or label in query):
            return event
        if "third toll" in query and "third" in eid:
            return event
        if "second toll" in query and "second" in eid:
            return event
        if "first toll" in query and "first" in eid:
            return event
    return None


def hours_until_event(event, world):
    if not event or event.get("fired"):
        return 0
    hc = world.get("hour_count", 0)
    target = event.get("fires_at_hour", hc)
    return max(0, target - hc)


def fire_due_events(player, world, area_id):
    """Mark events whose hour has arrived. Returns newly fired events."""
    if not area_id:
        return []
    hc = world.get("hour_count", 0)
    store = _area_store(player, area_id)
    fired = []
    for eid, event in store.items():
        if event.get("fired"):
            continue
        if event.get("fires_at_hour", 999999) <= hc:
            event["fired"] = True
            fired.append(dict(event))
    return fired


def build_scheduled_events_block(player, area_id, world):
    """Tell narrator which timed events are real and pending."""
    pending = list_pending_events(player, area_id)
    hc = world.get("hour_count", 0)
    lines = ["SCHEDULED EVENTS (simulation — only these may fire on wait/advance):"]
    if pending:
        for e in pending[:6]:
            hrs = max(0, e.get("fires_at_hour", hc) - hc)
            lines.append(f"- PENDING: {e.get('label')} in ~{hrs} hour(s).")
    else:
        lines.append("- None scheduled — do NOT promise specific bell tolls, auctions, or timed meetings.")
    lines.append(
        "- Do NOT invent timed plot events the player can wait for unless listed above."
    )
    return "\n".join(lines)


def event_fired_directive(events):
    if not events:
        return ""
    labels = ", ".join(e.get("label", "event") for e in events)
    return (
        f"SCHEDULED EVENT FIRED: {labels}. "
        "Describe this occurrence now — it is simulation-authoritative. "
        "Background crowd only; no new named persistent NPCs unless SCENE FACTS list them."
    )
