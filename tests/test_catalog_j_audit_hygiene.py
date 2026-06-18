"""
Catalog J — persistence, audit hygiene, state-independent audits (priority 2).
"""

import copy

import pytest

from scripts.simulation_audit import (
    _cleanup_audit_fixtures,
    _cleanup_audit_scholars,
    _inject_audit_scholars,
    _reset_player_baseline,
    audit_confession_witness,
    audit_talk_priest_overrides_focus,
    AuditSkip,
)
from storage import load, save


@pytest.fixture
def isolated_save(tmp_path, monkeypatch):
    """Run audit helpers against an isolated save tree."""
    import storage

    for sub in ("player", "characters", "world", "rumors", "events"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))

    player = {
        "area": "test:district",
        "location": "test",
        "district": "district",
        "stats": {"health": 100, "max_health": 100, "stamina": 30, "max_stamina": 30},
        "inventory": [],
        "equipment": {"weapon": None, "armor": None, "trinket": None},
        "known_npcs": {},
        "journal": [],
    }
    areas = {"test:district": {"name": "Test District", "city": "test"}}
    npcs = {
        "soldier_a": {
            "id": "soldier_a",
            "name": "Audit Soldier",
            "role": "soldier",
            "gender": "male",
            "status": "alive",
            "area": "test:district",
            "location": "test",
            "schedule": {"home_area": "test:district"},
            "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
            "traits": {},
            "physique": {"presentation": 50},
        },
        "priest_a": {
            "id": "priest_a",
            "name": "Audit Priest",
            "role": "priest",
            "gender": "male",
            "status": "alive",
            "area": "test:district",
            "location": "test",
            "schedule": {"home_area": "test:district"},
            "stats": {"health": 80, "max_health": 80, "stamina": 20, "max_stamina": 20},
            "traits": {},
            "physique": {"presentation": 50},
        },
    }
    save("player/player.json", player)
    save("world/areas.json", areas)
    save("characters/npcs.json", npcs)
    save("world/world.json", {"day": 1, "hour": 8, "time_of_day": "morning"})
    save("rumors/rumors.json", [])
    save("events/events.json", [])
    yield tmp_path


def test_audit_fixtures_cleaned_up(isolated_save):
    npcs = load("characters/npcs.json", {})
    pl = load("player/player.json", {})
    _inject_audit_scholars(pl, npcs)
    assert "audit_scholar_a" in npcs
    pl["scene_focus"] = "audit_scholar_a"
    pl.setdefault("journal", []).append({"focus_npc": "audit_scholar_a", "action": "test"})

    _cleanup_audit_scholars(npcs, pl)
    assert "audit_scholar_a" not in npcs
    assert "audit_scholar_b" not in npcs
    assert pl.get("scene_focus") not in ("audit_scholar_a", "audit_scholar_b", "audit_priest_reloc")
    assert not any(
        (e.get("focus_npc") or "") in ("audit_scholar_a", "audit_scholar_b")
        for e in (pl.get("journal") or [])
    )


def test_audit_stand_in_cleaned_up(isolated_save):
    from storage import load, save

    npcs = load("characters/npcs.json", {})
    pl = load("player/player.json", {})
    npcs["audit_stand_in"] = {
        "id": "audit_stand_in",
        "name": "Audit Stand-in",
        "role": "merchant",
        "status": "alive",
        "area": pl.get("area"),
    }
    pl["scene_focus"] = "audit_stand_in"
    pl.setdefault("known_npcs", {})["audit_stand_in"] = {"name_known": True}
    save("characters/npcs.json", npcs)
    save("player/player.json", pl)

    _cleanup_audit_fixtures(npcs, pl)
    assert "audit_stand_in" not in load("characters/npcs.json", {})
    pl = load("player/player.json", {})
    assert pl.get("scene_focus") != "audit_stand_in"
    assert "audit_stand_in" not in (pl.get("known_npcs") or {})


def test_reset_baseline_is_deterministic(isolated_save):
    pl = load("player/player.json", {})
    pl["pending_target_clarification"] = {"kind": "attack", "options": []}
    pl["scene_focus"] = "soldier_a"
    pl["last_combat_target"] = "soldier_a"
    save("player/player.json", pl)

    _reset_player_baseline()
    pl = load("player/player.json", {})
    assert pl.get("pending_target_clarification") is None
    assert pl.get("last_combat_target") is None
    assert pl.get("journal") == []


def test_talk_priest_audit_on_isolated_world(isolated_save, monkeypatch):
    from unittest.mock import MagicMock, patch
    from scripts import simulation_audit as sa
    from simulation import simulation_runner

    simulation_runner.stop()
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = sa._mock_generate_scene
    sa.CAPTURED.clear()
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        audit_talk_priest_overrides_focus()
    last = sa.CAPTURED[-1]
    assert last["kind"] == "talk"
    assert load("characters/npcs.json", {})["priest_a"]["role"] == "priest"
    npcs = load("characters/npcs.json", {})
    assert last.get("target_id") == "priest_a" or npcs[last["target_id"]]["role"] == "priest"


def test_confession_audit_on_isolated_world(isolated_save, monkeypatch):
    from unittest.mock import MagicMock, patch
    from scripts import simulation_audit as sa
    from simulation import simulation_runner

    simulation_runner.stop()
    mock_narr = MagicMock()
    mock_narr.generate_scene.side_effect = sa._mock_generate_scene
    sa.CAPTURED.clear()
    with patch("simulation.story_loop.get_narrator", return_value=mock_narr):
        try:
            audit_confession_witness()
        except AuditSkip as exc:
            pytest.skip(str(exc))
    pl = load("player/player.json", {})
    assert pl.get("last_combat_target")
