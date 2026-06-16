"""
Daily agendas — NPCs move between districts by hour and prefer scheduled activities.

Travel between scheduled districts uses the same area graph as the player:
NPCs enter transit for path_hours and arrive when world hour_count catches up.
"""

import random

from storage import load, save
from simulation.travel_engine import path_hours

AREAS_FILE = "world/areas.json"
NPC_FILE = "characters/npcs.json"

# role -> list of (start_hour, end_hour, activity, district_suffix, label)
_ROLE_AGENDA = {
    "merchant": [
        (8, 13, "trade", "market", "opens stall"),
        (13, 14, "rest", "market", "closes accounts"),
        (14, 17, "trade", "market", "afternoon trade"),
        (17, 19, "socialise", "high_quarter", "meets creditors"),
        (19, 22, "socialise", "market", "tavern near the stalls"),
    ],
    "innkeeper": [
        (6, 11, "craft", "market", "breakfast service"),
        (11, 22, "socialise", "market", "runs the common room"),
        (22, 6, "rest", "market", "locks up"),
    ],
    "priest": [
        (6, 9, "study", "temple_row", "morning rites"),
        (9, 12, "help", "temple_row", "tends the poor"),
        (12, 15, "socialise", "temple_row", "counsels petitioners"),
        (15, 18, "study", "temple_row", "records and prayer"),
        (18, 21, "socialise", "market", "evening alms round"),
    ],
    "guard": [
        (6, 14, "fight", "high_quarter", "day watch"),
        (14, 22, "fight", "market", "evening patrol"),
        (22, 6, "rest", "high_quarter", "barracks rest"),
    ],
    "soldier": [
        (6, 14, "fight", "high_quarter", "garrison duty"),
        (14, 18, "train", "high_quarter", "drill yard"),
        (18, 22, "socialise", "market", "off-duty drink"),
    ],
    "scholar": [
        (8, 12, "study", "temple_row", "archive work"),
        (12, 14, "rest", "high_quarter", "midday meal"),
        (14, 18, "study", "high_quarter", "research"),
        (18, 21, "socialise", "market", "debates at a table"),
    ],
    "thief": [
        (10, 14, "hide", "the_warrens", "sleeps late"),
        (14, 18, "plan", "the_warrens", "scores a job"),
        (18, 23, "trade", "market", "fences goods"),
        (23, 3, "hide", "the_warrens", "vanishes"),
    ],
    "sailor": [
        (6, 12, "craft", "docks", "ship work"),
        (12, 17, "socialise", "docks", "crew gossip"),
        (17, 23, "socialise", "docks", "harbour tavern"),
    ],
    "blacksmith": [
        (7, 13, "craft", "market", "forge open"),
        (13, 14, "rest", "market", "meal"),
        (14, 19, "craft", "market", "commissions"),
    ],
    "default": [
        (8, 12, "craft", "market", "morning work"),
        (12, 13, "rest", "market", "meal"),
        (13, 17, "trade", "market", "afternoon errands"),
        (17, 20, "socialise", "market", "evening"),
    ],
}


def _city_areas(city, areas):
    return [aid for aid, a in areas.items() if a.get("city") == city and a.get("type") == "district"]


def _area_for_suffix(city, suffix, areas, fallback):
    target = f"{city}:{suffix}"
    if target in areas:
        return target
    for aid in _city_areas(city, areas):
        if aid.endswith(":" + suffix):
            return aid
    return fallback


def build_schedule(npc, areas):
    """Build a daily agenda from role and home district."""
    city = npc.get("location")
    home = npc.get("area")
    if not city or not home:
        return None

    role = npc.get("role", "merchant")
    template = _ROLE_AGENDA.get(role, _ROLE_AGENDA["default"])
    slots = []
    for start, end, activity, suffix, label in template:
        area_id = _area_for_suffix(city, suffix, areas, home)
        slot_hours = path_hours(home, area_id, areas) if area_id and home else 0
        slots.append({
            "start": start,
            "end": end,
            "area": area_id,
            "activity": activity,
            "label": label,
            "travel_hours_from_home": slot_hours or 0,
        })

    return {
        "home_area": home,
        "slots": slots,
        "flexibility": random.randint(0, 2),
    }


def attach_schedules(npcs, areas):
    """Assign schedules to all alive NPCs (generation or patch)."""
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if not npc.get("schedule"):
            sched = build_schedule(npc, areas)
            if sched:
                npc["schedule"] = sched
    return npcs


def slot_for_hour(schedule, hour):
    """Return active slot for hour 0-23, or None."""
    if not schedule:
        return None
    for slot in schedule.get("slots", []):
        start, end = slot["start"], slot["end"]
        if start <= end:
            if start <= hour < end:
                return slot
        else:
            if hour >= start or hour < end:
                return slot
    return None


