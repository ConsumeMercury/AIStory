"""
Assemble budgeted memory sections for the narrator prompt.
"""

from simulation.memory_budget import apply_memory_budget, format_memory_debug
from simulation.journal_summary import distant_context_block, recent_journal_block
from simulation.immersion_context import format_world_echoes
from simulation.narrative_memory import narrative_memory_block
from simulation.memory_immersion import (
    pick_memory_callback,
    subjective_memory_lines,
    surface_memory_limit,
)


def _focal_npc_memory_block(focal_npc_id, npcs, *, current_tick, query_words=None):
    if not focal_npc_id:
        return ""
    lines = subjective_memory_lines(
        focal_npc_id, npcs, current_tick=current_tick, limit=2, query_words=query_words,
    )
    if not lines:
        return ""
    npc = (npcs or {}).get(focal_npc_id, {})
    label = npc.get("name") or focal_npc_id
    return (
        f"FOCAL NPC MEMORY ({label}'s subjective recall — color dialogue and manner, not exposition dump):\n"
        + "\n".join(f"- {line}" for line in lines)
    )


def _memory_callback_block(player, focal_npc_id, *, kind, action_ctx, current_tick, npcs):
    cb = pick_memory_callback(
        player, focal_npc_id, kind=kind, action_ctx=action_ctx,
        current_tick=current_tick, npcs=npcs,
    )
    if not cb:
        return ""
    return cb["text"]


def build_memory_context(
    player, npcs, memories, *, focal_npc_id=None, present_ids=None, kind=None,
    action_ctx=None, current_tick=0, world=None,
):
    """
    Build journal history and retrieved events under token budget.
    Plot summary lives in NARRATIVE THREAD (beat_structure) — not duplicated here.
    Returns (prompt_block, debug_dict).
    """
    ctx = action_ctx or {}
    plan = ctx.get("beat_plan") or {}
    query_words = set((plan.get("memory_query") or "").lower().split())
    mem_limit = surface_memory_limit(kind or ctx.get("kind") or "general")
    packet_whispers = ""
    if world and player:
        from simulation.memory_immersion import packets_as_rumor_whispers
        packet_lines = packets_as_rumor_whispers(world, player, limit=2)
        if packet_lines:
            packet_whispers = "SOCIAL WHISPERS (second-hand — may be distorted):\n" + "\n".join(packet_lines)

    sections = {
        "memory_callback": _memory_callback_block(
            player, focal_npc_id, kind=kind, action_ctx=ctx,
            current_tick=current_tick, npcs=npcs,
        ),
        "narrative_memory": narrative_memory_block(player),
        "focal_npc_memory": _focal_npc_memory_block(
            focal_npc_id, npcs, current_tick=current_tick, query_words=query_words,
        ),
        "recent_journal": recent_journal_block(player),
        "distant_history": distant_context_block(player),
        "retrieved_events": format_world_echoes(memories[:mem_limit + 2], limit=mem_limit) if memories else "",
        "social_whispers": packet_whispers,
    }
    pin = ("focal_npc_memory", "memory_callback") if focal_npc_id else ("memory_callback",)
    trimmed, evictions = apply_memory_budget(sections, pin_slots=pin)
    debug = format_memory_debug(trimmed, evictions)
    if ctx is not None:
        from simulation.memory_immersion import build_memory_trace
        ctx["memory_trace"] = build_memory_trace(
            player, focal_npc_id, kind=kind, action_ctx=ctx,
            current_tick=current_tick, npcs=npcs,
        )

    parts = [trimmed[k] for k in (
        "memory_callback",
        "narrative_memory",
        "focal_npc_memory",
        "social_whispers",
        "distant_history",
        "recent_journal",
        "retrieved_events",
    ) if trimmed.get(k)]
    if not parts:
        return "", debug
    return "\n\n".join(parts), debug
