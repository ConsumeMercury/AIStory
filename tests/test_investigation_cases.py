"""Investigation case generation — victim eligibility and cast rules."""

from simulation.investigation_cases import generate_mystery, case_narrator_block
from simulation.scene_cast import select_scene_cast


def _npc(nid, *, area="ashmoor:market", status="alive", name="NPC"):
    return {"id": nid, "name": name, "status": status, "area": area, "role": "merchant"}


def test_murder_victim_not_present_or_focus():
    npcs = {
        "fahir": _npc("fahir", name="Fahir al-Zahir"),
        "zera": _npc("zera", name="Zera Kveld"),
        "other": _npc("other", name="Other Person"),
    }
    player = {"scene_focus": "fahir", "starting_pipeline": {"key_npc_ids": ["fahir"]}}
    present_ids = ["fahir", "zera"]

    case, changed = generate_mystery(
        "ashmoor:market",
        npcs,
        {"ashmoor:market": {"name": "Market"}},
        player=player,
        present_ids=present_ids,
    )

    assert case is not None
    assert case["victim_id"] not in present_ids
    assert case["victim_id"] != "fahir"
    assert npcs[case["victim_id"]]["status"] == "dead"
    assert changed is True


def test_investigate_cast_is_environment_only():
    fahir = _npc("fahir", name="Fahir al-Zahir")
    player = {"scene_focus": "fahir", "known_npcs": {"fahir": {"name_known": True}}}
    action_ctx = {"kind": "investigate", "target_id": "fahir"}

    focus, note, focal_id = select_scene_cast([fahir], player, action_ctx)

    assert focus == []
    assert focal_id is None
    assert action_ctx["target_id"] is None
    assert "Environment-only" in note


def test_case_block_warns_when_victim_alive_and_present():
    npcs = {"fahir": _npc("fahir", name="Fahir al-Zahir")}
    player = {
        "active_case": {
            "title": "Death in Market",
            "victim_id": "fahir",
            "victim_name": "Fahir al-Zahir",
            "stage": 0,
            "stages": ["learn what happened", "identify suspects", "find proof", "accuse or expose"],
            "suspect_ids": [],
            "evidence": [],
            "solved": False,
        }
    }
    block = case_narrator_block(player, npcs, present_ids=["fahir"])
    assert "do not treat anyone present as the corpse" in block.lower()
    assert "alive here" in block.lower()
