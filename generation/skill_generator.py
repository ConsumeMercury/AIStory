"""
Skills are EARNED and ROLE-DEPENDENT.

Each skill is stored as {"xp": int, "level": int}. Level is derived from
xp (see progression_engine.level_for_xp), so growth is gradual and tracked.
A blacksmith starts competent at smithing and weak at arcana; a scholar the
reverse. NPCs start with a small, role-appropriate spread, not a full sheet.
"""

import random

ALL_SKILLS = [
    "swordsmanship", "archery", "brawling", "knife_fighting",   # combat
    "haggling", "appraisal", "smuggling", "accounting",         # trade
    "persuasion", "deception", "intimidation", "empathy",       # social
    "herbalism", "arcana", "history", "navigation", "medicine", # knowledge
    "blacksmithing", "alchemy", "lockpicking", "survival",      # craft / field
]

ROLE_SKILLS = {
    "merchant":   ["haggling", "appraisal", "accounting", "persuasion"],
    "guard":      ["swordsmanship", "intimidation", "brawling", "survival"],
    "scholar":    ["history", "arcana", "medicine", "appraisal"],
    "thief":      ["lockpicking", "deception", "knife_fighting", "smuggling"],
    "herbalist":  ["herbalism", "alchemy", "medicine", "empathy"],
    "blacksmith": ["blacksmithing", "appraisal", "brawling", "haggling"],
    "innkeeper":  ["persuasion", "empathy", "accounting", "brawling"],
    "soldier":    ["swordsmanship", "archery", "survival", "intimidation"],
    "priest":     ["empathy", "persuasion", "history", "medicine"],
    "farmer":     ["survival", "herbalism", "brawling", "navigation"],
    "sailor":     ["navigation", "brawling", "survival", "smuggling"],
    "mercenary":  ["swordsmanship", "archery", "intimidation", "survival"],
    "apothecary": ["alchemy", "herbalism", "medicine", "appraisal"],
    "scribe":     ["history", "accounting", "deception", "persuasion"],
    "hunter":     ["archery", "survival", "navigation", "knife_fighting"],
}

LEVEL_TITLES = ["untrained", "novice", "apprentice", "journeyman",
                "skilled", "expert", "master"]


def _skill(xp):
    from simulation.progression_engine import level_for_xp
    return {"xp": xp, "level": level_for_xp(xp)}


def generate_npc_skills(role):
    """Role skills start a bit higher; everyone gets a couple of stray skills."""
    skills = {}
    primary = ROLE_SKILLS.get(role, random.sample(ALL_SKILLS, 3))

    for s in primary:
        # role skills: meaningful but not maxed — there is room to grow
        skills[s] = _skill(random.randint(150, 900))

    # a couple of incidental skills from life
    for s in random.sample([x for x in ALL_SKILLS if x not in primary], k=random.randint(1, 2)):
        skills[s] = _skill(random.randint(0, 200))

    return skills
