"""
Earned progression. Skills gain XP from use and level up gradually;
levels never jump. Also used to award the player XP for actions.

Curve: each level needs more XP than the last (triangular-ish), so early
levels come quickly and mastery is a long grind — the "slow burn" the
design calls for.
"""

# xp thresholds for levels 0..6  (untrained .. master)
_THRESHOLDS = [0, 100, 300, 700, 1500, 3000, 6000]


def level_for_xp(xp):
    lvl = 0
    for i, t in enumerate(_THRESHOLDS):
        if xp >= t:
            lvl = i
    return lvl


def add_skill_xp(entity, skill, amount):
    """
    Add XP to a skill on any entity (npc or player) that stores
    skills as {name: {"xp":..., "level":...}}. Returns True if the
    skill leveled up (callers may want to log/narrate that).
    """
    skills = entity.setdefault("skills", {})
    node = skills.get(skill)
    if node is None:
        node = {"xp": 0, "level": 0}
        skills[skill] = node
    before = node["level"]
    node["xp"] += int(amount)
    node["level"] = level_for_xp(node["xp"])
    return node["level"] > before


def skill_level(entity, skill):
    node = entity.get("skills", {}).get(skill)
    return node["level"] if node else 0


# which skill an NPC action trains, and how much (kept small => slow burn)
ACTION_SKILL_XP = {
    "trade":     ("haggling", 12),
    "fight":     ("brawling", 18),
    "hunt":      ("archery", 16),
    "help":      ("empathy", 10),
    "plan":      ("persuasion", 8),
    "study":     ("history", 14),
    "craft":     ("blacksmithing", 14),
    "travel":    ("navigation", 10),
}


def train_from_action(entity, action):
    mapping = ACTION_SKILL_XP.get(action)
    if not mapping:
        return False
    skill, amt = mapping
    return add_skill_xp(entity, skill, amt)
