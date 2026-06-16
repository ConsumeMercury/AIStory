"""Plot summary from simulation state."""

from simulation.plot_summary import build_plot_summary


def _player_with_case():
    return {
        "starting_pipeline": {
            "title": "Fang Market",
            "hook": "Forged lodge seals undercut real hunters.",
            "current": "fakes implicate the clerk",
        },
        "goals": [
            {"text": "Uncover the market fraud", "progress": 2, "target": 3, "complete": False},
        ],
        "active_case": {
            "title": "Death in Market",
            "victim_id": "v1",
            "victim_name": "Offscreen Victim",
            "stage": 1,
            "stages": ["learn", "identify", "prove", "accuse"],
            "suspect_ids": ["s1"],
            "evidence": [{"text": "Zera was off duty", "discovered": True}],
            "solved": False,
        },
        "known_npcs": {"f1": {"name_known": True}},
        "last_acquired_item": {"name": "Notched Blade", "rarity": "uncommon"},
    }


def test_plot_summary_includes_pipeline_goals_and_case():
    npcs = {
        "v1": {"id": "v1", "name": "Offscreen Victim", "status": "dead", "role": "merchant"},
        "s1": {"id": "s1", "name": "Zera Kveld", "status": "alive", "role": "guard"},
        "f1": {"id": "f1", "name": "Fahir al-Zahir", "status": "alive", "role": "merchant"},
    }
    block = build_plot_summary(_player_with_case(), npcs, focal_npc_id="f1", present_ids=["f1"])
    assert "PLOT SUMMARY" in block
    assert "Fang Market" in block
    assert "Uncover the market fraud" in block
    assert "Death in Market" in block
    assert "Zera was off duty" in block
    assert "Fahir al-Zahir" in block
    assert "Notched Blade" in block


def test_plot_summary_warns_living_present_victim():
    npcs = {
        "f1": {"id": "f1", "name": "Fahir al-Zahir", "status": "alive", "role": "merchant"},
    }
    player = _player_with_case()
    player["active_case"]["victim_id"] = "f1"
    player["active_case"]["victim_name"] = "Fahir al-Zahir"
    block = build_plot_summary(player, npcs, present_ids=["f1"])
    assert "alive and present" in block
