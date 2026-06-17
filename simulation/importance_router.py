"""
Universal importance routing — one scoring layer for sim, memory, and narrator.

Wraps event_importance and arc/focal boosts used across subsystems.
"""

from simulation.event_importance import score_event_importance
from simulation.story_manager import get_primary_arc

_GROUNDING_BOOST = {
    "witnessed": 12,
    "rumored": 6,
    "inferred": 4,
}


def arc_keywords(arc):
    if not arc:
        return set()
    words = set()
    for field in ("title", "next_beat", "hook", "stage_label"):
        text = (arc.get(field) or "").lower()
        words.update(w for w in text.split() if len(w) > 3)
    for nid in arc.get("key_npc_ids") or []:
        words.add(str(nid).lower())
    return words


def score_event(event, *, player=None, arc=None):
    if not isinstance(event, dict):
        return 1
    base = int(event.get("importance") or score_event_importance(
        event.get("type"), event.get("action"),
        effects=event.get("effects"), target=event.get("target"),
    ))
    if player and arc is None:
        arc = get_primary_arc(player)
    text = " ".join(
        str(event.get(k, "")) for k in ("action", "type", "target", "location")
    ).lower()
    for kw in arc_keywords(arc):
        if kw in text:
            base += 10
            break
    return max(1, min(100, base))


def score_rumor(rumor, *, player, arc=None, focal_npc_id=None, npcs=None):
    """Rumor relevance for narrator whispers and sim spread priority."""
    if not isinstance(rumor, dict):
        return 0
    score = int(rumor.get("spread") or 20)
    text = (rumor.get("text") or "").lower()
    if not text:
        return 0

    city = (player.get("location") or "").lower().replace("_", " ")
    area_tail = (player.get("area") or "").split(":")[-1].lower().replace("_", " ")
    if city and city in text:
        score += 15
    if area_tail and len(area_tail) > 3 and area_tail in text:
        score += 10

    arc = arc if arc is not None else get_primary_arc(player, npcs)
    for kw in arc_keywords(arc):
        if kw in text:
            score += 12

    if focal_npc_id and npcs:
        name = ((npcs.get(focal_npc_id) or {}).get("name") or "").lower()
        if name and name in text:
            score += 22

    interp = rumor.get("interpretation", "")
    if interp in ("dangerous", "scandalous", "mysterious", "suspicious"):
        score += 8

    imp = rumor.get("importance")
    if imp is not None:
        score = max(score, int(imp))

    return max(1, min(100, score))


def score_npc(npc, *, player, arc=None, institutions=None, npc_id=None):
    """Simulation tick weight baseline from story and proximity."""
    if not npc or npc.get("status") != "alive":
        return 0.0
    arc = arc if arc is not None else get_primary_arc(player)
    key_ids = set(arc.get("key_npc_ids") or []) if arc else set()
    nid = npc_id or npc.get("id")
    score = 10.0

    player_area = player.get("area")
    player_city = player.get("location")
    if npc.get("area") == player_area:
        score += 25
    elif npc.get("location") == player_city:
        score += 10

    if nid in key_ids:
        score += 35
    if nid == player.get("scene_focus"):
        score += 28

    inst = npc.get("institution") or {}
    if inst.get("rank") in ("leader", "master", "captain", "high priest"):
        score += 12

    if (npc.get("personal_objective") or {}).get("text"):
        score += 8

    beliefs = npc.get("beliefs") or []
    if beliefs:
        top = max(b.get("confidence", 0) for b in beliefs)
        score += top * 15

    return score


def score_memory_record(record, *, player=None, arc=None):
    """Narrative memory / journal candidate importance."""
    if not isinstance(record, dict):
        return 1
    base = int(record.get("importance") or 40)
    text = (record.get("story_meaning") or record.get("text") or record.get("action") or "").lower()
    arc = arc if arc is not None else (get_primary_arc(player) if player else None)
    for kw in arc_keywords(arc):
        if kw in text:
            base += 12
            break
    grounding = (record.get("grounding") or record.get("source") or "").lower()
    base += _GROUNDING_BOOST.get(grounding, 0)
    return max(1, min(100, base))


def should_retain_memory(record, *, threshold=35, player=None):
    return score_memory_record(record, player=player) >= threshold


_JOURNAL_KIND_BOOST = {
    "attack": 28,
    "accuse": 24,
    "confess": 24,
    "blackmail": 22,
    "investigate": 18,
    "find": 14,
    "search": 10,
    "talk": 8,
    "ask_about": 12,
    "personal_talk": 10,
    "travel": 6,
    "explore": 5,
}


def score_journal_entry(entry, *, player=None):
    """Rank journal beats for retention when trimming long campaigns."""
    if not isinstance(entry, dict):
        return 1
    base = 28
    kind = entry.get("kind") or ""
    base += _JOURNAL_KIND_BOOST.get(kind, 0)
    if entry.get("combat_fatal"):
        base += 22
    if entry.get("target_ambiguous"):
        base += 6
    boundary = entry.get("boundary") or {}
    if boundary.get("regen", {}).get("attempts"):
        base += 8
    if boundary.get("auditor", {}).get("confirmed_count"):
        base += 5
    text = " ".join(
        str(entry.get(k, "")) for k in ("action", "excerpt", "scene", "place")
    ).lower()
    arc = get_primary_arc(player) if player else None
    for kw in arc_keywords(arc):
        if kw in text:
            base += 10
            break
    return max(1, min(100, base))


def rank_rumors(rumors, *, player, limit=3, focal_npc_id=None, npcs=None, areas=None):
    """Sorted rumors for narrator injection."""
    if not rumors:
        return []
    arc = get_primary_arc(player, npcs, areas=areas)
    pool = list(rumors[-40:])
    scored = [
        (score_rumor(r, player=player, arc=arc, focal_npc_id=focal_npc_id, npcs=npcs), r)
        for r in pool
    ]
    scored.sort(key=lambda row: row[0], reverse=True)
    return [r for s, r in scored if s > 0][:limit]
