"""
Narrative boundary instrumentation — stakes, structure, promises, soft regen gate.
"""

import os

from simulation.narrative_promises import list_promises
from simulation.story_manager import get_active_arcs, get_primary_arc

_SOCIAL_KINDS = frozenset({
    "talk", "ask_about", "personal_talk", "accuse", "blackmail", "confess",
})

_NARRATIVE_REGEN_PRIORITY = {
    "generic placeholder": 48,
    "lacks dramatic_question": 52,
    "story_manager block omitted": 55,
    "stalled beat prose": 38,
    "open narrative promises": 32,
}


def narrative_regen_mode():
    """
    off     — observe only
    shadow  — observe only (alias)
    soft    — regen on priority >= 50 (default)
    on      — regen on priority >= 35
    """
    raw = (os.environ.get("AISTORY_NARRATIVE_REGEN") or "soft").strip().lower()
    if raw in ("off", "shadow", "soft", "on"):
        return raw
    return "soft"


def _issue_priority(issue_text):
    text = (issue_text or "").lower()
    best = 0
    for key, score in _NARRATIVE_REGEN_PRIORITY.items():
        if key in text:
            best = max(best, score)
    return best or 25


def narrative_issues_for_regen(issues, *, kind=None):
    """Filter narrative issues that should participate in regen loop."""
    mode = narrative_regen_mode()
    if mode in ("off", "shadow") or not issues:
        return []
    threshold = 50 if mode == "soft" else 35
    out = []
    for issue in issues:
        if _issue_priority(issue) >= threshold:
            out.append(f"narrative: {issue}")
    return out


def build_narrative_correction_block(issues):
    if not issues:
        return ""
    lines = [
        "NARRATIVE OBLIGATION (rewrite — advance story meaning, not filler):",
    ]
    stakes_lines = []
    for issue in issues[:5]:
        if "dramatic_question" in issue or "story_manager" in issue:
            stakes_lines.append(f"- Fix: {issue}")
        else:
            stakes_lines.append(f"- {issue}")
    return "\n".join(lines + stakes_lines)


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
    arc_state = player.get("story_arc_state") or {}

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
        "arc_stage": arc_state.get("stage", arc.get("stage") if arc else None),
        "active_arc_count": len(arcs),
        "structure_mode": structure_mode or (action_ctx or {}).get("structure_mode"),
        "promises_open": len(open_p),
        "promises_sample": [p.get("label", "")[:60] for p in open_p[:3]],
        "narrator_blocks_included": list(blocks or []),
        "narrator_block_count": len(blocks or []),
        "focal_npc_id": focal_npc_id or (action_ctx or {}).get("target_id"),
        "regen_mode": narrative_regen_mode(),
        "orchestrator": (action_ctx or {}).get("story_orchestrator") or {},
        "beat_plan_arc_stage": ((action_ctx or {}).get("beat_plan") or {}).get("arc_stage"),
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
    """Narrative checks — recorded on boundary trace; may gate regen when enabled."""
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
