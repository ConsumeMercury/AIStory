"""
Rank simulation context for narrator injection — importance and thread relevance.
"""

from simulation.story_manager import get_primary_arc


def _arc_keywords(arc):
    if not arc:
        return set()
    words = set()
    for field in ("title", "next_beat", "hook", "stage_label"):
        text = (arc.get(field) or "").lower()
        words.update(w for w in text.split() if len(w) > 3)
    for nid in arc.get("key_npc_ids") or []:
        words.add(str(nid).lower())
    return words


def score_rumor_relevance(rumor, *, player, arc=None, focal_npc_id=None, npcs=None):
    """Higher score = more worth whispering to the narrator this beat."""
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
    for kw in _arc_keywords(arc):
        if kw in text:
            score += 12

    if focal_npc_id and npcs:
        npc = npcs.get(focal_npc_id) or {}
        name = (npc.get("name") or "").lower()
        if name and name in text:
            score += 22

    interp = rumor.get("interpretation", "")
    if interp in ("dangerous", "scandalous", "mysterious", "suspicious"):
        score += 8

    return score


def rank_rumors_for_narrator(
    rumors,
    *,
    player,
    kind,
    limit=3,
    focal_npc_id=None,
    npcs=None,
    areas=None,
):
    """Return top rumors for this beat instead of naive tail slice."""
    if not rumors:
        return []
    from simulation.narrator_blocks import rumor_whisper_limit

    limit = limit or rumor_whisper_limit(kind)
    arc = get_primary_arc(player, npcs, areas=areas)
    pool = list(rumors[-40:])
    scored = [
        (score_rumor_relevance(r, player=player, arc=arc, focal_npc_id=focal_npc_id, npcs=npcs), r)
        for r in pool
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for s, r in scored if s > 0][:limit]
