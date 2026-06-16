"""Action interpreter — intent classification."""

from simulation.action_interpreter import interpret_action


def test_interpret_travel():
    player = {"area": "city:market", "location": "city"}
    ctx = interpret_action("go to the docks", player, [], {})
    assert ctx["kind"] == "travel"


def test_interpret_attack():
    ctx = interpret_action("attack him", {"area": "x"}, [{"id": "n1", "name": "Bob"}], {})
    assert ctx["kind"] == "attack"


def test_interpret_meta_explore():
    ctx = interpret_action("look around", {"area": "x"}, [], {})
    assert ctx["kind"] == "explore"
