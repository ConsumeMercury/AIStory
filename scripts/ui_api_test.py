"""
UI/API contract checks — run with server optional for offline state shape tests.

  python scripts/ui_api_test.py          # offline state shape
  python scripts/ui_api_test.py --live   # hit http://127.0.0.1:8765
"""

import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


REQUIRED_STATE_KEYS = (
    "header", "player", "world", "world_sidebar", "inventory_panel",
    "relations", "relations_full", "rumors", "rumors_full",
    "codex", "timeline", "story_history", "help",
)

REQUIRED_PLAYER_KEYS = (
    "name", "level", "background", "health", "stamina", "stress",
    "combat", "attributes", "skills", "goals", "wealth",
)

REQUIRED_HEADER_KEYS = ("time", "place_short", "weather", "health", "stamina", "wealth")

REQUIRED_DEST_KEYS = ("id", "name", "hours", "detail")


def test_offline_state():
    from simulation.ui_state import get_full_state
    from storage import load

    player = load("player/player.json", {})
    if not player:
        print("SKIP  offline state (no player save — create a character first)")
        return

    state = get_full_state()
    assert state is not None, "get_full_state returned None"
    for key in REQUIRED_STATE_KEYS:
        assert key in state, f"missing state.{key}"

    for key in REQUIRED_PLAYER_KEYS:
        assert key in state["player"], f"missing player.{key}"

    for key in REQUIRED_HEADER_KEYS:
        assert key in state["header"], f"missing header.{key}"

    for dest in state["world"].get("destinations", []):
        for key in REQUIRED_DEST_KEYS:
            assert key in dest, f"destination missing {key}: {dest}"

    for block in state.get("story_history") or []:
        assert "scene" in block, f"story_history block missing scene: {block.keys()}"

    for place in state.get("codex", {}).get("places") or []:
        assert "description" in place, f"place missing description: {place}"

    print("OK    offline state shape")


def _fetch(url, method="GET", body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_live_api(base="http://127.0.0.1:8765"):
    from unittest.mock import patch

    status, health = _fetch(f"{base}/api/health")
    assert status == 200 and health.get("ok"), health
    print("OK    GET /api/health")

    status, setup = _fetch(f"{base}/api/setup")
    assert status == 200 and "backgrounds" in setup, setup
    print("OK    GET /api/setup")

    if not health.get("has_character"):
        print("SKIP  live action tests (no character)")
        return

    status, state = _fetch(f"{base}/api/state")
    assert status == 200, state
    for key in REQUIRED_STATE_KEYS:
        assert key in state, f"live state missing {key}"
    print("OK    GET /api/state")

    # Meta command — no Gemini required
    status, result = _fetch(f"{base}/api/action", method="POST", body={"text": "status"})
    assert status == 200, result
    assert result.get("scene"), "action missing scene"
    assert result.get("state"), "action missing state"
    assert result.get("turn"), "action missing turn"
    assert isinstance(result.get("action_hints"), list), "action_hints not list"
    print("OK    POST /api/action (status)")

    # Static assets
    for path in ("/", "/ui/app.js?v=13", "/ui/styles.css?v=13"):
        req = urllib.request.Request(f"{base}{path}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200, path
            body = resp.read(200)
            assert len(body) > 0, f"empty response for {path}"
    print("OK    static assets")


def main():
    live = "--live" in sys.argv
    base = os.environ.get("AISTORY_URL", "http://127.0.0.1:8765")

    try:
        test_offline_state()
    except AssertionError as exc:
        print(f"FAIL  offline: {exc}")
        sys.exit(1)

    if live:
        try:
            test_live_api(base)
        except (AssertionError, urllib.error.URLError, ConnectionRefusedError) as exc:
            print(f"FAIL  live API: {exc}")
            print(f"      Start server: python api/server.py")
            sys.exit(1)

    print("\nUI/API checks passed.")


if __name__ == "__main__":
    main()
