"""
Shared generation / simulation quality helpers for offline and live runs.
"""

import copy
import re

from simulation.prose_validator import (
    analyze_prose,
    build_beat_context,
    focal_referenced,
    gender_mismatch,
    role_mismatch,
    _FOCAL_DIALOGUE_KINDS,
)

_DEATH_PROSE = re.compile(
    r"\b("
    r"corpse|lifeless body|slain|murdered (?:him|her)|"
    r"killed (?:him|her)|he is dead|she is dead|"
    r"fatal wound|bled out|stopped breathing|"
    r"body (?:went|falls?) still|death rattle"
    r")\b",
    re.I,
)

_ROLE_WORDS = {
    "scholar": ("scholar", "scribe", "academic"),
    "priest": ("priest", "cleric", "monk", "chaplain"),
    "blacksmith": ("blacksmith", "smith", "forge"),
    "merchant": ("merchant", "trader", "stall"),
    "sailor": ("sailor", "dockhand", "crewman"),
    "guard": ("guard", "watchman", "soldier"),
}

SCENARIOS = {
    "dock_fight": [
        "look around",
        "attack her",
        "find a sword",
        "attack anyway",
        "I have killed him",
    ],
    "social": [
        "look around",
        "what is your name?",
        "ask for work",
    ],
}

FULL_SCENARIOS = {
    "01_explore_focus": [
        "look around",
        "observe the crowd quietly",
        "look around again",
    ],
    "02_time_wait": [
        "look around",
        "keep watch",
    ],
    "03_social_chain": [
        "look around",
        "what is your name?",
        "talk to them",
        "show respect",
        "insult them",
    ],
    "04_guild_work": [
        "look around",
        "ask for work",
    ],
    "05_items_search": [
        "find a sword",
        "examine the blade",
    ],
    "06_rest_recovery": [
        "look around",
        "rest for a moment",
    ],
    "07_travel_market": [
        "go to the market",
        "look around",
        "go to the docks",
    ],
    "08_combat_full": [
        "look around",
        "attack her",
        "find a sword",
        "attack anyway",
        "I have killed him",
    ],
    "09_find_person": [
        "look around",
        "find the priest",
    ],
    "10_withdraw": [
        "look around",
        "talk to them",
        "walk away",
    ],
}

_BASELINE_WORLD = None
_BASELINE_PLAYER = None


def backup_saves():
    from storage import load
    return {
        "player": copy.deepcopy(load("player/player.json", {})),
        "world": copy.deepcopy(load("world/world_state.json", {})),
        "npcs": copy.deepcopy(load("characters/npcs.json", {})),
    }


def restore_saves(backups):
    from storage import save
    if backups.get("player"):
        save("player/player.json", backups["player"])
    if backups.get("world"):
        save("world/world_state.json", backups["world"])
    if backups.get("npcs"):
        save("characters/npcs.json", backups["npcs"])


def reset_baseline(*, area_only_npcs=True):
    """Reset player + local NPCs (+ world clock) for a reproducible scenario start."""
    global _BASELINE_WORLD, _BASELINE_PLAYER
    from storage import load, save

    player = load("player/player.json", {})
    if not player:
        raise RuntimeError("No player save — create a character first.")

    if _BASELINE_PLAYER is None:
        _BASELINE_PLAYER = copy.deepcopy(player)
    player = copy.deepcopy(_BASELINE_PLAYER)

    player["journal"] = []
    player["scene_focus"] = None
    player["last_combat_target"] = None
    player["last_combat_fatal"] = False
    player["combat_witnesses"] = []
    player.pop("last_acquired_item", None)
    player.pop("last_check", None)
    player.pop("scene_subplace", None)
    stats = player.setdefault("stats", {})
    stats["health"] = stats.get("max_health", 100)
    stats["stamina"] = stats.get("max_stamina", 30)
    stats["stress"] = max(0, stats.get("stress", 0) - 15)
    player["inventory"] = []
    player["equipment"] = {"weapon": None, "armor": None, "trinket": None}
    player["injuries"] = []

    area = player.get("area")
    loc = player.get("location")
    npcs = load("characters/npcs.json", {})
    for npc in npcs.values():
        in_scope = npc.get("area") == area if area_only_npcs else True
        if not in_scope and loc and npc.get("location") != loc:
            continue
        if npc.get("status") == "dead":
            npc["status"] = "alive"
        nstats = npc.setdefault("stats", {})
        nstats["health"] = nstats.get("max_health", 80)
        nstats["stamina"] = nstats.get("max_stamina", 20)

    world = load("world/world_state.json", {})
    if _BASELINE_WORLD is None:
        _BASELINE_WORLD = copy.deepcopy(world)
    else:
        world = copy.deepcopy(_BASELINE_WORLD)
    save("world/world_state.json", world)
    save("characters/npcs.json", npcs)
    save("player/player.json", player)
    return player, world


