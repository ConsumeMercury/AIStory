"""
In-memory game state — single load / single flush per turn or sim tick.

All JSON persistence paths used at runtime are cached here during a transaction
so engines stop clobbering each other's read-modify-write cycles.
"""

import copy

from storage import _disk_load, _disk_save, MANAGED_PATHS

# Default empty shapes for list vs dict files
_DEFAULTS = {
    "events/event_log.json": [],
    "rumors/rumors.json": [],
}


class GameState:
    """Mutable in-memory mirror of managed save files."""

    __slots__ = ("_data",)

    def __init__(self, data=None):
        self._data = data if data is not None else {}

    @classmethod
    def load_all(cls):
        state = cls()
        for path in MANAGED_PATHS:
            default = _DEFAULTS.get(path, {})
            state._data[path] = _disk_load(path, copy.deepcopy(default))
        return state

    def get(self, relpath, default=None):
        if relpath in self._data:
            return self._data[relpath]
        if default is None:
            default = _DEFAULTS.get(relpath, {})
        return default

    def set(self, relpath, data):
        self._data[relpath] = data

    def flush_all(self):
        for path, data in self._data.items():
            _disk_save(path, data)

    def snapshot(self, paths=None):
        """Deep copy of selected paths for narration while the sim may advance."""
        paths = paths or MANAGED_PATHS
        return {p: copy.deepcopy(self._data[p]) for p in paths if p in self._data}


def build_narration_snapshot(state, *, player_path="player/player.json", world_path="world/world_state.json",
                             npc_path="characters/npcs.json", rumor_path="rumors/rumors.json"):
    """Immutable-ish bundle for generate_scene while lock is released."""
    snap = state.snapshot([
        player_path, world_path, npc_path, rumor_path,
        "world/areas.json", "characters/relationships.json",
    ])
    return snap
