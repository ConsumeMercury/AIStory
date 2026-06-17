"""Storyline engine persistence."""

import os
import sys

import pytest

import storage


@pytest.fixture
def world_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    for sub in ("world", "player", "rumors"):
        os.makedirs(tmp_path / sub, exist_ok=True)
    return tmp_path


def test_institution_rumor_persists_without_district_storylines(world_tmp, monkeypatch):
    monkeypatch.setattr("simulation.storyline_engine.random.random", lambda: 0.0)
    monkeypatch.setattr("simulation.storyline_engine.random.randint", lambda a, b: b)

    storage.save("world/institutions.json", {
        "guild": {
            "id": "guild",
            "name": "Harbor Guild",
            "type": "guild",
            "city": "embermoor",
            "leader": "npc_leader",
            "arc": {
                "tension": 65,
                "stage": 0,
                "stages": ["Whispers of embezzlement", "Open inquiry"],
                "current": "Whispers of embezzlement",
            },
        },
    })
    storage.save("world/areas.json", {})
    storage.save("rumors/rumors.json", [])

    storage.begin_transaction()
    from simulation.storyline_engine import advance_storylines

    advance_storylines(tick=3)
    rumors = storage.load("rumors/rumors.json", [])
    assert len(rumors) == 1
    assert "Harbor Guild" in rumors[0]["text"]
    storage.commit_transaction()

    disk = storage.load("rumors/rumors.json", [])
    assert len(disk) == 1


def test_rumor_save_runs_once_per_tick(world_tmp, monkeypatch):
    monkeypatch.setattr("simulation.storyline_engine.random.random", lambda: 1.0)

    storage.save("world/institutions.json", {})
    storage.save("world/areas.json", {
        "a1": {"storyline": {"source": "district", "tension": 10, "stage": 0, "stages": ["x"]}},
        "a2": {"storyline": {"source": "district", "tension": 10, "stage": 0, "stages": ["y"]}},
    })
    storage.save("rumors/rumors.json", [{"text": "existing"}])

    saves = []
    original_save = storage.save

    def track_save(path, data):
        if path == "rumors/rumors.json":
            saves.append(len(data))
        return original_save(path, data)

    monkeypatch.setattr(storage, "save", track_save)

    storage.begin_transaction()
    from simulation.storyline_engine import advance_storylines

    advance_storylines(tick=1)
    storage.commit_transaction()

    assert saves.count(1) <= 1
