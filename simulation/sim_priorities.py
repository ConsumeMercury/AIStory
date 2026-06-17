"""
Simulation priorities — story arc drives background tick and cast weighting.

Single source for which NPCs, districts, and events matter between player turns.
"""

from simulation.story_manager import get_primary_arc


def build_sim_priorities(player, *, npcs=None, areas=None):
    """
    Story-derived priorities consumed by npc_actions, rumor_engine, and beat_plan.
    Persisted on player during prepare_beat for background ticks.
    """
    arc = get_primary_arc(player, npcs, areas=areas)
    priority = list(arc.get("key_npc_ids") or [])[:8] if arc else []
    focal = player.get("scene_focus")
    if focal and focal not in priority:
        priority = [focal] + priority

    player_area = player.get("area")
    district_tension = None
    if player_area and areas:
        sl = (areas.get(player_area, {}) or {}).get("storyline") or {}
        district_tension = int(sl.get("tension") or 0)

    return {
        "arc_id": arc.get("arc_id") if arc else None,
        "arc_stage": int(arc.get("stage") or 0) if arc else 0,
        "priority_npc_ids": priority,
        "player_area": player_area,
        "player_city": player.get("location"),
        "district_tension": district_tension,
    }


def npc_tick_multiplier(npc_id, npc, sim_priorities):
    """Scale background sim weight for story-relevant NPCs."""
    mult = 1.0
    priority = sim_priorities.get("priority_npc_ids") or []
    if npc_id in priority:
        rank = priority.index(npc_id)
        mult *= max(1.05, 1.45 - rank * 0.08)
    if sim_priorities.get("player_area") and npc.get("area") == sim_priorities["player_area"]:
        mult *= 1.12
    return mult


def rumor_spread_threshold(sim_priorities):
    """Minimum event importance before a rumor is likely to form."""
    base = 32
    tension = sim_priorities.get("district_tension")
    if tension is not None and tension >= 50:
        base -= 4
    return max(25, base)
