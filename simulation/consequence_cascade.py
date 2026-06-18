"""
Consequence cascades — public entry points for the propagation engine.

Preserves the original API used by story_loop and narrative_causality.
"""

from simulation.consequence_propagation import propagate, template_for_fatal_kill


def register_combat_consequences(
    player, target_npc, *, world, areas, fatal=False, tick=None, memory_id=None,
    institutions=None, action_ctx=None,
):
    """
    Propagate immediate + delayed consequences when the player fatally kills an NPC.
    """
    if not fatal or not target_npc:
        return False
    if target_npc.get("status") != "dead":
        return False

    template = template_for_fatal_kill(target_npc)
    if not template:
        return False

    changed, trace = propagate(
        template,
        player=player,
        world=world,
        areas=areas,
        target_npc=target_npc,
        memory_id=memory_id,
        tick=tick,
        institutions=institutions,
    )
    if action_ctx is not None:
        action_ctx["consequence_trace"] = trace
    return changed


def register_from_causal_link(player, link, *, world, areas=None, action_ctx=None):
    """Enqueue delayed fallout when a high-importance causal link forms."""
    if not link:
        return False
    imp = int(link.get("importance") or 0)
    if imp < 65:
        return False

    cause = (link.get("cause") or "").lower()
    if cause not in ("violence", "accusation", "blackmail", "theft"):
        return False

    changed, trace = propagate(
        "causal_ripple",
        player=player,
        world=world,
        areas=areas,
        causal_link=link,
    )
    if action_ctx is not None:
        action_ctx["consequence_trace"] = trace
    return changed
