"""Combat target resolution — role-specific attacks must not hit random bystanders."""

from simulation.action_resolution import resolve_combat_target


def _present():
    return [
        {
            "id": "npc_merchant",
            "status": "alive",
            "gender": "male",
            "name": "Tomas",
            "role": "merchant",
            "appearance": {},
        },
        {
            "id": "npc_guard",
            "status": "alive",
            "gender": "male",
            "name": "Holt",
            "role": "guard",
            "appearance": {},
        },
    ]


def test_fight_knights_without_match_returns_none():
    present = [_present()[0]]
    player = {"scene_focus": None, "last_combat_target": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    target, kind = resolve_combat_target(
        "fight the knights", player, present, npcs, {}, "city:market", "city",
    )

    assert target is None
    assert kind is None


def test_fight_guard_hits_guard_not_merchant():
    present = _present()
    player = {"scene_focus": None, "last_combat_target": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    target, kind = resolve_combat_target(
        "fight the guard", player, present, npcs, {}, "city:market", "city",
    )

    assert target["id"] == "npc_guard"
    assert kind == "npc"


def test_generic_fight_with_crowd_requires_target():
    present = _present()
    player = {"scene_focus": None, "last_combat_target": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    target, kind = resolve_combat_target("fight", player, present, npcs, {}, "city:market", "city")
    assert target is None
    assert kind is None


def test_compound_description_prefers_best_overlap():
    from simulation.action_resolution import match_npc_by_description

    present = [
        {
            "id": "npc_a",
            "status": "alive",
            "gender": "female",
            "name": "Mara",
            "role": "merchant",
            "appearance": {"hair": "red"},
        },
        {
            "id": "npc_b",
            "status": "alive",
            "gender": "male",
            "name": "Dock",
            "role": "sailor",
            "appearance": {},
        },
    ]
    hit = match_npc_by_description("find the red-haired captain", present)
    assert hit and hit["id"] == "npc_a"


def test_named_absent_hunter_does_not_substitute_focus():
    """Attacking a specific absent role must not hit scene_focus bystander."""
    herbalist = {
        "id": "npc_herbalist",
        "status": "alive",
        "gender": "female",
        "name": "",
        "role": "herbalist",
        "appearance": {},
    }
    present = [herbalist]
    player = {
        "scene_focus": "npc_herbalist",
        "last_combat_target": None,
        "known_npcs": {},
    }
    npcs = {herbalist["id"]: herbalist}

    target, kind = resolve_combat_target(
        "attack the three-fingered hunter",
        player,
        present,
        npcs,
        {},
        "city:high_quarter",
        "city",
    )

    assert target is None
    assert kind is None


def test_hunter_in_present_hits_hunter_not_herbalist():
    hunter = {
        "id": "npc_hunter",
        "status": "alive",
        "gender": "male",
        "name": "Rook",
        "role": "hunter",
        "appearance": {"hands": "three fingers on right"},
    }
    herbalist = {
        "id": "npc_herbalist",
        "status": "alive",
        "gender": "female",
        "role": "herbalist",
        "appearance": {},
    }
    present = [herbalist, hunter]
    player = {"scene_focus": "npc_herbalist", "last_combat_target": None, "known_npcs": {}}
    npcs = {n["id"]: n for n in present}

    target, kind = resolve_combat_target(
        "attack the hunter",
        player,
        present,
        npcs,
        {},
        "city:high_quarter",
        "city",
    )

    assert target["id"] == "npc_hunter"
    assert kind == "npc"


def test_fatal_combat_target_preserved_when_absent_from_present():
    from simulation.scene_cast import select_scene_cast

    dead = {"id": "victim", "status": "dead", "role": "sailor", "name": "Bess", "gender": "female"}
    player = {"scene_focus": "victim", "known_npcs": {}}
    ctx = {
        "kind": "attack",
        "target_id": "victim",
        "combat_snapshot": dead,
        "combat_fatal": True,
    }
    focus, _, focal_id = select_scene_cast([], player, ctx)
    assert ctx["target_id"] == "victim"
    assert focus == []
