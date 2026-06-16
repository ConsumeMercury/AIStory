"""Tests for atomic storage and in-memory transactions."""

import json
import os

import pytest

import storage


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "BASE_DIR", str(tmp_path))
    os.makedirs(tmp_path / "player", exist_ok=True)
    yield tmp_path


def test_load_missing_returns_default(isolated_storage):
    assert storage.load("player/player.json", {"x": 1}) == {"x": 1}


def test_save_and_load_roundtrip(isolated_storage):
    storage.save("player/player.json", {"name": "Test"})
    assert storage.load("player/player.json")["name"] == "Test"


def test_transaction_batches_writes(isolated_storage):
    storage.begin_transaction()
    storage.save("player/player.json", {"name": "InMemory"})
    path = storage.full_path("player/player.json")
    assert not os.path.exists(path)
    storage.commit_transaction()
    data = storage.load("player/player.json", {})
    assert data.get("name") == "InMemory"


def test_transaction_rollback_discards(isolated_storage):
    storage.save("player/player.json", {"name": "Before"})
    storage.begin_transaction()
    storage.save("player/player.json", {"name": "After"})
    storage.rollback_transaction()
    assert storage.load("player/player.json")["name"] == "Before"


def test_corrupt_json_returns_default(isolated_storage):
    path = storage.full_path("player/player.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert storage.load("player/player.json", []) == []
