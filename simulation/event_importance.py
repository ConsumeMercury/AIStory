"""
Score event importance for retrieval, consolidation, and rumor priority.
"""

import re

_HIGH = frozenset({
    "combat", "death", "murder", "kill", "confess", "accuse", "blackmail",
    "attack", "betrayal", "case", "reveal", "legacy",
})

_MED = frozenset({
    "help", "gift", "trade", "insult", "threat", "investigate", "discover",
    "travel", "institution_event", "storyline_beat",
})

_LOW = frozenset({
    "npc_action", "schedule", "wait", "rest", "ambient",
})


def score_event_importance(event_type, action, *, effects=None, target=None):
    """Return 0–100 importance for memory ranking and consolidation."""
    etype = (event_type or "").lower()
    text = f"{action or ''} {' '.join(str(e) for e in (effects or []))}".lower()

    score = 30
    if etype in ("player_action", "player_interaction"):
        score = 45
    elif etype == "combat":
        score = 88
    elif etype in ("institution_event", "storyline_beat"):
        score = 62
    elif etype in _LOW:
        score = 12
    elif etype in _MED:
        score = 50

    for word in _HIGH:
        if word in text or word in etype:
            score = max(score, 75 if word not in ("attack", "combat") else 85)

    if target and etype in ("player_action", "player_interaction", "combat"):
        score += 8

    if re.search(r"\b(murder|killed|died|confess|accuse|secret|clue|evidence)\b", text):
        score = max(score, 78)

    return max(1, min(100, score))


def infer_story_meaning(event_type, action, *, kind=None, target=None):
    """Short narrative meaning for long-horizon memory (not raw action log)."""
    action = (action or "")[:120]
    kind = (kind or "").lower()
    if kind == "attack" or (event_type or "") == "combat":
        return f"The outsider fought here: {action[:80]}"
    if kind in ("help", "give", "show_respect"):
        return f"The outsider showed goodwill: {action[:80]}"
    if kind in ("accuse", "blackmail", "confess"):
        return f"A confrontation over truth: {action[:80]}"
    if kind in ("investigate", "ask_about", "find", "search"):
        return f"The outsider pursued answers: {action[:80]}"
    if kind in ("insult", "threaten"):
        return f"Tension rose with the outsider: {action[:80]}"
    if (event_type or "") == "storyline_beat":
        return f"The district plot moved: {action[:80]}"
    return ""
