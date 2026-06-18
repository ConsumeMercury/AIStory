"""Memory immersion — subjective POV, decay, callbacks, consequences."""

import storage

from simulation.memory_immersion import (
    absorb_npc_memories_into_reputation,
    effective_salience,
    format_subjective_line,
    maybe_append_gossip_rumor,
    pick_memory_callback,
    score_at_retrieval,
    subjective_memory_lines,
)
from simulation.memory_index import retrieve_memories_for_beat
from simulation.memory_record import record_beat_outcome
from simulation.npc_memory_engine import record_player_action


def test_effective_salience_decays_with_age():
    fresh = {"salience": 50, "valence": -0.8, "tick": 100}
    old = {"salience": 50, "valence": -0.8, "tick": 10}
    assert effective_salience(fresh, 100) > effective_salience(old, 100)


def test_subjective_line_includes_valence_tone():
    line = format_subjective_line(
        {"summary": "the outsider attacked them", "valence": -0.9},
        "Solena",
    )
    assert "Solena" in line
    assert "hostile" in line or "raw" in line or "guarded" in line


def test_record_player_action_writes_subjective_target_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    record_player_action(
        ["s1"], "attack", "ask about the missing girl",
        "city:market", tick=5, day=1, target_id="s1",
    )
    mems = storage.load("characters/npc_memories.json", {}).get("s1", [])
    assert mems
    assert any("remember" in m.get("summary", "").lower() for m in mems)


def test_pick_memory_callback_from_beat_log():
    player = {
        "journal": [{"action": "prior"}],
        "beat_memory_log": [{
            "action": "accused Solena of hiding the girl",
            "story_meaning": "The outsider accused Solena of hiding the girl",
            "importance": 80,
            "target_id": "s1",
            "tick": 8,
        }],
        "last_tick": 20,
    }
    cb = pick_memory_callback(
        player, "s1", kind="talk", action_ctx={"beat_plan": {"memory_query": "Solena girl"}},
        current_tick=20, npcs={"s1": {"name": "Solena"}},
    )
    assert cb
    assert "CALLBACK" in cb["text"] or "Solena" in cb["text"]


def test_score_at_retrieval_penalizes_old_beats():
    player = {"beat_memory_log": []}
    fresh = {"importance": 60, "story_meaning": "met the guard", "tick": 90}
    old = {"importance": 60, "story_meaning": "met the guard", "tick": 5}
    assert score_at_retrieval(fresh, player=player, current_tick=100) > score_at_retrieval(
        old, player=player, current_tick=100,
    )


def test_retrieve_memories_caps_surface_count():
    events = [
        {"type": "player_action", "actor": "player", "action": f"event {i}", "id": f"e{i}"}
        for i in range(12)
    ]
    player = {"beat_memory_log": [], "narrative_memories": [], "last_tick": 50}
    hits = retrieve_memories_for_beat(
        events, "event", limit=20, player=player, kind="talk",
    )
    assert len(hits) <= 2


def test_absorb_npc_memories_into_reputation(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    storage.save("characters/npc_memories.json", {
        "g1": [{
            "summary": "the outsider attacked them",
            "valence": -0.9,
            "salience": 70,
            "tick": 10,
            "about_player": True,
        }],
    })
    storage.save("rumors/rumors.json", [])
    storage.save("characters/relationships.json", {})
    player = {"legacy": [], "story_flags": {}, "last_tick": 20}
    profile = absorb_npc_memories_into_reputation(player)
    assert profile["violent"] > 15


def test_record_beat_outcome_updates_reputation(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    for sub in ("characters", "world", "rumors"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    storage.save("characters/npcs.json", {
        "g1": {"id": "g1", "name": "Guard", "status": "alive", "traits": {}, "beliefs": []},
    })
    storage.save("world/institutions.json", {})
    storage.save("rumors/rumors.json", [])

    player = {"area": "city:docks", "location": "city", "narrative_memories": [], "legacy": []}
    world = {"day": 2}
    ctx = {"kind": "attack", "memory_tag": "attack", "target_id": "g1", "skill_check": {"success": True}}
    evt = {
        "id": "e1", "type": "player_interaction", "actor": "player",
        "action": "attack", "target": "g1", "effects": ["attack"], "importance": 80,
    }
    record_beat_outcome(
        player, kind="attack", action="attack guard", action_ctx=ctx, world=world,
        tick=10, focal_id="g1", focus_npcs=[{"id": "g1"}], present=[{"id": "g1"}],
        interaction_event=evt,
    )
    assert player.get("reputation_profile")
    assert player["reputation_profile"]["violent"] > 15


def test_gossip_rumor_from_salient_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "rumors").mkdir(parents=True, exist_ok=True)
    storage.save("rumors/rumors.json", [])
    player = {"location": "city"}
    mem = {"summary": "the outsider attacked them", "valence": -0.9, "salience": 80}
    text = maybe_append_gossip_rumor(player, mem, tick=5)
    assert text
    rumors = storage.load("rumors/rumors.json", [])
    assert rumors


def test_subjective_memory_lines_for_focal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    storage.save("characters/npc_memories.json", {
        "s1": [{
            "summary": "I remember when the outsider asked about the girl",
            "valence": -0.2,
            "salience": 45,
            "tick": 15,
            "about_player": True,
        }],
    })
    lines = subjective_memory_lines(
        "s1", {"s1": {"name": "Solena"}}, current_tick=20,
    )
    assert lines
    assert "Solena" in lines[0]
