import json
import random
import os
from simulation.event_logger import log_event

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(filename):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)


def save(filename, data):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# -------------------------
# FIXED CLAMP (BUG-3 HARD FIX)
# -------------------------
def clamp(value, lo=0, hi=100):
    try:
        value = float(value)
    except:
        return lo
    return round(max(lo, min(hi, value)), 2)


# -------------------------
# MAIN CONSEQUENCE ENGINE
# -------------------------
def apply_npc_consequences(tick=None):
    world     = load("world/world_state.json")
    factions  = load("world/factions.json")
    locations = load("world/locations.json")
    npcs      = load("characters/npcs.json")

    world.setdefault("global_stability", 50)

    for npc_id, npc in npcs.items():
        action = npc.get("last_action")
        loc    = npc.get("location")

        if not action:
            continue

        city = locations.get("cities", {}).get(loc, None)

        # -------------------------
        # TRADE
        # -------------------------
        if action == "trade":
            if city:
                city["wealth"] = clamp(city.get("wealth", 0) + 1)
                city["stability"] = clamp(city.get("stability", 50) + 0.1)

            world["global_stability"] = clamp(world["global_stability"] + 0.01)

            log_event(
                "economy_change",
                npc_id,
                "trade_boosted_economy",
                location=loc,
                effects=["wealth_increase", "stability_increase"],
                tick=tick
            )

        # -------------------------
        # FIGHT (BUG-5 FIX: DEATH NOW POSSIBLE)
        # -------------------------
        elif action == "fight":
            if city:
                city["crime_rate"] = clamp(city.get("crime_rate", 0) + 2)
                city["stability"]  = clamp(city.get("stability", 50) - 1)

            world["global_stability"] = clamp(world["global_stability"] - 0.5)

            # faction weakening
            for f in factions.values():
                f["power"] = clamp(f.get("power", 50) - 0.1)

            # NEW: death chance (was missing entirely)
            if npc.get("status") == "alive" and random.random() < 0.03:
                npc["status"] = "dead"
                log_event(
                    "death",
                    npc_id,
                    "killed_in_conflict",
                    location=loc,
                    effects=["npc_removed"],
                    tick=tick
                )

            log_event(
                "conflict",
                npc_id,
                "violence_occurred",
                location=loc,
                effects=["stability_drop", "crime_increase"],
                tick=tick
            )

        # -------------------------
        # HELP
        # -------------------------
        elif action == "help":
            if city:
                city["stability"] = clamp(city.get("stability", 50) + 0.5)

            log_event(
                "social_event",
                npc_id,
                "helped_others",
                location=loc,
                effects=["stability_gain", "trust_increase"],
                tick=tick
            )

        # -------------------------
        # PLAN
        # -------------------------
        elif action == "plan":
            for f in factions.values():
                if random.random() < 0.2:
                    f["influence"] = clamp(f.get("influence", 50) + 0.1)

        # -------------------------
        # HIDE
        # -------------------------
        elif action == "hide":
            world["global_stability"] = clamp(world["global_stability"] + 0.01)

    # -------------------------
    # SAVE ALL STATE (SAFE)
    # -------------------------
    save("world/world_state.json", world)
    save("world/factions.json", factions)
    save("world/locations.json", locations)
    save("characters/npcs.json", npcs)