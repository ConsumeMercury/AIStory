"""Catalog F — scheduled events & temporal grounding."""

import os

import storage

from simulation.fact_gate import validate_schedule_emission
from simulation.scheduled_events import (
    parse_schedule_tags,
    record_scheduled_events,
    strip_schedule_tags,
)
from simulation.world_clock import advance_clock, resolve_wait_advance
from tests.fixtures.isolated_game import bootstrap_isolated_game, run_mocked_actions


def test_schedule_promised_emits_tag():
    scene = (
        'He nods toward the chute.\n'
        '[SCHEDULE: coal_chute_entry | the junior boys enter through the coal-chutes | +2h]\n'
    )
    tags = parse_schedule_tags(scene)
    assert tags
    assert tags[0]["id"] == "coal_chute_entry"


def test_wait_until_named_time_resolves():
    world = {"hour_count": 100, "hour": 3, "time_of_day": "deep night"}
    pl = {"scheduled_events": {}}
    result = resolve_wait_advance("Wait until dawn", world, pl, "city:market")
    assert not result["refused"]
    assert result["hours"] == 2
    assert result["target_label"] == "dawn"


def test_schedule_untagged_is_flagged():
    scene = 'She says, "Wait for the third toll before you go behind the wall."'
    assert validate_schedule_emission(scene)


def test_time_advances_monotonically(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "world", exist_ok=True)
    storage.save("world/world_state.json", {"hour_count": 10, "hour": 10, "day": 1})
    before = storage.load("world/world_state.json", {})["hour_count"]
    advanced = advance_clock(3)
    assert advanced["hour_count"] > before


def test_schedule_fires_on_wait_integration(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    area = storage.load("player/player.json", {})["area"]

    def scene_fn(kw):
        action = (kw.get("player_action") or "").lower()
        if "scholar" in action and "wait" not in action:
            return (
                "He nods.\n"
                "[SCHEDULE: coal_chute_entry | the junior boys enter through the coal-chutes | +2h]"
            )
        return "[after wait]"

    run_mocked_actions(
        ["Ask the scholar about the back way", "Wait for the junior boys to enter through the coal-chutes"],
        scene_fn,
    )
    pl = storage.load("player/player.json", {})
    assert pl.get("scheduled_events", {}).get(area)
    last = (pl.get("journal") or [])[-1]
    assert last.get("kind") == "wait"


def test_record_scheduled_events_strips_tags_from_player_view():
    pl = {"scheduled_events": {}}
    world = {"hour_count": 10, "hour": 10}
    scene = '[SCHEDULE: toll | third toll | +3h]\nThe bell waits.'
    record_scheduled_events(pl, scene, "city:market", world)
    cleaned = strip_schedule_tags(scene)
    assert "[SCHEDULE:" not in cleaned
