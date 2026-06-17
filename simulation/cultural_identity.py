"""
Cultural identity — city/district customs affect reactions and narrator texture.
"""

from storage import load

LOC_FILE = "world/locations.json"
AREAS_FILE = "world/areas.json"

TABOO_HINTS = {
    "cosmopolitan": "open trade, suspicion of outsiders who break contracts",
    "clan loyalty": "blood ties before coin; insult the family, not the person",
    "court intrigue": "every compliment may be a trap",
    "everyone armed": "reach for a weapon reads as normal, not shocking",
    "pilgrim traffic": "sacred hours and fasting days matter",
    "frontier justice": "duels and vendettas tolerated",
    "sailors' superstitions": "salt, bells, and drowned names are bad luck",
}


def city_culture(player, areas=None, locations=None):
    areas = areas if areas is not None else load(AREAS_FILE, {})
    locations = locations if locations is not None else load(LOC_FILE, {})
    city_name = player.get("location")
    cities = locations.get("cities", {})
    city = cities.get(city_name, {})
    culture = list(city.get("culture") or [])
    aid = player.get("area")
    if aid and aid in areas:
        suffix = aid.split(":")[-1]
        area = areas[aid]
        if area.get("atmosphere"):
            culture.extend(area["atmosphere"][:1])
        culture.append(suffix.replace("_", " "))
    return culture[:4]


def cultural_reaction_block(player, *, areas=None, locations=None):
    culture = city_culture(player, areas=areas, locations=locations)
    if not culture:
        return ""
    hints = []
    for c in culture:
        key = c.lower()
        for tag, hint in TABOO_HINTS.items():
            if tag in key or key in tag:
                hints.append(hint)
                break
    lines = [f"CULTURE ({', '.join(culture[:3])}):"]
    if hints:
        lines.append(f"- Locals: {hints[0][:100]}.")
    lines.append("- Same action may read differently here than elsewhere.")
    return "\n".join(lines)
