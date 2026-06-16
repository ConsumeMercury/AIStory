"""
Structured player goals — what to do next, with trackable progress.
"""

import re

BACKGROUND_GOALS = {
    "soldier": {
        "id": "prove_worth",
        "text": "Prove your worth in a world that only respects strength.",
        "hint": "Win a fight, earn respect from soldiers or guards, survive danger.",
        "target": 3,
        "track": "renown_actions",
    },
    "merchant": {
        "id": "build_fortune",
        "text": "Build a fortune through shrewd deals.",
        "hint": "Trade successfully, grow your coin, talk your way into opportunities.",
        "target": 100,
        "track": "wealth",
    },
    "scholar": {
        "id": "uncover_truth",
        "text": "Uncover a truth others have buried.",
        "hint": "Talk to scholars and clerics, investigate, learn names and secrets.",
        "target": 4,
        "track": "discovery_actions",
    },
    "thief": {
        "id": "climb_underworld",
        "text": "Climb the city's underside without getting caught.",
        "hint": "Steal, survive the warrens, make contacts who will vouch for you.",
        "target": 3,
        "track": "underworld_actions",
    },
    "wanderer": {
        "id": "find_place",
        "text": "Find where you belong — or who needs you.",
        "hint": "Explore districts, help someone, follow local storylines.",
        "target": 4,
        "track": "explore_actions",
    },
}

MOTIVATION_PATTERNS = [
    (re.compile(r"\b(glory|fame|renown|legend)\b", re.I), {
        "id": "earn_renown",
        "text": "Earn renown — let people remember your name.",
        "hint": "Win respect through combat, bold action, or public deeds.",
        "target": 4,
        "track": "renown_actions",
    }),
    (re.compile(r"\b(power|rule|control|dominat)\b", re.I), {
        "id": "gain_power",
        "text": "Gain power over people and outcomes.",
        "hint": "Intimidate, bargain, ally with leaders, control key moments.",
        "target": 4,
        "track": "power_actions",
    }),
    (re.compile(r"\b(knowledge|learn|truth|secret|study)\b", re.I), {
        "id": "seek_knowledge",
        "text": "Seek knowledge others guard.",
        "hint": "Visit academies and temples, ask personal questions, investigate.",
        "target": 4,
        "track": "discovery_actions",
    }),
    (re.compile(r"\b(wealth|coin|gold|rich|money)\b", re.I), {
        "id": "grow_wealth",
        "text": "Grow your wealth.",
        "hint": "Trade, complete paid work, don't go broke.",
        "target": 80,
        "track": "wealth",
    }),
    (re.compile(r"\b(revenge|score|vengeance|payback)\b", re.I), {
        "id": "settle_score",
        "text": "Settle a score — yours or someone else's.",
        "hint": "Find who wronged whom; violence or leverage may follow.",
        "target": 3,
        "track": "conflict_actions",
    }),
    (re.compile(r"\b(brother|sister|family|father|mother|kin|lost|missing|find him|find her)\b", re.I), {
        "id": "find_someone",
        "text": "Find someone you have lost — or who lost you.",
        "hint": "Ask around, follow rumors, watch who avoids your questions.",
        "target": 4,
        "track": "personal_actions",
    }),
]

TRACK_TO_THEME = {
    "renown_actions": "renown",
    "wealth": "wealth",
    "discovery_actions": "discovery",
    "underworld_actions": "underworld",
    "power_actions": "power",
    "conflict_actions": "conflict",
    "explore_actions": "explore",
    "personal_actions": "personal",
}

MOTIVATION_THEME_WORDS = {
    "discovery": ("truth", "secret", "ledger", "record", "clue", "murder", "mystery", "investigate"),
    "wealth": ("coin", "debt", "fortune", "trade", "merchant", "profit", "cargo"),
    "renown": ("glory", "honor", "duel", "prove", "respect", "hero"),
    "conflict": ("revenge", "vengeance", "enemy", "rival", "blood", "grudge"),
    "power": ("power", "control", "guildmaster", "captain", "office", "throne"),
    "underworld": ("thief", "smuggl", "fence", "gang", "warrens", "black market"),
    "personal": ("brother", "sister", "love", "marry", "family", "home", "heirloom"),
    "explore": ("belong", "wander", "road", "journey", "new start"),
}


