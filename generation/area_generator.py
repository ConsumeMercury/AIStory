"""
Areas + a travel graph with TIME COSTS.

An "area" is a place you can be: a district inside a city, or wilderness
between cities. Travelling between areas costs HOURS (sometimes days),
and the simulation runs that many background ticks while you travel — so
when you arrive, the world has visibly moved on.

We build areas from the generated cities: each city gets a few districts,
and cities are linked by wilderness stretches.
"""

import random

CITY_DISTRICTS = ["market", "docks", "temple_row", "the_warrens", "high_quarter"]
WILDERNESS_TYPES = ["wilderness", "forest", "marsh", "road", "ruins"]


def build_areas(cities):
    """
    cities: dict of city_key -> city dict (from location_generator).
    Returns {area_id: area} with travel edges (area_id -> hours).
    """
    areas = {}

    # districts within each city (short hops, 1-3 hours)
    for ckey in cities:
        district_keys = []
        for d in random.sample(CITY_DISTRICTS, k=random.randint(3, 4)):
            aid = f"{ckey}:{d}"
            district_keys.append(aid)
            areas[aid] = {
                "id": aid, "name": d.replace("_", " ").title(),
                "city": ckey, "type": "district",
                "area_type": "city", "edges": {},
            }
        # link districts to each other within the city
        for a in district_keys:
            for b in district_keys:
                if a != b:
                    areas[a]["edges"][b] = random.choice([1, 2, 3])

    # wilderness stretches between connected cities (long hops, hours->days)
    city_list = list(cities.keys())
    for ckey, city in cities.items():
        for neighbour in city.get("connected", []):
            if neighbour not in cities:
                continue
            wid = "wild:" + "_".join(sorted([ckey, neighbour]))
            if wid not in areas:
                areas[wid] = {
                    "id": wid, "name": "The Wilds",
                    "city": None, "type": "wilderness",
                    "area_type": random.choice(WILDERNESS_TYPES),
                    "edges": {},
                }
            # connect a gate-district of each city to the wilderness
            gate_a = next((a for a in areas if a.startswith(ckey + ":")), None)
            gate_b = next((a for a in areas if a.startswith(neighbour + ":")), None)
            travel_hours = random.choice([10, 14, 20, 28, 36])  # long
            if gate_a:
                areas[gate_a]["edges"][wid] = travel_hours
                areas[wid]["edges"][gate_a] = travel_hours
            if gate_b:
                areas[gate_b]["edges"][wid] = travel_hours
                areas[wid]["edges"][gate_b] = travel_hours

    return areas
