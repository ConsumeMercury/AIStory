import random
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CITY_PREFIX = [
    "Iron", "Black", "Storm", "Ash", "Silver", "Blood", "Frost",
    "Ember", "Dusk", "Stone", "Red", "Hollow", "Grim", "Bone"
]

CITY_SUFFIX = [
    "port", "haven", "reach", "hold", "ford", "gate", "watch",
    "fall", "moor", "bridge", "crest", "hollow", "wick", "vale"
]


def make_name(used_names):
    # FIX: stronger uniqueness guarantee without biasing loop failure silently
    attempts = 0
    while attempts < 100:
        name = random.choice(CITY_PREFIX) + random.choice(CITY_SUFFIX)
        if name.lower() not in used_names:
            return name
        attempts += 1

    raise RuntimeError(
        "Could not generate unique city name — expand prefix/suffix lists"
    )


def generate_locations(count=5):
    cities = {}

    for _ in range(count):
        name = make_name(cities)
        key = name.lower()

        cities[key] = {
            "name": name,
            "type": "city",
            "population": int(random.randint(2000, 120000)),
            "wealth": int(random.randint(20, 100)),
            "stability": int(random.randint(20, 100)),
            "crime_rate": int(random.randint(5, 80)),
            "resources": random.sample(
                ["iron", "wood", "food", "stone", "gold"],
                k=random.randint(1, 3)
            ),
            "connected": []
        }

    # -----------------------------
    # FIX: symmetric connectivity
    # ensures consistent travel graph
    # -----------------------------
    city_keys = list(cities.keys())

    for key in city_keys:
        neighbors = [k for k in city_keys if k != key]
        chosen = random.sample(neighbors, k=min(2, len(neighbors)))
        cities[key]["connected"] = chosen

    # enforce bidirectional consistency
    for key, city in cities.items():
        for neighbor in city["connected"]:
            if key not in cities[neighbor]["connected"]:
                cities[neighbor]["connected"].append(key)

    return {"cities": cities}


def save_locations(data):
    path = os.path.join(BASE_DIR, "world", "locations.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    loc = generate_locations()
    save_locations(loc)
    print("Locations generated:", list(loc["cities"].keys()))