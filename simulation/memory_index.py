"""
Unified memory retrieval facade — events, journal, narrative memories.

Single entry point for narrator memory assembly; delegates to memory_retrieval
and merges narrative_memories with shared importance scoring.
"""

from simulation.importance_router import score_memory_record
from simulation.memory_immersion import score_at_retrieval, surface_memory_limit
from simulation.memory_retrieval import get_relevant_memories


def _beat_log_candidates(player, query_words, *, focal_npc_id=None, current_tick=None):
    candidates = []
    for i, rec in enumerate((player or {}).get("beat_memory_log") or []):
        text = (rec.get("story_meaning") or rec.get("action") or "").strip()
        if not text:
            continue
        score = score_at_retrieval(rec, player=player, current_tick=current_tick)
        score += sum(1 for w in query_words if w in text.lower()) * 16
        if focal_npc_id and focal_npc_id == rec.get("target_id"):
            score += 24
        candidates.append({
            "id": rec.get("id") or f"beat:{i}",
            "text": text,
            "score": score,
            "memory": {
                "type": "beat_memory",
                "action": text[:200],
                "actor": "player",
                "importance": rec.get("importance") or score,
                "tick": rec.get("tick"),
            },
        })
    return candidates


def _npc_memory_candidates(focal_npc_id, query_words, *, current_tick=None, limit=2):
    """Subjective NPC memories ranked for this beat."""
    if not focal_npc_id:
        return []
    from simulation.memory_immersion import effective_salience
    from simulation.npc_memory_engine import player_memories

    candidates = []
    for i, mem in enumerate(player_memories(focal_npc_id, n=8)):
        summary = (mem.get("summary") or "").strip()
        if not summary:
            continue
        score = effective_salience(mem, current_tick or 0)
        score += sum(12 for w in query_words if w in summary.lower())
        candidates.append({
            "id": f"npcmem:{focal_npc_id}:{i}",
            "text": summary,
            "score": score,
            "memory": {
                "type": "npc_subjective",
                "action": summary[:200],
                "actor": focal_npc_id,
                "importance": int(score),
                "valence": mem.get("valence"),
                "tick": mem.get("tick"),
            },
        })
    candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
    return candidates[:limit]


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


def memory_limit_for_kind(kind):
    """Default retrieval cap — higher for investigative beats."""
    return surface_memory_limit(kind) + 6 if kind in ("investigate", "accuse", "find") else surface_memory_limit(kind) + 4


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

    current_tick = (player or {}).get("last_tick")
    if current_tick is None:
        current_tick = (ctx or {}).get("tick") or 0
    surface_cap = surface_memory_limit(kind)

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
        return event_hits[:surface_cap]

    narrative = _narrative_memory_candidates(player, query_words, focal_npc_id=focal_npc_id)
    beat_log = _beat_log_candidates(
        player, query_words, focal_npc_id=focal_npc_id, current_tick=current_tick,
    )
    npc_subj = _npc_memory_candidates(
        focal_npc_id, query_words, current_tick=current_tick, limit=2,
    )
    narrative.sort(key=lambda c: c.get("score", 0), reverse=True)
    beat_log.sort(key=lambda c: c.get("score", 0), reverse=True)

    seen_text = set()
    merged = []
    for mem in event_hits:
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    for cand in narrative[: max(2, surface_cap // 2)]:
        mem = cand["memory"]
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    for cand in npc_subj:
        mem = cand["memory"]
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    for cand in beat_log[: max(2, surface_cap // 2)]:
        mem = cand["memory"]
        key = (mem.get("action") or "")[:80].lower()
        if key and key in seen_text:
            continue
        seen_text.add(key)
        merged.append(mem)

    merged.sort(
        key=lambda m: score_at_retrieval(
            {"importance": m.get("importance"), "story_meaning": m.get("action"), "text": m.get("action"),
             "tick": m.get("tick"), "valence": m.get("valence")},
            player=player,
            current_tick=current_tick,
        ),
        reverse=True,
    )
    return merged[:surface_cap]
