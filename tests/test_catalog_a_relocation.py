"""
Catalog A — relocation & scene-cast integrity (priority 3).

Extends test_scene_population.py with catalog-named regressions.
"""

from simulation.scene_cast import select_scene_cast
from simulation.scene_coherence import mark_scene_relocation, collect_prior_cast_ids
from simulation.scene_population import bootstrap_scene_cast, resolve_scene_present
from tests.fixtures.catalog_fixtures import npc, npc_map, player


def _area_npcs():
    priest = npc("p1", role="priest", name="Father Hale", key_npc=True)
    soldier = npc("s1", role="soldier", name="Solia")
    extras = [npc(f"x{i}") for i in range(4)]
    return [priest, soldier] + extras


def test_relocation_clears_scene_focus():
    pl = player(scene_focus="p1")
    ctx = {"kind": "approach"}
    mark_scene_relocation(pl, ctx, prior_present=[npc("p1")], prior_cast_ids=["p1"])
    assert pl.get("scene_focus") is None
    assert ctx.get("relocated") is True


def test_approach_to_subplace_leaves_cast_behind():
    """Catalog: approach_to_subplace_leaves_cast_behind."""
    cast = _area_npcs()
    npcs = npc_map(*cast)
    pl = player(
        area="docks",
        scene_focus="p1",
        scene_cast={"area": "docks", "subplace": "timber", "ids": ["p1", "s1"]},
    )
    ctx = {"kind": "approach", "relocated": True, "left_behind_cast": ["p1", "s1"]}
    present = resolve_scene_present(cast, pl, ctx, npcs)
    ids = {n["id"] for n in present}
    assert "p1" not in ids
    assert "s1" not in ids
    assert len(ids) >= 1


def test_travel_to_new_area_leaves_cast_behind():
    """Catalog: travel_to_new_area_leaves_cast_behind."""
    from simulation.scene_coherence import mark_scene_relocation

    cast = _area_npcs()
    npcs = npc_map(*cast)
    pl = player(
        area="embermoor:docks",
        scene_focus="p1",
        scene_cast={"area": "embermoor:docks", "subplace": None, "ids": ["p1"]},
    )
    ctx = {"kind": "travel"}
    mark_scene_relocation(pl, ctx, prior_present=[cast[0]], prior_cast_ids=["p1"])
    assert ctx.get("relocated")
    assert "p1" in (ctx.get("left_behind_cast") or [])
    present = resolve_scene_present(cast, pl, ctx, npcs)
    assert "p1" not in {n["id"] for n in present}


def test_relocation_does_not_resurrect_focus_via_population():
    """High-scoring left-behind NPC must not re-enter cast after relocation."""
    priest = npc("p1", role="priest", name="Priest", key_npc=True)
    others = [npc(f"x{i}", role="laborer") for i in range(5)]
    all_npcs = [priest] + others
    npcs = npc_map(*all_npcs)
    pl = player(area="docks", scene_focus="p1", known_npcs={"p1": {"name_known": True}})
    ctx = {
        "kind": "approach",
        "relocated": True,
        "left_behind_cast": ["p1"],
        "target_id": "x0",
    }
    boot = bootstrap_scene_cast(all_npcs, pl, ctx, npcs)
    ids = {n["id"] for n in boot}
    assert "p1" not in ids


def test_continuation_beat_keeps_same_focal():
    scholar = npc("s1", role="scholar", name="Nedkin")
    other = npc("s2", role="scholar", name="Zaim", gender="female")
    pl = player(
        scene_focus="s1",
        journal=[{"focus_npc": "s1", "kind": "talk", "action": "hello"}],
    )
    ctx = {"kind": "ask_about", "target_id": "s1"}
    focus, _note, fid = select_scene_cast([scholar, other], pl, ctx)
    assert fid == "s1"
    assert focus[0]["id"] == "s1"


def test_same_role_two_npcs_focus_sticky():
    m1 = npc("m1", role="merchant", name="Tomas")
    m2 = npc("m2", role="merchant", name="Lira", gender="female")
    pl = player(
        scene_focus="m1",
        journal=[{"focus_npc": "m1", "kind": "talk"}],
        known_npcs={"m1": {"name_known": True}},
    )
    ctx = {"kind": "talk", "target_id": "m1"}
    focus, _note, fid = select_scene_cast([m1, m2], pl, ctx)
    assert fid == "m1"


def test_subplace_mismatch_backstop_without_reloc_flag():
    priest = npc("p1", role="priest", key_npc=True)
    extras = [npc("x1"), npc("x2")]
    npcs = npc_map(priest, *extras)
    pl = player(
        area="docks",
        scene_subplace={"id": "cellar", "label": "Cellar"},
        scene_focus="p1",
        scene_cast={"area": "docks", "subplace": None, "ids": ["p1"]},
    )
    present = resolve_scene_present([priest] + extras, pl, {}, npcs)
    assert "p1" not in {n["id"] for n in present}


def test_failed_travel_preserves_cast():
    guard = npc("g1", role="guard", name="Kasah")
    scholar = npc("s1", role="scholar", name="Razar")
    area = [guard, scholar]
    npcs = npc_map(*area)
    pl = player(
        area="hq",
        scene_focus="g1",
        scene_cast={"area": "hq", "subplace": None, "ids": ["g1", "s1"]},
        journal=[{"area": "hq", "focus_npc": "g1", "scene_cast_ids": ["g1", "s1"]}],
    )
    ctx = {"kind": "travel", "travel_failed": True}
    present = resolve_scene_present(area, pl, ctx, npcs)
    assert {n["id"] for n in present} == {"g1", "s1"}
