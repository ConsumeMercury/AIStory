"""
World time tracked in HOURS. One tick = one in-world hour by default.
Day/season/weather derive from the hour counter. advance_hours() lets the
travel engine jump time forward (a long journey).
"""

import random
import re

from storage import load, save

WORLD_FILE = "world/world_state.json"
HOURS_PER_DAY = 24
DAYS_PER_SEASON = 30
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]

# Start hour for each named time-of-day period.
TIME_OF_DAY_TARGETS = {
    "deep night": 0,
    "midnight": 0,
    "dawn": 5,
    "morning": 8,
    "afternoon": 12,
    "evening": 17,
    "night": 21,
    "noon": 12,
    "sunrise": 5,
    "sunset": 17,
    "dusk": 19,
}

# In-world hours consumed by player actions (dialogue is same moment).
ACTION_TIME_HOURS = {
    "talk": 0,
    "personal_talk": 0,
    "ask_name": 0,
    "ask_about": 0,
    "help": 0,
    "give": 0,
    "threaten": 0,
    "insult": 0,
    "show_respect": 0,
    "trade": 0,
    "withdraw": 0,
    "guild": 0,
    "blackmail": 0,
    "accuse": 0,
    "examine": 0,
    "approach": 0,
    "explore": 1,
    "observe": 1,
    "general": 0,
    "find": 1,
    "search": 1,
    "attack": 1,
    "confess": 1,
    "investigate": 1,
    "hunt": 2,
    "rest": 2,
    "wait": 2,
    "travel": 0,
    "meta": 0,
}
WEATHER_BY_SEASON = {
    "Spring": ["Clear", "Rain", "Rain", "Fog"],
    "Summer": ["Clear", "Clear", "Heatwave", "Storm"],
    "Autumn": ["Clear", "Rain", "Storm", "Fog"],
    "Winter": ["Clear", "Snow", "Snow", "Fog"],
}

_UNTIL_TIME = re.compile(
    r"\b(?:wait|sleep|rest|stay)\s+(?:until|till|til)\s+(?:the\s+)?(.+?)(?:\s*$|\.|,)",
    re.I,
)


def _recompute(world):
    total_hours = world.get("hour_count", 0)
    world["day"] = total_hours // HOURS_PER_DAY + 1
    world["hour"] = total_hours % HOURS_PER_DAY
    season_index = ((world["day"] - 1) // DAYS_PER_SEASON) % len(SEASONS)
    world["season"] = SEASONS[season_index]
    # weather changes a few times a day, weighted by season
    if total_hours % 6 == 0 or "weather" not in world:
        world["weather"] = random.choice(WEATHER_BY_SEASON[world["season"]])
    # human-readable time of day
    h = world["hour"]
    world["time_of_day"] = (
        "deep night" if h < 5 else "dawn" if h < 8 else "morning" if h < 12
        else "afternoon" if h < 17 else "evening" if h < 21 else "night"
    )
    return world


def hours_until_hour(current_hour, target_hour):
    """Hours until target hour (0–23), wrapping past midnight if needed."""
    current_hour = current_hour % HOURS_PER_DAY
    target_hour = target_hour % HOURS_PER_DAY
    if target_hour > current_hour:
        return target_hour - current_hour
    if target_hour < current_hour:
        return (HOURS_PER_DAY - current_hour) + target_hour
    return HOURS_PER_DAY


def parse_named_time_target(action):
    """Return (label, target_hour) from 'wait until dawn' etc., or None."""
    if not action:
        return None
    text = action.lower()
    m = _UNTIL_TIME.search(text.strip())
    fragment = (m.group(1) if m else text).strip().rstrip(".,")
    if not fragment:
        return None
    for name in sorted(TIME_OF_DAY_TARGETS, key=len, reverse=True):
        if name in fragment or fragment.startswith(name.split()[0]):
            return name, TIME_OF_DAY_TARGETS[name]
    return None


def resolve_wait_advance(action, world, player=None, area_id=None):
    """
    Compute wait duration and optional targets.
    Returns dict: hours, target_label, event, refused, refusal_message.
    """
    base = ACTION_TIME_HOURS.get("wait", 2)
    result = {
        "hours": base,
        "target_label": None,
        "event": None,
        "refused": False,
        "refusal_message": "",
    }
    if not action or not re.search(r"\bwait\b", action, re.I):
        return result

    from simulation.scheduled_events import parse_wait_for_event, hours_until_event

    if re.search(r"\bwait\s+(?:for|until)\b", action, re.I):
        event = parse_wait_for_event(action, player, area_id)
        if event:
            hrs = hours_until_event(event, world)
            if hrs <= 0:
                result["hours"] = 0
                result["event"] = event
                result["target_label"] = event.get("label")
                return result
            result["hours"] = max(1, hrs)
            result["event"] = event
            result["target_label"] = event.get("label")
            return result
        if re.search(r"\b(?:toll|bell|auction|buyers?|bid|chute|coal)\b", action, re.I):
            result["refused"] = True
            result["hours"] = 0
            result["refusal_message"] = (
                "WAIT REFUSED — that event is not scheduled in simulation. "
                "No time passes. Do NOT narrate the bell or auction firing. "
                "One short beat of stillness — do NOT repeat the prior NPC line verbatim."
            )
            return result

    named = parse_named_time_target(action)
    if named:
        label, target_hour = named
        current = world.get("hour", 0)
        hours = hours_until_hour(current, target_hour)
        if hours <= 0:
            hours = HOURS_PER_DAY
        result["hours"] = hours
        result["target_label"] = label
        return result

    return result


def advance_clock(hours=1):
    if not hours:
        return load(WORLD_FILE, {})
    world = load(WORLD_FILE, {})
    world["hour_count"] = world.get("hour_count", 0) + hours
    _recompute(world)
    save(WORLD_FILE, world)
    return world


def advance_for_action(kind, action=None, world=None, player=None, area_id=None):
    """Advance world time for a player turn — dialogue costs no hours."""
    if kind == "wait":
        world = world or load(WORLD_FILE, {})
        wait = resolve_wait_advance(action, world, player=player, area_id=area_id)
        if wait.get("refused") or wait.get("hours", 0) <= 0:
            return world
        return advance_clock(wait["hours"])

    hours = ACTION_TIME_HOURS.get(kind, 0)
    if hours:
        return advance_clock(hours)
    return load(WORLD_FILE, {})


def advance_hours(hours):
    return advance_clock(hours)
