"""
Cities with correlated, weighted stats driven by archetype and resources.
"""

import random

from storage import load, save as storage_save

CITY_PREFIX = [
    "Iron", "Black", "Storm", "Ash", "Silver", "Blood", "Frost",
    "Ember", "Dusk", "Stone", "Red", "Hollow", "Grim", "Bone",
]
CITY_SUFFIX = [
    "port", "haven", "reach", "hold", "ford", "gate", "watch",
    "fall", "moor", "bridge", "crest", "hollow", "wick", "vale",
]

ARCHETYPES = {
    "port": {
        "weight": 2.0,
        "population": (15000, 95000),
        "wealth_bias": 12,
        "crime_bias": 15,
        "stability_bias": -5,
        "resources": ["fish", "salt", "trade"],
        "culture": ["cosmopolitan", "sailors' superstitions", "pidgin trade tongue"],
        "district_bias": {"market": 1.3, "docks": 1.8, "the_warrens": 1.2},
    },
    "mining": {
        "weight": 1.2,
        "population": (3000, 35000),
        "wealth_bias": 5,
        "crime_bias": 8,
        "stability_bias": -8,
        "resources": ["iron", "stone", "coal"],
        "culture": ["clan loyalty", "shift-whistle time", "lung sickness"],
        "district_bias": {"market": 1.0, "the_warrens": 1.5, "high_quarter": 0.6},
    },
    "agrarian": {
        "weight": 1.5,
        "population": (2000, 25000),
        "wealth_bias": -5,
        "crime_bias": -5,
        "stability_bias": 10,
        "resources": ["food", "wood", "wool"],
        "culture": ["seasonal festivals", "church bells", "land feuds"],
        "district_bias": {"market": 1.2, "temple_row": 1.3},
    },
    "capital": {
        "weight": 0.7,
        "population": (40000, 120000),
        "wealth_bias": 18,
        "crime_bias": 10,
        "stability_bias": 5,
        "resources": ["gold", "grain", "law"],
        "culture": ["court intrigue", "posted edicts", "spies in cafes"],
        "district_bias": {"high_quarter": 1.8, "market": 1.2, "temple_row": 1.1},
    },
    "frontier": {
        "weight": 1.0,
        "population": (800, 12000),
        "wealth_bias": -10,
        "crime_bias": 20,
        "stability_bias": -15,
        "resources": ["fur", "wood", "iron"],
        "culture": ["everyone armed", "missing persons", "frontier justice"],
        "district_bias": {"market": 0.9, "the_warrens": 1.4},
    },
    "holy": {
        "weight": 0.8,
        "population": (5000, 40000),
        "wealth_bias": 0,
        "crime_bias": -8,
        "stability_bias": 15,
        "resources": ["incense", "pilgrims", "stone"],
        "culture": ["pilgrim traffic", "fast days", "confessional secrets"],
        "district_bias": {"temple_row": 2.0, "high_quarter": 0.8},
    },
}

RESOURCE_POOL = ["iron", "wood", "food", "stone", "gold", "fish", "salt", "wool", "grain"]


def _pick_archetype():
    keys = list(ARCHETYPES.keys())
    weights = [ARCHETYPES[k]["weight"] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def _clamp(v, lo=0, hi=100):
    return int(max(lo, min(hi, round(v))))


def _build_city(archetype_key):
    spec = ARCHETYPES[archetype_key]
    pop_lo, pop_hi = spec["population"]
    population = random.randint(pop_lo, pop_hi)

    # correlated core stats
    wealth = _clamp(random.gauss(50 + spec["wealth_bias"], 12))
    stability = _clamp(random.gauss(50 + spec["stability_bias"] + (wealth - 50) * 0.15, 10))
    crime = _clamp(random.gauss(35 + spec["crime_bias"] - (stability - 50) * 0.25, 12))

    resources = list(spec.get("resources", []))
    extra = random.sample([r for r in RESOURCE_POOL if r not in resources], k=random.randint(0, 1))
    resources.extend(extra)

    culture = random.sample(spec["culture"], k=min(2, len(spec["culture"])))
    governance = random.choice(["council", "lord", "guild compact", "temple regency", "military governor"])
    prosperity = _clamp((wealth + stability) // 2)
    unrest = _clamp(100 - stability + crime // 2)

    return {
        "type": "city",
        "archetype": archetype_key,
        "population": population,
        "wealth": wealth,
        "stability": stability,
        "crime_rate": crime,
        "prosperity": prosperity,
        "unrest": unrest,
        "governance": governance,
        "resources": resources,
        "culture": culture,
        "tax_rate": _clamp(random.gauss(wealth / 5, 8), 5, 35),
        "wall_strength": _clamp(random.gauss(stability * 0.8, 15)),
        "district_bias": spec.get("district_bias", {}),
        "connected": [],
    }


def make_name(used_names):
    for _ in range(100):
        name = random.choice(CITY_PREFIX) + random.choice(CITY_SUFFIX)
        if name.lower() not in used_names:
            return name
    raise RuntimeError("Could not generate unique city name")


def generate_locations(count=5):
    cities = {}
    for _ in range(count):
        name = make_name(cities)
        key = name.lower()
        arch = _pick_archetype()
        cities[key] = {"name": name, **_build_city(arch)}

    city_keys = list(cities.keys())
    for key in city_keys:
        neighbors = [k for k in city_keys if k != key]
        n_count = min(2, len(neighbors))
        chosen = random.sample(neighbors, k=n_count)
        cities[key]["connected"] = chosen
        for n in chosen:
            # Pre-defined inter-city hours (symmetric); used by area wilderness edges.
            dist = random.randint(6, 48)
            cities[key].setdefault("travel_hours", {})[n] = dist

    for key, city in cities.items():
        for neighbor in city["connected"]:
            if key not in cities[neighbor]["connected"]:
                cities[neighbor]["connected"].append(key)
            peer_hours = city.get("travel_hours", {}).get(neighbor)
            if peer_hours is None:
                peer_hours = random.randint(6, 48)
            cities[neighbor].setdefault("travel_hours", {})[key] = peer_hours
            city.setdefault("travel_hours", {})[neighbor] = max(
                peer_hours, city["travel_hours"].get(neighbor, peer_hours),
            )

    return {"cities": cities}


def save_locations(data):
    storage_save("world/locations.json", data)


def city_check_modifier(city_key, locations_data=None):
    """Difficulty modifier for skill checks in this city."""
    if locations_data is None:
        locations_data = load("world/locations.json", {})
    city = locations_data.get("cities", {}).get(city_key, {})
    if not city:
        return 0
    mod = 0
    mod += (city.get("crime_rate", 30) - 40) // 15
    mod += (50 - city.get("stability", 50)) // 20
    if city.get("archetype") == "frontier":
        mod += 1
    if city.get("archetype") == "holy":
        mod -= 1
    return mod
