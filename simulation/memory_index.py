"""
Unified memory retrieval facade — events, journal, narrative memories.

Single entry point for narrator memory assembly; delegates to memory_retrieval
and merges narrative_memories with shared importance scoring.
"""

from simulation.importance_router import score_memory_record
from simulation.memory_retrieval import get_relevant_memories


def _narrative_memory_candidates(player, query_words, *, focal_npc_id=None):
    candidates = []
    for i, mem in enumerate((player or {}).get("narrative_memories") or []):
        text = (mem.get("story_meaning") or mem.get("summary") or "").strip()
        if not text:
            continue
        score = score_memory_record(mem, player=player)
        score += sum(1 for w in query_words if w in text.lower()) * 14
        if focal_npc_id and focal_npc_id in text.lower():
            score += 20
        candidates.append({
            "id": mem.get("id") or f"narrative:{i}",
            "text": text,
            "score": score,
            "memory": {
                "type": "narrative_memory",
                "action": text[:200],
                "actor": "story",
                "importance": score,
            },
        })
    return candidates


def retrieve_memories_for_beat(
    events,
    query,
    *,
    limit=20,
    player=None,
    area=None,
    focal_npc_id=None,
    npcs=None,
    kind=None,
    action_ctx=None,
):
    """
    Ranked memory dicts for narrator context — events, journal, narrative layer.
    """
    ctx = action_ctx or {}
    plan = ctx.get("beat_plan") or {}
    enriched = (plan.get("memory_query") or "").strip()
    if enriched:
        query = enriched
    elif query and plan.get("dramatic_question"):
        query = f"{query} {plan['dramatic_question']}"

    query_words = set((query or "").lower().split())
    if area:
        query_words.update(w for w in area.lower().replace("_", " ").split() if len(w) > 3)

    event_hits = get_relevant_memories(
        events,
        query,
        limit=limit,
        player=player,
        area=area,
        focal_npc_id=focal_npc_id,
        npcs=npcs,
        kind=kind,
    )

    if not player:
        return event_hits[:limit]

    narrative = _narrative_memory_candidates(player, query_words, focal_npc_id=focal_npc_id)
    narrative.sort(key=lambda c: c.get("score", 0), reverse=True)

    seen_text = set()
    merged = []
    for mem in event_hits:
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    for cand in narrative[: max(3, limit // 4)]:
        mem = cand["memory"]
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    merged.sort(
        key=lambda m: score_memory_record(
            {"importance": m.get("importance"), "story_meaning": m.get("action"), "text": m.get("action")},
            player=player,
        ),
        reverse=True,
    )
    return merged[:limit]
