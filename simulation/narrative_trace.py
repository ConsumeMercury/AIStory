"""
Narrative boundary instrumentation — stakes, structure, promises (shadow validation).

Deterministic metrics for debug_state and future regen gates; no LLM calls.
"""

from simulation.narrative_promises import list_promises
from simulation.story_manager import get_active_arcs, get_primary_arc

_SOCIAL_KINDS = frozenset({
    "talk", "ask_about", "personal_talk", "accuse", "blackmail", "confess",
})


def build_narrative_trace(
    player,
    *,
    kind,
    action_ctx=None,
    npcs=None,
    areas=None,
    focal_npc_id=None,
    narrator_blocks=None,
    structure_mode=None,
):
    """Compact narrative state for boundary trace / offline review."""
    stakes = player.get("scene_stakes") or {}
    arc = get_primary_arc(player, npcs, areas=areas)
    arcs = get_active_arcs(player, npcs, areas=areas)
    open_p = list_promises(player)

    blocks = narrator_blocks
    if blocks is None:
        blocks = (action_ctx or {}).get("narrator_blocks_included")

    return {
        "dramatic_question": (stakes.get("dramatic_question") or "")[:120] or None,
        "gain": stakes.get("gain"),
        "lose": stakes.get("lose"),
        "purpose": (stakes.get("purpose") or "")[:90] or None,
        "arc_id": stakes.get("arc_id") or (arc.get("arc_id") if arc else None),
        "arc_title": (arc.get("title") or "")[:80] if arc else None,
        "arc_kind": arc.get("kind") if arc else None,
        "active_arc_count": len(arcs),
        "structure_mode": structure_mode or (action_ctx or {}).get("structure_mode"),
        "promises_open": len(open_p),
        "promises_sample": [p.get("label", "")[:60] for p in open_p[:3]],
        "narrator_blocks_included": list(blocks or []),
        "narrator_block_count": len(blocks or []),
        "focal_npc_id": focal_npc_id or (action_ctx or {}).get("target_id"),
    }


def validate_narrative_function(
    player,
    *,
    kind,
    action_ctx=None,
    raw_scene=None,
    structure_mode=None,
    focal_npc_id=None,
):
    """Shadow narrative checks — recorded on boundary trace, no regen yet."""
    issues = []
    ctx = action_ctx or {}
    stakes = player.get("scene_stakes") or {}
    scene = (raw_scene or "").strip().lower()
    mode = structure_mode or ctx.get("structure_mode")
    q = (stakes.get("dramatic_question") or "").strip()

    if q and "the plot" in q.lower():
        issues.append("dramatic_question uses generic placeholder 'the plot'")

    if kind in _SOCIAL_KINDS and not q and not ctx.get("absent_npc"):
        issues.append("social beat lacks dramatic_question in scene_stakes")

    if mode == "stalled" and scene and len(scene) > 800:
        stall_markers = ("still", "nothing", "wait", "unchanged", "blocked", "cannot", "can't")
        if not any(w in scene for w in stall_markers):
            issues.append("stalled beat prose may not acknowledge lack of change")

    open_p = list_promises(player)
    if open_p and mode == "continuation" and scene and len(scene) > 600:
        tokens = []
        for p in open_p[:3]:
            label = (p.get("label") or "").lower()
            tokens.extend(t for t in label.split() if len(t) > 4)
        if tokens and not any(t in scene for t in tokens[:5]):
            issues.append("continuation beat may ignore open narrative promises")

    blocks = ctx.get("narrator_blocks_included") or []
    if kind in ("explore", "investigate", "accuse") and "story_manager" not in blocks:
        issues.append("story_manager block omitted on story-forward beat")

    return issues
