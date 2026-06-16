"""
Background world bootstrap — lets the web server accept connections while world data generates.
"""

import logging
import threading

log = logging.getLogger(__name__)

_lock = threading.Lock()
_ready = False
_error = None
_status = "pending"
_sim_started = False
_thread = None


def boot_status():
    with _lock:
        return {
            "ready": _ready,
            "error": _error,
            "status": _status,
        }


def boot_ready():
    with _lock:
        return _ready and not _error


def _set_status(status, *, ready=False, error=None):
    global _ready, _error, _status
    with _lock:
        _status = status
        if ready:
            _ready = True
        if error is not None:
            _error = error


def _run_bootstrap():
    global _sim_started
    from simulation import simulation_runner
    from simulation.world_patch import ensure_world_extensions
    from game.setup import ensure_world_data

    try:
        _set_status("generating_world")
        log.info("Bootstrap: generating world data…")
        ensure_world_data()
        _set_status("patching_world")
        ensure_world_extensions()
        _set_status("starting_simulation")
        simulation_runner.start()
        _sim_started = True
        _set_status("ready", ready=True)
        log.info("Bootstrap: complete")
    except Exception as err:
        log.exception("Bootstrap failed")
        _set_status("error", error=str(err))


def start_bootstrap():
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run_bootstrap, name="aistory-bootstrap", daemon=True)
        _thread.start()


def stop_bootstrap():
    if _sim_started:
        from simulation import simulation_runner
        simulation_runner.stop()
