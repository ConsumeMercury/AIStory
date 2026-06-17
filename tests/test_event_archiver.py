"""Event log archiver tests."""

import json
import os

import storage

from simulation.event_archiver import maybe_archive_events, archive_stats, _hot_cap


def _setup_tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "events", exist_ok=True)
    os.makedirs(tmp_path / "rumors", exist_ok=True)
    storage.save("rumors/rumors.json", [])


def test_archive_moves_low_importance_events(tmp_path, monkeypatch):
    _setup_tmp_storage(tmp_path, monkeypatch)
    cap = 100
    monkeypatch.setenv("AISTORY_EVENT_HOT_CAP", str(cap))

    events = []
    for i in range(150):
        events.append({
            "id": f"e{i}",
            "tick": i,
            "type": "npc_action",
            "action": f"ambient {i}",
            "importance": 10 + (i % 5),
        })
    storage.save("events/event_log.json", events)

    result = maybe_archive_events(force=True)
    assert result["archived"] >= 50
    remaining = storage.load("events/event_log.json", [])
    assert len(remaining) <= cap
    archive = storage.load("events/event_archive.json", [])
    assert archive
    assert archive[-1]["count"] == result["archived"]


def test_protected_rumor_source_not_archived(tmp_path, monkeypatch):
    _setup_tmp_storage(tmp_path, monkeypatch)
    monkeypatch.setenv("AISTORY_EVENT_HOT_CAP", "100")

    events = [
        {"id": "keep-me", "tick": 1, "type": "storyline_beat", "action": "big", "importance": 5},
        {"id": "drop-me", "tick": 2, "type": "npc_action", "action": "small", "importance": 5},
        {"id": "drop-too", "tick": 3, "type": "npc_action", "action": "small2", "importance": 5},
    ]
    storage.save("events/event_log.json", events)
    storage.save("rumors/rumors.json", [{"source_event_id": "keep-me", "text": "x"}])

    maybe_archive_events(force=True)
    remaining = {e["id"] for e in storage.load("events/event_log.json", [])}
    assert "keep-me" in remaining


def test_archive_stats_reads_counts(tmp_path, monkeypatch):
    _setup_tmp_storage(tmp_path, monkeypatch)
    storage.save("events/event_log.json", [])
    storage.save("events/event_archive.json", [{"count": 12}])
    stats = archive_stats()
    assert stats["archived_events_total"] == 12
    assert stats["hot_cap"] == _hot_cap()
