"""Tests for unified memory record and hierarchical simulation tiers."""

import storage

from simulation.memory_record import record_beat_outcome
from simulation.memory_index import retrieve_memories_for_beat
from simulation.sim_tiers import (
    hierarchical_npc_sample,
    partition_by_tier,
    run_abstract_regional_pulse,
    tier_for_npc,
)


def test_record_beat_outcome_writes_canonical_log(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    for sub in ("characters", "world"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    storage.save("characters/npcs.json", {
        "g1": {"id": "g1", "name": "Guard", "status": "alive", "traits": {}, "beliefs": []},
    })
    storage.save("world/institutions.json", {})

    player = {"area": "city:docks", "location": "city", "narrative_memories": []}
    world = {"day": 2}
    ctx = {"kind": "attack", "memory_tag": "attack", "target_id": "g1", "skill_check": {"success": True}}
    evt = {
        "id": "e1",
        "type": "player_interaction",
        "actor": "player",
        "action": "attack",
        "target": "g1",
        "effects": ["attack"],
        "importance": 80,
    }
    outcome = record_beat_outcome(
        player,
        kind="attack",
        action="attack the guard",
        action_ctx=ctx,
        world=world,
        tick=10,
        focal_id="g1",
        focus_npcs=[{"id": "g1"}],
        present=[{"id": "g1"}],
        interaction_event=evt,
    )
    assert outcome["target_live"]
    assert player.get("beat_memory_log")
    assert player["beat_memory_log"][-1]["kind"] == "attack"
    assert storage.load("characters/npc_memories.json", {}).get("g1")
    npc = storage.load("characters/npcs.json", {})["g1"]
    assert npc.get("beliefs") or npc.get("actual_memories")


def test_memory_index_reads_beat_log():
    player = {
        "beat_memory_log": [{
            "id": "b1",
            "action": "accused the dockmaster of forgery",
            "story_meaning": "The outsider accused the dockmaster of forgery",
            "importance": 85,
            "target_id": "dock1",
        }],
        "narrative_memories": [],
    }
    hits = retrieve_memories_for_beat(
        [], "forgery dockmaster", limit=5, player=player, focal_npc_id="dock1",
    )
    assert any(h.get("type") == "beat_memory" for h in hits)


def test_tier_partition():
    player = {"area": "city:docks", "location": "city"}
    npcs = {
        "a": {"area": "city:docks", "location": "city"},
        "b": {"area": "city:market", "location": "city"},
        "c": {"area": "far:wild", "location": "far"},
    }
    tiers = partition_by_tier(list(npcs), npcs, player)
    assert "a" in tiers[1]
    assert "b" in tiers[2]
    assert "c" in tiers[3]
    assert tier_for_npc(npcs["a"], player) == 1


def test_hierarchical_sample_prefers_local_district():
    player = {"area": "city:docks", "location": "city"}
    npcs = {f"n{i}": {"area": f"city:d{i}", "location": "city", "status": "alive"} for i in range(6)}
    for i in range(4):
        npcs[f"local{i}"] = {"area": "city:docks", "location": "city", "status": "alive"}
    weights = {nid: 10.0 for nid in npcs}
    active, pulse = hierarchical_npc_sample(list(npcs), npcs, player, weights, 5)
    assert len(active) == 5
    local_picks = sum(1 for nid in active if npcs[nid].get("area") == "city:docks")
    assert local_picks >= 2


def test_abstract_regional_pulse(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "events").mkdir(parents=True, exist_ok=True)
    storage.save("events/event_log.json", [])
    npcs = {
        "d1": {"status": "alive", "location": "far", "stats": {"health": 10, "max_health": 80, "stamina": 5, "max_stamina": 20}},
        "d2": {"status": "alive", "location": "far", "stats": {"health": 10, "max_health": 80, "stamina": 5, "max_stamina": 20}},
    }
    touched = run_abstract_regional_pulse(["d1", "d2"], npcs, tick=3, limit=2)
    assert touched >= 1
    from simulation.event_logger import flush_events
    flush_events()
    events = storage.load("events/event_log.json", [])
    assert events