def capture_state(player, world, npcs, sim_tick):
    area = player.get("area")
    area_npcs = []
    for nid, npc in npcs.items():
        if npc.get("area") != area:
            continue
        st = npc.get("stats", {})
        area_npcs.append({
            "id": nid,
            "name": npc.get("name"),
            "role": npc.get("role"),
            "gender": npc.get("gender"),
            "status": npc.get("status"),
            "health": st.get("health"),
            "max_health": st.get("max_health"),
        })
    stats = player.get("stats", {})
    known = sum(
        1 for rec in (player.get("known_npcs") or {}).values()
        if rec.get("name_known")
    )
    return {
        "sim_tick": sim_tick,
        "hour_count": world.get("hour_count"),
        "day": world.get("day"),
        "hour": world.get("hour"),
        "season": world.get("season"),
        "weather": world.get("weather"),
        "area": area,
        "location": player.get("location"),
        "subplace": (player.get("scene_subplace") or {}).get("label"),
        "health": stats.get("health"),
        "max_health": stats.get("max_health"),
        "stamina": stats.get("stamina"),
        "max_stamina": stats.get("max_stamina"),
        "stress": stats.get("stress"),
        "wealth": player.get("wealth"),
        "inv_count": len(player.get("inventory") or []),
        "equipped_weapon": (player.get("equipment") or {}).get("weapon"),
        "injuries": len(player.get("injuries") or []),
        "journal_len": len(player.get("journal") or []),
        "scene_focus": player.get("scene_focus"),
        "last_combat_target": player.get("last_combat_target"),
        "last_combat_fatal": player.get("last_combat_fatal"),
        "combat_witnesses": len(player.get("combat_witnesses") or []),
        "known_names": known,
        "met_npcs": len(player.get("met_npcs") or []),
        "xp": player.get("xp"),
        "area_npc_count": len(area_npcs),
        "area_npcs_alive": sum(1 for n in area_npcs if n.get("status") == "alive"),
        "area_npcs_dead": sum(1 for n in area_npcs if n.get("status") == "dead"),
    }


def format_delta(before, after):
    parts = []
    for key in (
        "sim_tick", "hour_count", "day", "hour", "area", "health", "stamina",
        "stress", "wealth", "inv_count", "journal_len", "injuries",
        "known_names", "met_npcs", "area_npcs_dead",
    ):
        bv, av = before.get(key), after.get(key)
        if bv != av:
            parts.append(f"{key}:{bv}->{av}")
    if before.get("scene_focus") != after.get("scene_focus"):
        parts.append(f"focus:{before.get('scene_focus')}->{after.get('scene_focus')}")
    if before.get("last_combat_fatal") != after.get("last_combat_fatal"):
        parts.append(f"combat_fatal:{before.get('last_combat_fatal')}->{after.get('last_combat_fatal')}")
    return ", ".join(parts) if parts else "(unchanged)"


def mechanical_checks(action, kind, before, after, journal_entry, npcs):
    issues = []
    action_l = (action or "").lower()

    if after["journal_len"] <= before["journal_len"]:
        issues.append("journal did not append entry")

    if kind == "explore" and not journal_entry.get("focus_npc"):
        issues.append("explore missing focus_npc in journal")

    if kind == "wait":
        delta = (after.get("hour_count") or 0) - (before.get("hour_count") or 0)
        if delta != 2:
            issues.append(f"wait should advance 2 hours, delta={delta}")

    if kind == "travel":
        if after.get("area") == before.get("area") and not after.get("subplace"):
            issues.append("travel did not change area or subplace")
        if (after.get("hour_count") or 0) <= (before.get("hour_count") or 0):
            if after.get("area") != before.get("area"):
                issues.append("travel changed area but hour_count did not advance")

    if kind == "search" and "sword" in action_l:
        if after["inv_count"] <= before["inv_count"]:
            issues.append("find sword should add inventory item")

    if kind == "attack":
        if not after.get("last_combat_target"):
            issues.append("attack missing last_combat_target")
        if not journal_entry.get("focus_npc"):
            issues.append("attack missing focus_npc in journal")
        if journal_entry.get("combat_fatal") is True:
            tid = after.get("last_combat_target")
            target = npcs.get(tid, {}) if tid else {}
            if target.get("status") != "dead":
                issues.append("fatal attack but NPC status is not dead")
        elif journal_entry.get("combat_fatal") is False:
            tid = after.get("last_combat_target")
            target = npcs.get(tid, {}) if tid else {}
            if target.get("status") == "dead":
                issues.append("non-fatal attack but NPC marked dead")

    if kind == "confess":
        if not journal_entry.get("focus_npc"):
            issues.append("confess missing respondent focus_npc")
        if after.get("last_combat_fatal") and journal_entry.get("focus_npc") == after.get("last_combat_target"):
            issues.append("confess respondent should not be the corpse")

    if kind == "find":
        action_l = (action or "").lower()
        if re.search(r"\b(priest|cleric|monk|merchant|sailor|captain)\b", action_l):
            focus_id = journal_entry.get("focus_npc")
            if focus_id:
                target = npcs.get(focus_id, {})
                if "priest" in action_l and target.get("role") != "priest":
                    issues.append(f"find priest matched role={target.get('role')} not priest")
                if "merchant" in action_l and target.get("role") not in ("merchant", "innkeeper"):
                    issues.append(f"find merchant matched role={target.get('role')}")
            elif "priest" in action_l or "merchant" in action_l:
                pass  # no match — failed search is OK

    if "sword" in action_l and after.get("equipped_weapon") and kind == "search":
        pass  # optional equip — not always auto-equip

    return issues

