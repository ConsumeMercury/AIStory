"""Tier 1 architecture — memory schema, consequence propagation, narrative director."""

import storage

from simulation.memory_schema import build_memory_record, compute_memory_weights, record_weights
from simulation.consequence_propagation import propagate, template_for_fatal_kill
from simulation.consequence_cascade import register_combat_consequences
from simulation.narrative_director import (
    build_dialogue_intents,
    build_dialogue_intents_block,
    plan_director_beat,
)
from simulation.story_orchestrator import prepare_beat
from simulation.memory_record import record_beat_outcome


def test_build_memory_record_has_weight_fields():
    record = build_memory_record(
        kind="attack",
        action="attack merchant",
        action_ctx={"memory_tag": "attack", "target_id": "m1"},
        tick=5,
        focal_id="m1",
        witness_ids=["m1"],
        importance=80,
        story_meaning="The outsider attacked the merchant",
    )
    assert record["id"]
    assert record.get("fact")
    assert record["emotional_weight"] >= 50
    assert record["narrative_weight"] == 80
    assert record["causal_weight"] >= 40
    assert "player" in record["participants"]


def test_compute_memory_weights_social_boost():
    talk = compute_memory_weights(kind="talk", importance=50, memory_tag="socialise")
    wait = compute_memory_weights(kind="wait", importance=50, memory_tag="general")
    assert talk["social_weight"] > wait["social_weight"]


def test_propagate_merchant_death_chain():
    player = {"area": "city:market", "pending_consequences": [], "institution_standing": {}}
    areas = {"city:market": {"state": {"prosperity": 50, "crime_level": 20, "flags": {}}}}
    institutions = {"guild1": {"type": "guild", "city": "city", "name": "Merchants Guild"}}
    target = {
        "id": "m1",
        "name": "Hadd",
        "role": "merchant",
        "status": "dead",
        "area": "city:market",
        "location": "city",
        "institution": {"id": "guild1"},
    }
    changed, trace = propagate(
        "fatal_kill_merchant",
        player=player,
        world={"day": 3},
        areas=areas,
        target_npc=target,
        institutions=institutions,
        memory_id="mem123",
        tick=10,
    )
    assert changed
    assert trace["template"] == "fatal_kill_merchant"
    assert trace["memory_id"] == "mem123"
    assert player["pending_consequences"]
    assert areas["city:market"]["state"]["prosperity"] < 50
    assert areas["city:market"]["state"]["flags"].get("trade_disrupted")
    assert player.get("emergent_hooks")


def test_template_for_fatal_kill_roles():
    assert template_for_fatal_kill({"role": "merchant"}) == "fatal_kill_merchant"
    assert template_for_fatal_kill({"role": "guard"}) == "fatal_kill_authority"
    assert template_for_fatal_kill({"role": "scholar"}) == "fatal_kill_generic"


def test_register_combat_consequences_sets_trace():
    player = {"area": "city:market", "pending_consequences": []}
    areas = {"city:market": {"state": {"prosperity": 50, "crime_level": 20}}}
    ctx = {}
    target = {"id": "m1", "name": "Hadd", "role": "merchant", "status": "dead"}
    assert register_combat_consequences(
        player, target, world={"day": 1}, areas=areas, fatal=True, action_ctx=ctx,
    )
    assert ctx.get("consequence_trace", {}).get("template") == "fatal_kill_merchant"


def test_director_suppresses_callback_on_breathe_beats():
    player = {
        "journal": [{"kind": "talk"}],
        "narrative_director": {"beats_since_callback": 0},
        "beat_memory_log": [{
            "action": "accused Solena",
            "story_meaning": "accused Solena",
            "importance": 80,
            "target_id": "s1",
            "tick": 1,
        }],
        "last_tick": 10,
    }
    scene_plan = {
        "structure_hint": "continuation",
        "must_surface": ["question one", "question two"],
        "memory_callback": {"text": "CALLBACK echo", "source": "beat_log", "score": 50},
    }
    plan = plan_director_beat(
        player, kind="wait", action_ctx={}, scene_plan=scene_plan, npcs={}, tick=10,
    )
    assert plan["pacing_mode"] == "breathe"
    assert not plan.get("memory_callback")
    assert len(plan.get("must_surface") or []) <= 1


def test_director_builds_dialogue_intents():
    npcs = {
        "s1": {
            "id": "s1",
            "name": "Solena",
            "status": "alive",
            "secrets": [{"summary": "bribed the watch"}],
        },
    }
    intents = build_dialogue_intents(
        "s1", npcs, kind="ask_about", action_ctx={"skill_check": {"success": True}}, player={"last_tick": 5},
    )
    assert intents
    assert intents[0]["goal"] in ("cooperate", "deflect", "neutral", "resist", "warm")
    block = build_dialogue_intents_block(intents)
    assert "DIALOGUE INTENT" in block
    assert "Solena" in block


def test_prepare_beat_includes_director_plan():
    player = {
        "area": "city:docks",
        "location": "city",
        "journal": [{"kind": "talk", "action": "hello"}],
        "scene_stakes": {"dramatic_question": "Who paid the watch?"},
        "starting_pipeline": {
            "area_id": "city:docks",
            "title": "Dock plot",
            "stage": 0,
            "stages": ["hook"],
            "key_npc_ids": [],
        },
    }
    ctx = {"kind": "talk", "target_id": "s1"}
    npcs = {"s1": {"id": "s1", "name": "Solena", "status": "alive", "role": "merchant"}}
    prepare_beat(player, kind="talk", action_ctx=ctx, npcs=npcs, tick=5)
    plan = ctx.get("beat_plan") or {}
    assert plan.get("director_plan", {}).get("pacing_mode")
    assert "dialogue_intent_count" in plan.get("director_plan", {})


def test_record_beat_outcome_returns_memory_id(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    for sub in ("characters", "world", "rumors"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    storage.save("characters/npcs.json", {
        "g1": {"id": "g1", "name": "Guard", "status": "alive", "traits": {}, "beliefs": []},
    })
    storage.save("world/institutions.json", {})
    storage.save("rumors/rumors.json", [])

    player = {"area": "city:docks", "location": "city", "narrative_memories": [], "legacy": []}
    ctx = {"kind": "help", "memory_tag": "help", "target_id": "g1", "skill_check": {"success": True}}
    outcome = record_beat_outcome(
        player, kind="help", action="help the guard", action_ctx=ctx, world={"day": 1},
        tick=3, focal_id="g1", focus_npcs=[{"id": "g1"}], present=[{"id": "g1"}],
    )
    assert outcome.get("memory_id")
    rec = player["beat_memory_log"][-1]
    assert rec.get("emotional_weight") is not None
    assert rec.get("fact")
