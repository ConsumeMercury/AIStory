"""Temporal grounding — named wait targets, scheduled events, dialogue places."""

from simulation.world_clock import (
    parse_named_time_target,
    hours_until_hour,
    resolve_wait_advance,
    HOURS_PER_DAY,
)
from simulation.scheduled_events import (
    extract_event_promises,
    record_scheduled_events,
    parse_wait_for_event,
    hours_until_event,
    fire_due_events,
)
from simulation.local_places import (
    _promote_from_journal_query,
    _destination_query,
    resolve_local_movement,
)
from simulation.beat_structure import classify_beat_structure


def test_parse_wait_until_dawn_from_deep_night():
    named = parse_named_time_target("Wait until dawn")
    assert named
    label, target_hour = named
    assert label == "dawn"
    assert target_hour == 5
    assert hours_until_hour(3, 5) == 2
    assert hours_until_hour(22, 5) == 7


def test_resolve_wait_until_dawn_advances_correct_hours():
    world = {"hour_count": 100, "hour": 3, "time_of_day": "deep night"}
    player = {"scheduled_events": {}}
    result = resolve_wait_advance("Wait until dawn", world, player, "city:market")
    assert not result["refused"]
    assert result["hours"] == 2
    assert result["target_label"] == "dawn"


def test_wait_for_unscheduled_toll_refuses():
    world = {"hour_count": 50, "hour": 10, "time_of_day": "morning"}
    player = {"scheduled_events": {"city:market": {}}}
    result = resolve_wait_advance("Wait for the third toll", world, player, "city:market")
    assert result["refused"]
    assert result["hours"] == 0


def test_scheduled_event_records_and_wait_advances_to_it():
    player = {"scheduled_events": {}}
    world = {"hour_count": 10, "hour": 10}
    scene = 'She says, "Wait for the third toll of the bell before you go behind the wall."'
    assert record_scheduled_events(player, scene, "city:market", world)
    event = parse_wait_for_event("Wait for the third toll", player, "city:market")
    assert event
    assert event["fires_at_hour"] == 13
    hrs = hours_until_event(event, world)
    assert hrs == 3
    result = resolve_wait_advance("Wait for the third toll", world, player, "city:market")
    assert result["hours"] == 3
    world["hour_count"] = 13
    fired = fire_due_events(player, world, "city:market")
    assert len(fired) == 1
    assert fired[0]["id"] == "third_toll"


def test_dialogue_place_promoted_from_journal():
    player = {
        "area": "city:market",
        "journal": [{
            "area": "city:market",
            "scene": 'The copyist whispers, "Meet the buyers behind the wall at the third toll."',
            "excerpt": "behind the wall",
        }],
        "story_flags": {},
        "narrator_places": {},
    }
    query = _destination_query("Go behind the wall to the buyers")
    assert query
    promoted = _promote_from_journal_query(query, player, "city:market")
    assert promoted
    sub, msg = resolve_local_movement("Go behind the wall to the buyers", player, "city:market")
    assert sub
    assert "wall" in sub["label"].lower()
    assert player.get("scene_subplace")


def test_wait_no_change_classifies_stalled():
    mode = classify_beat_structure(
        "wait",
        {"wait_no_change": True},
        {},
        [{"area": "city:market", "excerpt": "prior beat"}],
        "city:market",
        None,
    )
    assert mode == "stalled"


def test_bare_wait_uses_default_hours():
    world = {"hour_count": 0, "hour": 8, "time_of_day": "morning"}
    result = resolve_wait_advance("Wait and watch", world, {}, "city:market")
    assert not result["refused"]
    assert result["hours"] == 2
