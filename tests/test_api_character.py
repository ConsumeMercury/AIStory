"""API character creation — must not 500 when opening scene generation fails."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from game.bootstrap import boot_ready, start_bootstrap


@pytest.fixture
def booted_client():
    from simulation import simulation_runner

    simulation_runner.stop()
    player_path = Path("player/player.json")
    if player_path.exists():
        player_path.unlink()

    start_bootstrap()
    for _ in range(60):
        if boot_ready():
            break
        import time
        time.sleep(0.05)
    assert boot_ready()

    # Background sim ticks can write an empty player shell before the POST.
    if player_path.exists():
        player_path.unlink()

    with TestClient(create_app()) as client:
        yield client

    simulation_runner.stop()


@pytest.fixture(autouse=True)
def _isolated_player_save():
    """Each API character test starts without a player save on disk."""
    player_path = Path("player/player.json")
    backup = player_path.read_text(encoding="utf-8") if player_path.exists() else None
    if player_path.exists():
        player_path.unlink()
    yield
    if backup is not None:
        player_path.write_text(backup, encoding="utf-8")
    elif player_path.exists():
        player_path.unlink()


def test_create_character_survives_opening_failure(booted_client):
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key", "AISTORY_AUTO_CHAR": ""}, clear=False):
        os.environ.pop("AISTORY_AUTO_CHAR", None)
        with patch(
            "simulation.story_loop.generate_opening_scene",
            side_effect=RuntimeError("API key not valid"),
        ):
            from game.setup import has_player
            assert not has_player(), "player save should be cleared before create test"
            r = booted_client.post(
                "/api/character",
                json={
                    "name": "Test",
                    "age": 18,
                    "background": "soldier",
                    "appearance": "x",
                    "motivation": "y",
                },
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("scene") is None
    assert "Character created" in (body.get("message") or "")
    assert body.get("state", {}).get("player", {}).get("name") == "Test"


def test_create_character_without_api_key(booted_client):
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
    with patch.dict(os.environ, env, clear=True):
        r = booted_client.post(
            "/api/character",
            json={"name": "NoKey", "age": 20, "background": "wanderer"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("scene") is None
    assert "GEMINI_API_KEY" in (body.get("message") or "")
