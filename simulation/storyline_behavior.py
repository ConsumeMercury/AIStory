"""
Storylines pull NPCs — district plots change where people go and what they do.
"""

import random

# theme -> role-specific behavior when that district plot is active
THEMES = {
    "smuggling": {
        "keywords": ("smuggl", "cargo", "pier", "quay", "harbour", "dock", "customs"),
        "narrator": "The harbour plot dominates — smuggling, fear, and knives after dark.",
        "roles": {
            "merchant": {"hide_mult": 1.4, "avoid_suffix": "docks"},
            "guard": {"pull_suffix": "docks", "fight_mult": 1.5, "plan_mult": 1.4},
            "soldier": {"pull_suffix": "docks", "fight_mult": 1.3},
            "thief": {"pull_suffix": "docks", "plan_mult": 1.7, "hide_mult": 0.8},
            "sailor": {"pull_suffix": "docks", "socialise_mult": 0.7},
            "priest": {"help_mult": 1.3, "pull_suffix": "docks"},
            "scholar": {"study_mult": 1.2},
        },
    },
    "crime": {
        "keywords": ("crime", "gang", "knife", "beaten", "informant", "law", "warrens"),
        "narrator": "Street crime is the story — people watch doors and speak in half-sentences.",
        "roles": {
            "merchant": {"hide_mult": 1.3, "trade_mult": 0.85},
            "guard": {"fight_mult": 1.4, "plan_mult": 1.3},
            "thief": {"plan_mult": 1.5, "hide_mult": 1.2},
            "priest": {"help_mult": 1.4, "socialise_mult": 1.2},
            "innkeeper": {"socialise_mult": 0.8},
        },
    },
    "heresy": {
        "keywords": ("heretic", "faith", "preach", "relic", "cleric", "temple", "judgement"),
        "narrator": "Religious tension splits the district — whispers where there used to be prayer.",
        "roles": {
            "priest": {"study_mult": 1.5, "socialise_mult": 1.3, "pull_suffix": "temple_row"},
            "scholar": {"study_mult": 1.4, "pull_suffix": "temple_row"},
            "guard": {"plan_mult": 1.3, "pull_suffix": "temple_row"},
            "merchant": {"hide_mult": 1.2},
        },
    },
    "corruption": {
        "keywords": ("bribe", "coin", "missing", "cheat", "scale", "licence", "merchant"),
        "narrator": "Trust in coin and scales is broken — every deal feels like a test.",
        "roles": {
            "merchant": {"plan_mult": 1.4, "trade_mult": 0.9, "hide_mult": 1.2},
            "guard": {"plan_mult": 1.5, "fight_mult": 1.2},
            "scribe": {"study_mult": 1.3},
            "thief": {"plan_mult": 1.3},
        },
    },
    "nobility": {
        "keywords": ("noble", "duel", "blood", "pedigree", "gathering", "gate", "guard", "salon", "heir"),
        "narrator": "High-quarter intrigue — invitations, duels, and guards who know too much.",
        "roles": {
            "guard": {"pull_suffix": "high_quarter", "fight_mult": 1.3, "plan_mult": 1.2},
            "soldier": {"pull_suffix": "high_quarter", "fight_mult": 1.2},
            "scholar": {"pull_suffix": "high_quarter", "study_mult": 1.3},
            "merchant": {"pull_suffix": "high_quarter", "trade_mult": 1.2},
        },
    },
    "intrigue": {
        "keywords": ("intrigue", "blackmail", "forg", "whisper", "ambassador", "impostor", "cipher", "ledger", "auction"),
        "narrator": "Secrets move faster than coin — every smile hides a ledger entry.",
        "roles": {
            "merchant": {"plan_mult": 1.4, "hide_mult": 1.2, "trade_mult": 0.95},
            "thief": {"plan_mult": 1.5, "hide_mult": 1.3},
            "scholar": {"study_mult": 1.3, "plan_mult": 1.2},
            "guard": {"plan_mult": 1.4},
            "scribe": {"study_mult": 1.4},
        },
    },
    "academic": {
        "keywords": ("examination", "academy", "thesis", "tutor", "student", "forbidden text", "plagiar", "curriculum"),
        "narrator": "The academy plot tightens — careers, secrets, and ink that won't wash out.",
        "roles": {
            "scholar": {"study_mult": 1.6, "pull_suffix": "high_quarter"},
            "student": {"study_mult": 1.4, "socialise_mult": 1.2},
            "guard": {"plan_mult": 1.2, "pull_suffix": "high_quarter"},
            "merchant": {"trade_mult": 1.1, "pull_suffix": "market"},
        },
    },
    "hunt": {
        "keywords": ("bounty", "beast", "tracker", "hunt", "warden", "poacher", "stag", "trap", "woods"),
        "narrator": "The lodge's hunt dominates — traps, trophies, and things that shouldn't be tracked.",
        "roles": {
            "hunter": {"plan_mult": 1.5, "fight_mult": 1.3},
            "tracker": {"plan_mult": 1.4, "pull_suffix": "market"},
            "merchant": {"trade_mult": 1.15},
            "guard": {"fight_mult": 1.2},
            "soldier": {"fight_mult": 1.2, "plan_mult": 1.1},
        },
    },
}


