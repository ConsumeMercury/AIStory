"""Target ambiguity detection and clarification flow."""

from simulation.target_ambiguity import (
    detect_target_ambiguity,
    resolve_clarification_pick,
    build_clarification_scene,
    collect_description_matches,
)
from simulation.action_resolution import resolve_combat_target


def _two_guards():
    return [
        {"id": "g1", "status": "alive", "gender": "male", "name": "Holt", "role": "guard", "appearance": {}},
        {"id": "g2", "status": "alive", "gender": "male", "name": "Venn", "role": "guard", "appearance": {}},
    ]


def test_two_guards_attack_is_ambiguous():
    present = _two_guards()
    player = {"scene_focus": None, "last_combat_target": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    amb = detect_target_ambiguity("fight", player, present, npcs, "attack")
    assert amb is not None
    assert len(amb["options"]) == 2

    target, kind = resolve_combat_target("fight", player, present, npcs, {}, "x:market", "x")
    assert target is None


def test_fight_guard_with_two_guards_is_ambiguous():
    present = _two_guards()
    player = {"scene_focus": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    amb = detect_target_ambiguity("fight the guard", player, present, npcs, "attack")
    assert amb is not None
    assert len(amb["options"]) == 2


def test_clarification_pick_by_chip():
    present = [
        {"id": "a", "status": "alive", "gender": "male", "name": "Holt", "role": "guard", "appearance": {}},
        {"id": "b", "status": "alive", "gender": "male", "name": "Tomas", "role": "merchant", "appearance": {}},
    ]
    player = {
        "pending_target_clarification": {
            "kind": "attack",
            "options": [
                {"id": "a", "label": "Holt (guard)", "chip": "attack Holt"},
                {"id": "b", "label": "Tomas (merchant)", "chip": "attack Tomas"},
            ],
        },
    }
    npcs = {n["id"]: n for n in present}

    kind, nid = resolve_clarification_pick("attack Holt", player, present, npcs)
    assert kind == "attack"
    assert nid == "a"


def test_clarification_scene_lists_options():
    pending = {
        "reason": "several people are here",
        "options": [{"label": "Holt (guard)"}, {"label": "Tomas (merchant)"}],
    }
    text = build_clarification_scene(pending)
    assert "Holt" in text
    assert "Tomas" in text


def test_collect_description_matches_two_guards():
    present = _two_guards()
    hits = collect_description_matches("find the guard", present)
    assert len(hits) == 2


def test_collect_name_matches_two_known_names():
    from simulation.target_ambiguity import collect_name_matches

    present = [
        {"id": "a", "status": "alive", "gender": "female", "name": "Zaim Suleima", "role": "scholar", "appearance": {}},
        {"id": "b", "status": "alive", "gender": "female", "name": "Valena Karim", "role": "soldier", "appearance": {}},
    ]
    player = {"scene_focus": None, "known_npcs": {"a": {"name_known": True}, "b": {"name_known": True}}}
    npcs = {n["id"]: n for n in present}
    hits = collect_name_matches(
        "ask Zaim Suleima and Valena Karim about the ledger",
        npcs,
        player,
        {n["id"] for n in present},
    )
    assert len(hits) == 2


def test_pending_clarification_stores_original_action():
    present = [
        {"id": "a", "status": "alive", "gender": "female", "name": "Zaim Suleima", "role": "scholar", "appearance": {}},
        {"id": "b", "status": "alive", "gender": "female", "name": "Valena Karim", "role": "soldier", "appearance": {}},
    ]
    player = {"scene_focus": None, "known_npcs": {"a": {"name_known": True}, "b": {"name_known": True}}}
    npcs = {n["id"]: n for n in present}
    amb = detect_target_ambiguity(
        "ask her if she is related to the dead master",
        player,
        present,
        npcs,
        "ask_about",
    )
    assert amb is not None
    assert amb.get("original_action")


def test_clarification_pick_by_full_name():
    present = [
        {"id": "a", "status": "alive", "gender": "female", "name": "Zaim Suleima", "role": "scholar", "appearance": {}},
        {"id": "b", "status": "alive", "gender": "female", "name": "Valena Karim", "role": "soldier", "appearance": {}},
    ]
    player = {
        "pending_target_clarification": {
            "kind": "ask_about",
            "original_action": "ask her if she is related to the dead master",
            "options": [
                {"id": "a", "label": "Zaim Suleima (scholar)", "chip": "ask Zaim"},
                {"id": "b", "label": "Valena Karim (soldier)", "chip": "ask Valena"},
            ],
        },
    }
    npcs = {n["id"]: n for n in present}
    kind, nid = resolve_clarification_pick("Zaim Suleima", player, present, npcs)
    assert kind == "ask_about"
    assert nid == "a"
