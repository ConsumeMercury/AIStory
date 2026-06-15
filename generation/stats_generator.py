"""
Combat / physical stats shared by NPCs, the player, and monsters so the
combat engine can treat them uniformly.

Stats are derived from age, role, and a couple of traits, then jittered,
so a young mercenary is genuinely tougher than an old scribe — but not
deterministically identical to the next mercenary.
"""

import random

# rough role multipliers for martial capability
_MARTIAL_ROLES = {
    "soldier": 1.3, "mercenary": 1.35, "guard": 1.25, "hunter": 1.15,
    "sailor": 1.05, "blacksmith": 1.1, "farmer": 1.0, "thief": 1.05,
    "merchant": 0.8, "scholar": 0.7, "scribe": 0.7, "priest": 0.8,
    "herbalist": 0.8, "apothecary": 0.75, "innkeeper": 0.95,
}


def _age_factor(age):
    # peak in late 20s, decline after
    if age <= 28:
        return 1.0
    return max(0.6, 1.0 - (age - 28) * 0.012)


def generate_stats(age, role, traits):
    martial = _MARTIAL_ROLES.get(role, 1.0)
    af = _age_factor(age)
    courage = traits.get("courage", 50)
    aggression = traits.get("aggression", 50)
    discipline = traits.get("discipline", 50)

    max_health = int(60 + 40 * martial * af + random.randint(-8, 8))
    attack = int((8 + 10 * martial * af) * (0.8 + aggression / 250) + random.randint(-2, 2))
    defense = int((6 + 8 * martial * af) * (0.8 + discipline / 250) + random.randint(-2, 2))
    speed = int((8 + 6 * af) * (0.8 + courage / 250) + random.randint(-2, 2))
    max_stamina = int(40 + 30 * martial * af + random.randint(-5, 5))

    return {
        "health": max_health, "max_health": max_health,
        "attack": max(1, attack), "defense": max(0, defense),
        "speed": max(1, speed),
        "stamina": max_stamina, "max_stamina": max_stamina,
    }
