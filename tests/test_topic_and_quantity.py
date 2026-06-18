"""Topic resolution and economy word numbers."""

from simulation.topic_resolution import (
    extract_ask_topic,
    classify_topic,
    gate_topic_for_npc,
    apply_topic_gates,
)
from simulation.economy_engine import parse_give_amount
from simulation.action_interpretation import detect_duplicate_action, apply_duplicate_action_guard
from tests.fixtures.catalog_fixtures import npc, player


def test_extract_ask_topic_murder():
    topic, ttype = extract_ask_topic("ask the priest about the murder")
    assert topic
    assert "murder" in topic.lower()
    assert ttype == "event"


def test_extract_ask_topic_reflexive():
    topic, ttype = extract_ask_topic("ask what you think of me")
    assert ttype == "reflexive"


def test_five_silver_word_amount():
    pl = {"wealth": 100}
    assert parse_give_amount("give her five silver", pl) == 5


def test_give_all_parses_wealth():
    pl = {"wealth": 42}
    assert parse_give_amount("give all my money", pl) == 42


def test_vague_topic_triggers_clarify():
    ctx = {"kind": "ask_about", "ask_topic": "stuff", "topic_type": "vague", "story_directive": ""}
    apply_topic_gates(ctx, player(), {"m1": npc("m1")}, [npc("m1")])
    assert ctx.get("interpretation_clarify")


def test_beggar_unknown_on_royal_politics():
    kid = npc("k1", role="beggar", name="Rat")
    level = gate_topic_for_npc("royal succession", "event", kid)
    assert level == "unknown"


def test_duplicate_action_detected():
    pl = player()
    pl["journal"] = [{"action": "look around", "kind": "explore"}]
    assert detect_duplicate_action("look around", pl)


def test_duplicate_guard_sets_clarify():
    pl = player()
    pl["journal"] = [{"action": "wait", "kind": "wait"}]
    ctx = {"story_directive": ""}
    assert apply_duplicate_action_guard("wait", pl, ctx)
    assert ctx.get("duplicate_action")
