"""
Track discovered places and build reference blurbs for the UI and narrator.
"""

from storage import load
from simulation.district_state import ensure_district_state

AREAS_FILE = "world/areas.json"
LOC_FILE = "world/locations.json"
WORLD_FILE = "world/world_state.json"
PLAYER_FILE = "player/player.json"


def _city_display(city_key, locs):
    if not city_key:
        return ""
    return locs.get("cities", {}).get(city_key, {}).get("name", city_key.replace("_", " ").title())


def area_subtitle(area_id, area=None, locs=None):
    """Short location label (city · district, or wilderness route)."""
    areas = load(AREAS_FILE, {}) if area is None else None
    locs = locs or load(LOC_FILE, {})
    area = area or areas.get(area_id, {})
    name = area.get("name", area_id.split(":")[-1].replace("_", " ").title())
    prefix = area_id.split(":")[0] if ":" in area_id else ""
    area_type = area.get("area_type") or area.get("type") or ""

    if prefix == "wild" or area.get("type") == "wilderness":
        slug = area_id.split(":", 1)[-1]
        parts = slug.split("_")
        if len(parts) >= 2:
            route = f"{_city_display(parts[0], locs)} → {_city_display(parts[-1], locs)}"
        else:
            route = slug.replace("_", " → ")
        kind = {"road": "Road", "forest": "Forest", "moor": "Moor", "hills": "Hills"}.get(
            area_type, "Wilderness"
        )
        return f"{kind} · {route}"

    city_key = area.get("city") or prefix
    city_name = _city_display(city_key, locs)
    kind = "District" if area.get("type") == "district" else area_type.replace("_", " ").title()
    return f"{city_name} · {kind}"


def build_area_blurb(area_id, areas=None, locs=None):
    """Brief reference description stored in the codex and fed to the narrator."""
    areas = areas or load(AREAS_FILE, {})
    locs = locs or load(LOC_FILE, {})
    area = areas.get(area_id, {})
    if not area:
        leaf = area_id.split(":")[-1].replace("_", " ").title()
        return {
            "id": area_id,
            "name": leaf,
            "subtitle": "",
            "description": "An unfamiliar place.",
            "type": "",
        }

    name = area.get("name", area_id.split(":")[-1].replace("_", " ").title())
    subtitle = area_subtitle(area_id, area, locs)
    sentences = []

    atmosphere = area.get("atmosphere") or []
    if atmosphere:
        sentences.append(f"{name} — {atmosphere[0].strip().capitalize()}.")
        if len(atmosphere) > 1:
            sentences.append(atmosphere[1].strip().capitalize() + ".")

    if area.get("type") == "district":
        st = ensure_district_state(area)
        crowd = area.get("crowd")
        if crowd:
            sentences.append(f"The streets are {crowd}.")
        mood = st.get("mood")
        if mood:
            sentences.append(f"The mood here is {mood}.")
    elif area.get("type") == "wilderness":
        kind = (area.get("area_type") or "wilderness").replace("_", " ")
        sentences.append(f"A {kind} stretch between settlements.")

    storyline = area.get("storyline") or {}
    hook = (storyline.get("hook") or storyline.get("title") or "").strip()
    if hook:
        sentences.append(hook)

    description = " ".join(sentences[:4]).strip()
    if len(description) > 320:
        description = description[:317].rsplit(" ", 1)[0] + "…"

    return {
        "id": area_id,
        "name": name,
        "subtitle": subtitle,
        "description": description or f"{name}. {subtitle}.",
        "type": area.get("type", ""),
    }


def migrate_discovered_areas(player):
    """One-time backfill for saves created before area discovery existed."""
    if player.get("discovered_areas"):
        return

    book = {}
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    world = load(WORLD_FILE, {})

    for entry in player.get("journal") or []:
        aid = entry.get("area")
        if not aid or aid in book:
            continue
        blurb = build_area_blurb(aid, areas, locs)
        book[aid] = {
            "name": blurb["name"],
            "subtitle": blurb["subtitle"],
            "description": blurb["description"],
            "type": blurb["type"],
            "first_day": entry.get("day", world.get("day")),
            "last_day": entry.get("day", world.get("day")),
            "visits": 1,
        }

    if player.get("area") and player["area"] not in book:
        blurb = build_area_blurb(player["area"], areas, locs)
        book[player["area"]] = {
            "name": blurb["name"],
            "subtitle": blurb["subtitle"],
            "description": blurb["description"],
            "type": blurb["type"],
            "first_day": world.get("day"),
            "last_day": world.get("day"),
            "visits": 1,
        }

    player["discovered_areas"] = book


def ensure_discovered_areas(player):
    migrate_discovered_areas(player)
    return player.setdefault("discovered_areas", {})


def record_area_arrival(player, area_id, world=None):
    """
    Register a visit to area_id. Returns arrival info including first_visit flag.
    Mutates player in place.
    """
    if not area_id:
        return None

    world = world or load(WORLD_FILE, {})
    book = player.setdefault("discovered_areas", {})
    first_visit = area_id not in book
    blurb = build_area_blurb(area_id)
    rec = book.get(area_id, {})
    visits = rec.get("visits", 0) + 1
    book[area_id] = {
        "name": blurb["name"],
        "subtitle": blurb["subtitle"],
        "description": blurb["description"],
        "type": blurb["type"],
        "first_day": rec.get("first_day", world.get("day")),
        "last_day": world.get("day"),
        "visits": visits,
    }
    player["discovered_areas"] = book

    return {
        "first_visit": first_visit,
        "id": area_id,
        "name": blurb["name"],
        "subtitle": blurb["subtitle"],
        "description": blurb["description"],
        "type": blurb["type"],
    }


def area_intro_directive(arrival):
    """Narrator instruction for the opening paragraph on first visit."""
    if not arrival:
        return ""
    return (
        f"FIRST VISIT — {arrival['name']} ({arrival['subtitle']}): "
        f"Opening scene — use the full 3–4 paragraph length to orient the player in this place: "
        f"how the space is laid out, who belongs here, what the district is for, "
        f"one tension or rule they should notice, and one cue for what they could do next. "
        f"No bullet lists or stat dumps. Grounding notes: {arrival['description']}"
    )


def get_discovered_places_view(player):
    """Places for codex / UI, sorted by name."""
    book = ensure_discovered_areas(player)
    places = []
    for aid, rec in book.items():
        places.append({
            "id": aid,
            "name": rec.get("name", aid),
            "subtitle": rec.get("subtitle", ""),
            "description": rec.get("description", ""),
            "type": rec.get("type", ""),
            "visits": rec.get("visits", 1),
            "first_day": rec.get("first_day"),
        })
    places.sort(key=lambda p: (p.get("type") != "district", p["name"]))
    return places
