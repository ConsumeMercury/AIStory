"""
Assemble a full, unique NPC:
  identity (locked gender + pronouns), physique, age, role,
  20-trait personality, generated background (origin/wound/secret/mannerism),
  role-weighted skills (with xp/levels), combat stats,
  derived goals/fears (soft, from traits), and bookkeeping fields.
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
from generation.item_generator import generate_item

OCCUPATIONS = list(ROLE_SKILLS.keys())


def _derive_goals(traits):
    """Soft goals from the strongest tendencies. Not forced — many NPCs
    just want to get by."""
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
    return goals or ["get through the week"]


def _derive_fears(traits):
    if traits.get("paranoia", 0) > 65:
        return ["being watched", "betrayal"]
    if traits.get("courage", 50) < 30:
        return ["violence", "ruin"]
    if traits.get("pride", 0) > 70:
        return ["public humiliation"]
    return ["an ordinary, forgotten death"]


def generate_npc(npc_id, locations=None):
    gender = random.choice(["male", "female"])
    age = random.randint(17, 68)
    role = random.choice(OCCUPATIONS)
    traits = generate_traits()

    npc = {
        "id": npc_id,
        "name": generate_name(),
        "gender": gender,
        "pronouns": lock_pronouns(gender),     # LOCKED — narrator must obey
        "age": age,
        "role": role,
        "occupation": role,                    # back-compat alias
        "location": random.choice(locations) if locations else None,

        "physique": generate_physique(age),
        "background": generate_background(role, traits),
        "persona": generate_persona(traits),
        "traits": traits,
        "skills": generate_npc_skills(role),
        "stats": generate_stats(age, role, traits),
        "level": 1,
        "xp": 0,

        "goals": _derive_goals(traits),
        "fears": _derive_fears(traits),
        "goals_progress": {},

        "relationships": {},
        "inventory": [it for _, it in (generate_item() for _ in range(random.randint(0, 2)))],
        "wealth": random.randint(0, 120),
        "status": "alive",
        "last_action": None,
        "known_by_player": False,    # mirror flag; player.json is source of truth
        "culture": None,             # set by family_generator
        "surname": None,
        "family": {"surname": None, "relations": {}},
        "institution": None,         # set by institution_generator
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
