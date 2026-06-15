"""
A large personality model. 20 traits, each 0-100.

These are NOT shown to the player as words. They (a) bias what an NPC
chooses to do in the simulation and (b) are translated into *behavioural
cues* for the narrator so personality is shown through action, never named.

Generation is correlated, not uniform: we roll a few "anchor" tendencies
so NPCs come out as coherent people (a cruel, proud, vain schemer) rather
than random noise across 20 axes.
"""

import random

TRAITS = [
    "courage", "aggression", "kindness", "greed", "ambition", "loyalty",
    "honesty", "pride", "curiosity", "patience", "temper", "discipline",
    "humor", "vanity", "paranoia", "generosity", "sentimentality",
    "vindictiveness", "piety", "wit",
    # expanded axes
    "impulsiveness", "secretiveness", "superstition", "gregariousness", "ruthlessness",
]

# Loose archetypes pull a handful of traits high/low; everything else is
# rolled around a personal midpoint so each NPC is internally consistent.
_ARCHETYPES = {
    "schemer":    {"ambition": 80, "wit": 75, "honesty": 25, "patience": 70, "paranoia": 60},
    "brute":      {"aggression": 85, "temper": 80, "courage": 70, "discipline": 30, "wit": 30},
    "saint":      {"kindness": 85, "generosity": 80, "honesty": 75, "greed": 15, "piety": 70},
    "merchant":   {"greed": 75, "wit": 65, "patience": 60, "vanity": 55, "honesty": 40},
    "zealot":     {"piety": 90, "discipline": 75, "patience": 40, "vindictiveness": 60, "humor": 20},
    "rogue":      {"wit": 75, "courage": 60, "honesty": 30, "loyalty": 35, "humor": 65},
    "stoic":      {"discipline": 85, "patience": 85, "temper": 20, "pride": 60, "sentimentality": 25},
    "coward":     {"courage": 15, "paranoia": 75, "aggression": 25, "loyalty": 40},
    "romantic":   {"sentimentality": 85, "kindness": 65, "vanity": 60, "courage": 55, "wit": 60},
    "tyrant":     {"pride": 90, "vindictiveness": 80, "ambition": 80, "kindness": 15, "temper": 65},
    "spy":        {"secretiveness": 90, "wit": 75, "paranoia": 70, "honesty": 20, "discipline": 70},
    "gambler":    {"impulsiveness": 85, "courage": 65, "greed": 60, "discipline": 20, "humor": 60},
    "fanatic":    {"superstition": 85, "piety": 80, "ruthlessness": 70, "patience": 35},
    "charmer":    {"gregariousness": 90, "wit": 75, "vanity": 65, "honesty": 35, "humor": 75},
    "butcher":    {"ruthlessness": 90, "aggression": 80, "kindness": 10, "sentimentality": 10, "temper": 55},
}


def _clamp(v):
    return max(0, min(100, int(round(v))))


def generate_traits():
    personal_mid = random.randint(35, 65)
    traits = {t: _clamp(random.gauss(personal_mid, 18)) for t in TRAITS}

    archetype = random.choice(list(_ARCHETYPES.keys()))
    for trait, target in _ARCHETYPES[archetype].items():
        # nudge toward the archetype anchor, not a hard set, so two
        # "schemers" still differ
        traits[trait] = _clamp((traits[trait] + target * 2) / 3)

    traits["_archetype"] = archetype  # kept for flavour / debugging
    return traits


def dominant_traits(traits, n=3):
    """Top N real traits (ignores the private _archetype tag)."""
    real = {k: v for k, v in traits.items() if not k.startswith("_")}
    return sorted(real, key=real.get, reverse=True)[:n]
