"""
World pressure — aggregate district mood into global tension signals.
"""

from storage import load

AREAS_FILE = "world/areas.json"
WORLD_FILE = "world/world_state.json"


def compute_world_pressure(areas=None, world=None):
    areas = areas if areas is not None else load(AREAS_FILE, {})
    world = world if world is not None else load(WORLD_FILE, {})
    moods = []
    crime = []
    tension = []
    for area in areas.values():
        if area.get("type") != "district":
            continue
        st = area.get("state") or {}
        crime.append(st.get("crime_level", area.get("crime", 30)))
        tension.append((area.get("storyline") or {}).get("tension", 20))
        mood = st.get("mood", "uneasy")
        mood_score = {
            "thriving": 85, "prosperous": 70, "uneasy": 45,
            "declining": 30, "desperate": 15, "ruined": 5,
        }.get(mood, 40)
        moods.append(mood_score)
    avg_mood = sum(moods) / max(1, len(moods))
    avg_crime = sum(crime) / max(1, len(crime))
    avg_tension = sum(tension) / max(1, len(tension))
    stability = world.get("global_stability", 50)
    pressure = int(
        avg_crime * 0.35 + avg_tension * 0.35 + (100 - avg_mood) * 0.2 + (100 - stability) * 0.1
    )
    return {
        "pressure": min(100, max(0, pressure)),
        "avg_crime": avg_crime,
        "avg_tension": avg_tension,
        "stability": stability,
    }


def world_pressure_block(player, *, areas=None, world=None):
    data = compute_world_pressure(areas=areas, world=world)
    p = data["pressure"]
    if p < 45:
        return ""
    level = "high" if p >= 70 else "rising"
    return (
        f"WORLD PRESSURE ({level} — {p}/100): crime, plot tension, or instability "
        "push the district toward consequence. Let ambient events feel earned, not random."
    )


def apply_pressure_to_world(world, areas=None):
    data = compute_world_pressure(areas=areas, world=world)
    world["world_pressure"] = data["pressure"]
    if data["pressure"] >= 75:
        world["global_stability"] = max(0, world.get("global_stability", 50) - 0.5)
    elif data["pressure"] <= 30:
        world["global_stability"] = min(100, world.get("global_stability", 50) + 0.2)
    return data
