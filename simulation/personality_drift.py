"""
Personality drift — traits shift slowly from lived experience.
"""

DRIFT_CAP = 8


def drift_trait(npc, trait, delta):
    traits = npc.setdefault("traits", {})
    base = traits.get(trait, 50)
    traits[trait] = max(0, min(100, int(base + delta)))


def drift_from_beat(npc, kind, *, success=True):
    """Small trait nudges after significant interaction with player."""
    if kind == "attack":
        drift_trait(npc, "aggression", 1 if success else 0)
        drift_trait(npc, "paranoia", 1)
    elif kind in ("help", "give"):
        if success:
            drift_trait(npc, "kindness", 1)
            drift_trait(npc, "generosity", 1)
    elif kind in ("threaten", "blackmail"):
        drift_trait(npc, "paranoia", 1)
        drift_trait(npc, "caution", 1)
    elif kind == "confess":
        drift_trait(npc, "honesty", 1)
    elif kind in ("accuse", "insult") and not success:
        drift_trait(npc, "pride", 1)


def drift_from_survival(npc):
    """Coward survives violence → more fearful; merchant gains wealth → greed."""
    traits = npc.get("traits", {})
    if traits.get("courage", 50) < 35 and npc.get("last_action") == "hide":
        drift_trait(npc, "paranoia", 1)
    wealth = npc.get("wealth", 0)
    if wealth > 400 and npc.get("role") == "merchant":
        drift_trait(npc, "greed", 1)
