import json
import random
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_faction_tick(tick=None):
    config_path = os.path.join(BASE_DIR, "system", "config.json")

    # load config safely
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception:
        config = {}

    if not config.get("enable_faction_wars", True):
        return

    factions_path = os.path.join(BASE_DIR, "world", "factions.json")

    try:
        with open(factions_path, "r") as f:
            factions = json.load(f)
    except Exception:
        return

    # factions stored as dict
    if not isinstance(factions, dict):
        return

    faction_list = list(factions.values())

    for i, fa in enumerate(faction_list):
        for fb in faction_list[i + 1:]:

            power_diff = abs(fa.get("power", 0) - fb.get("power", 0))

            # war trigger condition
            if power_diff > 30 and random.random() < 0.1:

                if fa["power"] > fb["power"]:
                    winner, loser = fa, fb
                else:
                    winner, loser = fb, fa

                loser["power"] = max(0, loser.get("power", 0) - random.randint(3, 8))
                winner["power"] = min(100, winner.get("power", 0) + random.randint(1, 4))

                # optional logging (safe import)
                try:
                    from simulation.event_logger import log_event

                    log_event(
                        "faction_conflict",
                        winner.get("id", "unknown"),
                        "faction_war",
                        target=loser.get("id", "unknown"),
                        effects=["power_shift", "instability"],
                        tick=tick,
                    )
                except Exception:
                    pass

    # save back
    try:
        with open(factions_path, "w") as f:
            json.dump(factions, f, indent=2)
    except Exception:
        pass