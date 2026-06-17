"""Cast selection edge cases."""

from simulation.scene_cast import pick_name_target


def _npc(nid, *, gender="female", build="wiry", known=False):
    return {
        "id": nid,
        "gender": gender,
        "physique": {"build": build},
    }


def test_pick_name_target_returns_none_when_ambiguous():
    player = {"known_npcs": {}}
    present = [_npc("a"), _npc("b", gender="male", build="barrel-chested")]
    assert pick_name_target(player, present, "what is your name?") is None


def test_pick_name_target_picks_sole_unknown():
    player = {"known_npcs": {"a": {"name_known": True}}}
    present = [_npc("a"), _npc("b")]
    target = pick_name_target(player, present, "what is your name?")
    assert target["id"] == "b"
