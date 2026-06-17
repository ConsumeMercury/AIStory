"""
Scoped reputation — local, faction, institution, and world layers.
"""

from storage import load

INST_FILE = "world/institutions.json"
FACTION_FILE = "world/factions.json"


def build_reputation_layers(player, *, area_id=None, target_npc=None, institutions=None):
    layers = {
        "local": 50,
        "faction": 50,
        "institution": 50,
        "world": 50,
    }
    profile = player.get("reputation_profile") or {}
    if profile:
        layers["world"] = int(
            (profile.get("heroic", 20) + profile.get("honorable", 50) - profile.get("violent", 15)) / 1.2
        )

    book = player.get("faction_standing") or {}
    if book:
        scores = [e.get("score", 0) for e in book.values()]
        layers["faction"] = 50 + int(sum(scores) / max(1, len(scores)))

    area_id = area_id or player.get("area")
    legacy = player.get("legacy") or []
    local = 50
    for leg in legacy[-8:]:
        cat = (leg.get("category") or "").lower()
        if cat == "kindness":
            local += 8
        elif cat in ("violence", "crime"):
            local -= 10
    layers["local"] = max(0, min(100, local))

    institutions = institutions if institutions is not None else load(INST_FILE, {})
    if target_npc:
        inst_id = (target_npc.get("institution") or {}).get("id")
        if inst_id and inst_id in institutions:
            mems = institutions[inst_id].get("institutional_memory") or []
            val = sum(m.get("valence", 0) for m in mems[-5:])
            layers["institution"] = max(0, min(100, 50 + int(val * 15)))

    player["reputation_layers"] = layers
    return layers


def reputation_layers_block(player, *, target_npc=None, institutions=None):
    layers = player.get("reputation_layers") or build_reputation_layers(
        player, target_npc=target_npc, institutions=institutions,
    )
    bits = []
    if layers.get("local", 50) >= 65:
        bits.append("locally liked")
    elif layers.get("local", 50) <= 35:
        bits.append("locally distrusted")
    if layers.get("faction", 50) >= 60:
        bits.append("faction-friendly")
    elif layers.get("faction", 50) <= 35:
        bits.append("faction-cold")
    if target_npc and layers.get("institution", 50) >= 60:
        bits.append("institution owes goodwill")
    elif target_npc and layers.get("institution", 50) <= 35:
        bits.append("institution wary")
    if layers.get("world", 50) >= 70:
        bits.append("growing legend")
    elif layers.get("world", 50) <= 30:
        bits.append("notorious")
    if not bits:
        return ""
    return f"REPUTATION SCOPE (ambient — never state scores): {', '.join(bits[:4])}."
