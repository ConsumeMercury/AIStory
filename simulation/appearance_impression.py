"""
First-impression favourability when an NPC meets the player.
Nudges early relationship dimensions; does not bypass familiarity gating.
"""

import random


def compute_impression_of_player(viewer, player):
    """How this NPC reads the player on sight."""
    vt = viewer.get("traits", {})
    appearance = (player.get("appearance") or "unremarkable").lower()
    age = player.get("age", 30)
    bg = player.get("background", "wanderer")

    tags = []
    if any(w in appearance for w in ("scar", "burn", "missing", "broken")):
        tags.append("marked-by-violence")
    if any(w in appearance for w in ("fine", " silk", "jewel", "noble", "court")):
        tags.append("well-presented")
    if any(w in appearance for w in ("rag", "filth", "hollow", "starv", "patch")):
        tags.append("rough-looking")
    if any(w in appearance for w in ("tall", "broad", "muscled", "heavy", "powerful")):
        tags.append("imposing")
    if any(w in appearance for w in ("small", "thin", "frail", "young")):
        tags.append("frail-seeming")
    if bg in ("soldier", "mercenary"):
        tags.append("martial")

    attraction = random.uniform(-1, 2)
    respect = random.uniform(-1, 2)
    fear = 0.0
    trust = 0.0

    vanity = vt.get("vanity", 50)
    courage = vt.get("courage", 50)
    kindness = vt.get("kindness", 50)
    paranoia = vt.get("paranoia", 50)

    if "well-presented" in tags:
        respect += 3 + vanity / 35
        attraction += 2
    if "rough-looking" in tags:
        respect -= 2 if vanity > 55 else 0
        fear += 2 if courage < 48 else 0
        trust -= 2 if paranoia > 55 else 0
    if "imposing" in tags:
        fear += 4 if courage < 50 else 1
        respect += 2
    if "frail-seeming" in tags and kindness > 58:
        trust += 3
    if "marked-by-violence" in tags:
        fear += 3
        respect += 1 if vt.get("aggression", 50) > 55 else -1
    if age < 22:
        respect -= 1
    if age > 50:
        respect += 1

    hint_parts = []
    if attraction > 3:
        hint_parts.append("finds something striking about them")
    if respect > 3:
        hint_parts.append("reads them as capable or worth noting")
    if fear > 3:
        hint_parts.append("keeps a wary distance")
    if respect < -1:
        hint_parts.append("does not take them seriously at first")
    if not hint_parts:
        hint_parts.append("no strong first read")

    return {
        "attraction": round(max(-10, min(15, attraction)), 1),
        "respect": round(max(-10, min(15, respect)), 1),
        "fear": round(max(0, min(15, fear)), 1),
        "trust": round(max(-10, min(10, trust)), 1),
        "tags": tags,
        "hint": "; ".join(hint_parts),
    }


def record_first_impression(player, npc):
    known = player.setdefault("known_npcs", {})
    nid = npc["id"]
    rec = known.setdefault(nid, {"name_known": False, "seen_before": False})
    if rec.get("impression"):
        return rec["impression"]
    imp = compute_impression_of_player(npc, player)
    rec["impression"] = imp
    return imp


def impression_relationship_nudge(impression):
    if not impression:
        return {}
    return {
        "attraction": impression.get("attraction", 0) * 0.12,
        "respect": impression.get("respect", 0) * 0.18,
        "fear": impression.get("fear", 0) * 0.15,
        "trust": impression.get("trust", 0) * 0.12,
    }
