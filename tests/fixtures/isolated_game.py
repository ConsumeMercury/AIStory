"""Minimal isolated save tree for catalog integration tests."""

import json
import os
from unittest.mock import MagicMock, patch

import storage


def write_json(root, relpath, data):
    path = root / relpath.replace("/", os.sep)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def bootstrap_isolated_game(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    area = "test:high_quarter"
    scholar_a = {
        "id": "sch_a",
        "name": "Nedkin al-Zahir",
        "role": "scholar",
        "gender": "male",
        "status": "alive",
        "area": area,
        "location": "test",
        "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
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
        "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
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
        "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
        "physique": {"build": "lean", "presentation": 40},
    }
    merchant = {
        "id": "merch_a",
        "name": "Tomas Reed",
        "role": "merchant",
        "gender": "male",
        "status": "alive",
        "area": area,
        "location": "test",
        "wealth": 40,
        "inventory": [{
            "id": "blade1",
            "name": "Notched Blade",
            "category": "weapon",
            "type": "sword",
            "value": 20,
        }],
        "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
        "physique": {"presentation": 50},
    }

    write_json(tmp_path, "player/player.json", {
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
            "merch_a": {"name_known": True, "seen_before": True},
        },
        "journal": [],
        "scene_focus": "sch_a",
        "scheduled_events": {},
        "story_flags": {},
        "narrator_places": {},
        "narrator_items": {},
    })
    write_json(tmp_path, "world/world_state.json", {
        "hour_count": 100,
        "hour": 3,
        "day": 5,
        "time_of_day": "deep night",
        "weather": "Rain",
        "season": "Autumn",
    })
    write_json(tmp_path, "world/areas.json", {
        area: {"city": "test", "type": "district", "name": "High Quarter", "atmosphere": ["Rain."]},
    })
    write_json(tmp_path, "world/locations.json", {"cities": {"test": {"name": "Test City"}}})
    write_json(tmp_path, "world/factions.json", {})
    write_json(tmp_path, "world/institutions.json", {})
    write_json(tmp_path, "characters/npcs.json", {
        "sch_a": scholar_a,
        "sch_b": scholar_b,
        "sold_a": soldier,
        "merch_a": merchant,
    })
    write_json(tmp_path, "characters/monsters.json", {})
    write_json(tmp_path, "characters/relationships.json", {})
    write_json(tmp_path, "characters/memories.json", {})
    write_json(tmp_path, "characters/npc_memories.json", {})
    write_json(tmp_path, "characters/_mem_state.json", {})
    write_json(tmp_path, "rumors/rumors.json", [])
    write_json(tmp_path, "events/event_log.json", [])

    return {
        "area": area,
        "scholar_a": scholar_a,
        "scholar_b": scholar_b,
        "soldier": soldier,
        "merchant": merchant,
    }


def run_mocked_actions(actions, scene_fn, *, tick=1):
    from simulation.story_loop import process_player_action

    captured = []
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = lambda **kw: (
        captured.append(kw) or scene_fn(kw)
    )
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        with patch("simulation.story_loop.simulation_runner.get_current_tick", return_value=tick):
            with patch("simulation.story_loop.try_meta_command", return_value=None):
                scenes = [process_player_action(a) for a in actions]
    return captured, scenes
