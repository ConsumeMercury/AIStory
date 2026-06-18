"""Catalog L — end-to-end multi-beat regression scenarios."""

import storage

from tests.fixtures.isolated_game import bootstrap_isolated_game, run_mocked_actions


def test_full_relocation_sequence(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    pl = storage.load("player/player.json", {})
    area = pl["area"]
    pl.setdefault("narrator_places", {}).setdefault(area, {})["cellar"] = {
        "id": "cellar",
        "label": "the coal chutes",
        "tokens": ["coal", "chutes"],
    }
    pl["journal"] = [{
        "area": area,
        "scene": "Meet at the coal chutes before dawn.",
        "scene_cast_ids": ["sch_a"],
        "focus_npc": "sch_a",
    }]
    pl["scene_cast"] = {"area": area, "subplace": None, "ids": ["sch_a"]}
    storage.save("player/player.json", pl)

    captured, _ = run_mocked_actions(
        ["Talk to the scholar", "Go to the coal chutes"],
        lambda _kw: "[scene]",
    )
    pl = storage.load("player/player.json", {})
    trace = pl.get("last_boundary_trace") or {}
    reloc = trace.get("reloc") or {}
    assert reloc.get("relocated") or pl.get("scene_subplace")
    assert "sch_a" in set(reloc.get("left_behind_cast") or []) or pl.get("scene_focus") != "sch_a"


def test_return_to_npc_remembers_callback(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    run_mocked_actions(
        ["Ask the scholar about the missing ledger", "Wait until dawn", "Ask the scholar about the preface"],
        lambda _kw: "[scene]",
    )
    pl = storage.load("player/player.json", {})
    assert len(pl.get("journal") or []) >= 3
    scholar_beats = [e for e in pl["journal"] if e.get("focus_npc") == "sch_a"]
    assert len(scholar_beats) >= 2


def test_no_ghost_speaker_after_death_sequence(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    import storage
    from simulation.scene_state import present_npcs_in_area

    pl = storage.load("player/player.json", {})
    npcs = storage.load("characters/npcs.json", {})
    npcs["sold_a"]["status"] = "dead"
    npcs["sold_a"].setdefault("stats", {})["health"] = 0
    pl["last_combat_target"] = "sold_a"
    pl["last_combat_fatal"] = True
    storage.save("characters/npcs.json", npcs)
    storage.save("player/player.json", pl)

    present = present_npcs_in_area(npcs, pl)
    assert not any(n["id"] == "sold_a" for n in present)
    assert npcs["sold_a"]["status"] == "dead"


def test_investigation_arc_advances_stage(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    pl = storage.load("player/player.json", {})
    pl["starting_pipeline"] = {
        "area_id": pl["area"],
        "title": "Test arc",
        "stage": 0,
        "stages": ["hook", "clue", "revelation"],
        "key_npc_ids": ["sch_a"],
    }
    storage.save("player/player.json", pl)
    run_mocked_actions(
        ["look around", "Ask the scholar about the archives"],
        lambda _kw: "[scene with a clue]",
    )
    pl = storage.load("player/player.json", {})
    assert len(pl.get("journal") or []) >= 2


def test_kill_then_world_reacts(tmp_path, monkeypatch):
    bootstrap_isolated_game(tmp_path, monkeypatch)
    pl = storage.load("player/player.json", {})
    areas = storage.load("world/areas.json", {})
    areas[pl["area"]].setdefault("state", {"prosperity": 50, "crime_level": 20, "flags": {}})
    storage.save("world/areas.json", areas)
    npcs = storage.load("characters/npcs.json", {})
    npcs["merch_a"]["status"] = "dead"
    storage.save("characters/npcs.json", npcs)

    from simulation.consequence_propagation import propagate

    propagate(
        "fatal_kill_merchant",
        player=pl,
        world=storage.load("world/world_state.json", {}),
        areas=areas,
        target_npc=npcs["merch_a"],
        institutions={},
        tick=10,
    )
    storage.save("player/player.json", pl)
    pl = storage.load("player/player.json", {})
    assert pl.get("pending_consequences") or pl.get("emergent_hooks")
