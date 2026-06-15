"""
Player travel through the area graph.

Travelling somewhere costs the edge's HOURS. While the player is on the
road, the world keeps living: we run that many background ticks (capped),
so distant places change, NPCs act, monsters move, and the player arrives
to a world that has moved on — exactly the "more time passes => more
events" feel the design wants.
"""

from storage import load, save
from simulation.world_clock import advance_clock

AREAS_FILE = "world/areas.json"
PLAYER_FILE = "player/player.json"

# don't run thousands of ticks for a 36-hour trip; sample the journey
MAX_BACKGROUND_TICKS = 24


def list_destinations(current_area_id):
    areas = load(AREAS_FILE, {})
    here = areas.get(current_area_id)
    if not here:
        return {}
    return dict(here.get("edges", {}))


def travel(destination_id, run_tick):
    """
    run_tick: callback (the simulation runner's _run_tick) used to advance
    the world while travelling. Returns (ok, message, hours, area).
    """
    player = load(PLAYER_FILE, {})
    current = player.get("area")
    areas = load(AREAS_FILE, {})

    here = areas.get(current, {})
    edges = here.get("edges", {})
    if destination_id not in edges:
        return False, f"You can't reach '{destination_id}' from here.", 0, current

    hours = edges[destination_id]

    # advance world time and run background ticks proportional to the trip
    ticks = min(MAX_BACKGROUND_TICKS, max(1, hours // 2))
    for _ in range(ticks):
        run_tick()
    advance_clock(hours)

    dest = areas.get(destination_id, {})
    player = load(PLAYER_FILE, {})
    player["area"] = destination_id
    if dest.get("city"):
        player["location"] = dest["city"]
    save(PLAYER_FILE, player)

    name = dest.get("name", destination_id)
    return True, f"After {hours} hours on the move, you reach {name}.", hours, destination_id
