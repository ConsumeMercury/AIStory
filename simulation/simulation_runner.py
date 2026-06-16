"""
simulation/simulation_runner.py

Runs the world simulation on a background thread, completely independent
of player input. The world advances every TICK_INTERVAL seconds whether
the player acts or not.
"""

import logging
import threading
import time

from game.state_context import state_lock
from simulation.npc_actions import simulate_npcs
from simulation.consequences_engine import apply_npc_consequences
from simulation.memory_engine import apply_memory_effects
from simulation.rumor_engine import spread_rumors
from simulation.world_clock import advance_clock
from simulation.event_logger import flush_events
from simulation.faction_engine import run_faction_tick
from simulation.relationship_engine import update_relationships
from simulation.bestiary_engine import maintain_monsters
from simulation.storyline_engine import advance_storylines
from simulation.consequence_queue import process_pending
from simulation.rival_engine import rival_tick
from simulation.npc_memory_engine import process_memories

from simulation.locks import get_tick_lock

log = logging.getLogger(__name__)

TICK_INTERVAL = 30
_stop_event = threading.Event()
_current_tick = 0
_worker = None


def get_current_tick():
    return _current_tick


def _run_engine(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:
        log.exception("sim tick engine failed: %s", name)


def _run_tick():
    global _current_tick

    with state_lock():
        _current_tick += 1
        tick = _current_tick

        from storage import load as _load, save as _save

        _run_engine("simulate_npcs", simulate_npcs, tick=tick)
        _run_engine("maintain_monsters", maintain_monsters)
        _run_engine("apply_npc_consequences", apply_npc_consequences, tick=tick)

        from simulation.district_state import advance_districts
        _run_engine("advance_districts", advance_districts, tick=tick)

        from simulation.institution_leadership import process_leadership_succession
        world = _load("world/world_state.json", {})
        _run_engine(
            "process_leadership_succession",
            process_leadership_succession,
            tick=tick,
            day=world.get("day"),
        )

        _run_engine("run_faction_tick", run_faction_tick, tick=tick)
        _run_engine("update_relationships", update_relationships)
        _run_engine("apply_memory_effects", apply_memory_effects)
        _run_engine("spread_rumors", spread_rumors)

        from simulation.rumor_belief import spread_rumor_beliefs
        world = _load("world/world_state.json", {})
        _run_engine(
            "spread_rumor_beliefs",
            spread_rumor_beliefs,
            tick=tick,
            day=world.get("day"),
        )

        _run_engine("advance_storylines", advance_storylines, tick=tick)
        _run_engine("advance_clock", advance_clock)
        _run_engine("flush_events", flush_events)

        player = _load("player/player.json", {})
        if player:
            fired = process_pending(player, world)
            if fired:
                player.setdefault("journal", []).append({
                    "tick": tick,
                    "day": world.get("day"),
                    "kind": "delayed",
                    "action": fired[0],
                    "excerpt": fired[0][:200],
                })
            from simulation.player_legacy import seed_legacy_rumors
            from simulation.goal_events import maybe_goal_rumor
            seed_legacy_rumors(player, tick=tick)
            maybe_goal_rumor(player, tick=tick)
            _save("player/player.json", player)

        player = _load("player/player.json", {})
        npcs = _load("characters/npcs.json", {})
        _run_engine("rival_tick", rival_tick, player, npcs, tick=tick)
        _save("characters/npcs.json", npcs)

        _run_engine("process_memories", process_memories)


def _simulation_loop():
    while not _stop_event.is_set():
        _run_tick()
        for _ in range(TICK_INTERVAL * 10):
            if _stop_event.is_set():
                break
            time.sleep(0.1)


def start():
    global _worker
    _stop_event.clear()
    _worker = threading.Thread(target=_simulation_loop, daemon=True, name="aistory-sim")
    _worker.start()
    return _worker


def stop():
    _stop_event.set()
    if _worker is not None:
        _worker.join(timeout=TICK_INTERVAL + 5)
