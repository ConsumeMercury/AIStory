"""
Goal-driven events — the player's typed motivation pulls related beats toward them.
"""

import random

from storage import load, save
from simulation.player_goals import derive_goal_themes, primary_goal_text
from simulation.scene_events import BASE_SCENE_EVENTS, scene_event_chance

RUMOR_FILE = "rumors/rumors.json"

GOAL_SCENE_EVENTS = [
    {
        "id": "goal_whisper_truth",
        "themes": {"discovery"},
        "text": "Someone lowers their voice about a sealed record or a name that should stay buried.",
        "check": ("empathy", 10),
        "success": "You catch the name — it connects to what you came to learn.",
        "fail": "The whisper stops when they notice you listening.",
        "goal_note": "This overheard thread should echo the protagonist's search for truth.",
    },
    {
        "id": "goal_dropped_page",
        "themes": {"discovery"},
        "text": "A folded scrap falls from a satchel — half a ledger line, a date, a signature.",
        "check": ("appraisal", 11),
        "success": "You read enough to know it matters before returning it — or keeping it.",
        "fail": "The owner snatches it back; you only saw fragments.",
        "goal_note": "Treat as a clue toward buried truth, not random litter.",
    },
    {
        "id": "goal_debt_chance",
        "themes": {"wealth"},
        "text": "A merchant curses short payment — someone else owes more than they can cover.",
        "check": ("haggling", 11),
        "success": "You see an angle: profit, leverage, or a deal no one else spotted.",
        "fail": "The moment passes; coin stays in other hands.",
        "goal_note": "Frame as a money-making opportunity aligned with building fortune.",
    },
    {
        "id": "goal_duel_notice",
        "themes": {"renown"},
        "text": "Word spreads of a public test — a fight, a challenge, or a deed that earns a name.",
        "check": ("persuasion", 10),
        "success": "You learn when and where — and who would notice if you showed.",
        "fail": "Details stay vague; the crowd moves on.",
        "goal_note": "Offer a path toward renown without resolving it in one beat.",
    },
    {
        "id": "goal_grudge_name",
        "themes": {"conflict"},
        "text": "Two people speak a name with hatred — old debt, old blood.",
        "check": ("empathy", 11),
        "success": "You learn who wronged whom — and who might still be alive.",
        "fail": "They see you listening and go silent.",
        "goal_note": "Tie to settling scores — a lead, not a finished revenge.",
    },
    {
        "id": "goal_gate_blocked",
        "themes": {"power"},
        "text": "Petitions stall at a guarded door — someone with authority holds the line.",
        "check": ("persuasion", 12),
        "success": "You learn what opens the door: favor, fear, or a name.",
        "fail": "You are waved away with the rest.",
        "goal_note": "Hint at gaining influence; the player must act to proceed.",
    },
    {
        "id": "goal_underworld_token",
        "themes": {"underworld"},
        "text": "A marked coin or chipped bone passes hand to hand — a sign only insiders know.",
        "check": ("deception", 11),
        "success": "You recognize the signal — or someone thinks you should.",
        "fail": "It vanishes before you can follow.",
        "goal_note": "A contact or trail into the city's underside.",
    },
    {
        "id": "goal_missing_person",
        "themes": {"personal"},
        "text": "Someone asks passersby about a face — a brother, a sister, someone gone.",
        "check": ("empathy", 10),
        "success": "The description stirs something — close to your own reason for being here.",
        "fail": "They move on before you can speak.",
        "goal_note": "Mirror the protagonist's personal stake without solving it.",
    },
    {
        "id": "goal_heirloom_rumor",
        "themes": {"personal", "wealth"},
        "text": "Talk of a stolen ring, ledger, or blade that someone wants back badly.",
        "check": ("appraisal", 10),
        "success": "You hear where it was last seen — or who took it.",
        "fail": "The story contradicts itself; truth stays muddy.",
        "goal_note": "Personal stakes — recovery, family, or debt.",
    },
    {
        "id": "goal_stranger_recognizes",
        "themes": {"renown", "conflict", "personal"},
        "text": "A stranger studies you as if matching you to a story they were told.",
        "check": ("empathy", 11),
        "success": "You learn what they think you did — or what they need from you.",
        "fail": "They look away; the moment slips.",
        "goal_note": "Connect to why the protagonist is here — fame, guilt, or kin.",
    },
    {
        "id": "goal_district_lead",
        "themes": {"explore"},
        "text": "A local points toward trouble in the next street — not your business, unless you make it so.",
        "check": ("survival", 9),
        "success": "You understand the lay of the place — where to start belonging.",
        "fail": "Directions blur; you are still an outsider.",
        "goal_note": "Open a thread in this district aligned with finding a place or purpose.",
    },
]

