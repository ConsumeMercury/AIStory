"""
Stat-based combat shared by NPCs, monsters, and the player.

resolve_combat(a, b) runs a short, deterministic-ish exchange:
  damage = max(1, attacker.attack + skill_bonus + roll - defender.defense)
  initiative by speed; stamina drains; whoever hits 0 health dies.

Everyone uses the same {"stats": {...}} shape, so the engine doesn't care
whether a combatant is a person or a bog-lurker. Health/stamina are
written back onto the passed-in dicts, so callers persist the mutation.
"""

import random
from simulation.progression_engine import skill_level, add_skill_xp

# which skill helps with attacking, picked from what the entity actually has
_WEAPON_SKILLS = ["swordsmanship", "knife_fighting", "brawling", "archery"]


def _attack_bonus(entity):
    best = 0
    for s in _WEAPON_SKILLS:
        best = max(best, skill_level(entity, s))
    return best * 2  # each skill level ~ +2 damage


def _alive(entity):
    return entity.get("stats", {}).get("health", 0) > 0 and entity.get("status") != "dead"


def _strike(attacker, defender):
    atk = attacker["stats"]["attack"] + _attack_bonus(attacker)
    dfn = defender["stats"].get("defense", 0)
    roll = random.randint(-3, 6)
    dmg = max(1, atk + roll - dfn)
    defender["stats"]["health"] = max(0, defender["stats"]["health"] - dmg)
    attacker["stats"]["stamina"] = max(0, attacker["stats"].get("stamina", 0) - 3)
    return dmg


def resolve_combat(a, b, max_rounds=12):
    """
    Returns a result dict describing the fight, with health written back.
    Does NOT log or save — the caller decides that (so combat can be used
    inside the sim loop or for the player).
    """
    log = []
    # initiative
    first, second = (a, b) if a["stats"].get("speed", 0) >= b["stats"].get("speed", 0) else (b, a)

    rounds = 0
    while _alive(a) and _alive(b) and rounds < max_rounds:
        rounds += 1
        for attacker, defender in ((first, second), (second, first)):
            if not (_alive(attacker) and _alive(defender)):
                continue
            # exhaustion makes you sloppy
            if attacker["stats"].get("stamina", 1) <= 0 and random.random() < 0.4:
                log.append((attacker.get("id"), "falters", 0))
                continue
            dmg = _strike(attacker, defender)
            log.append((attacker.get("id"), defender.get("id"), dmg))

    a_dead = not _alive(a)
    b_dead = not _alive(b)
    if a_dead and not b_dead:
        winner, loser = b, a
    elif b_dead and not a_dead:
        winner, loser = a, b
    else:
        winner, loser = None, None  # both standing (or both down): a draw/break

    # award combat skill xp to survivors who landed hits
    for who in (a, b):
        if _alive(who):
            for s in _WEAPON_SKILLS:
                if s in who.get("skills", {}):
                    add_skill_xp(who, s, 8)
                    break

    if winner is not None:
        winner["xp"] = winner.get("xp", 0) + 20
        if loser["stats"]["health"] <= 0:
            loser["status"] = "dead"

    return {
        "rounds": rounds, "log": log,
        "winner": winner.get("id") if winner else None,
        "loser": loser.get("id") if loser else None,
        "a_health": a["stats"]["health"], "b_health": b["stats"]["health"],
        "fatal": bool(winner and loser["stats"]["health"] <= 0),
    }
