import logging
import random

from storage import load, save

log = logging.getLogger(__name__)


def run_faction_tick(tick=None):
    config = load("system/config.json", {})
    if not isinstance(config, dict):
        config = {}

    if not config.get("enable_faction_wars", True):
        return

    factions = load("world/factions.json", {})
    if not isinstance(factions, dict) or not factions:
        return

    faction_list = list(factions.values())

    for i, fa in enumerate(faction_list):
        for fb in faction_list[i + 1:]:
            fa_power = fa.get("power", 0)
            fb_power = fb.get("power", 0)
            power_diff = abs(fa_power - fb_power)

            if power_diff > 30 and random.random() < 0.1:
                if fa_power > fb_power:
                    winner, loser = fa, fb
                else:
                    winner, loser = fb, fa

                loser["power"] = max(0, loser.get("power", 0) - random.randint(3, 8))
                winner["power"] = min(100, winner.get("power", 0) + random.randint(1, 4))

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
                    log.exception("faction conflict event log failed")

    save("world/factions.json", factions)
