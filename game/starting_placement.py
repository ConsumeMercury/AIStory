"""
Where new characters begin — city and district selection, opening quest seed.
"""

import random

from simulation.investigation_cases import generate_mystery

# District suffix -> relative weight per player background
BACKGROUND_DISTRICT_WEIGHTS = {
    "soldier": {
        "high_quarter": 3.0,
        "docks": 2.0,
        "market": 1.5,
        "the_warrens": 1.0,
        "temple_row": 1.0,
    },
    "merchant": {
        "market": 4.0,
        "high_quarter": 2.5,
        "docks": 2.0,
        "temple_row": 1.0,
        "the_warrens": 1.0,
    },
    "scholar": {
        "high_quarter": 3.0,
        "temple_row": 3.0,
        "market": 1.5,
        "docks": 1.0,
        "the_warrens": 1.0,
    },
    "thief": {
        "the_warrens": 4.0,
        "market": 2.5,
        "docks": 2.0,
        "high_quarter": 1.0,
        "temple_row": 1.0,
    },
    "wanderer": {
        "market": 1.5,
        "docks": 1.5,
        "temple_row": 1.5,
        "the_warrens": 1.5,
        "high_quarter": 1.5,
    },
}

MYSTERY_BACKGROUNDS = frozenset({"scholar", "thief"})
MYSTERY_MOTIVATION_WORDS = (
    "mystery", "truth", "secret", "murder", "investigate", "find out", "clue",
)


def district_suffix(area_id):
    return area_id.split(":")[-1] if area_id else ""


def pick_start_city(cities, rng=None):
    """Pick a random arrival city — not dict insertion order."""
    rng = rng or random
    keys = list(cities.keys())
    if not keys:
        return None
    return rng.choice(keys)


def _score_start_area(area_id, area, background, rng):
    suffix = district_suffix(area_id)
    weights = BACKGROUND_DISTRICT_WEIGHTS.get(background, BACKGROUND_DISTRICT_WEIGHTS["wanderer"])
    score = weights.get(suffix, 1.0)

    sl = area.get("storyline") or {}
    if sl.get("source") == "institution":
        score += 2.5
    score += (sl.get("tension") or 15) / 25.0
    if sl.get("key_npc_ids"):
        score += 0.75
    score += rng.uniform(0.25, 1.75)
    return score


def pick_start_area(areas, city, background, rng=None):
    """
    Weighted district pick — background affinity + storyline richness + jitter.
    Never uses alphabetical order (which always landed players on :docks).
    """
    rng = rng or random
    candidates = [
        aid for aid, area in areas.items()
        if area.get("city") == city and area.get("type") == "district"
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    scored = [
        (aid, _score_start_area(aid, areas[aid], background, rng))
        for aid in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_n = min(3, len(scored))
    top = scored[:top_n]
    ids, weights = zip(*top)
    return rng.choices(list(ids), weights=list(weights), k=1)[0]


def should_seed_opening_case(player):
    bg = (player.get("background") or "").lower()
    if bg in MYSTERY_BACKGROUNDS:
        return True
    mot = (player.get("motivation") or "").lower()
    return any(word in mot for word in MYSTERY_MOTIVATION_WORDS)


def seed_starting_pipeline(player, area_id, areas, npcs):
    """Attach an opening quest thread tied to the start district's storyline."""
    area = areas.get(area_id, {})
    sl = area.get("storyline") or {}
    stages = list(sl.get("stages") or [])
    current = sl.get("current") or (stages[0] if stages else "")
    hook = sl.get("hook") or sl.get("title") or "Something local is wrong."

    pipeline = {
        "area_id": area_id,
        "district": district_suffix(area_id),
        "title": sl.get("title", area.get("name", "Local trouble")),
        "source": sl.get("source", "district"),
        "theme": sl.get("theme"),
        "institution_id": sl.get("institution_id"),
        "hook": hook,
        "stage": sl.get("stage", 0),
        "stages": stages,
        "current": current,
        "key_npc_ids": list(sl.get("key_npc_ids") or []),
    }
    player["starting_pipeline"] = pipeline

    flags = player.setdefault("story_flags", {})
    flags["start_district"] = pipeline["district"]
    flags["start_story_title"] = pipeline["title"]

    opening_goal = {
        "id": "local_opening",
        "text": f"Uncover what is happening in {area.get('name', 'this district')}: {hook[:90]}",
        "hint": f"Explore here, talk to people, follow the thread — {current[:80]}",
        "target": 3,
        "track": "explore_actions",
        "pipeline": True,
    }
    goals = player.get("goals") or []
    player["goals"] = [opening_goal] + [g for g in goals if g.get("id") != "local_opening"]

    if should_seed_opening_case(player):
        kind = "murder" if "murder" in (player.get("motivation") or "").lower() else "mystery"
        case, _ = generate_mystery(area_id, npcs, areas, player=player, kind=kind)
        if case:
            player["active_case"] = case

    return pipeline


def starting_pipeline_narrator_block(player):
    pipe = player.get("starting_pipeline")
    if not pipe:
        return ""
    journal = player.get("journal") or []
    if len(journal) > 8:
        return ""
    area_name = pipe.get("district", "district").replace("_", " ")
    lines = [
        f"OPENING THREAD ({pipe.get('title', 'local plot')}): {pipe.get('hook', '')[:140]}",
        f"You arrived in the {area_name} — this is the trouble on the ground now: {pipe.get('current', '')[:100]}",
    ]
    if pipe.get("key_npc_ids"):
        lines.append("Key figures in this thread already exist locally — do not invent replacements.")
    return "\n".join(lines)
