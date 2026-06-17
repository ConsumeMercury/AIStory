"""
Promise / payoff tracking — Chekhov objects and setup lines.

Extends scheduled_events with narrative object promises.
"""

import re
import uuid

MAX_PROMISES = 30

PROMISE_PATTERNS = (
    (re.compile(r"\b(strange|odd|unusual)\s+(key|letter|seal|token|map|ledger)\b", re.I), "object"),
    (re.compile(r"\b(third bell|coal.?chute|reliquary|hidden door|back way)\b", re.I), "location"),
    (re.compile(r"\b(will tell you|meet you|gather at|when the .+ rings)\b", re.I), "event"),
)


def _promise_id(label):
    return str(uuid.uuid4())[:10]


def list_promises(player, *, unresolved_only=True):
    promises = player.get("narrative_promises") or []
    if unresolved_only:
        return [p for p in promises if not p.get("resolved")]
    return promises


def record_promise(player, *, label, kind="object", source_tick=None, arc_id=None, promise_id=None):
    if not label:
        return None
    label = label.strip()[:120]
    promises = player.setdefault("narrative_promises", [])
    if any(p.get("label", "").lower() == label.lower() and not p.get("resolved") for p in promises):
        return None
    rec = {
        "id": promise_id or _promise_id(label),
        "label": label,
        "kind": kind,
        "setup_tick": source_tick,
        "arc_id": arc_id,
        "resolved": False,
    }
    promises.append(rec)
    player["narrative_promises"] = promises[-MAX_PROMISES:]
    return rec


def detect_promises_in_scene(player, scene, *, tick=None, kind=None, action_ctx=None):
    """Scan prose for setup objects/locations worth tracking."""
    if not scene:
        return []
    text = scene[:1200]
    stakes = player.get("scene_stakes") or {}
    arc_id = stakes.get("arc_id")
    found = []
    for pat, pkind in PROMISE_PATTERNS:
        m = pat.search(text)
        if m:
            label = m.group(0).strip()
            rec = record_promise(
                player,
                label=label,
                kind=pkind,
                source_tick=tick,
                arc_id=arc_id,
            )
            if rec:
                found.append(rec)
    item = (action_ctx or {}).get("acquired_item")
    if item and item.get("name"):
        rec = record_promise(
            player,
            label=item["name"],
            kind="inventory",
            source_tick=tick,
            arc_id=arc_id,
        )
        if rec:
            found.append(rec)
    return found


def resolve_promise(player, label_or_id, *, tick=None):
    promises = player.get("narrative_promises") or []
    label_l = (label_or_id or "").lower()
    resolved = False
    for p in promises:
        if p.get("resolved"):
            continue
        if p.get("id") == label_or_id or label_l in (p.get("label") or "").lower():
            p["resolved"] = True
            p["payoff_tick"] = tick
            resolved = True
    return resolved


def try_resolve_from_action(player, action, kind, *, tick=None):
    """Pay off promises when player explicitly references the setup."""
    if not action:
        return []
    text = action.lower()
    paid = []
    for p in list_promises(player):
        label = (p.get("label") or "").lower()
        if not label or len(label) < 4:
            continue
        tokens = [t for t in re.split(r"\W+", label) if len(t) > 3]
        if tokens and any(t in text for t in tokens[:3]):
            if resolve_promise(player, p["id"], tick=tick):
                paid.append(p)
    return paid


def unresolved_promises_block(player, *, limit=3):
    open_p = list_promises(player)
    if not open_p:
        return ""
    lines = ["UNRESOLVED SETUPS (pay these off or complicate — do not forget):"]
    for p in open_p[-limit:]:
        lines.append(f"- [{p.get('kind', '?')}] {p.get('label', '')[:90]}")
    return "\n".join(lines)
