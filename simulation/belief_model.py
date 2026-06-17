"""
Structured NPC beliefs — proposition + confidence updated from rumors and events.

Complements episodic memories with durable world-model propositions.
"""

import re

MAX_BELIEFS = 24

PROPOSITION_PATTERNS = (
    ("player_is_murderer", re.compile(r"\b(murder(?:ed|s)?|killed|slain|assassin|blood)\b", re.I)),
    ("player_is_hero", re.compile(r"\b(hero|saved|rescued|brave|slew.*monster)\b", re.I)),
    ("player_is_thief", re.compile(r"\b(stole|theft|pickpocket|thief|snatch)\b", re.I)),
    ("player_is_dangerous", re.compile(r"\b(dangerous|violent|menace|threaten)\b", re.I)),
    ("guild_is_corrupt", re.compile(r"\b(guild.*corrupt|fixing.*scale|bribe|fraud)\b", re.I)),
    ("temple_in_trouble", re.compile(r"\b(temple|altar|relic|pilgrim).*(trouble|missing|stolen|burn)\b", re.I)),
)


def _clamp_confidence(val):
    return max(0.0, min(1.0, round(float(val), 3)))


def get_beliefs(npc):
    return npc.setdefault("beliefs", [])


def upsert_belief(npc, proposition, confidence_delta, *, source="rumor", tick=None, day=None):
    """Add or adjust confidence for a proposition on one NPC."""
    if not proposition:
        return False
    beliefs = get_beliefs(npc)
    for b in beliefs:
        if b.get("proposition") == proposition:
            b["confidence"] = _clamp_confidence(b.get("confidence", 0.3) + confidence_delta)
            b["source"] = source
            b["tick"] = tick
            b["day"] = day
            return True
    beliefs.append({
        "proposition": proposition,
        "confidence": _clamp_confidence(0.25 + confidence_delta),
        "source": source,
        "tick": tick,
        "day": day,
    })
    npc["beliefs"] = sorted(beliefs, key=lambda x: x.get("confidence", 0), reverse=True)[:MAX_BELIEFS]
    return True


def infer_propositions(text):
    if not text:
        return []
    hits = []
    for prop, pat in PROPOSITION_PATTERNS:
        if pat.search(text):
            hits.append(prop)
    return hits


def update_beliefs_from_rumor(npc, rumor, *, tick=None, day=None):
    text = rumor.get("text", "")
    if not text:
        return []
    interp = (rumor.get("interpretation") or "").lower()
    base = 0.12
    if interp in ("dangerous", "suspicious", "worrying"):
        base = 0.18
    elif interp in ("heroic",):
        base = 0.16
    updated = []
    for prop in infer_propositions(text):
        upsert_belief(npc, prop, base, source="rumor", tick=tick, day=day)
        updated.append(prop)
    if "outsider" in text.lower() or "stranger" in text.lower():
        upsert_belief(npc, "outsider_is_notable", 0.08, source="rumor", tick=tick, day=day)
        updated.append("outsider_is_notable")
    return updated


def update_beliefs_from_event(npc, event, *, tick=None):
    if not event:
        return []
    text = " ".join(
        str(event.get(k, "")) for k in ("action", "type", "target")
    )
    updated = []
    for prop in infer_propositions(text):
        delta = 0.22 if int(event.get("importance", 30)) >= 70 else 0.14
        upsert_belief(npc, prop, delta, source="witnessed", tick=tick)
        updated.append(prop)
    return updated


def top_beliefs(npc, *, min_confidence=0.35, limit=4):
    return [
        b for b in get_beliefs(npc)
        if b.get("confidence", 0) >= min_confidence
    ][:limit]


def focal_belief_block(npc_id, npcs):
    npc = (npcs or {}).get(npc_id, {})
    beliefs = top_beliefs(npc)
    if not beliefs:
        return ""
    lines = []
    for b in beliefs:
        prop = (b.get("proposition") or "").replace("_", " ")
        conf = int(b.get("confidence", 0) * 100)
        lines.append(f"- believes ({conf}%): {prop}")
    label = npc.get("name") or npc_id
    return (
        f"FOCAL BELIEFS ({label} — colors tone, do not lecture the player):\n"
        + "\n".join(lines)
    )


def sync_beliefs_from_memories(npc_id, npc, mem_store):
    """Backfill structured beliefs from existing rumor memories."""
    mems = (mem_store or {}).get(npc_id, [])[-10:]
    for mem in mems:
        if mem.get("source") != "rumor":
            continue
        update_beliefs_from_rumor(
            npc,
            {"text": mem.get("summary", ""), "interpretation": "uncertain"},
            tick=mem.get("tick"),
            day=mem.get("day"),
        )