def detect_theme(area):
    sl = area.get("storyline") or {}
    explicit = sl.get("theme")
    if explicit and explicit in THEMES:
        return explicit, THEMES[explicit]
    blob = " ".join([
        sl.get("title", ""), sl.get("hook", ""), sl.get("current", ""),
        " ".join(sl.get("stages") or []),
    ]).lower()
    for name, spec in THEMES.items():
        if any(k in blob for k in spec["keywords"]):
            return name, spec
    if area.get("crime", 0) > 55:
        return "crime", THEMES["crime"]
    return None, None


def theme_for_area(area_id, areas):
    area = areas.get(area_id, {})
    if not area or area.get("type") != "district":
        return None, None
    return detect_theme(area)


def _area_with_suffix(city, suffix, areas, fallback):
    target = f"{city}:{suffix}"
    if target in areas:
        return target
    for aid in areas:
        if areas[aid].get("city") == city and aid.endswith(":" + suffix):
            return aid
    return fallback


def apply_storyline_to_npc(npc, areas, tension=30):
    """
    Maybe redirect NPC to storyline hotspot or return action weight multipliers.
    Returns (weight_mults dict, area_override or None).
    """
    area_id = npc.get("area")
    if not area_id:
        return {}, None
    theme_name, spec = theme_for_area(area_id, areas)
    if not spec:
        return {}, None

    city = npc.get("location")
    role = npc.get("role", "merchant")
    role_spec = spec["roles"].get(role, {})
    mults = {}
    for key, val in role_spec.items():
        if key.endswith("_mult"):
            mults[key.replace("_mult", "")] = val

    area_override = None
    if tension >= 25 and random.random() < 0.35:
        pull = role_spec.get("pull_suffix")
        avoid = role_spec.get("avoid_suffix")
        if pull:
            area_override = _area_with_suffix(city, pull, areas, area_id)
        elif avoid and area_id.endswith(":" + avoid) and random.random() < 0.5:
            area_override = _area_with_suffix(city, "market", areas, area_id)

    return mults, area_override


def apply_storyline_weights(weights, mults):
    for action, mult in mults.items():
        if action in weights:
            weights[action] *= mult


def narrator_storyline_block(area_id, areas):
    area = areas.get(area_id, {})
    theme_name, spec = theme_for_area(area_id, areas)
    if not spec:
        return ""
    sl = area.get("storyline") or {}
    return (
        f"DISTRICT STORY ({sl.get('title', 'local plot')}): {spec['narrator']}\n"
        f"Current beat: {sl.get('current', sl.get('hook', ''))[:120]}. "
        f"NPCs should behave as if this plot is real — not background lore."
    )
