"""
After the player is created, tune NPC ages/presentation and cap crowd density per area.
"""

import random

MAX_NPCS_PER_AREA = 2


def cap_area_density(npcs, areas):
    """No more than MAX_NPCS_PER_AREA named people in one district."""
    counts = {}
    for nid, npc in list(npcs.items()):
        aid = npc.get("area")
        if not aid:
            continue
        counts.setdefault(aid, []).append(nid)

    for aid, ids in counts.items():
        if len(ids) <= MAX_NPCS_PER_AREA:
            continue
        keep = random.sample(ids, MAX_NPCS_PER_AREA)
        city = areas.get(aid, {}).get("city")
        city_areas = [a for a in areas if areas[a].get("city") == city and a != aid]
        for nid in ids:
            if nid in keep:
                continue
            if city_areas:
                npcs[nid]["area"] = random.choice(city_areas)
            else:
                npcs[nid]["area"] = aid  # fallback


def tune_for_player(npcs, player, start_city=None):
    """
    Bias a subset of NPCs toward player's age and higher presentation
    so romance/social scenes feel plausible.
    """
    age = player.get("age", 30)
    start_city = start_city or player.get("location")

    pool = [
        nid for nid, n in npcs.items()
        if n.get("status") == "alive" and n.get("location") == start_city
    ]
    if not pool:
        pool = list(npcs.keys())

    # ~40% become age-appropriate social prospects
    prospects = random.sample(pool, k=min(len(pool), max(3, len(pool) * 2 // 5)))
    for nid in prospects:
        n = npcs[nid]
        delta = random.randint(-5, 5)
        n["age"] = max(16, min(70, age + delta))
        phys = n.setdefault("physique", {})
        phys["presentation"] = random.randint(58, 88)
        phys["attractiveness_note"] = random.choice([
            "easy to notice in a room", " memorable face", " striking without effort",
            " composed and readable", " warmth in the eyes when they listen",
        ])
        n["social_eligible"] = True

    # rest get normal presentation spread
    for nid, n in npcs.items():
        if nid in prospects:
            continue
        phys = n.setdefault("physique", {})
        phys.setdefault("presentation", random.randint(35, 75))
        n.setdefault("social_eligible", random.random() < 0.25)
