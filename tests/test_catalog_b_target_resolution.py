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


def test_gender_descriptor_with_no_match_returns_absent():
    """talk to the woman with only male NPCs must not substitute a man."""
    males = [
        npc("m1", role="merchant", name="Xithar", gender="male"),
        npc("m2", role="guard", name="Grimson", gender="male"),
    ]
    pl = player(scene_focus="m1")
    target = resolve_action_target("Talk to the woman", pl, males, kind="talk")
    assert target is None

    action_ctx = {"kind": "talk", "action_summary": "Talk to the woman", "story_directive": ""}
    resolve_target_and_absence(
        "Talk to the woman", pl, males, npc_map(*males), action_ctx, {}, {},
    )
    assert action_ctx.get("target_id") is None
    assert action_ctx.get("target_constraint_failed")


def test_gender_descriptor_with_match_resolves_correctly():
    woman = npc("w1", role="merchant", name="Mara", gender="female")
    man = npc("m1", role="guard", name="Holt", gender="male")
    pl = player(scene_focus="m1")
    target = resolve_action_target("Talk to the woman", pl, [woman, man], kind="talk")
    assert target and target["id"] == "w1"


def test_gender_constraint_blocks_scene_cast_fallback():
    from simulation.scene_cast import select_scene_cast

    males = [
        npc("m1", role="merchant", name="Xithar", gender="male"),
        npc("m2", role="guard", name="Grimson", gender="male"),
    ]
    pl = player(scene_focus="m1")
    ctx = {"kind": "talk", "action_summary": "Talk to the woman"}
    focus, _note, focal_id = select_scene_cast(males, pl, ctx)
    assert focal_id is None
    assert focus == []
    assert ctx.get("target_constraint_failed")


# --- Expanded constraint-engine catalog ---


def test_no_constraint_single_present_auto_targets():
    lone = npc("solo", role="merchant", name="Tomas", gender="male")
    pl = player(scene_focus=None)
    target = resolve_action_target("talk", pl, [lone], kind="talk")
    assert target and target["id"] == "solo"


def test_no_constraint_multi_present_no_focus_clarifies_or_absent():
    from simulation.target_constraints import TargetStatus, resolve_target

    pair = [
        npc("a", role="merchant", gender="male"),
        npc("b", role="guard", gender="male"),
    ]
    pl = player(scene_focus=None)
    result = resolve_target("talk", pl, pair, kind="talk")
    assert result.status == TargetStatus.AMBIGUOUS


def test_role_multi_match_clarifies_among_role():
    from simulation.target_constraints import TargetStatus, resolve_target

    priests = [
        npc("p1", role="priest", name="Hale", gender="male"),
        npc("p2", role="priest", name="Mira", gender="female"),
    ]
    pl = player(scene_focus=None)
    result = resolve_target("talk to the priest", pl, priests, kind="talk")
    assert result.status == TargetStatus.AMBIGUOUS
    assert len(result.candidates) == 2
    assert all(n.get("role") == "priest" for n in result.candidates)


def test_gender_multi_match_clarifies_among_gender():
    from simulation.target_constraints import TargetStatus, resolve_target

    women = [
        npc("w1", role="merchant", gender="female", name="Mara"),
        npc("w2", role="scholar", gender="female", name="Lira"),
    ]
    pl = player(scene_focus=None)
    result = resolve_target("talk to the woman", pl, women, kind="talk")
    assert result.status == TargetStatus.AMBIGUOUS
    assert len(result.candidates) == 2
    assert all(n.get("gender") == "female" for n in result.candidates)


def test_gender_no_match_does_not_substitute_other_gender():
    males = [
        npc("m1", role="merchant", gender="male"),
        npc("m2", role="guard", gender="male"),
    ]
    pl = player(scene_focus="m1")
    from simulation.target_constraints import TargetStatus, resolve_target

    result = resolve_target("Talk to the woman", pl, males, kind="talk")
    assert result.status == TargetStatus.ABSENT
    assert result.constraint_violated == "gender:female"
    assert resolve_action_target("Talk to the woman", pl, males, kind="talk") is None


def test_compound_all_must_hold_partial_is_no_match():
    from simulation.target_constraints import TargetStatus, resolve_target

    tall_priest = npc("tp", role="priest", gender="male", physique={"build": "tall"})
    short_priest = npc("sp", role="priest", gender="male", physique={"build": "stocky"})
    pl = player(scene_focus="sp")
    result = resolve_target("talk to the tall priest", pl, [short_priest], kind="talk")
    assert result.status == TargetStatus.ABSENT

    result2 = resolve_target("talk to the tall priest", pl, [tall_priest, short_priest], kind="talk")
    assert result2.status == TargetStatus.MATCHED
    assert result2.npc_id == "tp"


def test_conflicting_constraints_clarify():
    from simulation.target_constraints import TargetStatus, resolve_target

    cast = [npc("x", role="merchant", gender="male"), npc("y", role="guard", gender="female")]
    pl = player(scene_focus=None)
    result = resolve_target("talk to her, the old man", pl, cast, kind="talk")
    assert result.status == TargetStatus.AMBIGUOUS
    assert result.constraint_violated == "conflicting constraints"


def test_attack_no_match_hard_fails_never_substitutes():
    from simulation.target_constraints import TargetStatus, resolve_target

    males = [npc("m1", role="guard", gender="male"), npc("m2", role="soldier", gender="male")]
    pl = player(scene_focus="m1")
    result = resolve_target("attack the woman", pl, males, kind="attack")
    assert result.status == TargetStatus.ABSENT
    assert result.constraint_violated == "gender:female"


def test_other_one_excludes_current_focal():
    from simulation.target_constraints import TargetStatus, resolve_target

    a = npc("a", role="merchant", gender="male", name="Tomas")
    b = npc("b", role="guard", gender="male", name="Holt")
    pl = player(scene_focus="a")
    result = resolve_target("talk to the other one", pl, [a, b], kind="talk")
    assert result.status == TargetStatus.MATCHED
    assert result.npc_id == "b"
