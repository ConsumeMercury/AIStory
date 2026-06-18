"""Scored interpretation benchmark — labeled input → expected slots."""

from simulation.interpretation_benchmark import run_benchmark, BENCHMARK_CASES


def test_benchmark_pass_rate():
    result = run_benchmark()
    assert result["total"] == len(BENCHMARK_CASES)
    assert result["pass_rate"] >= 0.85, result["failures"]


def test_impossible_action_reframed():
    from simulation.action_interpreter import interpret_action
    from tests.fixtures.catalog_fixtures import npc, player
    present = [npc("g1", role="guard", name="Holt")]
    ctx = interpret_action("I fly away", player(), present, {})
    assert ctx.get("impossible_action")
    assert ctx.get("kind") == "observe"


def test_mislabel_single_npc():
    from simulation.action_interpreter import interpret_action
    from tests.fixtures.catalog_fixtures import npc, player
    present = [npc("g1", role="guard", name="Holt", gender="male")]
    ctx = interpret_action("talk to the woman", player(), present, {})
    assert ctx.get("mislabel_resolution")
    assert ctx.get("target_id") == "g1"


def test_deceive_kind():
    from simulation.action_interpreter import interpret_action
    from tests.fixtures.catalog_fixtures import npc, player
    present = [npc("g1", role="guard", name="Holt")]
    ctx = interpret_action("lie and say I'm a merchant", player(), present, {})
    assert ctx.get("kind") == "deceive"


def test_intent_echo_populated():
    from simulation.action_interpreter import interpret_action
    from tests.fixtures.catalog_fixtures import npc, player
    present = [npc("g1", role="guard", name="Holt")]
    ctx = interpret_action("talk to Holt", player(), present, {})
    assert ctx.get("intent_echo")
    assert "kind=talk" in ctx["intent_echo"]
