"""
Authoritative scene state — assembled once per refresh, read-only downstream.
"""

from dataclasses import dataclass, field
from typing import Any

from simulation.scene_coherence import place_label
from simulation.scene_population import resolve_scene_present, persist_scene_cast
from simulation.scheduled_events import list_pending_events
from simulation.world_clock import ensure_clock_coherent


def present_npcs_in_area(npcs, player):
    """All alive NPCs in the player's current area (district population)."""
    loc = player.get("location")
    area = player.get("area")
    here = []
    for n in npcs.values():
        if n.get("status") != "alive":
            continue
        ts = n.get("travel_state") or {}
        if ts.get("hours_remaining", 0) > 0:
            continue
        if (area and n.get("area") == area) or n.get("location") == loc:
            here.append(n)
    return here


@dataclass(frozen=True)
class SceneState:
    """Immutable snapshot of what is true in the social scene this beat."""
    tick: int
    day: int
    hour: int
    time_of_day: str
    area_id: str | None
    subplace_id: str | None
    place_label: str
    area_present: tuple[dict, ...]
    cast: tuple[dict, ...]
    cast_ids: frozenset[str]
    scene_focus: str | None
    pending_events: tuple[dict, ...]
    constraints: tuple[str, ...] = field(default_factory=tuple)

    def cast_for_classifier(self):
        """Compact NPC list for structured action classification."""
        rows = []
        for n in self.cast:
            rows.append({
                "id": n.get("id"),
                "name": n.get("name") or "",
                "role": n.get("role") or "",
            })
        return rows


def _place_label(player, areas_data):
    area = areas_data.get(player.get("area"), {}) if areas_data else {}
    return place_label(player, area)


def assemble_scene_state(
    player,
    npcs,
    world,
    action_ctx,
    tick,
    *,
    areas_data=None,
    persist=True,
):
    """
    Build the single authoritative scene snapshot for this beat.
    Resolves area population → persisted scene cast.
    """
    ensure_clock_coherent(world, persist=False)
    ctx = action_ctx or {}
    area_present = present_npcs_in_area(npcs, player)
    cast = resolve_scene_present(area_present, player, ctx, npcs)
    if persist and cast:
        persist_scene_cast(player, cast, ctx)
    cast_ids = frozenset(n["id"] for n in cast)
    area_id = player.get("area")
    sub = player.get("scene_subplace") or {}
    pending = tuple(list_pending_events(player, area_id) or [])
    constraints = tuple(ctx.get("scene_constraints") or ())
    return SceneState(
        tick=tick,
        day=world.get("day", 1),
        hour=world.get("hour", 0),
        time_of_day=world.get("time_of_day") or "day",
        area_id=area_id,
        subplace_id=sub.get("id"),
        place_label=_place_label(player, areas_data or {}),
        area_present=tuple(area_present),
        cast=tuple(cast),
        cast_ids=cast_ids,
        scene_focus=player.get("scene_focus"),
        pending_events=pending,
        constraints=constraints,
    )


def refresh_scene_state(scene, player, npcs, world, action_ctx, *, areas_data=None, persist=True):
    """Re-assemble after mechanics mutate place or population."""
    return assemble_scene_state(
        player, npcs, world, action_ctx, scene.tick,
        areas_data=areas_data, persist=persist,
    )
