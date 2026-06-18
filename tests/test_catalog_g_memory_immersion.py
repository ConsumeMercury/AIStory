"""
Catalog G — memory immersion extensions.
"""

import storage

from simulation.memory_immersion import (
    effective_salience,
    maybe_append_gossip_rumor,
    surface_memory_limit,
)
from simulation.memory_index import retrieve_memories_for_beat
from simulation.npc_memory_engine import record_player_action


def test_witness_valence_diluted_vs_target(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    record_player_action(
        ["target", "witness"],
        "attack",
        "struck them",
        "city:market",
        tick=5,
        day=1,
        target_id="target",
    )
    mems = storage.load("characters/npc_memories.json", {})
    target_val = abs(mems["target"][0]["valence"])
    witness_val = abs(mems["witness"][0]["valence"])
    assert witness_val < target_val
    assert witness_val <= target_val * 0.36


def test_salience_decays_over_ticks():
    mem = {"salience": 50, "valence": -0.5, "tick": 10}
    assert effective_salience(mem, 10) > effective_salience(mem, 80)


def test_trivial_memory_drops_below_threshold():
    mem = {"salience": 5, "valence": 0.0, "tick": 1}
    assert effective_salience(mem, 200) < 8


def test_high_salience_memory_persists():
    mem = {"salience": 90, "valence": -0.8, "tick": 10}
    trivial = {"salience": 5, "valence": 0.0, "tick": 10}
    at_100 = effective_salience(mem, 100)
    assert at_100 > effective_salience(trivial, 100)
    assert effective_salience(mem, 10) > at_100


def test_gossip_respects_salience_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "rumors").mkdir(parents=True, exist_ok=True)
    storage.save("rumors/rumors.json", [])
    low = maybe_append_gossip_rumor(
        {"location": "city"},
        {"summary": "minor glance", "valence": -0.1, "salience": 20},
        tick=1,
    )
    assert low is None
    high = maybe_append_gossip_rumor(
        {"location": "city"},
        {"summary": "violent assault", "valence": -0.9, "salience": 80},
        tick=2,
    )
    assert high


def test_memory_not_over_surfaced():
    events = [
        {"type": "player_action", "actor": "player", "action": f"evt {i}", "id": f"e{i}"}
        for i in range(20)
    ]
    pl = {"beat_memory_log": [], "narrative_memories": [], "last_tick": 50}
    routine = retrieve_memories_for_beat(events, "hello", limit=20, player=pl, kind="talk")
    assert len(routine) <= surface_memory_limit("talk")
    investigative = retrieve_memories_for_beat(
        events, "clues", limit=20, player=pl, kind="investigate",
    )
    assert len(investigative) <= surface_memory_limit("investigate")


def test_subjective_memory_is_first_person_for_target(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    record_player_action(
        ["target", "witness"], "attack", "struck them in the alley",
        "city:market", tick=5, day=1, target_id="target",
    )
    mems = storage.load("characters/npc_memories.json", {})
    assert "I remember" in mems["target"][0]["summary"] or "struck" in mems["target"][0]["summary"].lower()
    assert "saw the outsider" in mems["witness"][0]["summary"]


def test_subjective_memory_is_humanized_not_raw_command(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    record_player_action(
        ["target"],
        "socialise",
        "Talk to the woman",
        "city:market",
        tick=8,
        day=1,
        target_id="target",
        kind="talk",
    )
    mems = storage.load("characters/npc_memories.json", {})
    summary = mems["target"][0]["summary"]
    assert "Talk to the woman" not in summary
    assert "approached" in summary.lower()


def test_memory_callback_surfaces_on_return():
    from simulation.memory_immersion import pick_memory_callback

    player = {
        "journal": [{"action": "left", "kind": "withdraw"}],
        "beat_memory_log": [{
            "action": "accused Solena of hiding the girl",
            "story_meaning": "The outsider accused Solena",
            "importance": 85,
            "target_id": "s1",
            "tick": 5,
        }],
        "last_tick": 30,
    }
    cb = pick_memory_callback(
        player, "s1", kind="talk", action_ctx={},
        current_tick=30, npcs={"s1": {"name": "Solena"}},
    )
    assert cb


def test_memory_changes_relationship_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    (tmp_path / "characters").mkdir(parents=True, exist_ok=True)
    storage.save("characters/relationships.json", {})
    from simulation.relationship_engine import apply_player_action_relationship

    apply_player_action_relationship("threaten", "s1")
    rels = storage.load("characters/relationships.json", {})
    assert rels["s1"]["player"]["fear"] > 0


def test_memory_behavior_directive_reflects_valence(monkeypatch):
    import simulation.npc_memory_engine as nme
    from simulation.npc_memory_engine import memory_behavior

    def fake_load(path, default=None):
        if path == nme.MEM_FILE:
            return {"s1": [{
                "summary": "the outsider threatened them",
                "valence": -0.9,
                "salience": 70,
                "tick": 1,
                "about_player": True,
            }]}
        return default if default is not None else {}

    monkeypatch.setattr(nme, "load", fake_load)
    directive = memory_behavior("s1")
    assert directive
    lowered = directive.lower()
    assert "hostility" in lowered or "fear" in lowered or "cold refusal" in lowered


def test_gossip_propagates_to_social_circle(monkeypatch):
    from simulation.memory_immersion import propagate_social_memory_gossip

    monkeypatch.setattr(
        "simulation.social_circles.circle_for_npc",
        lambda _nid, _npcs: {"allies": ["ally1"]},
    )
    world = {"information_packets": []}
    player = {"area": "city:market", "location": "city"}
    npcs = {
        "v1": {"id": "v1", "name": "Solena", "role": "merchant", "status": "alive"},
        "ally1": {"id": "ally1", "name": "Mira", "role": "merchant", "status": "alive"},
    }
    mem = {"summary": "the outsider attacked them", "valence": -0.8, "salience": 70, "tick": 10}
    pkt = propagate_social_memory_gossip(
        world, player, "v1", mem, tick=20, day=2, npcs=npcs,
    )
    assert pkt is not None or world.get("information_packets")
