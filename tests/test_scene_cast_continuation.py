"""Scene cast continuity — same conversation partner across beats."""

from simulation.scene_cast import select_scene_cast


def _scholar(nid, gender="male", name=""):
    return {
        "id": nid,
        "name": name,
        "role": "scholar",
        "gender": gender,
        "status": "alive",
        "physique": {"build": "barrel-chested" if gender == "male" else "wiry"},
    }


def test_wait_keeps_prior_conversation_partner():
    nedkin = _scholar("n1", gender="male")
    zaim = _scholar("z1", gender="female", name="Zaim")
    player = {
        "scene_focus": "n1",
        "journal": [{"focus_npc": "n1", "kind": "ask_about"}],
        "known_npcs": {},
    }
    ctx = {"kind": "wait", "action_summary": "Wait until dawn"}
    focus, _note, fid = select_scene_cast([nedkin, zaim], player, ctx)
    assert len(focus) == 1
    assert focus[0]["id"] == "n1"
    assert fid == "n1"
