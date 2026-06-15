"""
Reset the world: deletes all generated state so the next `python src/main.py`
starts a brand-new world and character. Safe to run anytime.

    python reset_world.py
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    "world/world_state.json", "world/factions.json", "world/locations.json",
    "world/areas.json", "world/institutions.json",
    "characters/npcs.json", "characters/monsters.json",
    "characters/relationships.json", "characters/memories.json",
    "characters/npc_memories.json", "characters/_mem_state.json",
    "events/event_log.json", "rumors/rumors.json",
    "player/player.json",
]

removed = 0
for rel in TARGETS:
    p = os.path.join(BASE, rel)
    if os.path.exists(p):
        os.remove(p)
        removed += 1
        print("removed", rel)

print(f"\nDone — {removed} file(s) cleared. Run `python src/main.py` to begin a new world.")
