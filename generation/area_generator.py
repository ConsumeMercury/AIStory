"""
Areas + a travel graph with TIME COSTS.

An "area" is a place you can be: a district inside a city, or wilderness
between cities. Travelling between areas costs HOURS (sometimes days),
and the simulation runs that many background ticks while you travel — so
when you arrive, the world has visibly moved on.

We build areas from the generated cities: each city gets districts that
include story-pipeline requirements, and cities are linked by wilderness
stretches whose hours come from locations.json travel_hours.
"""

import random

from generation.area_storylines import districts_required_for_institution_types

CITY_DISTRICTS = ["market", "docks", "temple_row", "the_warrens", "high_quarter"]
WILDERNESS_TYPES = ["wilderness", "forest", "marsh", "road", "ruins"]

# Pre-defined intra-city travel times (hours) between district suffixes.
_DISTRICT_TRAVEL_HOURS = {
    ("docks", "high_quarter"): 3,
    ("docks", "market"): 2,
    ("docks", "temple_row"): 3,
    ("docks", "the_warrens"): 2,
    ("high_quarter", "market"): 2,
    ("high_quarter", "temple_row"): 2,
    ("high_quarter", "the_warrens"): 3,
    ("market", "temple_row"): 2,
    ("market", "the_warrens"): 2,
    ("temple_row", "the_warrens"): 3,
}

# Sensory anchors seeded per area at generation — narrator picks from these
_DISTRICT_ATMOSPHERE = {
    "market": [
        "grease smoke and shouted prices overlapping",
        "coin changing hands faster than names are exchanged",
        "rotting fruit underfoot, hot oil from a fry-stall",
        "a boy hawking charms that smell of cheap tin",
        "stacked crates blocking the sun, voices bargaining in three languages",
    ],
    "docks": [
        "tar and salt on everything, gulls fighting for scraps",
        "rope creak and hull timber groaning against pilings",
        "wet wool drying on lines between masts",
        "foreign accents thick as the harbour fog",
        "a customs shed where papers matter more than people",
    ],
    "temple_row": [
        "incense layered until the air tastes sweet",
        "bare feet on cold stone, murmured litanies behind closed doors",
        "beggars and penitents sharing the same shade",
        "brass bells rung without rhythm",
        "chalk marks on steps counting debts to the gods",
    ],
    "the_warrens": [
        "wash water dripping from upper windows",
        "narrow alleys where daylight arrives late and leaves early",
        "the smell of cabbage and unwashed wool",
        "children's games played in languages the law doesn't speak",
        "a knife-grinder's wheel singing the same note all day",
    ],
    "high_quarter": [
        "guards who know your face before you know theirs",
        "cobbles too clean for honest mud",
        "perfume masking something older underneath",
        "carriage wheels and the hush money buys",
        "windows shuttered against curiosity",
    ],
}

_WILDERNESS_ATMOSPHERE = {
    "wilderness": [
        "wind that finds every gap in your clothes",
        "distance without landmarks",
        "birds going quiet for no reason you can see",
    ],
    "forest": [
        "needles underfoot muffling your steps",
        "light falling in broken coins through the canopy",
        "something moving just outside sight",
    ],
    "marsh": [
        "breath that tastes of iron and rot",
        "ground that gives when trusted",
        "insects in a constant low roar",
    ],
    "road": [
        "wheel ruts baked hard in summer dust",
        "milestones chipped by bored hands",
        "a lone tree where travellers leave offerings",
    ],
    "ruins": [
        "stone remembering a floorplan the world forgot",
        "ivy pulling mortar apart grain by grain",
        "echoes that arrive a half-second late",
    ],
}

_GATE_PREFS = {
    "port": ["docks", "market"],
    "holy": ["temple_row", "market"],
    "capital": ["high_quarter", "market"],
    "mining": ["market", "the_warrens"],
    "agrarian": ["market", "temple_row"],
    "frontier": ["market", "the_warrens"],
}


def _seed_atmosphere(district_key=None, wilderness_type=None):
    if district_key and district_key in _DISTRICT_ATMOSPHERE:
        pool = _DISTRICT_ATMOSPHERE[district_key]
    elif wilderness_type and wilderness_type in _WILDERNESS_ATMOSPHERE:
        pool = _WILDERNESS_ATMOSPHERE[wilderness_type]
    else:
        pool = ["ordinary sounds for the hour", "dust or damp depending on season"]
    return random.sample(pool, k=min(3, len(pool)))


def district_edge_hours(suffix_a, suffix_b):
    """Fixed travel hours between two districts in the same city."""
    if suffix_a == suffix_b:
        return 0
    key = tuple(sorted([suffix_a, suffix_b]))
    return _DISTRICT_TRAVEL_HOURS.get(key, 2)


def plan_city_districts(city, institution_types=None):
    """
    District suffixes for a city — random sample plus all story-pipeline needs.
    """
    required = districts_required_for_institution_types(institution_types or [])
    bias_map = city.get("district_bias", {})
    weighted = sorted(CITY_DISTRICTS, key=lambda d: (-bias_map.get(d, 1.0), d))

    chosen = set(required)
    for suffix in weighted:
        if len(chosen) >= 4:
            break
        chosen.add(suffix)
    while len(chosen) < 3:
        for suffix in CITY_DISTRICTS:
            chosen.add(suffix)
            if len(chosen) >= 3:
                break

    return sorted(chosen)


def gate_district_for_city(ckey, areas, city):
    """District that links this city to wilderness travel routes."""
    arch = city.get("archetype", "")
    prefs = _GATE_PREFS.get(arch, ["market", "docks", "high_quarter"])
    for suffix in prefs:
        aid = f"{ckey}:{suffix}"
        if aid in areas:
            return aid
    return next((aid for aid in areas if aid.startswith(ckey + ":")), None)


