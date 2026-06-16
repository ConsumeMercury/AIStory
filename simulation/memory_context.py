"""
Assemble budgeted memory sections for the narrator prompt.
"""

from simulation.memory_budget import apply_memory_budget, format_memory_debug
from simulation.journal_summary import distant_context_block, recent_journal_block
from simulation.immersion_context import format_world_echoes


def build_memory_context(player, npcs, memories, *, focal_npc_id=None, present_ids=None):
    """
    Build journal history and retrieved events under token budget.
    Plot summary lives in NARRATIVE THREAD (beat_structure) — not duplicated here.
    Returns (prompt_block, debug_dict).
    """
    sections = {
        "recent_journal": recent_journal_block(player),
        "distant_history": distant_context_block(player),
        "retrieved_events": format_world_echoes(memories[:8], limit=6) if memories else "",
    }
    trimmed, evictions = apply_memory_budget(sections)
    debug = format_memory_debug(trimmed, evictions)

    parts = [trimmed[k] for k in (
        "distant_history", "recent_journal", "retrieved_events",
    ) if trimmed.get(k)]
    if not parts:
        return "", debug
    return "\n\n".join(parts), debug
