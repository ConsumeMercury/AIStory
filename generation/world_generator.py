import random
import json
import os

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
        "world_seed": seed
    }


def save_world(world):
    path = os.path.join(BASE_DIR, "world", "world_state.json")

    # ✅ ADD THIS LINE
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        json.dump(world, f, indent=2)


if __name__ == "__main__":
    world = generate_world()
    save_world(world)
    print("World generated:", world["world_name"])
