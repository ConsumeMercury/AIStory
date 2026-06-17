"""Tests for sim priorities, consequence cascades, and journal retention."""

from simulation.sim_priorities import build_sim_priorities, npc_tick_multiplier, rumor_spread_threshold
from simulation.consequence_cascade import register_combat_consequences, register_from_causal_link
from simulation.journal_retention import trim_journal
from simulation.importance_router import score_journal_entry, score_event
from simulation.scene_cast import select_scene_cast


def test_build_sim_priorities_includes_arc_cast():
    player = {
        "area": "stormbridge:docks",
        "location": "stormbridge",
        "scene_focus": "npc_b",
        "starting_pipeline": {
            "area_id": "stormbridge:docks",
            "title": "Dock plot",
            "stage": 1,
            "stages": ["hook", "twist"],
            "key_npc_ids": ["npc_a"],
        },
    }
    areas = {
        "stormbridge:docks": {
            "storyline": {"stages": ["hook", "twist"], "stage": 1, "tension": 55},
        },
    }
    pri = build_sim_priorities(player, npcs={}, areas=areas)
    assert pri["priority_npc_ids"][0] == "npc_b"
    assert "npc_a" in pri["priority_npc_ids"]
    assert pri["district_tension"] == 55


def test_npc_tick_multiplier_boosts_priority():
    sim = {"priority_npc_ids": ["hero1", "hero2"], "player_area": "a:1"}
    npc = {"area": "a:1"}
    assert npc_tick_multiplier("hero1", npc, sim) > npc_tick_multiplier("other", npc, sim)


def test_register_combat_consequences_merchant_queues_trade_shock():
    player = {"area": "city:market", "pending_consequences": []}
    areas = {"city:market": {"state": {"prosperity": 50, "crime_level": 20}}}
    world = {"day": 3}
    target = {"id": "m1", "name": "Hadd", "role": "merchant", "status": "dead"}
    changed = register_combat_consequences(
        player, target, world=world, areas=areas, fatal=True,
    )
    assert changed
    assert player["pending_consequences"]
    assert areas["city:market"]["state"]["prosperity"] < 50


def test_register_from_causal_link_high_importance():
    player = {"pending_consequences": []}
    link = {
        "cause": "violence",
        "importance": 72,
        "summary": "Because the outsider violence: attack → someone hurt.",
    }
    assert register_from_causal_link(player, link, world={"day": 1})
    assert player["pending_consequences"]


def test_trim_journal_keeps_important_old_beats():
    journal = [{"kind": "explore", "action": f"walk {i}"} for i in range(280)]
    journal.append({"kind": "attack", "action": "kill the merchant", "combat_fatal": True})
    journal.extend({"kind": "wait", "action": f"wait {i}"} for i in range(30))
    trimmed = trim_journal(journal, cap=300, keep_recent=40, player={})
    assert len(trimmed) <= 300
    assert any(e.get("combat_fatal") for e in trimmed)


def test_score_journal_entry_boosts_combat():
    fatal = score_journal_entry({"kind": "attack", "combat_fatal": True})
    ambient = score_journal_entry({"kind": "explore"})
    assert fatal > ambient


def test_scene_cast_uses_beat_plan_priority():
    player = {"known_npcs": {}, "scene_focus": None}
    scholar_a = {"id": "audit_scholar_a", "role": "scholar", "gender": "male"}
    scholar_b = {"id": "audit_scholar_b", "role": "scholar", "gender": "female"}
    ctx = {
        "kind": "talk",
        "beat_plan": {"priority_npc_ids": ["audit_scholar_a", "audit_scholar_b"]},
    }
    focus, _note, fid = select_scene_cast([scholar_b, scholar_a], player, ctx)
    assert fid == "audit_scholar_a"


def test_score_event_uses_arc_keywords():
    player = {
        "starting_pipeline": {
            "area_id": "x",
            "title": "Forgery at the docks",
            "stage": 0,
            "stages": ["hook"],
            "key_npc_ids": [],
        },
    }
    event = {"type": "player_interaction", "action": "investigate forgery at docks", "importance": 40}
    boosted = score_event(event, player=player)
    assert boosted >= 50