def scheduled_location(npc, hour, areas):
    """Where this NPC should be right now."""
    sched = npc.get("schedule")
    slot = slot_for_hour(sched, hour)
    if slot:
        return slot["area"], slot.get("activity"), slot.get("label")
    home = sched.get("home_area") if sched else None
    return npc.get("area") or home, "rest", "off duty"


def _hour_count(world):
    return world.get("hour_count", world.get("day", 1) * 24 + world.get("hour", 12))


def _update_transit_remaining(npc, world):
    ts = npc.get("travel_state")
    if not ts:
        return
    remaining = max(0, ts.get("arrives_at", 0) - _hour_count(world))
    ts["hours_remaining"] = remaining


def resolve_npc_transit(npcs, world, areas):
    """Complete in-flight moves when travel time has elapsed."""
    hour_count = _hour_count(world)
    changed = False
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        ts = npc.get("travel_state")
        if not ts:
            continue
        _update_transit_remaining(npc, world)
        if hour_count >= ts.get("arrives_at", 0):
            npc["area"] = ts.get("to_area") or npc.get("area")
            npc.pop("travel_state", None)
            npc["schedule_activity"] = "travel"
            npc["schedule_label"] = "just arrived"
            changed = True
    return changed


def _begin_transit(npc, from_area, to_area, world, areas):
    """Put NPC en route; returns True if transit started."""
    if not from_area or not to_area or from_area == to_area:
        return False
    hours = path_hours(from_area, to_area, areas)
    if hours is None:
        hours = 2
    flex = (npc.get("schedule") or {}).get("flexibility", 0)
    if flex:
        hours = max(1, hours + random.randint(-flex, flex))

    hour_count = _hour_count(world)
    npc["travel_state"] = {
        "from_area": from_area,
        "to_area": to_area,
        "departed_at": hour_count,
        "arrives_at": hour_count + hours,
        "hours_remaining": hours,
    }
    npc["schedule_activity"] = "travel"
    npc["schedule_label"] = f"en route ({hours}h)"
    return True


def apply_schedules_to_npcs(npcs=None, world=None, areas=None):
    """
    Move NPCs toward scheduled districts for current hour.
    Long commutes use travel_state so background time matches the map.
    """
    loaded_internally = npcs is None
    npcs = npcs if npcs is not None else load(NPC_FILE, {})
    world = world if world is not None else load("world/world_state.json", {})
    areas = areas if areas is not None else load(AREAS_FILE, {})
    hour = world.get("hour", 12)
    changed = resolve_npc_transit(npcs, world, areas)

    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if not npc.get("schedule"):
            continue
        if npc.get("travel_state"):
            _update_transit_remaining(npc, world)
            continue

        area_id, activity, label = scheduled_location(npc, hour, areas)
        current = npc.get("area")
        if area_id and current != area_id:
            if _begin_transit(npc, current, area_id, world, areas):
                changed = True
            else:
                npc["area"] = area_id
                changed = True
        npc["schedule_activity"] = activity
        npc["schedule_label"] = label

    if changed and loaded_internally:
        save(NPC_FILE, npcs)
    return npcs


def schedule_hint(npc, world=None):
    """One line for narrator / player commands."""
    world = world or load("world/world_state.json", {})
    ts = npc.get("travel_state")
    if ts and ts.get("hours_remaining", 0) > 0:
        dest = ts.get("to_area", "")
        return f"En route to {dest.split(':')[-1].replace('_', ' ')} (~{ts['hours_remaining']}h)."
    hour = world.get("hour", 12)
    sched = npc.get("schedule")
    if not sched:
        return ""
    slot = slot_for_hour(sched, hour)
    if slot:
        return f"Routine now: {slot.get('label', slot.get('activity', ''))}."
    return "Off schedule — at home or resting."


def next_appearance(npc, world=None, areas=None):
    """When/where the NPC will be next (for stake-outs), including travel delay."""
    world = world or load("world/world_state.json", {})
    areas = areas or load(AREAS_FILE, {})
    hour = world.get("hour", 12)
    sched = npc.get("schedule")
    if not sched:
        return None

    transit_wait = 0
    current_area = npc.get("area")
    ts = npc.get("travel_state")
    if ts and ts.get("hours_remaining", 0) > 0:
        transit_wait = ts["hours_remaining"]
        current_area = ts.get("to_area") or current_area

    for offset in range(1, 25):
        h = (hour + offset) % 24
        slot = slot_for_hour(sched, h)
        if not slot:
            continue
        slot_area = slot["area"]
        commute = path_hours(current_area, slot_area, areas) or 0
        area = areas.get(slot_area, {})
        return {
            "in_hours": offset + transit_wait + commute,
            "hour": h,
            "area": slot_area,
            "area_name": area.get("name", slot_area),
            "label": slot.get("label", ""),
            "activity": slot.get("activity", ""),
            "travel_hours": commute,
        }
    return None


def npc_in_transit(npc):
    """True when NPC is travelling between districts."""
    ts = npc.get("travel_state") or {}
    return ts.get("hours_remaining", 0) > 0
