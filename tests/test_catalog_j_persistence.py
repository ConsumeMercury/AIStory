"""Catalog J (persistence) — save hygiene, undo, archiver, concurrency."""

import json
import os
import threading

import pytest
import storage

from simulation.event_archiver import maybe_archive_events
from simulation.locks import get_action_turn_lock


def test_atomic_write_no_partial_save(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    path = tmp_path / "player" / "player.json"
    storage.save("player/player.json", {"name": "Hero", "journal": []})
    raw = path.read_text(encoding="utf-8")
    json.loads(raw)
    assert not list(tmp_path.rglob("*.tmp"))


def test_undo_restores_prior_state(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    from game.undo import can_undo, push_undo_snapshot, undo_last_turn

    storage.save("player/player.json", {"name": "Hero", "journal": [{"action": "look"}]})
    storage.begin_transaction()
    push_undo_snapshot()
    pl = storage.load("player/player.json", {})
    pl = dict(pl)
    pl["journal"] = list(pl["journal"]) + [{"action": "attack"}]
    storage.save("player/player.json", pl)
    storage.commit_transaction()
    assert can_undo()
    restored = undo_last_turn()
    assert len(restored["journal"]) == 1


def test_event_archiver_fires_at_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "events", exist_ok=True)
    os.makedirs(tmp_path / "rumors", exist_ok=True)
    os.makedirs(tmp_path / "player", exist_ok=True)
    monkeypatch.setenv("AISTORY_EVENT_HOT_CAP", "100")
    storage.save("rumors/rumors.json", [])
    storage.save("player/player.json", {})
    events = [
        {"id": f"e{i}", "tick": i, "type": "npc_action", "action": f"a{i}", "importance": 5}
        for i in range(150)
    ]
    storage.save("events/event_log.json", events)
    result = maybe_archive_events(force=True)
    assert result["archived"] >= 30
    remaining = storage.load("events/event_log.json", [])
    assert len(remaining) <= 100


def test_archived_events_still_retrievable(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "events", exist_ok=True)
    os.makedirs(tmp_path / "rumors", exist_ok=True)
    os.makedirs(tmp_path / "player", exist_ok=True)
    monkeypatch.setenv("AISTORY_EVENT_HOT_CAP", "100")
    storage.save("rumors/rumors.json", [])
    storage.save("player/player.json", {})
    storage.save("events/event_log.json", [
        {"id": f"e{i}", "tick": i, "type": "npc_action", "action": f"a{i}", "importance": 10 + (i % 5)}
        for i in range(150)
    ])
    result = maybe_archive_events(force=True)
    assert result["archived"] >= 50
    archive = storage.load("events/event_archive.json", [])
    assert archive


def test_player_turn_and_sim_tick_dont_race():
    lock = get_action_turn_lock()
    holder = []

    def hold_lock():
        with lock:
            holder.append("held")
            import time
            time.sleep(0.05)

    def try_lock():
        if lock.acquire(blocking=False):
            holder.append("stolen")
            lock.release()

    t1 = threading.Thread(target=hold_lock)
    t2 = threading.Thread(target=try_lock)
    t1.start()
    import time
    time.sleep(0.01)
    t2.start()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert "held" in holder
    assert "stolen" not in holder