GOAL_RUMOR_TEMPLATES = {
    "discovery": [
        "They say a stranger is asking questions — the kind that get doors closed.",
        "Word is someone wants the old records opened, and clerks are nervous.",
    ],
    "wealth": [
        "Merchants whisper that an outsider is looking for coin and opportunity.",
        "Someone new is sniffing around deals that don't belong to tourists.",
    ],
    "renown": [
        "People talk about a newcomer who might take a public challenge.",
        "Guards mention a name they do not know yet — but might soon.",
    ],
    "conflict": [
        "Rumor says someone new carries a grudge like a blade under their coat.",
        "Old enemies are watching who asks about past wrongs.",
    ],
    "power": [
        "Someone without ties is being noticed by people who grant favors.",
        "Word in the garrison: an outsider wants access they haven't earned.",
    ],
    "underworld": [
        "Fence-runners say a new face is learning the signs.",
        "The warrens know when someone is looking for work that isn't legal.",
    ],
    "personal": [
        "A traveler asks after family — kin, lost, or left behind.",
        "Someone is searching for a person who may not want to be found.",
    ],
    "explore": [
        "A wanderer keeps turning up where local trouble gathers.",
        "They say the newcomer hasn't picked a side yet — which makes everyone nervous.",
    ],
}


def _event_pool(player):
    themes = set(player.get("goal_themes") or derive_goal_themes(
        player.get("motivation", ""), player.get("goals"),
    ))
    pool = list(BASE_SCENE_EVENTS)
    weights = [1.0] * len(pool)
    for ev in GOAL_SCENE_EVENTS:
        pool.append(ev)
        overlap = themes & set(ev.get("themes") or [])
        weights.append(4.0 if overlap else 0.35)
    return pool, weights, themes


def pick_goal_scene_event(player, action_kind, area=None, force=False):
    """Weighted scene event — goal-themed beats fire more often."""
    themes = set(player.get("goal_themes") or [])
    chance = scene_event_chance(action_kind, area)
    if themes:
        chance = min(0.92, chance + 0.14)
    if not force and random.random() > chance:
        return None

    pool, weights, themes = _event_pool(player)
    ev = random.choices(pool, weights=weights, k=1)[0]
    out = dict(ev)
    if out.get("goal_note") and themes:
        aim = primary_goal_text(player)
        if aim:
            out["goal_note"] = f"{out['goal_note']} Protagonist's aim: {aim[:90]}."
    return out


def goal_narrator_note(player):
    """Short immersion line when a goal-tied beat is active."""
    themes = player.get("goal_themes") or []
    if not themes:
        return ""
    aim = primary_goal_text(player)
    if not aim:
        return ""
    return (
        f"GOAL PRESSURE (weave lightly — not a lecture): "
        f"something related to \"{aim[:80]}\" may surface this beat."
    )


def maybe_goal_rumor(player, tick=None):
    """Background sim: occasional rumors echoing the player's motivation."""
    themes = player.get("goal_themes") or derive_goal_themes(
        player.get("motivation", ""), player.get("goals"),
    )
    if not themes or random.random() > 0.07:
        return False

    theme = random.choice(themes)
    templates = GOAL_RUMOR_TEMPLATES.get(theme) or GOAL_RUMOR_TEMPLATES.get("explore", [])
    if not templates:
        return False

    text = random.choice(templates)
    motivation = (player.get("motivation") or "").strip()
    if motivation and len(motivation) > 15 and random.random() < 0.35:
        text = f"{text} ({motivation[:70]}…)"

    rumors = load(RUMOR_FILE, [])
    rumors.append({
        "source_event_id": f"goal_{tick or 0}",
        "text": text,
        "interpretation": {
            "discovery": "mysterious",
            "wealth": "suspicious",
            "renown": "heroic",
            "conflict": "dangerous",
            "power": "suspicious",
            "underworld": "suspicious",
            "personal": "mysterious",
            "explore": "mysterious",
        }.get(theme, "mysterious"),
        "spread": random.randint(10, 28),
        "area_id": player.get("area"),
        "goal_theme": theme,
    })
    save(RUMOR_FILE, rumors[-200:])
    return True
