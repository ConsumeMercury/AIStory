"""
NPC-to-NPC bonds and tensions — drama that exists before the player arrives.
"""

import random

from storage import load, save
from simulation.relationship_engine import apply_interaction

REL_FILE = "characters/relationships.json"


def seed_drama(npcs, relationships=None):
    """
    Seed resentments, debts, and attractions between co-located NPCs.
    Mutates relationships dict in place.
    """
    by_area = {}
    for nid, n in npcs.items():
        if n.get("status") != "alive":
            continue
        by_area.setdefault(n.get("area"), []).append(nid)

    drama_notes = []

    for area, ids in by_area.items():
        if len(ids) < 2:
            continue
        for _ in range(min(2, len(ids) // 2)):
            a, b = random.sample(ids, 2)
            na, nb = npcs[a], npcs[b]
            roll = random.random()
            if roll < 0.35:
                apply_interaction(b, "insult", intensity=0.6, actor_id=a)
                drama_notes.append({
                    "area": area,
                    "a": a, "b": b,
                    "text": f"{na.get('name')} and {nb.get('name')} are at odds.",
                })
            elif roll < 0.55:
                apply_interaction(b, "charm", intensity=0.5, actor_id=a)
                drama_notes.append({
                    "area": area,
                    "a": a, "b": b,
                    "text": f"{na.get('name')} is entangled with {nb.get('name')}.",
                })
            elif roll < 0.7:
                apply_interaction(b, "owed_debt", intensity=0.8, actor_id=a)
                drama_notes.append({
                    "area": area,
                    "a": a, "b": b,
                    "text": f"{nb.get('name')} owes {na.get('name')} a debt.",
                })

    return drama_notes


def drama_in_area(area_id, npcs, relationships=None):
    """Return tension lines for narrator when player enters a district."""
    relationships = relationships or load(REL_FILE, {})
    here = [n for n in npcs.values() if n.get("area") == area_id and n.get("status") == "alive"]
    if len(here) < 2:
        return []

    lines = []
    for n in here[:4]:
        nid = n["id"]
        book = relationships.get(nid, {})
        for other_id, rel in book.items():
            if other_id == "player":
                continue
            other = npcs.get(other_id)
            if not other or other.get("area") != area_id:
                continue
            if rel.get("resentment", 0) >= 35:
                lines.append(
                    f"{n.get('name', 'Someone')} and {other.get('name', 'someone')} "
                    f"have bad blood — do not invent this; it is real."
                )
            elif rel.get("obligation", 0) >= 40:
                lines.append(
                    f"{other.get('name', 'Someone')} owes {n.get('name', 'someone')} — "
                    f"tension in every glance."
                )
            if len(lines) >= 2:
                return lines
    return lines


def format_drama_block(area_id, npcs):
    lines = drama_in_area(area_id, npcs)
    if not lines:
        return ""
    return "LOCAL DRAMA (weave subtly — not a list):\n" + "\n".join(f"- {l}" for l in lines)
