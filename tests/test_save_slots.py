"""Save slot copy/load."""

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
