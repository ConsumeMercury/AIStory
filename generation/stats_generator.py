"""
Physical + mental attributes and derived combat stats.

Six core attributes (1–20) drive health, attack, defense, speed, and stamina.
Mental fields (stress, focus) support narration and future systems.
Existing combat fields are preserved for combat_engine compatibility.
"""

import random

_MARTIAL_ROLES = {
    "soldier": 1.3, "mercenary": 1.35, "guard": 1.25, "hunter": 1.15,
    "sailor": 1.05, "blacksmith": 1.1, "farmer": 1.0, "thief": 1.05,
    "merchant": 0.8, "scholar": 0.7, "scribe": 0.7, "priest": 0.8,
    "herbalist": 0.8, "apothecary": 0.75, "innkeeper": 0.95,
}


def _age_factor(age):
    if age <= 28:
        return 1.0
    if age <= 45:
        return 0.95
    return max(0.55, 1.0 - (age - 28) * 0.015)


def _clamp_attr(v):
    return max(1, min(20, int(round(v))))


def _roll_attr(base, spread=3):
    return _clamp_attr(base + random.randint(-spread, spread))


def generate_attributes(age, role, traits):
    martial = _MARTIAL_ROLES.get(role, 1.0)
    af = _age_factor(age)

    courage = traits.get("courage", 50)
    aggression = traits.get("aggression", 50)
    discipline = traits.get("discipline", 50)
    wit = traits.get("wit", 50)
    patience = traits.get("patience", 50)
    gregarious = traits.get("gregariousness", 50)

    strength = _roll_attr(8 + martial * 4 * af + aggression / 40)
    agility = _roll_attr(7 + martial * 3 * af + (100 - patience) / 50)
    endurance = _roll_attr(8 + martial * 3.5 * af + courage / 45)
    wit_attr = _roll_attr(6 + wit / 12 + (4 if role in ("scholar", "scribe", "apothecary") else 0))
    will = _roll_attr(7 + discipline / 14 + courage / 50)
    presence = _roll_attr(6 + gregarious / 14 + wit / 40)

    return {
        "strength": strength,
        "agility": agility,
        "endurance": endurance,
        "wit": wit_attr,
        "will": will,
        "presence": presence,
    }


def derive_combat_stats(attributes, age, role, traits):
    martial = _MARTIAL_ROLES.get(role, 1.0)
    af = _age_factor(age)
    s, a, e = attributes["strength"], attributes["agility"], attributes["endurance"]
    aggression = traits.get("aggression", 50)
    discipline = traits.get("discipline", 50)
    courage = traits.get("courage", 50)

    max_health = int(40 + e * 3.2 + s * 1.2 + 15 * martial * af + random.randint(-6, 6))
    attack = int(s * 0.55 + a * 0.35 + martial * 2 * af * (0.75 + aggression / 300) + random.randint(-1, 2))
    defense = int(e * 0.4 + attributes["will"] * 0.25 + martial * 1.5 * af * (0.75 + discipline / 300))
    speed = int(a * 0.6 + attributes["wit"] * 0.15 + 4 * af * (0.8 + courage / 250))
    max_stamina = int(25 + e * 2.2 + s * 0.8 + 12 * martial * af + random.randint(-4, 4))

    return {
        "health": max_health,
        "max_health": max_health,
        "attack": max(1, attack),
        "defense": max(0, defense),
        "speed": max(1, speed),
        "stamina": max_stamina,
        "max_stamina": max_stamina,
        "stress": random.randint(5, 35),
        "max_stress": 100,
        "focus": _clamp_attr(attributes["wit"] + attributes["will"] // 2),
    }


def generate_stats(age, role, traits):
    attributes = generate_attributes(age, role, traits)
    stats = derive_combat_stats(attributes, age, role, traits)
    stats["attributes"] = attributes
    return stats
