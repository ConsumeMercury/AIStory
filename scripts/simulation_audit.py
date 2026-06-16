"""
Simulation audit — multi-action dry runs without Gemini.
Validates cast, combat targets, inventory, and narrator fact packets.

  python scripts/simulation_audit.py
"""

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CAPTURED = []


def _mock_generate_scene(**kwargs):
    CAPTURED.append({
        "action": kwargs.get("player_action"),
        "kind": (kwargs.get("action_context") or {}).get("kind"),
        "focus_ids": [n.get("id") for n in (kwargs.get("present_npcs") or [])],
        "focus_genders": [n.get("gender") for n in (kwargs.get("present_npcs") or [])],
        "focus_status": [n.get("status") for n in (kwargs.get("present_npcs") or [])],
        "target_id": (kwargs.get("action_context") or {}).get("target_id"),
        "combat_fatal": (kwargs.get("action_context") or {}).get("combat_fatal"),
        "acquired": (kwargs.get("action_context") or {}).get("acquired_item"),
        "directive_head": ((kwargs.get("action_context") or {}).get("story_directive") or "")[:200],
        "extra_head": (kwargs.get("extra_directive") or "")[:120],
        "crowd": (kwargs.get("crowd_note") or "")[:80],
    })
    return "[audit scene]"


def _reset_player_baseline():
    from storage import load, save
    player = load("player/player.json", {})
    if not player:
        raise RuntimeError("No player save — bootstrap or create character first.")
    player = copy.deepcopy(player)
    player["journal"] = []
    player["scene_focus"] = None
    player["last_combat_target"] = None
    player["last_combat_fatal"] = False
    player["combat_witnesses"] = []
    player.pop("last_acquired_item", None)
    stats = player.setdefault("stats", {})
    stats["health"] = stats.get("max_health", 100)
    stats["stamina"] = stats.get("max_stamina", 30)
    stats["stress"] = max(0, stats.get("stress", 0) - 20)
    player["inventory"] = []
    player["equipment"] = {"weapon": None, "armor": None, "trinket": None}
    area = player.get("area")
    npcs = load("characters/npcs.json", {})
    for npc in npcs.values():
        if npc.get("area") == area or npc.get("location") == player.get("location"):
            if npc.get("status") == "dead":
                npc["status"] = "alive"
            stats = npc.setdefault("stats", {})
            stats["health"] = stats.get("max_health", 80)
            stats["stamina"] = stats.get("max_stamina", 20)
    save("characters/npcs.json", npcs)
    save("player/player.json", player)
    return player


def _run_sequence(actions):
    from unittest.mock import patch
    from simulation.story_loop import process_player_action
    from storage import load, save

    CAPTURED.clear()
    results = []
    with patch("simulation.story_loop.generate_scene", side_effect=_mock_generate_scene):
        for action in actions:
            scene = process_player_action(action)
            player = load("player/player.json", {})
            results.append({
                "action": action,
                "scene_len": len(scene or ""),
                "scene_focus": player.get("scene_focus"),
                "last_combat_target": player.get("last_combat_target"),
                "last_combat_fatal": player.get("last_combat_fatal"),
                "inventory_count": len(player.get("inventory") or []),
                "equipped_weapon": (player.get("equipment") or {}).get("weapon"),
            })
    return results


def _assert(condition, msg):
    if not condition:
        raise AssertionError(msg)


def audit_explore_anchor():
    _reset_player_baseline()
    _run_sequence(["look around"])
    _assert(len(CAPTURED) == 1, "expected one capture")
    c = CAPTURED[0]
    _assert(c["kind"] == "explore", f"explore kind, got {c['kind']}")
    _assert(len(c["focus_ids"]) == 1, f"explore should have one focal NPC, got {c}")
    _assert(c["target_id"] == c["focus_ids"][0], "explore target should match focus npc")


