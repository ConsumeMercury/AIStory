"""Undo last turn snapshot."""

import storage


def test_undo_restores_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    import os
    os.makedirs(tmp_path / "player", exist_ok=True)

    from game.undo import push_undo_snapshot, undo_last_turn, can_undo

    storage.save("player/player.json", {
        "name": "Hero",
        "journal": [{"action": "look around"}],
    })
    storage.begin_transaction()
    push_undo_snapshot()
    player = storage.load("player/player.json")
    player = dict(player)
    player["journal"] = list(player.get("journal") or [])
    player["journal"].append({"action": "attack"})
    storage.save("player/player.json", player)
    storage.commit_transaction()

    assert can_undo()
    restored = undo_last_turn()
    assert len(restored["journal"]) == 1


def test_undo_restores_npc_state(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    import os
    os.makedirs(tmp_path / "player", exist_ok=True)
    os.makedirs(tmp_path / "characters", exist_ok=True)

    from game.undo import push_undo_snapshot, undo_last_turn

    storage.save("player/player.json", {
        "name": "Hero",
        "journal": [{"action": "look around"}],
    })
    storage.save("characters/npcs.json", {
        "n1": {"id": "n1", "name": "Alive", "status": "alive"},
    })

    storage.begin_transaction()
    push_undo_snapshot()
    player = storage.load("player/player.json")
    player = dict(player)
    player["journal"] = list(player.get("journal") or [])
    player["journal"].append({"action": "attack"})
    storage.save("player/player.json", player)
    npcs = storage.load("characters/npcs.json")
    npcs = dict(npcs)
    npcs["n1"] = dict(npcs["n1"])
    npcs["n1"]["status"] = "dead"
    storage.save("characters/npcs.json", npcs)
    storage.commit_transaction()

    undo_last_turn()
    assert storage.load("characters/npcs.json")["n1"]["status"] == "alive"
    assert len(storage.load("player/player.json")["journal"]) == 1
