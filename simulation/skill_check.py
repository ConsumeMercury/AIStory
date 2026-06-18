"""
Skill checks for environment interaction, social tests, and risky actions.

Returns success/failure with margin so callers apply consequences and feed
clear results to the narrator.
"""

import random

from simulation.progression_engine import skill_level

# skill -> default attribute tie-in
_SKILL_ATTR = {
    "lockpicking": "agility", "survival": "endurance", "navigation": "wit",
    "persuasion": "presence", "deception": "wit", "intimidation": "presence",
    "empathy": "presence", "appraisal": "wit", "haggling": "presence",
    "arcana": "wit", "medicine": "wit", "brawling": "strength",
    "swordsmanship": "strength", "stealth": "agility",
}

# action kind -> (skill, base_dc)
ACTION_DC = {
    "examine": ("appraisal", 11),
    "search": ("appraisal", 12),
    "observe": ("empathy", 10),
    "explore": ("survival", 10),
    "steal": ("lockpicking", 15),
    "trade": ("haggling", 12),
    "help": ("medicine", 13),
    "threaten": ("intimidation", 13),
    "insult": ("intimidation", 10),
    "talk": ("persuasion", 11),
    "personal_talk": ("empathy", 12),
    "give": ("persuasion", 10),
    "show_respect": ("persuasion", 10),
    "find": ("persuasion", 10),
    "investigate": ("appraisal", 13),
    "ask_about": ("empathy", 12),
    "accuse": ("intimidation", 14),
    "blackmail": ("deception", 14),
    "deceive": ("deception", 13),
    "wait": ("survival", 10),
    "hunt": ("survival", 12),
    "guild": ("persuasion", 11),
    "general": ("survival", 12),
}

FAIL_CONSEQUENCES = {
    "steal": [
        "spotted — suspicion rises; you may be searched or followed",
        "hand caught — a scuffle, lost coin, or public shame",
        "alarm raised — guards alerted to the district",
    ],
    "examine": [
        "miss the important detail — wrong conclusion",
        "trigger a hidden mechanism or noise — attention drawn",
        "damage the object — evidence of tampering",
    ],
    "observe": [
        "misread the situation — false assumption",
        "noticed watching — target becomes guarded",
        "nothing learned — time wasted, patience thin",
    ],
    "trade": [
        "bad deal — overcharged or cheated",
        "merchant refuses — reputation ding locally",
        "haggling fails — doors closed to you here",
    ],
    "help": [
        "botched aid — wound worsens or trust lost",
        "help rejected — pride or fear turns them cold",
        "complication — your involvement makes it worse",
    ],
    "threaten": [
        "backfire — they call your bluff",
        "witness intervenes — odds shift against you",
        "grudge seeded — they'll remember this",
    ],
    "talk": [
        "wrong words — offense taken silently",
        "brushed off — no traction, awkward exit",
        "misunderstood — rumour starts about you",
    ],
    "general": [
        "attempt fails — cost in time, stamina, or pride",
        "partial failure — success with a price",
        "environment pushes back — injury or embarrassment",
    ],
}


def _attr_bonus(entity, skill):
    attrs = entity.get("stats", {}).get("attributes", {})
    key = _SKILL_ATTR.get(skill, "wit")
    return attrs.get(key, 10) // 2


def _stress_penalty(entity):
    stats = entity.get("stats", {})
    stress = stats.get("stress", 0)
    max_stress = stats.get("max_stress", 100)
    if max_stress <= 0:
        return 0
    ratio = stress / max_stress
    if ratio > 0.7:
        return -3
    if ratio > 0.45:
        return -1
    return 0


def _equipment_skill_bonus(entity, skill):
    if entity.get("journal") is None:
        return 0
    from simulation.item_engine import equipment_bonuses
    _, skill_mods = equipment_bonuses(entity)
    return skill_mods.get(skill, 0)


def resolve_check(entity, skill, difficulty, modifiers=0, advantage=False, disadvantage=False):
    """
    d20-style check: roll + skill level + attr/2 + modifiers vs DC.
    """
    roll = random.randint(1, 20)
    if advantage:
        roll = max(roll, random.randint(1, 20))
    if disadvantage:
        roll = min(roll, random.randint(1, 20))

    level = skill_level(entity, skill)
    total = (
        roll + level + _attr_bonus(entity, skill) + int(modifiers)
        + _stress_penalty(entity) + _equipment_skill_bonus(entity, skill)
    )
    margin = total - difficulty
    success = margin >= 0

    return {
        "success": success,
        "margin": margin,
        "roll": roll,
        "total": total,
        "difficulty": difficulty,
        "skill": skill,
        "critical_success": roll == 20 and success,
        "critical_fail": roll == 1,
    }


def run_action_check(player, action_kind, world=None, area=None, intents=None):
    """Run a check for an interpreted action; adjust DC by location/world."""
    if action_kind not in ACTION_DC:
        return None

    skill, base_dc = ACTION_DC[action_kind]
    dc = base_dc
    intents = intents or []

    if world:
        if world.get("weather") in ("Storm", "Fog", "Snow"):
            dc += 1
        if world.get("time_of_day") in ("deep night", "night"):
            if action_kind in ("observe", "steal"):
                dc += 1 if action_kind == "steal" else -1

    if area:
        dc += area.get("check_modifier", 0)

    mods = 0
    if "careful" in intents:
        mods += 2
        dc += 1
    if "urgent" in intents:
        mods -= 1
        dc -= 1

    result = resolve_check(player, skill, dc, modifiers=mods,
                           disadvantage="urgent" in intents and "careful" not in intents)
    result["consequence"] = None
    if not result["success"]:
        pool = FAIL_CONSEQUENCES.get(action_kind, FAIL_CONSEQUENCES["general"])
        result["consequence"] = random.choice(pool)
        if result["critical_fail"]:
            result["consequence"] += " (critical failure — worse than usual)"
    elif result["critical_success"]:
        result["consequence"] = "exceptional success — extra detail, advantage, or respect earned"
    result["skill"] = skill
    result["kind"] = action_kind
    return result


def apply_check_costs(player, result, action_kind):
    """Mechanical fallout from failed or costly checks."""
    if not result:
        return []
    effects = []
    stats = player.setdefault("stats", {})
    if not result["success"]:
        stats["stamina"] = max(0, stats.get("stamina", 0) - random.randint(2, 6))
        stats["stress"] = min(stats.get("max_stress", 100),
                              stats.get("stress", 0) + random.randint(3, 8))
        effects.append("stamina_loss")
        effects.append("stress_up")
        if result["critical_fail"] and action_kind == "steal":
            player["wealth"] = max(0, player.get("wealth", 0) - random.randint(5, 20))
            effects.append("fine_or_loss")
        if result["critical_fail"] and action_kind in ("examine", "general"):
            stats["health"] = max(1, stats.get("health", 1) - random.randint(1, 4))
            effects.append("minor_injury")
    elif result["margin"] >= 5:
        stats["stamina"] = min(stats.get("max_stamina", 30),
                               stats.get("stamina", 0) + 2)
    return effects
