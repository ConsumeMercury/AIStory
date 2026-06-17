"""
Rank simulation context for narrator injection — importance and thread relevance.
"""

from simulation.importance_router import rank_rumors, score_rumor


def score_rumor_relevance(rumor, *, player, arc=None, focal_npc_id=None, npcs=None):
    """Backward-compatible alias."""
    return score_rumor(
        rumor, player=player, arc=arc, focal_npc_id=focal_npc_id, npcs=npcs,
    )


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
    return rank_rumors(
        rumors,
        player=player,
        limit=limit,
        focal_npc_id=focal_npc_id,
        npcs=npcs,
        areas=areas,
    )
