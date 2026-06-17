"""
Economy pressure — lightweight supply/scarcity from district state.
"""

CHAIN_HINTS = {
    "docks": ("ore", "smith", "merchant"),
    "market": ("farm", "merchant", "guild"),
    "high_quarter": ("guild", "merchant", "temple"),
}


def district_suffix(area_id):
    return area_id.split(":")[-1] if area_id else ""


def economy_pressure_for_area(area_id, areas):
    area = (areas or {}).get(area_id, {})
    st = area.get("state") or {}
    prosperity = st.get("prosperity", area.get("prosperity", 50))
    crime = st.get("crime_level", area.get("crime", 30))
    mood = st.get("mood", "uneasy")
    scarcity = max(0, min(100, int(100 - prosperity + crime * 0.3)))
    return {
        "prosperity": prosperity,
        "crime": crime,
        "mood": mood,
        "scarcity": scarcity,
    }


def economy_narrator_block(player, areas):
    aid = player.get("area")
    if not aid:
        return ""
    pressure = economy_pressure_for_area(aid, areas)
    suffix = district_suffix(aid)
    chain = CHAIN_HINTS.get(suffix, ("trade", "labour", "coin"))
    lines = [
        f"ECONOMY ({pressure['mood']} district — scarcity ~{pressure['scarcity']}/100):",
        f"- Supply chain touchstones: {' → '.join(chain)}.",
    ]
    if pressure["scarcity"] >= 60:
        lines.append("- Goods are dear; haggling harder; banditry plausible.")
    elif pressure["scarcity"] <= 25:
        lines.append("- Trade flows; stalls stocked; coin moves.")
    return "\n".join(lines)


def ripple_from_district_shock(area_id, areas, *, prosperity_delta=0, crime_delta=0):
    """Propagate small shocks along abstract chain roles in same district."""
    area = (areas or {}).get(area_id, {})
    if not area:
        return False
    st = area.setdefault("state", {})
    st["prosperity"] = max(0, min(100, st.get("prosperity", 50) + prosperity_delta))
    st["crime_level"] = max(0, min(100, st.get("crime_level", 30) + crime_delta))
    return True
