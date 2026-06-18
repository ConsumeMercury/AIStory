"""Shared fixtures for architecture catalog tests — no live save dependency."""


def npc(
    nid,
    *,
    role="stranger",
    name="",
    gender="male",
    status="alive",
    appearance=None,
    physique=None,
    key_npc=False,
    **extra,
):
    data = {
        "id": nid,
        "name": name or nid.replace("_", " ").title(),
        "role": role,
        "gender": gender,
        "status": status,
        "appearance": appearance or {},
        "physique": physique or {"presentation": 50},
        **({"key_npc": True} if key_npc else {}),
    }
    data.update(extra)
    return data


def player(**overrides):
    base = {
        "area": "test:district",
        "location": "test",
        "scene_focus": None,
        "known_npcs": {},
        "journal": [],
        "scene_cast": {},
        "scene_subplace": None,
        "last_combat_target": None,
        "last_combat_fatal": False,
    }
    base.update(overrides)
    return base


def npc_map(*npcs):
    return {n["id"]: n for n in npcs}
