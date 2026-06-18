"""
Unified memory record schema — canonical beat facts with derived weight views.

Single write shape on player.beat_memory_log; other stores remain projections
until a full migration. Old log entries without weight fields still work.
"""

import uuid

_EMOTIONAL_KINDS = frozenset({
    "attack", "help", "threaten", "insult", "confess", "accuse", "blackmail", "give",
})
_SOCIAL_KINDS = frozenset({
    "talk", "personal_talk", "ask_about", "ask_name", "trade", "guild", "accuse",
})
_CAUSAL_KINDS = frozenset({
    "attack", "accuse", "confess", "blackmail", "steal", "investigate", "find",
})

_TAG_EMOTION = {
    "attack": 0.95,
    "help": 0.65,
    "gift": 0.45,
    "threat": 0.75,
    "insult": 0.55,
    "theft": 0.8,
    "trade": 0.15,
    "socialise": 0.2,
    "general": 0.1,
}


def compute_memory_weights(*, kind, importance, memory_tag=None, interaction_event=None):
    """Derive view weights from beat metadata — used for retrieval ranking."""
    imp = max(1, min(100, int(importance or 40)))
    tag = memory_tag or "general"
    emotional = abs(_TAG_EMOTION.get(tag, 0.1)) * 100
    if kind in _EMOTIONAL_KINDS:
        emotional = min(100, emotional + 18)
    if interaction_event and interaction_event.get("effects"):
        emotional = min(100, emotional + 10)

    narrative = float(imp)
    social = 22.0
    if kind in _SOCIAL_KINDS or tag in ("socialise", "trade"):
        social = min(100, 35 + imp * 0.35)
    causal = 18.0
    if kind in _CAUSAL_KINDS:
        causal = min(100, 40 + imp * 0.45)

    return {
        "emotional_weight": round(emotional, 1),
        "narrative_weight": round(narrative, 1),
        "social_weight": round(social, 1),
        "causal_weight": round(causal, 1),
    }


def build_memory_record(
    *,
    kind,
    action,
    action_ctx,
    tick,
    focal_id,
    witness_ids,
    importance,
    story_meaning=None,
    interaction_event=None,
):
    """Canonical MemoryRecord for beat_memory_log."""
    ctx = action_ctx or {}
    arc_id = (ctx.get("beat_plan") or {}).get("arc_id")
    if not arc_id:
        stakes_arc = (ctx.get("scene_stakes") or {}).get("arc_id")
        arc_id = stakes_arc
    target_id = ctx.get("target_id") or focal_id
    mem_tag = ctx.get("memory_tag", "general")
    weights = compute_memory_weights(
        kind=kind,
        importance=importance,
        memory_tag=mem_tag,
        interaction_event=interaction_event,
    )
    fact = (story_meaning or action or "")[:240]
    participants = ["player"]
    for wid in witness_ids or []:
        if wid and wid not in participants:
            participants.append(wid)
    if target_id and target_id not in participants:
        participants.append(target_id)

    return {
        "id": str(uuid.uuid4())[:12],
        "tick": tick,
        "kind": kind,
        "action": (action or "")[:200],
        "target_id": target_id,
        "focal_id": focal_id,
        "witness_ids": list(witness_ids or [])[:12],
        "importance": int(importance or 40),
        "story_meaning": fact or None,
        "fact": fact or None,
        "arc_id": arc_id,
        "participants": participants[:14],
        "source": "player_beat",
        "grounding": "witnessed",
        "memory_tag": mem_tag,
        **weights,
    }


def record_weights(record):
    """Safe weight read for legacy records missing new fields."""
    if not isinstance(record, dict):
        return {}
    imp = int(record.get("importance") or record.get("narrative_weight") or 40)
    return {
        "emotional_weight": float(record.get("emotional_weight") or 0),
        "narrative_weight": float(record.get("narrative_weight") or imp),
        "social_weight": float(record.get("social_weight") or 0),
        "causal_weight": float(record.get("causal_weight") or 0),
    }


def combined_retrieval_score(record, *, player=None, current_tick=None):
    """Blend weights for ranking — used by memory_index / immersion."""
    from simulation.memory_immersion import score_at_retrieval

    base = score_at_retrieval(record, player=player, current_tick=current_tick)
    w = record_weights(record)
    blend = (
        w["narrative_weight"] * 0.45
        + w["emotional_weight"] * 0.25
        + w["social_weight"] * 0.15
        + w["causal_weight"] * 0.15
    )
    return max(base, blend * 0.85)