def inter_city_travel_hours(city_a, city_b, cities):
    """Hours between two cities — from locations travel_hours, symmetric."""
    a = cities.get(city_a, {})
    b = cities.get(city_b, {})
    ha = (a.get("travel_hours") or {}).get(city_b)
    hb = (b.get("travel_hours") or {}).get(city_a)
    if ha and hb:
        return max(int(ha), int(hb))
    if ha:
        return int(ha)
    if hb:
        return int(hb)
    return 20


def annotate_city_gates(cities, areas):
    """Record each city's wilderness gate on the location record."""
    for ckey, city in cities.items():
        gate = gate_district_for_city(ckey, areas, city)
        if gate:
            city["gate_area"] = gate
    return cities


def ensure_story_districts(areas, cities, institution_plan=None, institutions=None):
    """
    Patch an existing area graph: add missing story districts and travel edges.
    Used when loading older saves.
    """
    institution_plan = institution_plan or {}
    required_by_city = {}
    for ckey in cities:
        types = institution_plan.get(ckey)
        if types is None and institutions:
            types = [i.get("type") for i in institutions.values() if i.get("city") == ckey]
        required_by_city[ckey] = plan_city_districts(cities[ckey], types)

    for ckey, suffixes in required_by_city.items():
        city = cities[ckey]
        for suffix in suffixes:
            aid = f"{ckey}:{suffix}"
            if aid in areas:
                continue
            bias_map = city.get("district_bias", {})
            d_bias = bias_map.get(suffix, 1.0)
            crime = max(5, min(95, int(city.get("crime_rate", 30) * d_bias)))
            prosperity = max(5, min(95, int(city.get("prosperity", 50) * d_bias)))
            areas[aid] = {
                "id": aid,
                "name": suffix.replace("_", " ").title(),
                "city": ckey,
                "type": "district",
                "area_type": "city",
                "edges": {},
                "atmosphere": _seed_atmosphere(district_key=suffix),
                "crime": crime,
                "prosperity": prosperity,
                "crowd": "moderate",
                "check_modifier": int((crime - 40) / 18 + (50 - prosperity) / 40),
            }

        district_ids = [f"{ckey}:{s}" for s in suffixes if f"{ckey}:{s}" in areas]
        for a in district_ids:
            sa = a.split(":")[-1]
            for b in district_ids:
                if a == b:
                    continue
                sb = b.split(":")[-1]
                hours = district_edge_hours(sa, sb)
                areas[a].setdefault("edges", {})[b] = hours

    _link_wilderness(areas, cities)
    annotate_city_gates(cities, areas)
    return areas


def _link_wilderness(areas, cities):
    """Connect cities via wilderness using pre-defined inter-city hours."""
    for ckey, city in cities.items():
        for neighbour in city.get("connected", []):
            if neighbour not in cities:
                continue
            wid = "wild:" + "_".join(sorted([ckey, neighbour]))
            if wid not in areas:
                wtype = random.choice(WILDERNESS_TYPES)
                areas[wid] = {
                    "id": wid,
                    "name": "The Wilds",
                    "city": None,
                    "type": "wilderness",
                    "area_type": wtype,
                    "edges": {},
                    "atmosphere": _seed_atmosphere(wilderness_type=wtype),
                }
            travel_hours = inter_city_travel_hours(ckey, neighbour, cities)
            gate_a = gate_district_for_city(ckey, areas, city)
            gate_b = gate_district_for_city(neighbour, areas, cities[neighbour])
            if gate_a:
                areas[gate_a].setdefault("edges", {})[wid] = travel_hours
                areas[wid].setdefault("edges", {})[gate_a] = travel_hours
            if gate_b:
                areas[gate_b].setdefault("edges", {})[wid] = travel_hours
                areas[wid].setdefault("edges", {})[gate_b] = travel_hours
            areas[wid]["inter_city_hours"] = {ckey: travel_hours, neighbour: travel_hours}


def build_areas(cities, institution_plan=None):
    """
    cities: dict of city_key -> city dict (from location_generator).
    institution_plan: optional {city_key: [institution_type, ...]} for story districts.
    Returns {area_id: area} with travel edges (area_id -> hours).
    """
    institution_plan = institution_plan or {}
    areas = {}

    for ckey in cities:
        city = cities[ckey]
        inst_types = institution_plan.get(ckey, [])
        district_suffixes = plan_city_districts(city, inst_types)
        district_keys = []

        for suffix in district_suffixes:
            aid = f"{ckey}:{suffix}"
            district_keys.append(aid)
            bias_map = city.get("district_bias", {})
            d_bias = bias_map.get(suffix, 1.0)
            crime = max(5, min(95, int(city.get("crime_rate", 30) * d_bias)))
            prosperity = max(5, min(95, int(city.get("prosperity", 50) * d_bias)))
            areas[aid] = {
                "id": aid,
                "name": suffix.replace("_", " ").title(),
                "city": ckey,
                "type": "district",
                "area_type": "city",
                "edges": {},
                "atmosphere": _seed_atmosphere(district_key=suffix),
                "crime": crime,
                "prosperity": prosperity,
                "crowd": random.choice(["sparse", "moderate", "busy", "packed"]),
                "check_modifier": int((crime - 40) / 18 + (50 - prosperity) / 40),
            }

        for a in district_keys:
            sa = a.split(":")[-1]
            for b in district_keys:
                if a == b:
                    continue
                sb = b.split(":")[-1]
                hours = district_edge_hours(sa, sb)
                areas[a]["edges"][b] = hours

    _link_wilderness(areas, cities)
    annotate_city_gates(cities, areas)
    return areas
