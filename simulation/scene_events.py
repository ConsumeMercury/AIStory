"""
Small ambient events that give scenes momentum — overheard, interrupted, discovered.
"""

import random


def scene_event_chance(action_kind, area=None):
    """Base probability before goal boosts."""
    if action_kind in ("attack", "travel", "rest"):
        chance = 0.15
    elif action_kind in ("explore", "talk", "personal_talk", "observe"):
        chance = 0.62
    else:
        chance = 0.42

    if area and area.get("crowd") in ("busy", "packed"):
        chance += 0.1
    if area and area.get("crime", 0) > 55:
        chance += 0.08
    return chance


# Shared with goal_events for weighted selection
BASE_SCENE_EVENTS = [
    {
        "id": "argument",
        "text": "Two dockworkers argue over short weight; voices rise then break off.",
        "check": ("empathy", 10),
        "success": "You catch the real grievance beneath the shouting.",
        "fail": "You only hear insults; the cause stays hidden.",
    },
    {
        "id": "pickpocket",
        "text": "Someone brushes past too close — a hand near your belt.",
        "check": ("survival", 12),
        "success": "You turn in time; the thief slips away empty-handed.",
        "fail": "Coin or a trinket is gone before you react.",
    },
    {
        "id": "patrol",
        "text": "A guard's boots slow near you; a look, then moving on.",
        "check": ("deception", 11),
        "success": "You look like you belong; they pass without words.",
        "fail": "You are questioned briefly — suspicion lingers.",
    },
    {
        "id": "accident",
        "text": "A crate shifts; someone shouts a warning.",
        "check": ("survival", 10),
        "success": "You sidestep; the danger passes.",
        "fail": "You take a glancing blow — pain, embarrassment.",
    },
    {
        "id": "offer",
        "text": "A peddler opens a cloth to show something you didn't know you needed.",
        "check": ("appraisal", 11),
        "success": "You see the flaw — or the value — before speaking.",
        "fail": "The price feels wrong but you can't say why.",
    },
    {
        "id": "recognition",
        "text": "A stranger's eyes catch on you a beat too long.",
        "check": ("empathy", 11),
        "success": "You read caution, not threat — or the reverse.",
        "fail": "The look passes; you can't place its meaning.",
    },
    {
        "id": "rain_leak",
        "text": "Water finds a gap in the roof — or the sky — and someone curses.",
        "check": ("survival", 9),
        "success": "You find dry footing and a moment's shelter.",
        "fail": "Cold water down the collar; composure slips.",
    },
    {
        "id": "song",
        "text": "Someone hums an old tune half-remembered; others fall quiet.",
        "check": ("empathy", 10),
        "success": "The melody pulls a memory loose — yours or theirs.",
        "fail": "The song ends before it means anything.",
    },
    {
        "id": "smoke",
        "text": "Smoke drifts from a alley — not cookfire, something sharper.",
        "check": ("survival", 11),
        "success": "You place the smell: tar, fear, or worse.",
        "fail": "It is gone before you can name it.",
    },
    {
        "id": "child",
        "text": "A child darts between legs, chased or chasing.",
        "check": ("empathy", 9),
        "success": "You see whether to step aside or intervene.",
        "fail": "You are jostled; irritation or guilt follows.",
    },
]


def maybe_scene_event(action_kind, area=None, force=False, player=None):
    """
    Returns event dict or None. Social/explore scenes get events more often.
    When player is given, goal-themed events are weighted toward their motivation.
    """
    if player:
        from simulation.goal_events import pick_goal_scene_event
        return pick_goal_scene_event(player, action_kind, area=area, force=force)

    chance = scene_event_chance(action_kind, area)
    if not force and random.random() > chance:
        return None

    ev = random.choice(BASE_SCENE_EVENTS)
    return dict(ev)
