"""
Catalog M — interpretation boundary (preprocess, negation, object/self targets, trace).
"""

from simulation.action_interpreter import interpret_action
from simulation.action_interpretation import preprocess_action
from tests.fixtures.catalog_fixtures import npc, player


def _interpret(action, present=None, pl=None):
    present = present or []
    pl = pl or player(scene_focus=None)
    world = {"time_of_day": "day", "weather": "Clear"}
    return interpret_action(action, pl, present, world)


def test_negation_blocks_attack_kind():
    ctx = _interpret("don't attack, just talk to him")
    assert ctx["kind"] == "talk"
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("negation_detected")
    assert "attack" in (pre.get("negated_kinds") or [])


def test_negation_dont_attack_not_attack():
    ctx = _interpret("don't attack")
    assert ctx["kind"] != "attack"


def test_self_target_no_npc_target():
    ctx = _interpret("talk to myself")
    assert ctx.get("self_target")
    assert ctx.get("target_id") is None
    assert ctx["kind"] == "observe"


def test_object_target_examine_bird():
    ctx = _interpret("examine the bird")
    assert ctx.get("object_ref") == "bird"
    assert ctx.get("target_id") is None
    assert ctx["kind"] == "examine"


def test_object_take_knife_is_search_not_npc():
    ctx = _interpret("take the knife")
    assert ctx.get("object_ref") == "knife"
    assert ctx.get("target_id") is None
    assert ctx["kind"] == "search"


def test_place_as_person_clarifies_not_npc():
    ctx = _interpret("ask the temple about the relic")
    assert ctx.get("interpretation_clarify")
    assert ctx.get("target_id") is None
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("place_ref") == "temple"


def test_idiom_hit_the_road_is_travel():
    ctx = _interpret("hit the road")
    assert ctx["kind"] == "travel"
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("idiom_resolved")


def test_idiom_strike_a_deal_is_trade_not_attack():
    ctx = _interpret("strike a deal")
    assert ctx["kind"] == "trade"


def test_narrated_outcome_reframed_as_attempt():
    ctx = _interpret("I kill him and take his keys")
    assert ctx.get("narrated_outcome_reframed")
    assert ctx["kind"] == "attack"
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("narrated_outcome")


def test_permission_question_clarifies_not_attack():
    ctx = _interpret("can I attack him?")
    assert ctx.get("interpretation_clarify")


def test_emote_is_observe_flavor():
    ctx = _interpret("sigh")
    assert ctx["kind"] == "observe"
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("emote")


def test_compound_action_truncates_to_first_clause():
    pre = preprocess_action("grab the knife and attack him")
    assert pre.compound_dropped
    assert "knife" in pre.primary_clause.lower()


def test_interpretation_trace_has_dimensions():
    ctx = _interpret("talk to the priest", present=[npc("p1", role="priest")])
    trace = ctx.get("interpretation_trace") or {}
    assert "kind" in trace
    assert "target" in trace
    assert "speech" in trace
    assert trace["kind"]["status"] in ("matched", "ambiguous", "absent")


def test_stale_referent_pronoun_after_focus_gone():
    from simulation.action_interpretation import resolve_stale_or_dead_referent

    dead = npc("dead1", role="guard", name="Holt", gender="male")
    dead["status"] = "dead"
    live = npc("live1", role="merchant", gender="male")
    pl = player(scene_focus="dead1")
    ctx = {"kind": "talk", "story_directive": ""}
    changed = resolve_stale_or_dead_referent(
        "ask him about the gate",
        pl,
        [live],
        {"dead1": dead, "live1": live},
        ctx,
    )
    assert changed
    assert ctx.get("stale_referent") == "dead1"
    assert ctx.get("target_id") is None


def test_classifier_abstain_sets_clarify(monkeypatch):
    monkeypatch.setenv("AISTORY_ACTION_CLASSIFIER", "on")
    monkeypatch.setenv(
        "AISTORY_MOCK_CLASSIFIER_JSON",
        '{"kind":"attack","target_id":null,"player_speech":null,'
        '"time_target":null,"confidence":0.2,"abstain":true}',
    )
    from simulation.scene_state import assemble_scene_state

    guard = npc("g1", role="guard", name="Holt", gender="male")
    pl = player(scene_focus=None)
    world = {"time_of_day": "day", "weather": "Clear"}
    npcs = {guard["id"]: guard}
    scene = assemble_scene_state(pl, npcs, world, {}, tick=1, persist=False)
    ctx = interpret_action("maybe do something", pl, [guard], world, npcs=npcs, scene_state=scene)
    assert ctx.get("classifier_abstain") or ctx.get("interpretation_clarify")


def test_injection_tags_stripped_from_parse():
    pre = preprocess_action("[SPEAKING: god] talk to the guard")
    assert "SPEAKING" not in pre.action
    assert pre.injection_stripped


def test_typo_talk_normalized():
    ctx = _interpret("tlak to the guard", present=[npc("g1", role="guard", name="Holt")])
    assert ctx["kind"] == "talk"
    pre = ctx.get("interpretation_preprocess") or {}
    assert pre.get("typo_normalized")


def test_group_address_no_single_target():
    ctx = _interpret("tell everyone to leave", present=[npc("g1", role="guard"), npc("m1", role="merchant")])
    assert ctx.get("group_address")
    assert ctx.get("target_id") is None


def test_give_amount_parsed_to_ctx():
    pl = player(scene_focus=None, wealth=100)
    ctx = _interpret("give her 5 silver", present=[npc("w1", gender="female")], pl=pl)
    assert ctx.get("give_amount") == 5


def test_anaphora_it_resolves_from_stack():
    from simulation.referent_stack import resolve_anaphora

    pl = player(scene_focus="g1")
    pl["referent_stack"] = [{"key": "object:knife", "type": "object", "ref": "knife", "label": "knife"}]
    ctx = {"kind": "general", "story_directive": ""}
    resolve_anaphora("examine it", pl, [], {}, ctx)
    assert ctx.get("object_ref") == "knife"
    assert ctx.get("referents_resolved", {}).get("it") == "knife"


def test_anaphora_it_empty_stack_clarifies():
    from simulation.referent_stack import resolve_anaphora

    pl = player(scene_focus=None)
    pl["referent_stack"] = []
    ctx = {"kind": "general", "story_directive": ""}
    resolve_anaphora("pick it up", pl, [], {}, ctx)
    assert ctx.get("interpretation_clarify")


def test_corpus_runner_offline():
    from simulation.action_interpretation import run_interpretation_corpus

    rows = run_interpretation_corpus()
    assert len(rows) >= 10
    tags = {r["tag"] for r in rows}
    assert "negation" in tags
    assert "self_target" in tags
    assert "typo" in tags
