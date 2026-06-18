"""
Catalog B — target resolution & ambiguity (priority 1).

State-independent: every test builds its own cast and player dict.
"""

from simulation.action_resolution import match_npc_by_description, resolve_pronoun_target
from simulation.scene_coherence import resolve_target_and_absence
from simulation.target_ambiguity import detect_target_ambiguity
from simulation.target_resolution import resolve_action_target
from tests.fixtures.catalog_fixtures import npc, npc_map, player


def test_role_target_with_no_match_returns_absent():
    """talk to priest with no priest present must not substitute another role."""
    soldier = npc("soldier", role="soldier", name="Solia")
    pl = player(scene_focus="soldier", known_npcs={"soldier": {"name_known": True}})
    present = [soldier]

    target = resolve_action_target("Talk to the priest", pl, present, kind="talk")
    assert target is None

    action_ctx = {"kind": "talk"}
    resolve_target_and_absence(
        "Talk to the priest", pl, present, npc_map(soldier), action_ctx, {}, {},
    )
    assert action_ctx.get("target_id") is None


def test_ambiguous_role_triggers_clarification():
    merchants = [
        npc("m1", role="merchant", name="Tomas", gender="male"),
        npc("m2", role="merchant", name="Lira", gender="female"),
    ]
    pl = player(scene_focus=None)
    amb = detect_target_ambiguity(
        "ask the merchant about prices", pl, merchants, npc_map(*merchants), "ask_about",
    )
    assert amb is not None
    assert len(amb["options"]) >= 2


def test_disambiguation_carries_original_intent():
    merchants = [
        npc("m1", role="merchant", name="Tomas"),
        npc("m2", role="merchant", name="Lira", gender="female"),
    ]
    pl = player(scene_focus=None)
    original = "ask the merchant about the missing ledger"
    amb = detect_target_ambiguity(
        original, pl, merchants, npc_map(*merchants), "ask_about",
    )
    assert amb is not None
    assert amb.get("original_action") == original


def test_pronoun_resolves_to_last_focal():
    focal = npc("s1", role="scholar", name="Solena", gender="female")
    other = npc("x1", role="guard", gender="male")
    pl = player(scene_focus="s1")
    hit = resolve_pronoun_target("ask her about the archives", pl, [focal, other])
    assert hit and hit["id"] == "s1"


def test_named_target_overrides_role():
    solena = npc("s1", role="scholar", name="Solena Dremar", gender="female")
    merchant = npc("m1", role="merchant", name="Tomas", key_npc=True)
    pl = player(
        scene_focus="m1",
        known_npcs={"s1": {"name_known": True}, "m1": {"name_known": True}},
    )
    target = resolve_action_target(
        "talk to Solena", pl, [merchant, solena], npcs=npc_map(merchant, solena), kind="talk",
    )
    assert target and target["id"] == "s1"


def test_absent_named_target_no_ghost_dialogue():
    absent = npc("away", role="priest", name="Father Hale")
    present_npc = npc("here", role="soldier", name="Solia")
    pl = player(
        scene_focus="here",
        known_npcs={"away": {"name_known": True}, "here": {"name_known": True}},
    )
    action_ctx = {"kind": "talk", "story_directive": ""}
    resolve_target_and_absence(
        "talk to Father Hale",
        pl,
        [present_npc],
        {**npc_map(present_npc), **npc_map(absent)},
        action_ctx,
        {},
        {},
    )
    assert action_ctx.get("absent_npc", {}).get("id") == "away"
    assert action_ctx.get("target_id") is None
    assert "NOT in this scene" in action_ctx.get("story_directive", "")


def test_descriptor_target_resolution_red_haired_woman():
    """Catalog: descriptor_target_resolution — trait-based match, not scene_focus luck."""
    redhead = npc(
        "w1",
        role="merchant",
        name="Mara",
        gender="female",
        appearance={"hair": "auburn"},
    )
    other = npc("w2", role="herbalist", gender="female", appearance={"hair": "black"})
    hit = match_npc_by_description("talk to the red-haired woman", [redhead, other])
    assert hit and hit["id"] == "w1"


def test_find_role_with_no_match_does_not_use_scene_focus():
    from simulation.action_resolution import resolve_find_person

    soldier = npc("soldier", role="soldier", name="Solia")
    pl = player(scene_focus="soldier")
    found = resolve_find_person("find the priest", pl, [soldier], {})
    assert found is None
