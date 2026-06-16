"""Starting city/district placement for new characters."""

import pytest

from game.starting_placement import ensure_start_area


def test_ensure_start_area_falls_back_to_any_district():
    areas = {
        "other:market": {"city": "other", "type": "district", "name": "Market"},
    }
    start = ensure_start_area(areas, "missing_city", "wanderer")
    assert start == "other:market"


def test_ensure_start_area_raises_when_world_empty():
    with pytest.raises(RuntimeError):
        ensure_start_area({}, "any", "wanderer")
