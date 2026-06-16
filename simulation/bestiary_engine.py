"""
Keeps the world's monster population alive between ticks: clears the dead,
and occasionally spawns new threats in wilderness areas. Small per tick so
the wilds stay dangerous without flooding.
"""

import random
from storage import load, save
from generation.monster_generator import spawn_for_area
from simulation.hunting_engine import refresh_bounty_board

MON_FILE = "characters/monsters.json"
AREAS_FILE = "world/areas.json"
MAX_MONSTERS = 40


def maintain_monsters():
    monsters = load(MON_FILE, {})
    areas = load(AREAS_FILE, {})
    if not isinstance(monsters, dict):
        monsters = {}

    # prune the dead
    monsters = {mid: m for mid, m in monsters.items() if m.get("status") == "alive"}

    wild = [a for a in areas.values() if a.get("type") == "wilderness"]
    if wild and len(monsters) < MAX_MONSTERS and random.random() < 0.5:
        area = random.choice(wild)
        for mon in spawn_for_area(area.get("area_type", "wilderness"), count=random.randint(0, 2)):
            mon["location"] = area["id"]
            mon["area"] = area["id"]
            monsters[mon["id"]] = mon

    if random.random() < 0.35:
        refresh_bounty_board(world=load("world/world_state.json", {}), monsters=monsters, areas=areas)

    save(MON_FILE, monsters)
