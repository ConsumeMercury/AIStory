"""
Discrete relationship states and what they unlock — milestones players remember.
"""

THRESHOLDS_POSITIVE = [
    (60, "loyal_ally", "Loyal ally — would risk themselves for you"),
    (45, "trusted_friend", "Trusted friend — shares real talk and favors"),
    (28, "friend", "Friend — warm, willing to help"),
    (12, "acquaintance", "Acquaintance — recognizes you, not close"),
    (0, "stranger", "Stranger — guarded, no bond yet"),
]

THRESHOLDS_NEGATIVE = [
    (-50, "nemesis", "Nemesis — wants you ruined"),
    (-35, "enemy", "Enemy — active hostility"),
    (-20, "hostile", "Hostile — bitter, watching for mistakes"),
    (-8, "suspicious", "Suspicious — distrusts your motives"),
]


def _score(rel):
    if not rel:
        return 0.0
    trust = rel.get("trust", 0)
    respect = rel.get("respect", 0)
    affection = rel.get("affection", 0)
    fear = rel.get("fear", 0)
    resentment = rel.get("resentment", 0)
    fam = rel.get("familiarity", 0)
    positive = (trust * 0.38 + respect * 0.32 + affection * 0.30)
    negative = (resentment * 0.4 + fear * 0.15)
    return positive - negative * 0.6


def relationship_state(rel):
    """Return (state_id, label) for NPC -> player bond."""
    if not rel or rel.get("familiarity", 0) < 6:
        return "stranger", "Stranger — just met"
    score = _score(rel)
    if score >= 0:
        for cutoff, sid, label in THRESHOLDS_POSITIVE:
            if score >= cutoff:
                return sid, label
        return "stranger", "Stranger"
    for cutoff, sid, label in THRESHOLDS_NEGATIVE:
        if score <= cutoff:
            return sid, label
    return "suspicious", "Suspicious"


def unlocks_for_state(state_id):
    """Narrator/mechanical hints per milestone."""
    return {
        "stranger": "Will not share anything sensitive.",
        "acquaintance": "May answer simple questions; no favors.",
        "friend": "Shares rumors and local gossip if asked.",
        "trusted_friend": "Offers discounts on trade; warns of danger.",
        "loyal_ally": "Would lie for you; intervenes if you're threatened.",
        "suspicious": "Answers curtly; watches what you do.",
        "hostile": "Refuses help; may insult or report you.",
        "enemy": "Active opposition — calls guards, spreads malice.",
        "nemesis": "Obsessed with your downfall.",
    }.get(state_id, "")


def format_bond_summary(rel):
    state_id, label = relationship_state(rel)
    unlock = unlocks_for_state(state_id)
    fam = rel.get("familiarity", 0) if rel else 0
    return f"{label} (familiarity {fam:.0f}). {unlock}"
