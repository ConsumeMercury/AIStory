"""
Plot events promised in narration or dialogue — scheduled to fire at a real hour.
Distinct from npc_schedule.py (NPC daily routines).
"""

import re

# Structured narrator emission — phrasing-independent capture.
# [SCHEDULE: event_id | human label | +Nh]  or  [SCHEDULE: human label | +Nh]
_SCHEDULE_TAG = re.compile(
    r"\[SCHEDULE:\s*(?:"
    r"(?P<id>[\w-]+)\s*\|\s*(?P<label_id>[^|\]]+?)\s*\|\s*\+(?P<hours_id>\d+)h?\s*"
    r"|"
    r"(?P<label>[^|\]]+?)\s*\|\s*\+(?P<hours>\d+)h?\s*"
    r")\]",
    re.I,
)

# Legacy regex fallbacks — kept for older saves/tests, not primary capture.
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
    (re.compile(r"\btide[\s-]?bell\b.*\b(?:twice|two|2)\b", re.I),
     "tide_bell_twice", 2, "the tide-bell rings twice"),
    (re.compile(r"\b(?:rings|ring)\s+(?:twice|two\s+times)\b.*\btide[\s-]?bell\b", re.I),
     "tide_bell_twice", 2, "the tide-bell rings twice"),
    (re.compile(r"\bcoal[\s-]?chutes?\b", re.I),
     "coal_chute_entry", 2, "the junior boys enter through the coal-chutes"),
    (re.compile(r"\b(?:junior\s+)?boys?\b.*\b(?:chute|coal)\b", re.I),
     "coal_chute_entry", 2, "the junior boys enter through the coal-chutes"),
)

_WAIT_FOR_EVENT = re.compile(
    r"\b(?:wait|watch|keep watch|stake out)\s+(?:for|until)\s+(?:the\s+)?(.+?)(?:\s*$|\.|,)",
    re.I,
)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:48]


def _event_tokens(text):
    stop = {"the", "a", "an", "to", "for", "at", "of", "and", "when", "until", "wait"}
    return {
        t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if t not in stop and len(t) > 1
    }


def parse_schedule_tags(text):
    """Extract structured [SCHEDULE: … | +Nh] tags from narrator output."""
    if not text:
        return []
    found = []
    seen = set()
    for m in _SCHEDULE_TAG.finditer(text):
        if m.group("id"):
            eid = m.group("id").strip().lower()
            label = (m.group("label_id") or "").strip()
            hours = int(m.group("hours_id") or 0)
        else:
            label = (m.group("label") or "").strip()
            eid = _slug(label) or "scheduled_event"
            hours = int(m.group("hours") or 0)
        if not label or hours <= 0 or eid in seen:
            continue
        seen.add(eid)
        found.append({"id": eid, "label": label, "hours_from_now": hours, "source": "tag"})
    return found


def strip_schedule_tags(text):
    """Remove simulation tags before showing prose to the player."""
    if not text:
        return text
    cleaned = _SCHEDULE_TAG.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _area_store(player, area_id):
    if not area_id:
        return {}
    return player.setdefault("scheduled_events", {}).setdefault(area_id, {})


def extract_event_promises(text):
    """Find schedulable event promises in prose, dialogue, or structured tags."""
    if not text:
        return []
    found = []
    seen = set()
    for p in parse_schedule_tags(text):
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        found.append(p)
    for pattern, eid, delta, label in _EVENT_PROMISES:
        if not pattern.search(text):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        found.append({"id": eid, "label": label, "hours_from_now": delta, "source": "regex"})
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
                "source": p.get("source", "narration"),
            }
            changed = True
        else:
            rec = store[eid]
            if not rec.get("fired") and rec.get("fires_at_hour", hc) <= hc:
                rec["fires_at_hour"] = hc + p["hours_from_now"]
                rec["label"] = p["label"]
                changed = True
    return changed


def list_pending_events(player, area_id):
    store = _area_store(player, area_id)
    return [e for e in store.values() if not e.get("fired")]


def _event_query_match(query, event):
    """Token overlap between wait-for phrasing and a stored event."""
    if not query:
        return False
    label = (event.get("label") or "").lower()
    eid = (event.get("id") or "").lower()
    q = _event_tokens(query)
    if not q:
        return False
    label_t = _event_tokens(label)
    id_t = _event_tokens(eid.replace("_", " "))
    overlap = q & (label_t | id_t)
    if len(overlap) >= 2:
        return True
    if len(overlap) >= 1 and len(q) <= 4:
        return True
    if query in label or label in query:
        return True
    q_norm = re.sub(r"[^a-z0-9]+", " ", query)
    l_norm = re.sub(r"[^a-z0-9]+", " ", label)
    if q_norm and (q_norm in l_norm or l_norm in q_norm):
        return True
    if "third toll" in query and "third" in eid:
        return True
    if "second toll" in query and "second" in eid:
        return True
    if "first toll" in query and "first" in eid:
        return True
    if "tide" in query and "bell" in query and "tide" in label and "bell" in label:
        return True
    if ("chute" in query or "coal" in query) and ("chute" in label or "coal" in label):
        return True
    if "boys" in query and "boys" in label:
        return True
    return False


def parse_wait_for_event(action, player, area_id):
    """Match a wait-for action to a pending scheduled event."""
    if not action or not area_id:
        return None
    text = action.lower()
    if not re.search(r"\bwait\s+(?:for|until)\b", text):
        return None
    store = _area_store(player, area_id)
    m = _WAIT_FOR_EVENT.search(action.strip())
    query = (m.group(1) if m else action).lower().strip()
    for event in store.values():
        if event.get("fired"):
            continue
        if _event_query_match(query, event):
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
        "- When you promise a timed plot event in dialogue, append on its own line: "
        "[SCHEDULE: event_id | human-readable label | +Nh] (simulation tag — stripped from player prose)."
    )
    lines.append(
        "- Do NOT invent timed plot events the player can wait for unless listed above or tagged."
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