def derive_goal_themes(motivation, goals=None):
    """Tags used to weight goal-related events and rumors."""
    motivation = (motivation or "").lower()
    themes = set()
    for goal in goals or []:
        if goal.get("complete"):
            continue
        theme = TRACK_TO_THEME.get(goal.get("track", ""))
        if theme:
            themes.add(theme)
    for theme, words in MOTIVATION_THEME_WORDS.items():
        if any(w in motivation for w in words):
            themes.add(theme)
    return sorted(themes)


def attach_goal_profile(player):
    """Store themes from typed motivation + structured goals."""
    motivation = player.get("motivation", "")
    if not player.get("goals"):
        player["goals"] = build_player_goals(motivation, player.get("background", "wanderer"))
    player["goal_themes"] = derive_goal_themes(motivation, player.get("goals"))
    return player


def primary_goal_text(player):
    goals = [g for g in (player.get("goals") or []) if not g.get("complete")]
    if goals:
        return goals[0].get("text", "")
    return player.get("motivation", "")[:120]


def _goal_template(t):
    return {
        "id": t["id"],
        "text": t["text"],
        "hint": t["hint"],
        "target": t["target"],
        "track": t["track"],
        "progress": 0,
        "complete": False,
    }


def build_player_goals(motivation, background_key):
    goals = []
    motivation = motivation or ""

    for pattern, template in MOTIVATION_PATTERNS:
        if pattern.search(motivation):
            goals.append(_goal_template(template))
            break

    bg = BACKGROUND_GOALS.get(background_key)
    if bg and not any(g["id"] == bg["id"] for g in goals):
        goals.append(_goal_template(bg))
    elif not goals and bg:
        goals.append(_goal_template(bg))

    if not goals:
        goals.append(_goal_template({
            "id": "survive_and_thrive",
            "text": "Survive and find your footing in a strange city.",
            "hint": "Explore, talk to people, follow tension in each district.",
            "target": 5,
            "track": "explore_actions",
        }))

    return goals[:2]


def _bump(trackers, key, amount=1):
    trackers[key] = trackers.get(key, 0) + amount


def update_player_goals(player, kind, action_ctx=None, world=None):
    """Advance goal progress after a player turn."""
    goals = player.get("goals") or []
    if not goals:
        return []

    trackers = player.setdefault("goal_trackers", {})
    action_ctx = action_ctx or {}
    completed = []

    if kind in ("explore", "travel", "observe"):
        _bump(trackers, "explore_actions")
    if kind in ("talk", "personal_talk", "ask_name", "find", "show_respect", "investigate", "ask_about"):
        _bump(trackers, "discovery_actions")
    if kind in ("talk", "personal_talk", "find", "ask_about"):
        _bump(trackers, "personal_actions")
    if kind in ("attack", "threaten") or (action_ctx.get("skill_check") or {}).get("success"):
        if kind in ("attack", "threaten", "show_respect", "hunt"):
            _bump(trackers, "renown_actions")
            _bump(trackers, "power_actions")
    if kind == "hunt":
        _bump(trackers, "discovery_actions")
    if kind in ("steal",):
        _bump(trackers, "underworld_actions")
    if kind in ("help", "give"):
        _bump(trackers, "discovery_actions")
        _bump(trackers, "explore_actions")
    if kind == "insult":
        _bump(trackers, "conflict_actions")
    if kind == "trade":
        _bump(trackers, "power_actions")

    trackers["wealth"] = player.get("wealth", 0)

    for goal in goals:
        if goal.get("complete"):
            continue
        track = goal.get("track", "")
        progress = trackers.get(track, 0)
        goal["progress"] = progress
        if progress >= goal.get("target", 1):
            goal["complete"] = True
            completed.append(goal["id"])
            player.setdefault("story_flags", {})[f"goal_{goal['id']}"] = True

    player["goals"] = goals
    return completed


def active_goal_hint(player, area_storyline=None):
    """One-line hint for narrator / status."""
    goals = [g for g in (player.get("goals") or []) if not g.get("complete")]
    if not goals:
        return "You have done what you set out to do — now choose what comes next."

    primary = goals[0]
    prog = primary.get("progress", 0)
    target = primary.get("target", 1)
    hint = primary.get("hint", "")
    line = f"Your aim: {primary.get('text', 'Survive')} ({prog}/{target}). {hint}"
    if area_storyline and area_storyline.get("current"):
        line += f" Here: {area_storyline['current'][:90]}."
    return line
