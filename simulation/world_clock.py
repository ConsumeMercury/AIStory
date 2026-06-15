"""
World time tracked in HOURS. One tick = one in-world hour by default.
Day/season/weather derive from the hour counter. advance_hours() lets the
travel engine jump time forward (a long journey).
"""

import random
from storage import load, save

WORLD_FILE = "world/world_state.json"
HOURS_PER_DAY = 24
DAYS_PER_SEASON = 30
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
WEATHER_BY_SEASON = {
    "Spring": ["Clear", "Rain", "Rain", "Fog"],
    "Summer": ["Clear", "Clear", "Heatwave", "Storm"],
    "Autumn": ["Clear", "Rain", "Storm", "Fog"],
    "Winter": ["Clear", "Snow", "Snow", "Fog"],
}


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


def advance_clock(hours=1):
    world = load(WORLD_FILE, {})
    world["hour_count"] = world.get("hour_count", 0) + hours
    _recompute(world)
    save(WORLD_FILE, world)
    return world


def advance_hours(hours):
    return advance_clock(hours)
