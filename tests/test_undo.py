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
