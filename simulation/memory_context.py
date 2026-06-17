"""
Assemble budgeted memory sections for the narrator prompt.
"""

from simulation.memory_budget import apply_memory_budget, format_memory_debug
from simulation.journal_summary import distant_context_block, recent_journal_block
from simulation.immersion_context import format_world_echoes
from simulation.narrative_memory import narrative_memory_block
from simulation.npc_memory_engine import top_memories


def _focal_npc_memory_block(focal_npc_id, npcs):
    if not focal_npc_id:
        return ""
    mems = top_memories(focal_npc_id, n=3)
    if not mems:
        return ""
    lines = []
    for m in mems:
        summary = (m.get("summary") or "")[:120]
        if summary:
            lines.append(f"- {summary}")
    if not lines:
        return ""
    npc = (npcs or {}).get(focal_npc_id, {})
    label = npc.get("name") or focal_npc_id
    return (
        f"FOCAL NPC MEMORY ({label} remembers — may color tone, not verbatim replay):\n"
        + "\n".join(lines)
    )


def build_memory_context(player, npcs, memories, *, focal_npc_id=None, present_ids=None):
    """
    Build journal history and retrieved events under token budget.
    Plot summary lives in NARRATIVE THREAD (beat_structure) — not duplicated here.
    Returns (prompt_block, debug_dict).
    """
    sections = {
        "narrative_memory": narrative_memory_block(player),
        "focal_npc_memory": _focal_npc_memory_block(focal_npc_id, npcs),
        "recent_journal": recent_journal_block(player),
        "distant_history": distant_context_block(player),
        "retrieved_events": format_world_echoes(memories[:8], limit=6) if memories else "",
    }
    trimmed, evictions = apply_memory_budget(sections)
    debug = format_memory_debug(trimmed, evictions)

    parts = [trimmed[k] for k in (
        "narrative_memory",
        "focal_npc_memory",
        "distant_history",
        "recent_journal",
        "retrieved_events",
    ) if trimmed.get(k)]
    if not parts:
        return "", debug
    return "\n\n".join(parts), debug
