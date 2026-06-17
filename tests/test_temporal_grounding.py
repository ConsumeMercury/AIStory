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
    parse_schedule_tags,
    strip_schedule_tags,
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


def test_schedule_tag_records_tide_bell_promise():
    player = {"scheduled_events": {}}
    world = {"hour_count": 20, "hour": 20}
    scene = (
        'He says the crews start when the tide-bell rings twice.\n'
        "[SCHEDULE: tide_bell_twice | the tide-bell rings twice | +2h]"
    )
    assert record_scheduled_events(player, scene, "city:wharf", world)
    event = parse_wait_for_event("Wait for the tide-bell to ring twice", player, "city:wharf")
    assert event
    assert event["id"] == "tide_bell_twice"
    assert event["fires_at_hour"] == 22
    assert strip_schedule_tags(scene) == "He says the crews start when the tide-bell rings twice."


def test_schedule_tag_two_part_form():
    tags = parse_schedule_tags("[SCHEDULE: the morning crews arrive | +3h]")
    assert len(tags) == 1
    assert tags[0]["hours_from_now"] == 3
    assert "morning crews" in tags[0]["label"].lower()


def test_coal_chute_promise_records_and_matches_wait():
    player = {"scheduled_events": {}}
    world = {"hour_count": 10, "hour": 10}
    scene = (
        'He whispers that the junior boys go in through the back by the coal-chutes '
        "before the bells even ring."
    )
    assert record_scheduled_events(player, scene, "city:high_quarter", world)
    event = parse_wait_for_event(
        "Wait for the junior boys to enter through the coal-chutes",
        player,
        "city:high_quarter",
    )
    assert event
    assert "chute" in event["label"].lower()
    result = resolve_wait_advance(
        "Wait for the junior boys to enter through the coal-chutes",
        world,
        player,
        "city:high_quarter",
    )
    assert not result["refused"]
    assert result["hours"] == 2
    assert result.get("event")


def test_wait_until_dawn_updates_time_of_day():
    from simulation.world_clock import advance_clock, _recompute

    world = {"hour_count": 99, "hour": 3, "time_of_day": "deep night", "day": 5}
    save_backup = world.copy()
    result = resolve_wait_advance("Wait until dawn", world, {}, "city:market")
    assert result["hours"] == 2
    world["hour_count"] = save_backup["hour_count"] + result["hours"]
    _recompute(world)
    assert world["hour"] == 5
    assert world["time_of_day"] == "dawn"
