"""
Ambient memory effects on NPC traits.

Recent world events nudge paranoia (fear-response) and kindness based on
what NPCs witness in the event log. Uses paranoia — the actual trait axis —
not a nonexistent "fear" field.
"""

from storage import load, save

NPC_FILE = "characters/npcs.json"
EVENT_FILE = "events/event_log.json"
CFG_FILE = "system/config.json"


def apply_memory_effects():
    config = load(CFG_FILE, {})
    npcs = load(NPC_FILE, {})
    events = load(EVENT_FILE, [])

    if not isinstance(npcs, dict):
        return
    if not isinstance(events, list):
        events = []

    recent_limit = config.get("memory_recent_limit", 20)
    recent_events = events[-recent_limit:]

    for npc_id, npc in npcs.items():
        traits = npc.setdefault("traits", {})
        base_paranoia = traits.get("paranoia", 50)

        paranoia_delta = 0.0
        kindness_delta = 0.0

        for e in recent_events:
            if not isinstance(e, dict):
                continue

            actor = e.get("actor")
            etype = e.get("type", "")
            action = e.get("action", "")

            if actor == npc_id:
                continue

            if "conflict" in etype or "combat" in etype:
                paranoia_delta += 0.25

            if action in ("help", "helped_others"):
                kindness_delta += 0.25

            if action in ("trade", "trade_boosted_economy"):
                kindness_delta += 0.05

            if action in ("violence_occurred",):
                paranoia_delta += 0.25

        current_paranoia = traits.get("paranoia", 50)
        paranoia_correction = (base_paranoia - current_paranoia) * 0.08
        traits["paranoia"] = max(0, min(100,
            current_paranoia + paranoia_delta + paranoia_correction
        ))

        current_kindness = traits.get("kindness", 50)
        kindness_correction = (50 - current_kindness) * 0.03
        traits["kindness"] = max(0, min(100,
            current_kindness + kindness_delta + kindness_correction
        ))

    save(NPC_FILE, npcs)
