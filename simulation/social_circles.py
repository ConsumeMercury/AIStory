"""
Social circles — explicit ally/rival links from relationship graph.
"""

from storage import load

REL_FILE = "characters/relationships.json"


def _npc_rel(a_id, b_id, rels):
    return (rels.get(a_id) or {}).get(b_id, {})


def circle_for_npc(npc_id, npcs, rels=None):
    rels = rels if rels is not None else load(REL_FILE, {})
    allies = []
    rivals = []
    for oid, onpc in (npcs or {}).items():
        if oid == npc_id or onpc.get("status") != "alive":
            continue
        rel = _npc_rel(npc_id, oid, rels)
        if rel.get("affection", 0) >= 55 or rel.get("trust", 0) >= 60:
            allies.append(onpc.get("name") or oid)
        if rel.get("rivalry", 0) >= 50 or rel.get("resentment", 0) >= 55:
            rivals.append(onpc.get("name") or oid)
    return {"allies": allies[:3], "rivals": rivals[:3]}


def social_circle_action_bias(npc_id, npcs, weights, rels=None):
    rels = rels if rels is not None else load(REL_FILE, {})
    circle = circle_for_npc(npc_id, npcs, rels)
    if circle["rivals"]:
        weights["plan"] = weights.get("plan", 5) * 1.12
        weights["fight"] = weights.get("fight", 5) * 1.08
    if circle["allies"]:
        weights["socialise"] = weights.get("socialise", 5) * 1.1
        weights["help"] = weights.get("help", 5) * 1.08


def focal_circle_block(npc_id, npcs, rels=None):
    circle = circle_for_npc(npc_id, npcs, rels)
    if not circle["allies"] and not circle["rivals"]:
        return ""
    npc = (npcs or {}).get(npc_id, {})
    label = npc.get("name") or npc_id
    parts = []
    if circle["allies"]:
        parts.append(f"allies: {', '.join(circle['allies'])}")
    if circle["rivals"]:
        parts.append(f"rivals: {', '.join(circle['rivals'])}")
    return f"SOCIAL CIRCLE ({label} — background only): {'; '.join(parts)}."
