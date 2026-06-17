"""
Confirming playtest scenarios — pins the post-v17 fixes at integration depth.

Maps to live verification checklist:
  #1 speech noun-phrase what-clauses
  #2 same-role focus stickiness
  #3 scheduled event fires on the wait action
  #4 disambiguation replays the original question
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import storage


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.fixture
def isolated_game_saves(tmp_path, monkeypatch):
    """Minimal save tree for offline story_loop runs."""
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    root = tmp_path

    area = "test:high_quarter"
    scholar_a = {
        "id": "sch_a",
        "name": "Nedkin al-Zahir",
        "role": "scholar",
        "gender": "male",
        "status": "alive",
        "area": area,
        "location": "test",
        "physique": {"build": "barrel-chested", "presentation": 50},
    }
    scholar_b = {
        "id": "sch_b",
        "name": "Zaim Suleima",
        "role": "scholar",
        "gender": "female",
        "status": "alive",
        "area": area,
        "location": "test",
        "physique": {"build": "wiry", "presentation": 55},
    }
    soldier = {
        "id": "sold_a",
        "name": "Valena Karim",
        "role": "soldier",
        "gender": "female",
        "status": "alive",
        "area": area,
        "location": "test",
        "physique": {"build": "lean", "presentation": 40},
    }

    _write_json(root / "player" / "player.json", {
        "name": "Tester",
        "age": 30,
        "area": area,
        "location": "test",
        "stats": {"health": 100, "max_health": 100, "stamina": 30, "max_stamina": 30, "stress": 0},
        "wealth": 50,
        "inventory": [],
        "equipment": {"weapon": None, "armor": None, "trinket": None},
        "known_npcs": {
            "sch_a": {"name_known": True, "seen_before": True},
            "sch_b": {"name_known": True, "seen_before": True},
            "sold_a": {"name_known": True, "seen_before": True},
        },
        "journal": [],
        "scene_focus": "sch_a",
        "scheduled_events": {},
        "story_flags": {},
        "narrator_places": {},
    })
    _write_json(root / "world" / "world_state.json", {
        "hour_count": 100,
        "hour": 3,
        "day": 5,
        "time_of_day": "deep night",
        "weather": "Rain",
        "season": "Autumn",
    })
    _write_json(root / "world" / "areas.json", {
        area: {
            "city": "test",
            "type": "district",
            "name": "High Quarter",
            "atmosphere": ["Rain on granite."],
        },
    })
    _write_json(root / "world" / "locations.json", {
        "cities": {"test": {"name": "Test City"}},
    })
    _write_json(root / "world" / "factions.json", {})
    _write_json(root / "world" / "institutions.json", {})
    _write_json(root / "characters" / "npcs.json", {
        "sch_a": scholar_a,
        "sch_b": scholar_b,
        "sold_a": soldier,
    })
    _write_json(root / "characters" / "monsters.json", {})
    _write_json(root / "characters" / "relationships.json", {})
    _write_json(root / "characters" / "memories.json", {})
    _write_json(root / "characters" / "npc_memories.json", {})
    _write_json(root / "characters" / "_mem_state.json", {})
    _write_json(root / "rumors" / "rumors.json", [])
    _write_json(root / "events" / "event_log.json", [])

    return {
        "area": area,
        "scholar_a": scholar_a,
        "scholar_b": scholar_b,
        "soldier": soldier,
    }


def _run_with_mock_narrator(actions, scene_fn):
    from simulation.story_loop import process_player_action

    captured = []
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = lambda **kw: (
        captured.append(kw) or scene_fn(kw)
    )
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        with patch("simulation.story_loop.simulation_runner.get_current_tick", return_value=1):
            with patch("simulation.story_loop.try_meta_command", return_value=None):
                scenes = []
                for action in actions:
                    scenes.append(process_player_action(action))
    return captured, scenes


def test_confirming_speech_what_noun_phrase_silent(isolated_game_saves):
    from simulation.action_interpreter import interpret_action

    player = storage.load("player/player.json", {})
    present = list(storage.load("characters/npcs.json", {}).values())
    world = storage.load("world/world_state.json", {})
    ctx = interpret_action(
        "ask the scholar what the boy found",
        player,
        present,
        world,
    )
    assert ctx["kind"] == "ask_about"
    assert ctx.get("player_speech") is None


def test_confirming_same_role_focus_across_beats(isolated_game_saves):
    player = storage.load("player/player.json", {})
    player["journal"] = [{"focus_npc": "sch_a", "kind": "talk", "area": isolated_game_saves["area"]}]
    storage.save("player/player.json", player)

    captured, _ = _run_with_mock_narrator(
        [
            "Ask the scholar about the archives",
            "Wait until dawn",
            "Ask the scholar about the preface",
        ],
        lambda _kw: "[scene]",
    )
    focal_ids = [c.get("focal_npc_id") for c in captured]
    target_ids = [(c.get("action_context") or {}).get("target_id") for c in captured]
    assert all(fid == "sch_a" for fid in focal_ids if fid), focal_ids
    assert all(tid == "sch_a" for tid in target_ids if tid), target_ids


def test_confirming_scheduled_event_fires_on_wait_action(isolated_game_saves):
    area = isolated_game_saves["area"]

    def scene_fn(kw):
        action = (kw.get("player_action") or "").lower()
        if "scholar" in action and "wait" not in action:
            return (
                "He nods toward the chute.\n"
                "[SCHEDULE: coal_chute_entry | the junior boys enter through the coal-chutes | +2h]"
            )
        return "[scene after wait]"

    captured, scenes = _run_with_mock_narrator(
        [
            "Ask the scholar about the back way",
            "Wait for the junior boys to enter through the coal-chutes",
        ],
        scene_fn,
    )
    player = storage.load("player/player.json", {})
    store = player.get("scheduled_events", {}).get(area, {})
    assert store, "promise should be recorded in player state"
    wait_capture = captured[-1]
    ctx = wait_capture.get("action_context") or {}
    assert ctx.get("events_fired") or "SCHEDULED EVENT FIRED" in (ctx.get("story_directive") or "")
    assert "[SCHEDULE:" not in (scenes[0] or "")


def test_confirming_disambiguation_replays_original_question(isolated_game_saves):
    player = storage.load("player/player.json", {})
    player["scene_focus"] = None
    player["pending_target_clarification"] = {
        "kind": "ask_about",
        "reason": "more than one person matches that pronoun",
        "original_action": "ask her if she is related to the dead master",
        "options": [
            {"id": "sch_b", "label": "Zaim Suleima (scholar)", "chip": "ask Zaim"},
            {"id": "sold_a", "label": "Valena Karim (soldier)", "chip": "ask Valena"},
        ],
    }
    storage.save("player/player.json", player)

    captured, _ = _run_with_mock_narrator(["Zaim Suleima"], lambda _kw: "[answer scene]")
    assert captured, "expected narrator call"
    kw = captured[-1]
    ctx = kw.get("action_context") or {}
    assert ctx.get("target_id") == "sch_b"
    assert ctx.get("clarification_resolved")
    assert "CLARIFICATION RESOLVED" in (ctx.get("story_directive") or "")
    assert kw.get("player_action") == "ask her if she is related to the dead master"
    player = storage.load("player/player.json", {})
    assert player.get("scene_focus") == "sch_b"
    assert player.get("pending_target_clarification") is None
