"""
Story orchestrator — single beat-planning layer between simulation and narrator.

prepare_beat() runs before prose: stakes, arc sync, memory query, scene intent.
finalize_beat() runs after prose: causal pressure and arc bookkeeping.
"""

from simulation.narrative_promises import list_promises
from simulation.sim_priorities import build_sim_priorities
from simulation.story_manager import (
    beat_obligation_directive,
    get_primary_arc,
    record_turn_story_progress,
)

_STORY_FORWARD_KINDS = frozenset({
    "investigate", "ask_about", "accuse", "find", "search", "attack",
    "blackmail", "explore", "talk", "personal_talk",
})

_INTENT_BY_KIND = {
    "ask_about": "extract or deflect information",
    "investigate": "surface evidence or contradiction",
    "accuse": "force a reckoning",
    "blackmail": "apply leverage",
    "confess": "witness truth land",
    "attack": "violence with cost",
    "explore": "orient and foreshadow",
    "talk": "advance relationship or agenda",
    "personal_talk": "deepen trust or fracture it",
    "search": "discover object or absence",
    "find": "locate a person",
    "wait": "let time change the board",
}


def _arc_stage(player, arc):
    state = player.get("story_arc_state") or {}
    if arc and state.get("arc_id") == arc.get("arc_id"):
        return int(state.get("stage", arc.get("stage") or 0))
    return int(arc.get("stage") or 0) if arc else 0


def build_memory_query(player, action, *, kind, action_ctx, arc, npcs=None):
    """Expanded retrieval query biased toward active arc and open threads."""
    ctx = action_ctx or {}
    parts = [action or "", kind or ""]
    if arc:
        for field in ("title", "stage_label", "next_beat", "hook"):
            val = arc.get(field)
            if val:
                parts.append(str(val))
        for nid in (arc.get("key_npc_ids") or [])[:4]:
            npc = (npcs or {}).get(nid) or {}
            if npc.get("name"):
                parts.append(npc["name"])
    stakes = player.get("scene_stakes") or {}
    if stakes.get("dramatic_question"):
        parts.append(stakes["dramatic_question"])
    for link in (player.get("causal_links") or [])[:2]:
        parts.append(link.get("summary") or "")
    for prom in list_promises(player)[:2]:
        parts.append(prom.get("label") or "")
    focal = ctx.get("target_id") or ctx.get("focal_npc_id")
    if focal and npcs:
        nm = (npcs.get(focal) or {}).get("name")
        if nm:
            parts.append(nm)
    return " ".join(p.strip() for p in parts if p and str(p).strip())[:400]


def build_scene_plan(player, *, kind, action_ctx, arc, npcs=None, areas=None):
    """Deterministic scene intent consumed by scene_objectives and directives."""
    stakes = player.get("scene_stakes") or {}
    stage = _arc_stage(player, arc)
    intent = _INTENT_BY_KIND.get(kind, "advance the moment")
    must_surface = []
    if stakes.get("dramatic_question"):
        must_surface.append(stakes["dramatic_question"][:90])
    if arc and arc.get("next_beat"):
        must_surface.append(str(arc["next_beat"])[:80])
    for prom in list_promises(player)[:2]:
        label = (prom.get("label") or "").strip()
        if label:
            must_surface.append(label[:70])
    obligation = beat_obligation_directive(
        player, kind, action_ctx, npcs=npcs, areas=areas,
    )
    structure_hint = "continuation"
    if kind in ("explore", "travel") and not (player.get("journal")):
        structure_hint = "arrival"
    elif kind in ("accuse", "attack", "blackmail", "confess"):
        structure_hint = "tension"
    elif kind in ("investigate", "search", "find", "ask_about"):
        structure_hint = "revelation"
    return {
        "intent": intent,
        "must_surface": must_surface[:4],
        "structure_hint": structure_hint,
        "arc_stage": stage,
        "obligation": obligation,
    }


def prepare_beat(player, *, kind, action_ctx, npcs=None, areas=None, tick=None):
    """
    Authoritative pre-narration setup. Updates stakes and writes beat_plan on action_ctx.
    Returns beat_plan dict.
    """
    ctx = action_ctx or {}
    record_turn_story_progress(
        player, kind=kind, action_ctx=ctx, areas=areas, npcs=npcs,
    )
    arc = get_primary_arc(player, npcs, areas=areas)
    stakes = player.get("scene_stakes") or {}
    action = ctx.get("action_summary") or ctx.get("original_action") or kind
    memory_query = build_memory_query(
        player, action, kind=kind, action_ctx=ctx, arc=arc, npcs=npcs,
    )
    scene_plan = build_scene_plan(
        player, kind=kind, action_ctx=ctx, arc=arc, npcs=npcs, areas=areas,
    )
    from simulation.memory_immersion import pick_memory_callback

    focal = ctx.get("target_id") or ctx.get("focal_npc_id")
    callback = pick_memory_callback(
        player, focal, kind=kind, action_ctx=ctx,
        current_tick=tick or player.get("last_tick") or 0, npcs=npcs,
    )
    if callback:
        scene_plan["memory_callback"] = callback
    priority_npc_ids = list(arc.get("key_npc_ids") or [])[:6] if arc else []
    if focal and focal not in priority_npc_ids:
        priority_npc_ids = [focal] + priority_npc_ids

    sim_priorities = build_sim_priorities(player, npcs=npcs, areas=areas)
    player["sim_priorities"] = sim_priorities

    beat_plan = {
        "arc_id": arc.get("arc_id") if arc else stakes.get("arc_id"),
        "arc_kind": arc.get("kind") if arc else None,
        "arc_title": (arc.get("title") or "")[:80] if arc else None,
        "arc_stage": _arc_stage(player, arc),
        "dramatic_question": stakes.get("dramatic_question"),
        "gain": stakes.get("gain"),
        "lose": stakes.get("lose"),
        "memory_query": memory_query,
        "priority_npc_ids": priority_npc_ids,
        "sim_priorities": sim_priorities,
        "open_promises": [p.get("label", "")[:60] for p in list_promises(player)[:3]],
        "scene_plan": scene_plan,
    }
    ctx["beat_plan"] = beat_plan
    ctx["story_orchestrator"] = {
        "arc_id": beat_plan.get("arc_id"),
        "arc_stage": beat_plan.get("arc_stage"),
        "memory_query_len": len(memory_query or ""),
        "must_surface_count": len(scene_plan.get("must_surface") or []),
    }
    if scene_plan.get("obligation") and kind in _STORY_FORWARD_KINDS:
        existing = (ctx.get("story_directive") or "").strip()
        ob = scene_plan["obligation"]
        if ob and ob not in existing:
            ctx["story_directive"] = (existing + " " + ob).strip() if existing else ob
    return beat_plan


def finalize_beat(player, *, kind, action_ctx, npcs=None, areas=None, tick=None):
    """Post-scene propagation from causality and arc pressure."""
    from simulation.narrative_causality import propagate_causal_pressure

    changed = propagate_causal_pressure(
        player, kind, action_ctx or {}, npcs=npcs, areas=areas, tick=tick,
    )
    plan = (action_ctx or {}).get("beat_plan") or {}
    if plan:
        player["last_beat_plan"] = {
            "arc_id": plan.get("arc_id"),
            "arc_stage": plan.get("arc_stage"),
            "kind": kind,
            "tick": tick,
        }
        changed = True
    return changed
