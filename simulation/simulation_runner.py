"""
simulation/simulation_runner.py

Runs the world simulation on a background thread, completely independent
of player input. The world advances every TICK_INTERVAL seconds whether
the player acts or not.
"""

import threading
import time
import traceback

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
from simulation.npc_memory_engine import process_memories

# How many real-world seconds between world ticks.
# 30 = one tick every 30 seconds. Lower = faster world.
TICK_INTERVAL = 30

_stop_event = threading.Event()
_tick_lock = threading.Lock()   # prevents race between sim and story read
_current_tick = 0
_worker = None


def get_tick_lock():
    """Story loop acquires this before reading world state."""
    return _tick_lock


def get_current_tick():
    return _current_tick


def _run_tick():
    global _current_tick

    with _tick_lock:
        _current_tick += 1
        tick = _current_tick

        try:
            simulate_npcs(tick=tick)
        except Exception:
            traceback.print_exc()

        try:
            maintain_monsters()
        except Exception:
            traceback.print_exc()

        try:
            apply_npc_consequences(tick=tick)
        except Exception:
            traceback.print_exc()

        try:
            run_faction_tick(tick=tick)
        except Exception:
            traceback.print_exc()

        try:
            update_relationships()
        except Exception:
            traceback.print_exc()

        try:
            apply_memory_effects()
        except Exception:
            traceback.print_exc()

        try:
            spread_rumors()
        except Exception:
            traceback.print_exc()

        try:
            advance_storylines(tick=tick)
        except Exception:
            traceback.print_exc()

        try:
            advance_clock()
        except Exception:
            traceback.print_exc()

        try:
            flush_events()
        except Exception:
            traceback.print_exc()

        try:
            process_memories()
        except Exception:
            traceback.print_exc()


def _simulation_loop():
    pass
    while not _stop_event.is_set():
        _run_tick()
        # Sleep in small increments so stop_event is checked promptly
        for _ in range(TICK_INTERVAL * 10):
            if _stop_event.is_set():
                break
            time.sleep(0.1)
    pass


def start():
    """Start the background simulation thread. Call once at game start."""
    global _worker
    _stop_event.clear()
    _worker = threading.Thread(target=_simulation_loop, daemon=True)
    _worker.start()
    return _worker


def stop():
    """Signal the simulation to stop cleanly and wait for the current
    tick to finish. Joining matters: a tick can be mid-write to a JSON
    file, and exiting the process before it finishes truncates that file
    and corrupts the save. The lock guarantees we only return between
    ticks, never during one."""
    _stop_event.set()
    if _worker is not None:
        _worker.join(timeout=TICK_INTERVAL + 5)