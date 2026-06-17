"""Tier 3 integration — emotions, planning, culture, economy, secrets, circles."""

from simulation.belief_model import update_beliefs_from_rumor
from simulation.npc_emotions import emotions_from_beat, decay_emotions, emotion_action_bias
from simulation.npc_planning import derive_subgoals, apply_plan_weights, advance_subgoal
from simulation.personality_drift import drift_from_beat
from simulation.institution_memory import record_institution_memory, record_from_player_action
from simulation.claimed_memory import record_beat_memory, sync_claim_from_actual, interrogation_directive
from simulation.secret_activity import enrich_secrets, tick_secret_exposure
from simulation.reputation_layers import build_reputation_layers, reputation_layers_block
from simulation.economy_pressure import economy_narrator_block, ripple_from_district_shock
from simulation.cultural_identity import cultural_reaction_block
from simulation.world_pressure import compute_world_pressure, world_pressure_block
from simulation.social_circles import circle_for_npc, social_circle_action_bias


def test_emotions_from_beat_and_decay():
    npc = {}
    emotions_from_beat(npc, "attack", success=True)
    assert npc["emotions"]["anger"] >= 10
    decay_emotions(npc)
    assert npc["emotions"]["anger"] <= 12


def test_npc_planning_subgoals():
    npc = {"personal_objective": {"text": "steal back a family heirloom from a fence"}}
    goals = derive_subgoals(npc)
    assert goals
    assert goals[0]["text"] == "steal"
    weights = {"plan": 5, "hide": 5, "trade": 5}
    apply_plan_weights(npc, weights)
    assert weights["plan"] > 5
    advance_subgoal(npc, "plan")
    assert npc["subgoals"][0]["progress"] >= 1


def test_institution_memory():
    institutions = {"g1": {"name": "Merchants Guild"}}
    assert record_institution_memory(
        institutions, "g1", summary="Outsider helped a member.", valence=0.5,
    )
    assert institutions["g1"]["institutional_memory"]


def test_claimed_memory_lies():
    npc = {"traits": {"greed": 90, "honesty": 10}}
    record_beat_memory(npc, "steal", "pick the pocket", tick=1)
    assert npc.get("actual_memories")
    assert npc.get("claimed_memories")
    block = interrogation_directive(npc, "ask_about")
    assert block == "" or "INTERROGATION" in block


def test_secret_enrichment():
    npc = {"secrets": [{"id": "s1", "text": "forged papers", "severity": "major"}]}
    enrich_secrets(npc)
    assert npc["secrets"][0].get("exposure_chance") is not None


def test_reputation_layers():
    player = {
        "legacy": [{"category": "kindness"}],
        "faction_standing": {"f1": {"score": 30}},
        "reputation_profile": {"heroic": 80, "honorable": 70, "violent": 10},
    }
    layers = build_reputation_layers(player)
    assert layers["local"] > 50
    block = reputation_layers_block(player)
    assert "REPUTATION SCOPE" in block


def test_economy_and_culture_blocks():
    player = {"area": "ashmoor:market", "location": "Ashmoor"}
    areas = {
        "ashmoor:market": {
            "type": "district",
            "state": {"prosperity": 30, "crime_level": 55, "mood": "declining"},
        }
    }
    econ = economy_narrator_block(player, areas)
    assert "ECONOMY" in econ
    culture = cultural_reaction_block(player, areas=areas, locations={"cities": {"Ashmoor": {"culture": ["cosmopolitan"]}}})
    assert "CULTURE" in culture


def test_world_pressure():
    areas = {
        "c:market": {
            "type": "district",
            "state": {"crime_level": 70, "mood": "desperate", "prosperity": 20},
            "storyline": {"tension": 80},
        }
    }
    data = compute_world_pressure(areas, {"global_stability": 40})
    assert data["pressure"] >= 50
    block = world_pressure_block({}, areas=areas, world={"global_stability": 40})
    assert "WORLD PRESSURE" in block


def test_social_circles():
    npcs = {
        "a": {"name": "Al", "status": "alive"},
        "b": {"name": "Bo", "status": "alive"},
    }
    rels = {"a": {"b": {"affection": 70, "trust": 65}}}
    circle = circle_for_npc("a", npcs, rels)
    assert "Bo" in circle["allies"]
    weights = {"socialise": 5, "plan": 5}
    social_circle_action_bias("a", npcs, weights, rels)
    assert weights["socialise"] > 5


def test_drift_from_beat():
    npc = {"traits": {"kindness": 50}}
    drift_from_beat(npc, "help", success=True)
    assert npc["traits"]["kindness"] >= 51
