import json
import os

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
# MEMORY SYSTEM (FIXED)
# -------------------------
def apply_memory_effects():
    config = load("system/config.json")
    npcs   = load("characters/npcs.json")
    events = load("events/event_log.json")

    recent_limit = config.get("memory_recent_limit", 20)
    recent_events = events[-recent_limit:]

    for npc_id, npc in npcs.items():

        traits = npc.get("traits", {})
        base_fear = traits.get("fear", 50)

        fear_delta = 0
        trust_delta = 0

        for e in recent_events:
            # SAFETY FIX (prevents KeyError crashes)
            if not isinstance(e, dict):
                continue

            actor = e.get("actor")
            etype = e.get("type", "")
            action = e.get("action", "")

            if actor == npc_id:
                continue

            # -------------------------
            # MEMORY SIGNALS (cleaned up)
            # -------------------------
            if "conflict" in etype or "combat" in etype:
                fear_delta += 0.25

            if action in ("help", "helped_others"):
                trust_delta += 0.25

            if action in ("trade", "trade_boosted_economy"):
                trust_delta += 0.05

            if action in ("violence_occurred",):
                fear_delta += 0.25

        # -------------------------
        # FEAR STABILIZATION MODEL
        # -------------------------
        current_fear = traits.get("fear", 50)

        # drift toward base_fear instead of exploding upward
        fear_correction = (base_fear - current_fear) * 0.08

        traits["fear"] = max(0, min(100,
            current_fear + fear_delta + fear_correction
        ))

        # -------------------------
        # KINDNESS STABILIZATION MODEL
        # -------------------------
        current_kindness = traits.get("kindness", 50)

        kindness_correction = (50 - current_kindness) * 0.03

        traits["kindness"] = max(0, min(100,
            current_kindness + trust_delta + kindness_correction
        ))

    save("characters/npcs.json", npcs)