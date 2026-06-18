"""Catalog C — combat & consequence mechanics."""

from unittest.mock import patch

import pytest

from simulation.action_resolution import (
    build_combat_facts,
    build_post_combat_facts,
    resolve_combat_target,
)
from simulation.combat_engine import resolve_combat
from simulation.scene_cast import select_scene_cast
from simulation.scene_state import present_npcs_in_area
from simulation.story_loop import _do_combat
from tests.fixtures.catalog_fixtures import npc, npc_map, player
from tests.fixtures.isolated_game import bootstrap_isolated_game, run_mocked_actions


def test_attack_resolves_to_named_target_not_focus():
    merchant = npc("m1", role="merchant", name="Tomas")
    soldier = npc("s1", role="soldier", name="Solia")
    pl = player(scene_focus="s1", known_npcs={"m1": {"name_known": True}})
    target, kind = resolve_combat_target(
        "attack Tomas", pl, [merchant, soldier], npc_map(merchant, soldier), {}, "x:market", "x",
    )
    assert target["id"] == "m1"
    assert kind == "npc"


def test_attack_absent_target_fails_cleanly():
    absent = npc("away", role="guard", name="Holt")
    present_npc = npc("here", role="soldier", name="Solia")
    pl = player(scene_focus="here", known_npcs={"away": {"name_known": True}})
    target, kind = resolve_combat_target(
        "attack Holt", pl, [present_npc], {**npc_map(present_npc), **npc_map(absent)}, {}, "x", "x",
    )
    assert target is None
    assert kind is None


def test_non_fatal_attack_npc_still_speaks():
    target = npc("v1", role="guard", name="Holt")
    result = {"fatal": False, "rounds": 2, "log": []}
    facts = build_combat_facts(target, result, "npc", {})
    assert "NOT FATAL" in facts
    assert "alive" in facts.lower()
    assert "may speak" in facts.lower()


def test_fatal_combat_sets_last_combat_target(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    import storage
    from simulation import simulation_runner

    simulation_runner.stop()
    pl = storage.load("player/player.json", {})
    pl["scene_cast"] = {
        "area": pl["area"],
        "subplace": None,
        "ids": ["sold_a"],
    }
    storage.save("player/player.json", pl)

    captured, _ = run_mocked_actions(
        ["look around", "attack Valena"],
        lambda _kw: "[combat scene]",
        tick=2,
    )
    pl = storage.load("player/player.json", {})
    assert pl.get("last_combat_target") == "sold_a"
    attack_caps = [c for c in captured if (c.get("action_context") or {}).get("kind") == "attack"]
    assert attack_caps


def test_dead_npc_cannot_speak_in_post_combat_facts():
    victim = npc("v1", role="merchant", name="Hadd", status="dead")
    pl = player(last_combat_target="v1", last_combat_fatal=True)
    facts = build_post_combat_facts(pl, {"v1": victim})
    assert facts
    assert "do not speak" in facts.lower() or "does not speak" in facts.lower()


def test_dead_npc_removed_from_area_present():
    alive = npc("a1", role="guard", area="x:y", location="x")
    dead = npc("d1", role="merchant", area="x:y", location="x", status="dead")
    pl = player(area="x:y", location="x")
    present = present_npcs_in_area({**npc_map(alive), **npc_map(dead)}, pl)
    assert len(present) == 1
    assert present[0]["id"] == "a1"


def test_combat_target_must_be_present():
    pl = player(scene_focus="ghost")
    target, kind = resolve_combat_target(
        "attack ghost", pl, [], {"ghost": npc("ghost", name="Ghost")}, {}, "x", "x",
    )
    assert target is None


def test_do_combat_records_last_target():
    pl = player(stats={"health": 100, "max_health": 100, "stamina": 30, "max_stamina": 30})
    target = npc("v1", role="guard", name="Holt", stats={"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20})
    npcs = npc_map(target)
    present = [target]
    ctx = {}
    with patch("simulation.story_loop.resolve_combat") as rc:
        rc.return_value = {
            "rounds": 1, "log": [], "winner": "player", "loser": "v1",
            "fatal": False, "consequences": ["draw"], "player_injuries": [],
        }
        out = _do_combat(pl, npcs, {}, present, 1, "attack Holt", ctx)
    assert pl.get("last_combat_target") == "v1"
    assert out[1] == "v1"


def test_fatal_combat_snapshot_keeps_dead_target_in_ctx():
    dead = npc("v1", role="sailor", name="Bess", status="dead")
    pl = player(scene_focus="v1")
    ctx = {
        "kind": "attack",
        "target_id": "v1",
        "combat_snapshot": dead,
        "combat_fatal": True,
    }
    focus, _note, fid = select_scene_cast([], pl, ctx)
    assert ctx["target_id"] == "v1"
    assert focus == []
    assert fid is None
