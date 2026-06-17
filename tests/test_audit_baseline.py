"""Simulation audit baseline resets player clarification state."""

import copy

import pytest

from scripts.simulation_audit import _reset_player_baseline
from storage import load, save


@pytest.fixture
def _restore_player_after():
    player = load("player/player.json", {})
    backup = copy.deepcopy(player) if player else None
    yield
    if backup is not None:
        save("player/player.json", backup)
    else:
        from pathlib import Path
        path = Path("player/player.json")
        if path.exists():
            path.unlink()


def test_reset_clears_pending_clarification(_restore_player_after):
    player = load("player/player.json", {})
    if not player:
        pytest.skip("No player save — bootstrap or create character first.")
    player["pending_target_clarification"] = {"kind": "attack", "options": []}
    player["delayed_directives"] = [{"directive": "stale"}]
    save("player/player.json", player)

    _reset_player_baseline()
    player = load("player/player.json", {})
    assert player.get("pending_target_clarification") is None
    assert player.get("delayed_directives") == []
