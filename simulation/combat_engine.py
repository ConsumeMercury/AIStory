"""
Stat-based combat with failure consequences: injuries, exhaustion, disarm, flee.
"""

import random

from simulation.progression_engine import skill_level, add_skill_xp

_WEAPON_SKILLS = ["swordsmanship", "knife_fighting", "brawling", "archery"]

_INJURIES = [
    "split lip", "cracked ribs", "sprained wrist", "deep bruising",
    "staggered knee", "wind knocked out",
]


def _attack_bonus(entity):
    best = 0
    for s in _WEAPON_SKILLS:
        best = max(best, skill_level(entity, s))
    return best * 2


def _alive(entity):
    return entity.get("stats", {}).get("health", 0) > 0 and entity.get("status") != "dead"


def _combat_stats(entity):
    if entity.get("journal") is not None:
        from simulation.item_engine import apply_equipment_to_entity
        return apply_equipment_to_entity(entity)
    return entity.setdefault("stats", entity.get("stats") or {})


def _strike(attacker, defender):
    a_stats = _combat_stats(attacker)
    d_stats = _combat_stats(defender)
    atk = a_stats.get("attack", 0) + _attack_bonus(attacker)
    dfn = d_stats.get("defense", 0)
    roll = random.randint(-3, 6)
    dmg = max(1, atk + roll - dfn)
    d_health = defender.setdefault("stats", {})
    a_stamina = attacker.setdefault("stats", {})
    d_health["health"] = max(0, d_health.get("health", 0) - dmg)
    a_stamina["stamina"] = max(0, a_stamina.get("stamina", 0) - 3)
    d_health["stamina"] = max(0, d_health.get("stamina", 0) - 2)
    return dmg


def _apply_injury(entity, severe=False):
    injuries = entity.setdefault("injuries", [])
    count = 2 if severe else 1
    for _ in range(count):
        inj = random.choice(_INJURIES)
        if inj not in injuries:
            injuries.append(inj)
    stats = entity.setdefault("stats", {})
    stats["stress"] = min(
        stats.get("max_stress", 100),
        stats.get("stress", 0) + random.randint(5, 15),
    )
    if severe:
        stats["speed"] = max(1, stats.get("speed", 5) - random.randint(1, 3))


def _temperament_setup(a, b):
    """Monster temperament nudges combat before rounds begin."""
    notes = []
    for entity, other in ((a, b), (b, a)):
        if entity.get("journal") is not None:
            continue
        temp = entity.get("temperament")
        estats = entity.setdefault("stats", {})
        ostats = other.setdefault("stats", {})
        if temp == "ambush" and estats.get("speed", 0) >= ostats.get("speed", 0):
            entity["_ambush"] = True
            notes.append("ambush")
        elif temp == "territorial":
            estats["defense"] = estats.get("defense", 0) + 2
            notes.append("territorial")
        elif temp == "pack":
            estats["speed"] = estats.get("speed", 0) + 1
        elif temp == "haunting" and other.get("journal") is not None:
            ostats["stress"] = min(
                ostats.get("max_stress", 100),
                ostats.get("stress", 0) + 6,
            )
            notes.append("haunting")
        elif temp == "relentless":
            estats["stamina"] = min(
                estats.get("max_stamina", 30),
                estats.get("stamina", 0) + 6,
            )
    return notes


def resolve_combat(a, b, max_rounds=12):
    log = []
    _temperament_setup(a, b)
    a.setdefault("stats", {})
    b.setdefault("stats", {})
    first, second = (a, b) if a["stats"].get("speed", 0) >= b["stats"].get("speed", 0) else (b, a)

    rounds = 0
    falter_a = falter_b = 0
    while _alive(a) and _alive(b) and rounds < max_rounds:
        rounds += 1
        for attacker, defender in ((first, second), (second, first)):
            if not (_alive(attacker) and _alive(defender)):
                continue
            stam = attacker.setdefault("stats", {}).get("stamina", 1)
            if stam <= 0:
                if random.random() < 0.5:
                    log.append((attacker.get("id"), "falters", 0))
                    if attacker is a:
                        falter_a += 1
                    else:
                        falter_b += 1
                    continue
            dmg = _strike(attacker, defender)
            if attacker.get("_ambush") and rounds == 1:
                dmg += random.randint(2, 5)
                attacker["_ambush"] = False
            log.append((attacker.get("id"), defender.get("id"), dmg))
            if dmg >= 8 and random.random() < 0.25:
                _apply_injury(defender, severe=False)

    a_dead = not _alive(a)
    b_dead = not _alive(b)
    if a_dead and not b_dead:
        winner, loser = b, a
    elif b_dead and not a_dead:
        winner, loser = a, b
    else:
        winner, loser = None, None

    consequences = []
    for who, falters, tag in ((a, falter_a, "a"), (b, falter_b, "b")):
        if not _alive(who):
            continue
        if who.setdefault("stats", {}).get("stamina", 0) <= 0:
            consequences.append(f"{tag}: exhausted — vulnerable")
            _apply_injury(who, severe=random.random() < 0.3)
        if falters >= 2:
            consequences.append(f"{tag}: overwhelmed — may flee or surrender")

    if winner is None and rounds >= max_rounds:
        consequences.append("draw — both standing, separated bruised and breathing hard")
        _apply_injury(a, severe=random.random() < 0.4)
        _apply_injury(b, severe=random.random() < 0.4)

    for who in (a, b):
        if _alive(who):
            for s in _WEAPON_SKILLS:
                if s in who.get("skills", {}):
                    add_skill_xp(who, s, 8 if winner is who else 3)
                    break

    if winner is not None:
        winner["xp"] = winner.get("xp", 0) + 20
        loser_stats = loser.setdefault("stats", {})
        if loser_stats.get("health", 0) <= 0:
            loser["status"] = "dead"
            consequences.append("fatal blow landed")
        else:
            _apply_injury(loser, severe=True)
            consequences.append("loser hurt badly but alive")

    player_entity = a if "journal" in a else b if "journal" in b else None

    return {
        "rounds": rounds,
        "log": log,
        "winner": winner.get("id") if winner else None,
        "loser": loser.get("id") if loser else None,
        "a_health": a.setdefault("stats", {}).get("health", 0),
        "b_health": b.setdefault("stats", {}).get("health", 0),
        "fatal": bool(
            winner and loser and loser.setdefault("stats", {}).get("health", 0) <= 0
        ),
        "consequences": consequences,
        "player_injuries": (player_entity.get("injuries") or []) if player_entity else [],
    }
