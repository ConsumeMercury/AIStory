"""Event logger flush persistence."""

import storage


def test_flush_events_persists_under_state_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    import os
    os.makedirs(tmp_path / "events", exist_ok=True)
    storage.save("events/event_log.json", [])

    from simulation.event_logger import log_event, flush_events, load_events, all_events

    log_event("test", "player", "probe", tick=0)
    assert len(all_events()) == 1
    assert len(load_events()) == 0

    flush_events()
    assert len(load_events()) == 1

    log_event("test", "player", "second", tick=1)
    flush_events()
    assert len(load_events()) == 2
