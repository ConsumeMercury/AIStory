"""Simulation audit baseline resets player clarification state."""

from scripts.simulation_audit import _reset_player_baseline
from storage import load, save


def test_reset_clears_pending_clarification():
    player = load("player/player.json", {})
    if not player:
        return
    player["pending_target_clarification"] = {"kind": "attack", "options": []}
    player["delayed_directives"] = [{"directive": "stale"}]
    save("player/player.json", player)

    _reset_player_baseline()
    player = load("player/player.json", {})
    assert player.get("pending_target_clarification") is None
    assert player.get("delayed_directives") == []
