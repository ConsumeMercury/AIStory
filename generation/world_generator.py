import random
import json
import os

from storage import save as storage_save

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORLD_NAMES = ["Asterra", "Valmire", "Korath", "Eldryn", "Thalor", "Virelia"]
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
WEATHER = ["Clear", "Rain", "Storm", "Fog", "Heatwave", "Snow"]


def generate_world(seed=None):
    if seed is None:
        seed = random.randint(10000, 99999)
    rng = random.Random(seed)

    return {
        "world_name": rng.choice(WORLD_NAMES),
        "day": 1,
        "hour_count": 0,
        "season": rng.choice(SEASONS),
        "weather": rng.choice(WEATHER),
        "global_stability": rng.randint(40, 85),
        "active_conflicts": [],
        "dominant_faction": None,
        "world_seed": seed,
    }


def save_world(world):
    storage_save("world/world_state.json", world)
