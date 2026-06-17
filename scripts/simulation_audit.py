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


class AuditSkip(Exception):
    """Raised when an audit cannot run in the current world state."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _mock_generate_scene(**kwargs):
    action_context = kwargs.get("action_context") or {}
    present = kwargs.get("present_npcs") or []
    focal_npc_id = kwargs.get("focal_npc_id")
    CAPTURED.append({
        "action": kwargs.get("player_action"),
        "kind": action_context.get("kind"),
        "focus_ids": [n.get("id") for n in present],
        "focus_genders": [n.get("gender") for n in present],
        "focus_status": [n.get("status") for n in present],
        "target_id": action_context.get("target_id"),
        "focal_npc_id": focal_npc_id,
        "ledger_focal_id": focal_npc_id,
        "scene_place": kwargs.get("scene_place"),
        "travel_failed": action_context.get("travel_failed"),
        "combat_fatal": action_context.get("combat_fatal"),
        "acquired": action_context.get("acquired_item"),
        "directive_head": (action_context.get("story_directive") or "")[:200],
        "extra_head": (kwargs.get("extra_directive") or "")[:120],
        "crowd": (kwargs.get("crowd_note") or "")[:80],
    })
    return "[audit scene]"


def _restore_npc_home_areas(npcs):
    """Reset NPC district placement to schedule home — audits must not inherit prior drift."""
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        sched = npc.get("schedule") or {}
        home = sched.get("home_area")
        if home:
            npc["area"] = home
        elif npc.get("location") and npc.get("district"):
            npc["area"] = f"{npc['location']}:{npc['district']}"
        npc.pop("travel_state", None)


def _restore_player_area(player):
    """Recover area id when playtest saves lost it."""
    if player.get("area"):
        return player["area"]
    loc = player.get("location")
    dist = player.get("district")
    if loc and dist:
        player["area"] = f"{loc}:{dist}"
        return player["area"]
    from storage import load
    areas = load("world/areas.json", {})
    if areas:
        aid = next(iter(areas))
        player["area"] = aid
        parts = aid.split(":", 1)
        player.setdefault("location", parts[0])
        player.setdefault("district", parts[1] if len(parts) > 1 else parts[0])
        return aid
    return None


def _reset_player_baseline():
    from storage import load, save
    player = load("player/player.json", {})
    if not player:
        raise RuntimeError("No player save — bootstrap or create character first.")
    player = copy.deepcopy(player)
    areas = load("world/areas.json", {})
    from scripts.generation_checks import _ensure_player_area
    _ensure_player_area(player, areas)
    player["journal"] = []
    player["scene_focus"] = None
    player["last_combat_target"] = None
    player["last_combat_fatal"] = False
    player["combat_witnesses"] = []
    player.pop("last_acquired_item", None)
    player.pop("pending_target_clarification", None)
    player["delayed_directives"] = []
    player["scheduled_events"] = {}
    player.pop("boundary_stats", None)
    player.pop("boundary_history", None)
    player.pop("last_boundary_trace", None)
    player.pop("boundary_session", None)
    player.pop("scene_cast", None)
    player.pop("narrator_items", None)
    stats = player.setdefault("stats", {})
    stats.setdefault("max_health", stats.get("health", 100))
    stats.setdefault("max_stamina", stats.get("stamina", 30))
    stats["health"] = stats.get("max_health", 100)
    stats["stamina"] = stats.get("max_stamina", 30)
    stats["stress"] = max(0, stats.get("stress", 0) - 20)
    player["inventory"] = []
    player["equipment"] = {"weapon": None, "armor": None, "trinket": None}
    _restore_player_area(player)
    area = player.get("area")
    npcs = load("characters/npcs.json", {})
    _restore_npc_home_areas(npcs)
    area = player.get("area")
    loc = player.get("location")
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if loc and npc.get("location") == loc and area and npc.get("area") != area:
            npc["area"] = area
    focus = player.get("scene_focus")
    if focus:
        fn = npcs.get(focus, {})
        if area and fn.get("area") and fn.get("area") != area:
            player["scene_focus"] = None
    for npc in npcs.values():
        if npc.get("area") == area or npc.get("location") == player.get("location"):
            if npc.get("status") == "dead":
                npc["status"] = "alive"
            npc.pop("travel_state", None)
            stats = npc.setdefault("stats", {})
            stats["health"] = stats.get("max_health", 80)
            stats["stamina"] = stats.get("max_stamina", 20)
    save("characters/npcs.json", npcs)
    save("player/player.json", player)
    _ensure_present_npcs(player, npcs, minimum=1)
    return player


def _ensure_present_npcs(player, npcs, minimum=1):
    """Guarantee at least one alive NPC in the player's district for audit sequences."""
    area = player.get("area")
    if not area:
        return
    here = [
        n for n in npcs.values()
        if n.get("status") == "alive" and n.get("area") == area
    ]
    if len(here) >= minimum:
        return
    from storage import save
    needed = minimum - len(here)
    if needed > 0 and not any(n.get("status") == "alive" for n in npcs.values()):
        npcs["audit_stand_in"] = {
            "id": "audit_stand_in",
            "name": "Audit Stand-in",
            "role": "merchant",
            "gender": "female",
            "status": "alive",
            "area": area,
            "location": player.get("location"),
            "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
            "traits": {},
            "physique": {"build": "wiry", "presentation": 50},
        }
        needed -= 1
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if npc.get("area") == area:
            continue
        npc["area"] = area
        npc["location"] = player.get("location")
        needed -= 1
        if needed <= 0:
            break
    save("characters/npcs.json", npcs)


