"""Find-person vs loot — 'Find Edvar' must not spawn a sword."""

from simulation.action_interpreter import interpret_action
from simulation.action_resolution import (
    extract_find_name_query,
    resolve_npc_by_name_query,
    try_acquire_item,
)


def test_find_edvar_is_find_kind():
    player = {"known_npcs": {}, "active_case": {"suspect_ids": ["e1"], "solved": False}}
    npcs = {
        "e1": {"id": "e1", "status": "alive", "name": "Edvar Dremar", "role": "priest"},
        "m1": {"id": "m1", "status": "alive", "name": "Mar Stonehand", "role": "scholar"},
    }
    present = [npcs["m1"]]
    ctx = interpret_action("Find Edvar", player, present, {}, npcs=npcs)
    assert ctx["kind"] == "find"


def test_find_edvar_does_not_acquire_blade():
    player = {"known_npcs": {}, "inventory": [], "equipment": {}, "wealth": 0, "stats": {"health": 100}}
    area = {"type": "district", "city": "test"}
    note, item = try_acquire_item("Find Edvar", player, area, tick=1)
    assert item is None
    assert note is None
    assert not player.get("inventory")


def test_resolve_npc_by_name_query_matches_case_suspect():
    player = {
        "known_npcs": {},
        "active_case": {"suspect_ids": ["e1"], "solved": False},
    }
    npcs = {"e1": {"id": "e1", "status": "alive", "name": "Edvar Dremar", "role": "priest"}}
    hit = resolve_npc_by_name_query("Find Edvar", npcs, player)
    assert hit and hit["id"] == "e1"


def test_extract_find_name_query():
    assert extract_find_name_query("Find Edvar") == "edvar"
    assert extract_find_name_query("find a sword") is None
