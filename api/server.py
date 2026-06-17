"""
AIStory web UI server — FastAPI backend + static frontend.

Run from project root:
  pip install -r requirements.txt
  set GEMINI_API_KEY=...
  python api/server.py

Then open http://127.0.0.1:8765
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.load_env import load_env

load_env()

from config.debug import debug_enabled, setup_logging

setup_logging()

UI_DIR = BASE_DIR / "ui"


def _gemini_user_message(exc):
    """Turn Gemini/client failures into player-facing text (no stack traces)."""
    msg = str(exc).strip() or exc.__class__.__name__
    low = msg.lower()
    if "api key not valid" in low or "api_key_invalid" in low:
        return (
            "Gemini rejected your API key. Check GEMINI_API_KEY in .env "
            "(https://aistudio.google.com/apikey) and restart the server."
        )
    if "missing api key" in low:
        return (
            "Set GEMINI_API_KEY in .env (see .env.example) and restart the server."
        )
    return msg


def _try_opening_scene():
    """Return (scene_text|None, error_message|None). Never raises."""
    import logging
    from simulation.story_loop import generate_opening_scene

    log = logging.getLogger(__name__)
    try:
        scene = generate_opening_scene()
    except Exception as exc:
        log.exception("Opening scene generation failed")
        return None, _gemini_user_message(exc)
    if not scene:
        return None, None
    return scene, None


@asynccontextmanager
async def lifespan(app):
    from game.bootstrap import start_bootstrap, stop_bootstrap

    start_bootstrap()
    yield
    stop_bootstrap()


def _cors_origins():
    raw = os.environ.get("AISTORY_CORS_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    from simulation.gemini_client import api_key
    from simulation.story_loop import process_player_action
    from simulation.ui_state import get_full_state, snapshot_for_delta, build_turn_metadata, HELP_COMMANDS
    from simulation.action_hints import build_action_hints, collect_action_suggestions
    from simulation import simulation_runner
    from simulation.turn_trace import get_last_turn
    from config.debug import debug_enabled
    from game.setup import (
        list_backgrounds,
        has_player,
        world_data_ready,
        get_starting_info,
        create_player_from_form,
        ensure_world_data,
    )
    from storage import load

    def _action_response(text, scene, meta_only=False, before=None):
        player = load("player/player.json", {})
        world = load("world/world_state.json", {})
        last_kind = (player.get("journal") or [{}])[-1].get("kind") if player else None
        state = get_full_state()
        turn = build_turn_metadata(player, world, text, before=before)
        hints = collect_action_suggestions(player, last_kind=last_kind, limit=5, force=True)
        hint = ""
        if player and not meta_only:
            hint = build_action_hints(player, last_kind=last_kind) or ""
        return {
            "scene": scene,
            "hint": hint,
            "turn": turn,
            "action_hints": hints,
            "location": turn.get("location"),
            "time": turn.get("time"),
            "new_rumors": turn.get("new_rumors", []),
            "relationship_changes": turn.get("relationship_changes", []),
            "codex_entries": turn.get("codex_entries", []),
            "journal_entry": turn.get("journal_entry"),
            "state": state,
            **({"debug": get_last_turn()} if debug_enabled() else {}),
        }

    app = FastAPI(title="AIStory", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    class ActionBody(BaseModel):
        text: str

    class CharacterBody(BaseModel):
        name: str = ""
        age: int = 30
        background: str = "wanderer"
        appearance: str = ""
        attire: str = ""
        motivation: str = ""

    class SaveSlotBody(BaseModel):
        label: str = ""

    def _require_boot_ready():
        from game.bootstrap import boot_ready, boot_status

        if boot_ready():
            return
        boot = boot_status()
        raise HTTPException(
            status_code=503,
            detail=boot["error"] or "World is still generating. Please wait…",
        )

    @app.get("/api/saves")
    def list_save_slots():
        from game.save_slots import list_slots
        return {"slots": list_slots()}

    @app.post("/api/saves/{slot_id}")
    def create_save_slot(slot_id: str, body: SaveSlotBody = SaveSlotBody()):
        from game.save_slots import save_slot
        from game.state_context import state_lock
        try:
            with state_lock():
                meta = save_slot(slot_id, label=body.label or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "slot": slot_id, "meta": meta}

    @app.post("/api/saves/{slot_id}/load")
    def load_save_slot(slot_id: str):
        from game.save_slots import load_slot
        from simulation.world_patch import ensure_world_extensions
        try:
            load_slot(slot_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        ensure_world_extensions()
        return {"ok": True, "state": get_full_state()}

    @app.delete("/api/saves/{slot_id}")
    def remove_save_slot(slot_id: str):
        from game.save_slots import delete_slot
        delete_slot(slot_id)
        return {"ok": True}

    @app.post("/api/undo")
    def undo_turn():
        from game.undo import undo_last_turn, can_undo
        from game.state_context import state_lock
        if not can_undo():
            raise HTTPException(status_code=409, detail="Nothing to undo.")
        try:
            with state_lock():
                undo_last_turn()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "state": get_full_state()}

    @app.get("/api/debug/world")
    def debug_world():
        if not debug_enabled():
            raise HTTPException(status_code=404, detail="Set AISTORY_DEBUG=1 to enable debug endpoints.")
        from simulation.world_inspector import build_world_inspector
        return build_world_inspector()

    @app.get("/api/setup")
    def setup_info():
        _require_boot_ready()
        info = get_starting_info()
        return {
            "has_character": has_player(),
            "world_ready": world_data_ready(),
            "backgrounds": list_backgrounds(),
            "starting_city": info.get("city_name"),
            "starting_cities": info.get("cities", []),
            "gemini_configured": bool(api_key()),
        }

    @app.post("/api/character")
    def create_character(body: CharacterBody):
        _require_boot_ready()
        if has_player():
            raise HTTPException(status_code=409, detail="A character already exists.")
        try:
            create_player_from_form(body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        from simulation.world_patch import ensure_world_extensions
        ensure_world_extensions()

        if not api_key():
            return {
                "scene": None,
                "message": "Character created. Set GEMINI_API_KEY and refresh for the opening scene.",
                "state": get_full_state(),
            }

        scene, err = _try_opening_scene()
        if err:
            return {
                "scene": None,
                "message": f"Character created, but the opening scene failed: {err}",
                "state": get_full_state(),
            }
        if not scene:
            return {
                "scene": None,
                "message": "Character created.",
                "state": get_full_state(),
            }
        return _action_response("look around", scene)

    @app.get("/api/health")
    def health():
        from game.bootstrap import boot_status

        boot = boot_status()
        return {
            "ok": boot["ready"] and not boot["error"],
            "booting": not boot["ready"] and not boot["error"],
            "boot_status": boot["status"],
            "boot_error": boot["error"],
            "gemini_configured": bool(api_key()),
            "has_character": has_player(),
        }

    @app.get("/api/state")
    def state():
        _require_boot_ready()
        if not has_player():
            raise HTTPException(status_code=404, detail="No character yet. Create one in the browser.")
        data = get_full_state()
        if not data:
            raise HTTPException(status_code=404, detail="No character found.")
        return data

    @app.get("/api/help")
    def help_commands():
        return {"commands": HELP_COMMANDS}

    @app.get("/api/debug/last-turn")
    def debug_last_turn():
        if not debug_enabled():
            raise HTTPException(status_code=404, detail="Set AISTORY_DEBUG=1 to enable debug endpoints.")
        from simulation.turn_trace import get_boundary_history, get_boundary_summary
        return {
            **get_last_turn(),
            "boundary_history_summary": get_boundary_summary(),
        }

    @app.get("/api/debug/boundary")
    def debug_boundary():
        if not debug_enabled():
            raise HTTPException(status_code=404, detail="Set AISTORY_DEBUG=1 to enable debug endpoints.")
        from simulation.turn_trace import get_boundary_history, get_boundary_summary, get_last_turn
        from simulation.boundary_metrics import summarize_player_boundary_history
        player = load("player/player.json", {})
        saved_hist = player.get("boundary_history") or []
        mem_hist = get_boundary_history()
        history = saved_hist if saved_hist else mem_hist
        return {
            "session_stats": player.get("boundary_stats") or {},
            "last_turn_trace": player.get("last_boundary_trace") or get_last_turn(),
            "history_summary": (
                summarize_player_boundary_history(saved_hist)
                if saved_hist
                else get_boundary_summary()
            ),
            "recent": history[-10:],
        }

    @app.get("/api/debug/summary")
    def debug_summary():
        if not debug_enabled():
            raise HTTPException(status_code=404, detail="Set AISTORY_DEBUG=1 to enable debug endpoints.")
        player = load("player/player.json", {})
        world = load("world/world_state.json", {})
        return {
            "tick": simulation_runner.get_current_tick(),
            "player_area": player.get("area"),
            "player_location": player.get("location"),
            "day": world.get("day"),
            "hour": world.get("hour"),
            "weather": world.get("weather"),
            "journal_entries": len(player.get("journal") or []),
            "last_turn": get_last_turn(),
        }

    @app.post("/api/opening")
    def opening():
        _require_boot_ready()
        if not api_key():
            raise HTTPException(
                status_code=503,
                detail="Set GEMINI_API_KEY before playing.",
            )
        player = load("player/player.json", {})
        if player.get("journal"):
            return {"scene": None, "skipped": True, "state": get_full_state()}
        scene, err = _try_opening_scene()
        if err:
            raise HTTPException(status_code=503, detail=err) from None
        if not scene:
            return {"scene": None, "skipped": True, "state": get_full_state()}
        return _action_response("look around", scene)

    def _is_meta_action(text):
        first = text.lower().split()[0]
        if first in {
            "help", "?", "stats", "status", "sheet", "skills", "inventory", "inv",
            "goals", "objectives", "map", "where", "journal", "bonds", "relationships",
            "factions", "reputation", "guilds", "institutions", "lodge", "bounties",
            "bestiary", "case", "investigation", "routines", "schedule", "check",
        }:
            return True
        lower = text.lower()
        return lower.startswith(("hints ", "equip ", "unequip ", "use "))

    @app.post("/api/action")
    def action(body: ActionBody):
        _require_boot_ready()
        text = (body.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Empty action.")

        if text.lower() in ("quit", "exit"):
            return _action_response(text, "Session ended. Close the browser tab or keep exploring.")

        meta_only = _is_meta_action(text)

        if not meta_only and not api_key():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Set GEMINI_API_KEY for roleplay actions. "
                    "Create a .env file in the project root (see .env.example) "
                    "or set the variable in Windows Environment Variables, then restart the server."
                ),
            )

        player_before = load("player/player.json", {})
        before = snapshot_for_delta(player_before)

        try:
            scene = process_player_action(text)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=_gemini_user_message(exc)) from exc

        return _action_response(text, scene, meta_only=meta_only, before=before)

    @app.post("/api/action/stream")
    def action_stream(body: ActionBody):
        import json
        import queue
        import threading

        from fastapi.responses import StreamingResponse

        _require_boot_ready()
        text = (body.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Empty action.")

        if text.lower() in ("quit", "exit"):
            return _action_response(text, "Session ended. Close the browser tab or keep exploring.")

        meta_only = _is_meta_action(text)

        if not meta_only and not api_key():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Set GEMINI_API_KEY for roleplay actions. "
                    "Create a .env file in the project root (see .env.example) "
                    "or set the variable in Windows Environment Variables, then restart the server."
                ),
            )

        player_before = load("player/player.json", {})
        before = snapshot_for_delta(player_before)
        events = queue.Queue()

        def worker():
            try:
                def on_chunk(chunk):
                    events.put({"type": "chunk", "text": chunk})

                scene = process_player_action(text, on_prose_chunk=on_chunk)
                payload = _action_response(text, scene, meta_only=meta_only, before=before)
                payload["type"] = "done"
                events.put(payload)
            except Exception as exc:
                events.put({"type": "error", "detail": _gemini_user_message(exc)})
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def event_generator():
            while True:
                item = events.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/")
    def index():
        index_path = UI_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="UI files missing.")
        return FileResponse(index_path)

    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

    return app


app = create_app()


def main():
    import socket
    import uvicorn

    host = os.environ.get("AISTORY_HOST", "127.0.0.1")
    port = int(os.environ.get("AISTORY_PORT", "8765"))

    # Fail fast with a clear message if the port is already taken.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        print(
            f"\n  Port {port} is already in use (another AIStory server may still be running).\n"
            f"  • Stop it:  netstat -ano | findstr :{port}   then   taskkill /PID <pid> /F\n"
            f"  • Or use another port:  set AISTORY_PORT=8766   then run again\n"
        )
        return
    finally:
        probe.close()

    print(f"\n  AIStory web UI — http://{host}:{port}\n")
    from simulation.gemini_client import api_key as _key
    if not _key():
        print(
            "  Warning: GEMINI_API_KEY not set — roleplay actions will fail.\n"
            "  Fix: copy .env.example to .env and add your key, then restart.\n"
            "  Get a key: https://aistudio.google.com/apikey\n"
        )
    uvicorn.run("api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
