"""Save slot copy/load and transaction coherence."""

import json
import os

import storage


def test_save_and_load_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    storage.save("player/player.json", {"name": "Hero", "journal": []})

    from game.save_slots import save_slot, load_slot, list_slots

    save_slot("slot_a", label="First")
    slots = list_slots()
    assert any(s["id"] == "slot_a" for s in slots)

    storage.save("player/player.json", {"name": "Changed", "journal": [{"x": 1}]})
    load_slot("slot_a")
    assert storage.load("player/player.json")["name"] == "Hero"


def test_save_slot_copies_in_memory_transaction(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    os.makedirs(tmp_path / "saves", exist_ok=True)
    storage.save("player/player.json", {"name": "Hero", "journal": []})

    from game.save_slots import save_slot, load_slot

    storage.begin_transaction()
    storage.save("player/player.json", {"name": "InMemory", "journal": []})
    save_slot("slot_a")
    slot_path = tmp_path / "saves" / "slot_a" / "player" / "player.json"
    assert slot_path.is_file(), list(slot_path.parent.parent.glob("**/*"))
    saved = json.loads(slot_path.read_text(encoding="utf-8"))
    assert saved["name"] == "InMemory"
    storage.rollback_transaction()

    load_slot("slot_a")
    assert storage.load("player/player.json")["name"] == "InMemory"


def test_load_slot_reloads_active_transaction(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    storage.save("player/player.json", {"name": "Hero", "journal": []})

    from game.save_slots import save_slot, load_slot

    save_slot("slot_a")
    storage.begin_transaction()
    storage.save("player/player.json", {"name": "Stale", "journal": []})
    load_slot("slot_a")
    assert storage.load("player/player.json")["name"] == "Hero"
    storage.commit_transaction()
    assert storage.load("player/player.json")["name"] == "Hero"