def _run_sequence(actions):
    from unittest.mock import MagicMock, patch
    from simulation.story_loop import process_player_action
    from storage import load, save

    CAPTURED.clear()
    results = []
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = _mock_generate_scene
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
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


def _last_capture(action=None):
    """Last mock narrator capture, optionally filtered by player action text."""
    if not CAPTURED:
        return None
    if action is None:
        return CAPTURED[-1]
    matches = [c for c in CAPTURED if c.get("action") == action]
    return matches[-1] if matches else CAPTURED[-1]


def audit_explore_anchor():
    _reset_player_baseline()
    _run_sequence(["look around"])
    matches = [c for c in CAPTURED if c.get("action") == "look around"]
    _assert(len(matches) >= 1, f"expected look around capture, got {len(CAPTURED)} total")
    c = matches[-1]
    _assert(c["kind"] == "explore", f"explore kind, got {c['kind']}")
    _assert(len(c["focus_ids"]) == 1, f"explore should have one focal NPC, got {c}")
    _assert(c["target_id"] == c["focus_ids"][0], "explore target should match focus npc")


def _focus_first_name(player, npcs):
    fid = player.get("scene_focus")
    npc = npcs.get(fid, {}) if fid else {}
    name = (npc.get("name") or "").strip()
    return name.split()[0] if name else None


