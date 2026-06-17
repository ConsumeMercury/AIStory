"""
Rank player-relevant memories for narrator context.

Keyword scoring is always available. When Gemini is configured, hybrid
semantic+keyword retrieval improves paraphrase recall.
"""

import os

from simulation.memory_embeddings import rank_by_embedding, semantic_memory_enabled

_PLAYER_EVENT_TYPES = frozenset({
    "player_action",
    "player_interaction",
})

_PLAYER_ACTORS = frozenset({"player"})

_LOW_STAKES_SEMANTIC_KINDS = frozenset({
    "observe", "rest", "withdraw", "ask_name", "wait", "meta_skip",
})


def semantic_retrieval_enabled_for_kind(kind=None):
    if os.environ.get("AISTORY_SKIP_SEMANTIC_MEMORY", "").lower() in ("1", "true", "yes"):
        return False
    if kind in _LOW_STAKES_SEMANTIC_KINDS:
        return False
    return semantic_memory_enabled()


def _event_text(memory):
    if not isinstance(memory, dict):
        return ""
    return " ".join(
        str(memory.get(field, ""))
        for field in ("action", "type", "actor", "location", "target")
    )


def player_relevant_events(memories):
    """Filter simulation noise — player actions and interactions only."""
    out = []
    for memory in memories or []:
        if not isinstance(memory, dict):
            continue
        etype = memory.get("type", "")
        actor = memory.get("actor", "")
        if etype in _PLAYER_EVENT_TYPES or actor in _PLAYER_ACTORS:
            out.append(memory)
    return out


def _keyword_score(memory, query_words):
    text = _event_text(memory).lower()
    score = float(memory.get("importance", 0))
    score += sum(1 for word in query_words if word in text) * 20
    return score


def _focal_boost(memory, focal_npc_id):
    if not focal_npc_id or not isinstance(memory, dict):
        return 0
    target = memory.get("target")
    actor = memory.get("actor")
    if target == focal_npc_id or actor == focal_npc_id:
        return 55
    if memory.get("type") == "journal_beat" and memory.get("focus_npc") == focal_npc_id:
        return 45
    return 0


def _build_retrieval_query(query, *, player=None, area=None, focal_npc_id=None, npcs=None, kind=None):
    parts = [query or "", kind or ""]
    if area:
        parts.append(str(area).lower().replace("_", " "))
    if focal_npc_id and npcs:
        npc = npcs.get(focal_npc_id) or {}
        parts.extend([
            npc.get("name") or "",
            npc.get("role") or "",
            focal_npc_id,
        ])
    if player and focal_npc_id:
        for entry in (player.get("journal") or [])[-4:]:
            if entry.get("focus_npc") == focal_npc_id:
                parts.append(entry.get("action") or "")
                break
    return " ".join(p for p in parts if p).strip()


def _journal_candidates(player, query_words, *, focal_npc_id=None):
    """Journal summaries and recent excerpts as retrieval candidates."""
    candidates = []
    from simulation.journal_summary import normalize_summaries, _summary_text

    for i, rec in enumerate(normalize_summaries((player or {}).get("journal_summaries"))):
        text = _summary_text(rec)
        if not text:
            continue
        score = sum(1 for w in query_words if w in text.lower()) * 15
        candidates.append({
            "id": rec.get("vector_key") or f"journal_summary:{i}",
            "text": text,
            "score": score,
            "kind": "journal_summary",
            "memory": {"type": "journal_summary", "action": text[:200], "actor": "journal"},
        })

    for entry in (player or {}).get("journal") or []:
        action = (entry.get("action") or "")[:120]
        excerpt = (entry.get("excerpt") or "")[:200]
        text = f"{action} {excerpt}".strip()
        if not text:
            continue
        tick = entry.get("tick", "?")
        score = sum(1 for w in query_words if w in text.lower()) * 12
        focus_npc = entry.get("focus_npc")
        mem = {
            "type": "journal_beat",
            "action": action,
            "actor": "player",
            "location": entry.get("place") or entry.get("location"),
            "focus_npc": focus_npc,
        }
        if focus_npc == focal_npc_id:
            score += 40
        candidates.append({
            "id": f"journal_beat:{tick}",
            "text": text,
            "score": score,
            "kind": "journal_beat",
            "memory": mem,
        })
    return candidates


def get_relevant_memories(
    memories,
    query,
    limit=20,
    *,
    player=None,
    area=None,
    focal_npc_id=None,
    npcs=None,
    kind=None,
):
    """
    Rank logged events and journal memories by relevance to query text.

    Scoped to player-relevant events plus journal summaries/beats — not raw tick stream.
    """
    retrieval_query = _build_retrieval_query(
        query,
        player=player,
        area=area,
        focal_npc_id=focal_npc_id,
        npcs=npcs,
        kind=kind,
    )
    query_words = set((retrieval_query or query or "").lower().split())
    if area:
        area_l = area.lower().replace("_", " ")
        query_words.update(w for w in area_l.split() if len(w) > 3)

    candidates = []

    for memory in player_relevant_events(memories):
        score = _keyword_score(memory, query_words) + _focal_boost(memory, focal_npc_id)
        if score <= 0 and not query_words:
            score = 1
        mid = memory.get("id") or f"event:{memory.get('tick')}:{memory.get('action', '')[:20]}"
        candidates.append({
            "id": mid,
            "text": _event_text(memory),
            "score": score,
            "kind": "event",
            "memory": memory,
        })

    if player:
        candidates.extend(_journal_candidates(player, query_words, focal_npc_id=focal_npc_id))

    if not candidates:
        return []

    if player and semantic_retrieval_enabled_for_kind(kind):
        ranked = rank_by_embedding(retrieval_query or query, candidates, player, limit=limit)
    else:
        ranked = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:limit]

    return [c["memory"] for c in ranked if c.get("memory")]
