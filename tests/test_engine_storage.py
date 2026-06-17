"""Engines must persist through the storage transaction layer."""

import json
import os

import storage


def test_faction_tick_writes_through_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "world", exist_ok=True)
    os.makedirs(tmp_path / "system", exist_ok=True)
    storage.save("system/config.json", {"enable_faction_wars": True})
    storage.save("world/factions.json", {
        "strong": {"id": "strong", "power": 80},
        "weak": {"id": "weak", "power": 10},
    })

    storage.begin_transaction()
    monkeypatch.setattr("simulation.faction_engine.random.random", lambda: 0.0)
    from simulation.faction_engine import run_faction_tick

    run_faction_tick(tick=1)
    factions = storage.load("world/factions.json", {})
    assert factions["weak"]["power"] < 10
    storage.commit_transaction()

    disk = json.loads((tmp_path / "world" / "factions.json").read_text(encoding="utf-8"))
    assert disk["weak"]["power"] == factions["weak"]["power"]


def test_spread_rumors_writes_through_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    for sub in ("system", "events", "rumors", "characters"):
        os.makedirs(tmp_path / sub, exist_ok=True)

    storage.save("system/config.json", {"enable_rumors": True})
    storage.save("events/event_log.json", [{
        "id": "evt1",
        "actor": "npc_a",
        "action": "trade",
        "tick": 1,
        "location": "docks",
    }])
    storage.save("rumors/rumors.json", [])
    storage.save("characters/npcs.json", {"npc_a": {"name": "Mira"}})

    storage.begin_transaction()
    from simulation.rumor_engine import spread_rumors

    spread_rumors()
    rumors = storage.load("rumors/rumors.json", [])
    assert len(rumors) == 1
    assert "Mira" in rumors[0]["text"]
    storage.commit_transaction()

    disk = json.loads((tmp_path / "rumors" / "rumors.json").read_text(encoding="utf-8"))
    assert len(disk) == 1