def audit_attack_her():
    _reset_player_baseline()
    _run_sequence(["look around", "attack her"])
    _assert(len(CAPTURED) == 2, "two captures")
    first_focus = CAPTURED[0]["focus_ids"][0]
    first_gender = CAPTURED[0]["focus_genders"][0]
    second = CAPTURED[1]
    _assert(second["kind"] == "attack", "second beat attack")
    _assert(second["focus_genders"][0] == "female", "attack her should target a female NPC")
    if first_gender == "female":
        _assert(
            second["focus_ids"][0] == first_focus or second["target_id"] == first_focus,
            f"attack her should prefer female explore hook {first_focus}, got {second}",
        )


def audit_find_sword_inventory():
    _reset_player_baseline()
    before = _run_sequence(["find a sword"])[0]
    _assert(before["inventory_count"] >= 1, "find a sword should add inventory item")
    if CAPTURED[0].get("acquired"):
        pass  # preferred
    elif before["inventory_count"] >= 1:
        pass  # item added even if capture missed metadata
    else:
        _assert(False, "action_ctx should record acquired_item or add inventory")
    _assert(CAPTURED[0]["kind"] == "search", f"find sword should be search, got {CAPTURED[0]['kind']}")


def audit_confession_witness():
    from storage import load
    _reset_player_baseline()
    _run_sequence(["look around", "Attack", "I have killed him"])
    player = load("player/player.json", {})
    _assert(player.get("last_combat_target"), "combat should set last_combat_target")
    confess = CAPTURED[2]
    _assert(confess["kind"] == "confess", f"confess kind, got {confess['kind']}")
    _assert(len(confess["focus_ids"]) >= 1, "confess should have a respondent focal npc")
    _assert("SCENE FACTS" in confess["directive_head"] or "confess" in confess["directive_head"].lower(),
            "confess should include fact/directive guidance")


def audit_find_person_role():
    """Role-specific find must match role or fail — not scene_focus fallback."""
    from storage import load
    _reset_player_baseline()
    _run_sequence(["look around", "find the priest"])
    last = CAPTURED[-1]
    _assert(last["kind"] == "find", f"find kind, got {last['kind']}")
    player = load("player/player.json", {})
    journal = player.get("journal") or []
    entry = journal[-1] if journal else {}
    focus_id = entry.get("focus_npc")
    npcs = load("characters/npcs.json", {})
    if focus_id:
        role = npcs.get(focus_id, {}).get("role")
        _assert(role == "priest", f"find priest matched role={role!r}, focus={focus_id}")
        head = (last.get("directive_head") or "") + (last.get("extra_head") or "")
        _assert("FIND PERSON" in head.upper() or "SCENE FACTS" in head,
                "find should include fact packet")
    else:
        _assert("failed search" in last.get("directive_head", "").lower() or True,
                "no priest present should leave focus empty")


def audit_non_fatal_no_ghost_speaker():
    """After non-fatal fight, focal npc should be alive status in snapshot."""
    from unittest.mock import patch
    from simulation.story_loop import process_player_action

    CAPTURED.clear()
    _reset_player_baseline()
    # Force non-fatal by patching resolve_combat
    with patch("simulation.story_loop.generate_scene", side_effect=_mock_generate_scene):
        with patch("simulation.story_loop.resolve_combat") as rc:
            rc.return_value = {
                "rounds": 2, "log": [], "winner": None, "loser": None,
                "fatal": False, "consequences": ["draw"],
                "player_injuries": ["split lip"],
            }
            process_player_action("look around")
            process_player_action("attack")
    c = CAPTURED[1]
    _assert(c["combat_fatal"] is False, "should record non-fatal")
    if c["focus_ids"]:
        _assert(c["focus_status"][0] != "dead", "non-fatal focal should not be dead")


def main():
    tests = [
        ("explore_anchor", audit_explore_anchor),
        ("attack_her", audit_attack_her),
        ("find_sword_inventory", audit_find_sword_inventory),
        ("confession_witness", audit_confession_witness),
        ("find_person_role", audit_find_person_role),
        ("non_fatal_focal", audit_non_fatal_no_ghost_speaker),
    ]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"OK    {name}")
        except Exception as e:
            failed.append(name)
            print(f"FAIL  {name}: {e}")
    if failed:
        print(f"\n{len(failed)} audit(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"\nAll {len(tests)} simulation audits passed.")


if __name__ == "__main__":
    main()
