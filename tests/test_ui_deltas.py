"""Turn delta computation for the web aftermath panel."""

from simulation.ui_state import compute_turn_deltas, snapshot_for_delta


def test_player_stat_deltas():
    before = {
        "health": 50,
        "stamina": 20,
        "stress": 10,
        "wealth": 100,
        "level": 1,
        "xp": 0,
        "area": "harbor_district",
        "inventory_ids": ["coin_pouch"],
        "last_check": None,
        "rumors": [],
        "relations_full": [],
    }
    player = {
        "stats": {"health": 45, "stamina": 18, "stress": 12},
        "wealth": 120,
        "level": 1,
        "xp": 5,
        "area": "harbor_district",
        "inventory": [{"id": "coin_pouch", "name": "Coin pouch"}, {"id": "knife", "name": "Rusty knife"}],
        "last_check": None,
    }
    deltas = compute_turn_deltas(before, player, {})
    labels = {r["label"] for r in deltas["player"]}
    assert "Health" in labels
    assert "Stamina" in labels
    assert "Stress" in labels
    assert "Wealth" in labels
    assert "XP" in labels
    assert deltas["items"][0]["name"] == "Rusty knife"
    assert not deltas["empty"]


def test_npc_relation_delta(monkeypatch):
    before = {
        "health": 50,
        "stamina": 20,
        "stress": 0,
        "wealth": 0,
        "level": 1,
        "xp": 0,
        "area": "market",
        "inventory_ids": [],
        "last_check": None,
        "rumors": [],
        "relations_full": [{
            "id": "npc_1",
            "name": "Mira",
            "familiarity": 10,
            "bars": {
                "trust": {"value": 20, "pct": 20},
                "respect": {"value": 10, "pct": 10},
                "fear": {"value": 0, "pct": 0},
                "affection": {"value": 5, "pct": 5},
                "familiarity": {"value": 10, "pct": 10},
            },
        }],
    }
    player = {
        "stats": {"health": 50, "stamina": 20, "stress": 0},
        "wealth": 0,
        "level": 1,
        "area": "market",
        "inventory": [],
    }

    def fake_relations(_player, limit=None):
        return [{
            "id": "npc_1",
            "name": "Mira",
            "familiarity": 10,
            "is_focus": True,
            "bars": {
                "trust": {"value": 28, "pct": 28},
                "respect": {"value": 10, "pct": 10},
                "fear": {"value": 0, "pct": 0},
                "affection": {"value": 5, "pct": 5},
                "familiarity": {"value": 10, "pct": 10},
            },
        }]

    monkeypatch.setattr("simulation.ui_state.get_relations_view", fake_relations)
    deltas = compute_turn_deltas(before, player, {})
    assert deltas["npcs"][0]["stat"] == "trust"
    assert deltas["npcs"][0]["delta"] == 8


def test_snapshot_for_delta_includes_vitals():
    player = {
        "stats": {"health": 40, "stamina": 15, "stress": 5},
        "wealth": 50,
        "level": 2,
        "xp": 10,
        "area": "docks",
        "inventory": [{"id": "a", "name": "A"}],
    }
    snap = snapshot_for_delta(player)
    assert snap["health"] == 40
    assert snap["inventory_ids"] == ["a"]
