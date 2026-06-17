"""
Hierarchical simulation tiers — district fidelity, regional sampling, distant abstract pulse.

Tier 1: player district (high slot share)
Tier 2: same city, other districts
Tier 3: distant cities — abstract offscreen pulse instead of full action budget
"""

import random

from simulation.event_logger import log_event
from simulation.story_manager import weighted_npc_sample

_TIER1_SHARE = 0.55
_TIER2_SHARE = 0.30
_TIER3_SHARE = 0.15


def tier_for_npc(npc, player):
    player_area = player.get("area")
    player_city = player.get("location")
    if player_area and npc.get("area") == player_area:
        return 1
    if player_city and npc.get("location") == player_city:
        return 2
    return 3


def partition_by_tier(npc_ids, npcs, player):
    tiers = {1: [], 2: [], 3: []}
    for nid in npc_ids:
        npc = npcs.get(nid) or {}
        tiers[tier_for_npc(npc, player)].append(nid)
    return tiers


def hierarchical_npc_sample(npc_ids, npcs, player, weights, max_npcs):
    """
    Sample NPCs for a background tick with district-first allocation.

    Returns (active_ids, tier3_pulse_ids) where tier3_pulse_ids get abstract offscreen updates.
    """
    if not npc_ids:
        return [], []

    tiers = partition_by_tier(npc_ids, npcs, player)
    if not tiers[1] and not tiers[2]:
        active = weighted_npc_sample(npc_ids, weights, min(max_npcs, len(npc_ids)))
        return active, []

    k = min(max_npcs, len(npc_ids))
    n1 = min(len(tiers[1]), max(1, round(k * _TIER1_SHARE))) if tiers[1] else 0
    n2 = min(len(tiers[2]), max(0, round(k * _TIER2_SHARE))) if tiers[2] else 0
    n3 = min(len(tiers[3]), max(0, k - n1 - n2)) if tiers[3] else 0

    if n1 + n2 + n3 < k:
        spare = k - n1 - n2 - n3
        if tiers[1] and n1 < len(tiers[1]):
            n1 = min(len(tiers[1]), n1 + spare)
        elif tiers[2] and n2 < len(tiers[2]):
            n2 = min(len(tiers[2]), n2 + spare)

    chosen = []
    if n1:
        chosen.extend(weighted_npc_sample(tiers[1], weights, n1))
    if n2:
        chosen.extend(weighted_npc_sample(tiers[2], weights, n2))
    if n3:
        chosen.extend(weighted_npc_sample(tiers[3], weights, n3))

    pulse_pool = [nid for nid in tiers[3] if nid not in chosen]
    pulse_ids = pulse_pool[: max(0, len(tiers[3]) - n3)]
    return chosen, pulse_ids


def run_abstract_regional_pulse(npc_ids, npcs, *, tick=None, limit=4):
    """
    Lightweight offscreen tick for distant NPCs — passive upkeep + sparse event log.
    """
    if not npc_ids:
        return 0
    sample = random.sample(npc_ids, min(limit, len(npc_ids)))
    touched = 0
    seen_cities = set()
    for nid in sample:
        npc = npcs.get(nid)
        if not npc or npc.get("status") != "alive":
            continue
        stats = npc.setdefault("stats", {})
        stats["health"] = min(stats.get("max_health", 80), stats.get("health", 0) + 1)
        stats["stamina"] = min(stats.get("max_stamina", 20), stats.get("stamina", 0) + 2)
        loc = npc.get("location", "unknown")
        if loc not in seen_cities:
            log_event(
                "npc_action", nid, "offscreen_life",
                location=loc,
                effects=["abstract_tick"],
                tick=tick,
            )
            seen_cities.add(loc)
        touched += 1
    return touched