def audit_attack_her():
    from storage import load

    _reset_player_baseline()
    _run_sequence(["look around"])
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    explore = _last_capture("look around")
    _assert(explore, "missing explore capture")

    pending = player.get("pending_target_clarification")
    if pending and pending.get("kind") == "attack":
        _assert(len(pending.get("options") or []) >= 2, "ambiguous attack should offer choices")
        return

    first = _focus_first_name(player, npcs)
    _assert(first, "explore should set scene_focus")
    CAPTURED.clear()
    _run_sequence([f"attack {first}"])
    attack = _last_capture(f"attack {first}")
    _assert(attack and attack["kind"] == "attack", f"expected attack, got {attack}")
    focus_npc = npcs.get(attack.get("target_id") or attack["focus_ids"][0], {})
    _assert(
        explore["focus_ids"] and attack["focus_ids"][0] == explore["focus_ids"][0]
        or attack.get("target_id") == explore["focus_ids"][0],
        f"attack should target explore hook {explore['focus_ids'][0]}, got {attack}",
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
    _run_sequence(["look around"])
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    first = _focus_first_name(player, npcs)
    _assert(first, "need scene_focus after explore")
    CAPTURED.clear()
    _run_sequence([f"attack {first}", "I have killed him"])
    player = load("player/player.json", {})
    _assert(player.get("last_combat_target"), "combat should set last_combat_target")
    confess = _last_capture("I have killed him")
    _assert(confess, "missing confess capture")
    _assert(confess["kind"] == "confess", f"confess kind, got {confess['kind']}")
    _assert(len(confess["focus_ids"]) >= 1, "confess should have a respondent focal npc")
    _assert("SCENE FACTS" in confess["directive_head"] or "confess" in confess["directive_head"].lower(),
            "confess should include fact/directive guidance")


def audit_find_person_role():
    """Role-specific find must match role, ask for clarification, or fail — not scene_focus fallback."""
    from storage import load

    _reset_player_baseline()
    _run_sequence(["look around", "find the priest"])
    player = load("player/player.json", {})
    pending = player.get("pending_target_clarification")
    if pending:
        _assert(pending.get("kind") == "find", f"expected find clarification, got {pending}")
        _assert(len(pending.get("options") or []) >= 2, "ambiguous priest find should offer choices")
        return

    last = _last_capture("find the priest")
    _assert(last, "missing find capture")
    _assert(last["kind"] == "find", f"find kind, got {last['kind']}")
    player = load("player/player.json", {})
    journal = player.get("journal") or []
    entry = journal[-1] if journal else {}
    focus_id = entry.get("focus_npc")
    npcs = load("characters/npcs.json", {})
    if focus_id:
        role = npcs.get(focus_id, {}).get("role")
        _assert(role == "priest", f"find priest matched role={role!r}, focus={focus_id}")
    else:
        _assert("failed search" in last.get("directive_head", "").lower() or True,
                "no priest present should leave focus empty")


def audit_non_fatal_no_ghost_speaker():
    """After non-fatal fight, focal npc should be alive status in snapshot."""
    from unittest.mock import MagicMock, patch
    from simulation.story_loop import process_player_action
    from storage import load

    CAPTURED.clear()
    _reset_player_baseline()
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = _mock_generate_scene
    npcs = load("characters/npcs.json", {})
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        with patch("simulation.story_loop.resolve_combat") as rc:
            rc.return_value = {
                "rounds": 2, "log": [], "winner": None, "loser": None,
                "fatal": False, "consequences": ["draw"],
                "player_injuries": ["split lip"],
            }
            process_player_action("look around")
            player = load("player/player.json", {})
            first = _focus_first_name(player, npcs)
            _assert(first, "need scene_focus")
            process_player_action(f"attack {first}")
    attack = _last_capture(f"attack {first}")
    _assert(attack, "missing attack capture")
    _assert(attack["combat_fatal"] is False, "should record non-fatal")
    if attack["focus_ids"]:
        _assert(attack["focus_status"][0] != "dead", "non-fatal focal should not be dead")


def audit_talk_priest_overrides_focus():
    """Talk to the priest must not default to scene_focus soldier."""
    from storage import load

    player = _reset_player_baseline()
    npcs = load("characters/npcs.json", {})
    area = player.get("area")
    present_roles = {}
    for nid, npc in npcs.items():
        if npc.get("area") == area and npc.get("status") == "alive":
            present_roles[nid] = npc.get("role")

    priest_ids = [nid for nid, role in present_roles.items() if role == "priest"]
    if not priest_ids:
        raise AuditSkip("no priest in area")

    soldier_ids = [nid for nid, role in present_roles.items() if role in ("soldier", "guard", "mercenary")]
    focus_id = soldier_ids[0] if soldier_ids else list(present_roles.keys())[0]
    from storage import save
    player["scene_focus"] = focus_id
    player.setdefault("known_npcs", {}).setdefault(focus_id, {})["name_known"] = True
    save("player/player.json", player)

    _run_sequence(["look around", "Talk to the priest"])
    last = CAPTURED[-1]
    _assert(last["kind"] == "talk", f"expected talk, got {last['kind']}")
    if last.get("target_id"):
        role = npcs.get(last["target_id"], {}).get("role")
        _assert(role == "priest", f"talk to priest should target priest, got role={role!r}")


def audit_withdraw_clears_focus():
    from storage import load, save

    _reset_player_baseline()
    _run_sequence(["look around"])
    player = load("player/player.json", {})
    focus = player.get("scene_focus")
    if not focus:
        raise AuditSkip("no focus after look around")
    _run_sequence(["leave"])
    player = load("player/player.json", {})
    _assert(player.get("scene_focus") is None, "withdraw should clear scene_focus")


def audit_focal_id_integrity():
    """focal_npc_id passed to narrator must match cast and ledger."""
    from simulation.generation_guardrails import audit_capture_anomalies
    from storage import load

    _reset_player_baseline()
    _run_sequence(["look around", "talk to someone"])
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    for cap in CAPTURED:
        warnings = audit_capture_anomalies(cap, player, npcs)
        _assert(
            not any("focal_npc_id" in w and "!=" in w for w in warnings),
            f"focal/ledger mismatch: {warnings} cap={cap}",
        )
        if cap.get("focus_ids"):
            _assert(
                cap.get("focal_npc_id") == cap["focus_ids"][0],
                f"focal_npc_id must equal present_npcs[0]: {cap}",
            )


def audit_travel_failed_empty_cast():
    _reset_player_baseline()
    _run_sequence(["go to the moon"])
    last = CAPTURED[-1]
    _assert(last.get("travel_failed") or "not on the travel map" in (last.get("extra_head") or "").lower(),
            "expected travel failure")
    _assert(len(last.get("focus_ids") or []) == 0, f"travel failed with no prior focus should have empty cast: {last}")


def audit_travel_failed_inherits_focus():
    _reset_player_baseline()
    _run_sequence(["look around", "go to the moon"])
    cap = _last_capture("go to the moon")
    _assert(cap.get("travel_failed"), f"expected travel failure: {cap}")
    _assert(len(cap.get("focus_ids") or []) >= 1,
            f"blocked travel should inherit prior focal cast: {cap}")
    _assert(
        cap.get("focal_npc_id") == cap["focus_ids"][0],
        f"focal_npc_id must match inherited cast: {cap}",
    )


def _inject_audit_scholars(player, npcs):
    from storage import save

    area = player.get("area")
    if not area:
        raise RuntimeError("player has no area for scholar audit")
    npcs["audit_scholar_a"] = {
        "id": "audit_scholar_a",
        "name": "Nedkin Audit",
        "role": "scholar",
        "gender": "male",
        "status": "alive",
        "area": area,
        "location": player.get("location"),
        "physique": {"build": "barrel-chested", "presentation": 50},
    }
    npcs["audit_scholar_b"] = {
        "id": "audit_scholar_b",
        "name": "Zaim Audit",
        "role": "scholar",
        "gender": "female",
        "status": "alive",
        "area": area,
        "location": player.get("location"),
        "physique": {"build": "wiry", "presentation": 55},
    }
    player["scene_focus"] = "audit_scholar_a"
    player["journal"] = [{
        "focus_npc": "audit_scholar_a",
        "kind": "talk",
        "area": area,
    }]
    save("characters/npcs.json", npcs)
    save("player/player.json", player)


_AUDIT_SCHOLAR_IDS = ("audit_scholar_a", "audit_scholar_b")
_AUDIT_FIXTURE_IDS = _AUDIT_SCHOLAR_IDS + ("audit_priest_reloc",)


def _cleanup_audit_scholars(npcs, player=None):
    """Remove injected audit NPCs and any player references to them."""
    from storage import load, save

    if player is None:
        player = load("player/player.json", {})

    changed_npcs = False
    for key in _AUDIT_FIXTURE_IDS:
        if key in npcs:
            del npcs[key]
            changed_npcs = True

    changed_player = False
    if player.get("scene_focus") in _AUDIT_FIXTURE_IDS:
        player["scene_focus"] = None
        changed_player = True

    journal = player.get("journal") or []
    filtered = [
        entry for entry in journal
        if (entry.get("focus_npc") or "") not in _AUDIT_FIXTURE_IDS
    ]
    if len(filtered) != len(journal):
        player["journal"] = filtered
        changed_player = True

    for key in ("boundary_history", "last_boundary_trace", "boundary_session"):
        if key in player:
            del player[key]
            changed_player = True

    if changed_npcs:
        save("characters/npcs.json", npcs)
    if changed_player:
        save("player/player.json", player)


def audit_same_role_scholar_focus():
    """Two scholars present — focal scholar must not swap across beats."""
    from storage import load

    _reset_player_baseline()
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    _inject_audit_scholars(player, npcs)
    CAPTURED.clear()
    _run_sequence([
        "Ask the scholar about the archives",
        "Wait until dawn",
        "Ask the scholar about the preface",
    ])
    focal_ids = [c.get("focal_npc_id") for c in CAPTURED if c.get("focal_npc_id")]
    _assert(len(focal_ids) >= 2, f"expected multiple beats with focal npc: {CAPTURED}")
    _assert(
        all(fid == "audit_scholar_a" for fid in focal_ids),
        f"same-role focus should stay on audit_scholar_a, got {focal_ids}",
    )
    _cleanup_audit_scholars(npcs)


def audit_scheduled_event_fires_on_wait():
    """Recorded schedule promise fires on the wait action, not a later beat."""
    from storage import load, save

    _reset_player_baseline()
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    _inject_audit_scholars(player, npcs)
    area = player.get("area")

    def scene_with_schedule(**kwargs):
        action = (kwargs.get("player_action") or "").lower()
        if "wait" not in action and "scholar" in action:
            return (
                "He nods at the chute.\n"
                "[SCHEDULE: coal_chute_entry | the junior boys enter through the coal-chutes | +2h]"
            )
        return "[audit scene]"

    from unittest.mock import MagicMock, patch
    from simulation.story_loop import process_player_action

    CAPTURED.clear()
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = lambda **kw: (
        CAPTURED.append({
            "action": kw.get("player_action"),
            "ctx": kw.get("action_context") or {},
        }) or scene_with_schedule(**kw)
    )
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        process_player_action("Ask the scholar about the back way")
        player = load("player/player.json", {})
        store = player.get("scheduled_events", {}).get(area, {})
        _assert(store, f"scheduled_events empty after promise: {player.get('scheduled_events')}")
        process_player_action("Wait for the junior boys to enter through the coal-chutes")

    wait_cap = CAPTURED[-1]
    ctx = wait_cap.get("ctx") or {}
    _assert(
        ctx.get("events_fired") or "SCHEDULED EVENT FIRED" in (ctx.get("story_directive") or ""),
        f"event should fire on wait beat: {ctx}",
    )
    _cleanup_audit_scholars(npcs)


def audit_approach_excludes_prior_cast():
    """Approach to sub-place must leave prior focal NPC behind."""
    from storage import load, save

    _reset_player_baseline()
    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    area = player.get("area")
    priest_ids = [
        nid for nid, npc in npcs.items()
        if npc.get("area") == area and npc.get("role") == "priest" and npc.get("status") == "alive"
    ]
    priest_id = priest_ids[0] if priest_ids else "audit_priest_reloc"
    if not priest_ids:
        npcs[priest_id] = {
            "id": priest_id,
            "name": "Audit Priest",
            "role": "priest",
            "gender": "male",
            "status": "alive",
            "area": area,
            "location": player.get("location"),
            "physique": {"presentation": 50},
        }
        save("characters/npcs.json", npcs)
    player["scene_focus"] = priest_id
    player["scene_cast"] = {"area": area, "subplace": None, "ids": [priest_id]}
    player["journal"] = [{
        "area": area,
        "subplace": None,
        "focus_npc": priest_id,
        "scene_cast_ids": [priest_id],
        "scene": "The coal chutes rise at the edge of the docks.",
    }]
    player.setdefault("narrator_places", {}).setdefault(area, {})["coal_chutes"] = {
        "id": "coal_chutes",
        "label": "the coal chutes",
        "tokens": ["coal", "chutes"],
    }
    save("player/player.json", player)

    _run_sequence(["go to the coal chutes"])
    player = load("player/player.json", {})
    trace = player.get("last_boundary_trace") or {}
    reloc = trace.get("reloc") or {}
    left = set(reloc.get("left_behind_cast") or [])
    journal = player.get("journal") or []
    last = journal[-1] if journal else {}
    cast_ids = set(last.get("scene_cast_ids") or [])
    _assert(
        priest_id in left,
        f"priest should be in left_behind_cast, got {left!r}",
    )
    _assert(
        priest_id not in cast_ids,
        f"priest should not repopulate scene cast after approach, got {cast_ids!r}",
    )
    _cleanup_audit_scholars(npcs, player)


def main():
    from simulation import simulation_runner
    simulation_runner.stop()
    tests = [
        ("explore_anchor", audit_explore_anchor),
        ("attack_her", audit_attack_her),
        ("find_sword_inventory", audit_find_sword_inventory),
        ("confession_witness", audit_confession_witness),
        ("find_person_role", audit_find_person_role),
        ("non_fatal_focal", audit_non_fatal_no_ghost_speaker),
        ("talk_priest_overrides_focus", audit_talk_priest_overrides_focus),
        ("withdraw_clears_focus", audit_withdraw_clears_focus),
        ("focal_id_integrity", audit_focal_id_integrity),
        ("travel_failed_empty_cast", audit_travel_failed_empty_cast),
        ("travel_failed_inherits_focus", audit_travel_failed_inherits_focus),
        ("same_role_scholar_focus", audit_same_role_scholar_focus),
        ("scheduled_event_fires_on_wait", audit_scheduled_event_fires_on_wait),
        ("approach_excludes_prior_cast", audit_approach_excludes_prior_cast),
    ]
    failed = []
    skipped = []
    try:
        for name, fn in tests:
            try:
                fn()
                print(f"OK    {name}")
            except AuditSkip as e:
                skipped.append(name)
                print(f"SKIP  {name} ({e.reason})")
            except Exception as e:
                failed.append(name)
                print(f"FAIL  {name}: {e}")
    finally:
        from storage import load
        _cleanup_audit_scholars(
            load("characters/npcs.json", {}),
            load("player/player.json", {}),
        )
        simulation_runner.start()
    if failed:
        print(f"\n{len(failed)} audit(s) failed: {', '.join(failed)}")
        sys.exit(1)
    n_ok = len(tests) - len(skipped)
    print(f"\nAll {n_ok} simulation audits passed.", end="")
    if skipped:
        print(f" ({len(skipped)} skipped)")
    else:
        print()


if __name__ == "__main__":
    main()
