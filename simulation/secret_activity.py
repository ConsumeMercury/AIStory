"""
Active secrets — knowers, exposure pressure, background leaks.
"""

import random


def enrich_secrets(npc, npcs=None):
    """Add simulation fields to generated secrets."""
    changed = False
    for sec in npc.get("secrets") or []:
        if sec.get("exposure_chance") is None:
            sev = sec.get("severity", "major")
            sec["exposure_chance"] = {"minor": 0.04, "major": 0.08, "deadly": 0.12}.get(sev, 0.06)
            changed = True
        if not sec.get("knowers"):
            sec["knowers"] = []
            changed = True
    return changed


def enrich_all_secrets(npcs):
    for npc in (npcs or {}).values():
        if npc.get("status") == "alive":
            enrich_secrets(npc, npcs)


def add_knower(npc, secret_id, knower_id):
    for sec in npc.get("secrets") or []:
        if sec.get("id") == secret_id:
            knowers = sec.setdefault("knowers", [])
            if knower_id not in knowers:
                knowers.append(knower_id)
            return True
    return False


def tick_secret_exposure(npcs, *, tick=None, day=None):
    """Random background exposure pressure — may spawn rumor hooks."""
    leaks = []
    for nid, npc in (npcs or {}).items():
        if npc.get("status") != "alive":
            continue
        for sec in npc.get("secrets") or []:
            if sec.get("exposed") or sec.get("exposed_to_player"):
                continue
            chance = sec.get("exposure_chance", 0.05)
            if random.random() < chance * 0.35:
                sec["exposure_pressure"] = sec.get("exposure_pressure", 0) + 1
                if sec["exposure_pressure"] >= 3:
                    sec["exposed"] = True
                    leaks.append({
                        "npc_id": nid,
                        "secret_id": sec.get("id"),
                        "hint": sec.get("text", "")[:80],
                    })
    return leaks


def secret_narrator_pressure(npc, present_ids=None):
    hidden = [s for s in (npc.get("secrets") or []) if not s.get("exposed_to_player")]
    if not hidden:
        return ""
    pressured = [s for s in hidden if s.get("exposure_pressure", 0) >= 2]
    if not pressured:
        return ""
    return (
        "SECRET PRESSURE — this person is near breaking; show strain, "
        "deflection, or a slip — do not dump the full secret unless SCENE FACTS allow."
    )
