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


def test_explicit_target_beats_higher_scored_npc():
    scholar = _scholar("s1", gender="male")
    merchant = {
        "id": "m1",
        "name": "Known Merchant",
        "role": "merchant",
        "gender": "male",
        "status": "alive",
        "key_npc": True,
        "physique": {"build": "stocky", "presentation": 80},
    }
    player = {
        "known_npcs": {"m1": {"name_known": True, "seen_before": True}},
    }
    ctx = {"kind": "ask_about", "target_id": "s1", "action_summary": "Ask the scholar about archives"}
    focus, _note, fid = select_scene_cast([merchant, scholar], player, ctx)
    assert fid == "s1"
    assert focus[0]["id"] == "s1"
