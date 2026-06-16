"""
District transformation — places drift with crime, prosperity, and story tension.
"""

import random

from storage import load, save

AREAS_FILE = "world/areas.json"
EVENT_FILE = "events/event_log.json"

MOOD_LABELS = [
    (75, "thriving"),
    (55, "prosperous"),
    (40, "uneasy"),
    (25, "declining"),
    (10, "desperate"),
    (0, "ruined"),
]


def _mood_label(score):
    for cutoff, label in MOOD_LABELS:
        if score >= cutoff:
            return label
    return "ruined"


def ensure_district_state(area):
    st = area.setdefault("state", {})
    st.setdefault("prosperity", area.get("prosperity", 50))
    st.setdefault("crime_level", area.get("crime", 30))
    st.setdefault("tension", (area.get("storyline") or {}).get("tension", 20))
    st.setdefault("mood", _mood_label(st["prosperity"] - st["crime_level"] * 0.4))
    return st


def advance_districts(tick=None):
    """Drift district stats from recent events and storyline tension."""
    areas = load(AREAS_FILE, {})
    events = load(EVENT_FILE, [])
    recent = events[-40:] if events else []
    changed = False

    for aid, area in areas.items():
        if area.get("type") != "district":
            continue
        st = ensure_district_state(area)
        city = area.get("city")

        for e in recent:
            if not isinstance(e, dict):
                continue
            loc = e.get("location") or ""
            if loc != aid and loc != city:
                continue
            etype = e.get("type", "")
            action = e.get("action", "")
            if etype in ("combat", "conflict") or action in ("fight", "violence_occurred"):
                st["crime_level"] = min(100, st.get("crime_level", 30) + random.uniform(0.5, 2.0))
            if action in ("trade", "trade_boosted_economy"):
                st["prosperity"] = min(100, st.get("prosperity", 50) + random.uniform(0.2, 1.0))
            if etype == "death":
                st["prosperity"] = max(0, st.get("prosperity", 50) - random.uniform(0.5, 1.5))
                st["crime_level"] = min(100, st.get("crime_level", 30) + random.uniform(0.3, 1.0))

        sl = area.get("storyline") or {}
        st["tension"] = sl.get("tension", st.get("tension", 20))
        if st["tension"] > 60:
            st["crime_level"] = min(100, st.get("crime_level", 30) + 0.3)

        # slow decay toward baseline
        st["crime_level"] = max(area.get("crime", 20), st["crime_level"] * 0.998)
        st["prosperity"] = max(10, min(100, st["prosperity"] * 0.999 + 0.05))

        mood_score = st["prosperity"] - st["crime_level"] * 0.45 - st["tension"] * 0.15
        st["mood"] = _mood_label(mood_score)
        area["crowd"] = {
            "thriving": "packed", "prosperous": "busy", "uneasy": "moderate",
            "declining": "sparse", "desperate": "sparse", "ruined": "sparse",
        }.get(st["mood"], area.get("crowd", "moderate"))
        area["check_modifier"] = int((st["crime_level"] - 40) / 15 + (50 - st["prosperity"]) / 35)
        changed = True

    if changed:
        save(AREAS_FILE, areas)
    return areas


def district_narrator_block(area_id, areas=None):
    areas = areas or load(AREAS_FILE, {})
    area = areas.get(area_id, {})
    if not area or area.get("type") != "district":
        return ""
    st = ensure_district_state(area)
    name = area.get("name", area_id)
    return (
        f"DISTRICT MOOD: {name} feels {st.get('mood', 'unchanged')} "
        f"(prosperity {st.get('prosperity', 0):.0f}, crime {st.get('crime_level', 0):.0f}). "
        f"The place has changed — show it in detail, not statistics."
    )
