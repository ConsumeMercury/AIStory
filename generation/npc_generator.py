"""
Assemble a full, unique NPC with correlated age, role, physique, background,
persona, skills, stats, and behaviour profile.
"""

import random

from generation.id_generator import generate_id
from generation.name_generator import generate_name
from generation.trait_generator import generate_traits, dominant_traits
from generation.skill_generator import generate_npc_skills, ROLE_SKILLS
from generation.stats_generator import generate_stats
from generation.descriptor_generator import generate_physique, lock_pronouns
from generation.background_generator import generate_background
from generation.persona_generator import generate_persona
from simulation.item_engine import roll_npc_inventory_item

OCCUPATIONS = list(ROLE_SKILLS.keys())

_ROLE_AGE = {
    "scholar": (22, 65), "scribe": (20, 60), "priest": (25, 70),
    "soldier": (19, 50), "mercenary": (20, 55), "guard": (21, 58),
    "merchant": (25, 68), "innkeeper": (28, 70), "blacksmith": (22, 62),
    "herbalist": (24, 68), "apothecary": (26, 65), "hunter": (18, 55),
    "farmer": (20, 70), "sailor": (18, 58), "thief": (17, 45),
}


def _derive_goals(traits, background):
    goals = []
    if traits.get("greed", 0) > 70:
        goals.append("accumulate wealth")
    if traits.get("ambition", 0) > 72:
        goals.append("gain power")
    if traits.get("kindness", 0) > 72 and traits.get("generosity", 0) > 60:
        goals.append("help others")
    if traits.get("vindictiveness", 0) > 72:
        goals.append("settle an old score")
    if traits.get("curiosity", 0) > 75:
        goals.append("uncover a secret")
    if background.get("hope"):
        goals.append(background["hope"])
    return list(dict.fromkeys(goals)) or ["get through the week"]


def _derive_fears(traits, background):
    fears = []
    if traits.get("paranoia", 0) > 65:
        fears.extend(["being watched", "betrayal"])
    if traits.get("courage", 50) < 30:
        fears.extend(["violence", "ruin"])
    if traits.get("pride", 0) > 70:
        fears.append("public humiliation")
    if "betrayed" in background.get("formative_event", ""):
        fears.append("trusting the wrong person again")
    return fears or ["an ordinary, forgotten death"]


def _behavior_profile(traits):
    """Unique action biases for simulation — normalized weights, not identical NPCs."""
    t = traits
    return {
        "social": t.get("gregariousness", 50) + t.get("humor", 50) * 0.5,
        "caution": t.get("paranoia", 50) + (100 - t.get("courage", 50)) * 0.4,
        "work": t.get("discipline", 50) + t.get("ambition", 50) * 0.3,
        "risk": t.get("courage", 50) + t.get("impulsiveness", 50) * 0.5,
        "kindness": t.get("kindness", 50) + t.get("generosity", 50) * 0.4,
    }


def generate_npc(npc_id, locations=None):
    gender = random.choice(["male", "female"])
    role = random.choice(OCCUPATIONS)
    lo, hi = _ROLE_AGE.get(role, (17, 68))
    age = random.randint(lo, hi)
    traits = generate_traits()
    background = generate_background(role, traits)

    npc = {
        "id": npc_id,
        "name": generate_name(),
        "gender": gender,
        "pronouns": lock_pronouns(gender),
        "age": age,
        "role": role,
        "occupation": role,
        "location": random.choice(locations) if locations else None,

        "physique": generate_physique(age, role=role, gender=gender),
        "background": background,
        "persona": generate_persona(traits, role=role),
        "traits": traits,
        "skills": generate_npc_skills(role),
        "stats": generate_stats(age, role, traits),
        "level": 1,
        "xp": 0,

        "goals": _derive_goals(traits, background),
        "fears": _derive_fears(traits, background),
        "goals_progress": {},
        "behavior_profile": _behavior_profile(traits),

        "relationships": {},
        "inventory": [
            roll_npc_inventory_item(role)
            for _ in range(random.randint(0, 2))
            if random.random() < 0.7
        ],
        "wealth": random.randint(0, 120),
        "status": "alive",
        "last_action": None,
        "known_by_player": False,
        "culture": None,
        "surname": None,
        "family": {"surname": None, "relations": {}},
        "institution": None,
    }
    return npc


def generate_population(count, locations):
    if not locations:
        locations = [None]
    npcs = {}
    for _ in range(count):
        npc_id = generate_id("npc")
        npcs[npc_id] = generate_npc(npc_id, locations)
    return npcs
