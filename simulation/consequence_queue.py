"""
Delayed consequences — insult today, guards cold three days later.
"""

import random
import uuid

from storage import load, save

PLAYER_FILE = "player/player.json"


def queue_consequence(player, *, fires_at_day, kind, summary, effects=None, target_id=None):
    """
    effects: dict with optional keys:
      faction_standing_delta, relationship_kind, relationship_intensity,
      narrator_directive, wealth_delta, story_flag
    """
    entry = {
        "id": str(uuid.uuid4())[:8],
        "fires_at_day": fires_at_day,
        "kind": kind,
        "summary": summary,
        "effects": effects or {},
        "target_id": target_id,
        "fired": False,
    }
    player.setdefault("pending_consequences", []).append(entry)
    return entry


def register_from_action(player, action_kind, action_ctx, world, target_npc=None):
    """Schedule delayed fallout for sharp player actions."""
    day = world.get("day", 1)
    target_id = action_ctx.get("target_id")
    check = action_ctx.get("skill_check") or {}
    success = check.get("success", True)

    if action_kind == "insult" and target_id:
        role = (target_npc or {}).get("role", "")
        inst = ((target_npc or {}).get("institution") or {})
        if role in ("guard", "soldier") or inst.get("type") == "garrison":
            queue_consequence(
                player,
                fires_at_day=day + random_delay(2, 4),
                kind="guard_grudge",
                summary="The garrison remembers your insult.",
                effects={
                    "narrator_directive": "Guards are colder — less help, more scrutiny.",
                    "faction_standing_delta": -8,
                },
                target_id=target_id,
            )
        else:
            queue_consequence(
                player,
                fires_at_day=day + random_delay(1, 3),
                kind="grudge",
                summary="Word of your insult spread.",
                effects={"relationship_kind": "insult", "relationship_intensity": 0.5},
                target_id=target_id,
            )

    elif action_kind == "help" and target_id and success:
        queue_consequence(
            player,
            fires_at_day=day + random_delay(3, 7),
            kind="gratitude",
            summary="Someone you helped speaks well of you.",
            effects={
                "narrator_directive": "A past kindness pays off — recommendation or rumor in your favor.",
                "relationship_kind": "kindness",
                "relationship_intensity": 0.6,
            },
            target_id=target_id,
        )

    elif action_kind == "threaten" and target_id and not success:
        queue_consequence(
            player,
            fires_at_day=day + random_delay(1, 2),
            kind="threat_backfire",
            summary="Your threat boomeranged.",
            effects={
                "narrator_directive": "They warned others about you.",
                "relationship_kind": "betrayal",
                "relationship_intensity": 0.8,
            },
            target_id=target_id,
        )


def random_delay(lo, hi):
    return random.randint(lo, hi)


def process_pending(player, world, factions=None, institutions=None):
    """Fire consequences whose day has arrived. Returns list of fired summaries."""
    day = world.get("day", 1)
    pending = player.get("pending_consequences") or []
    fired_notes = []
    remaining = []

    from simulation.faction_reputation import adjust_standing, institution_faction
    from simulation.relationship_engine import apply_npc_toward_player

    factions = factions or load("world/factions.json", {})
    institutions = institutions or load("world/institutions.json", {})
    npcs = load("characters/npcs.json", {})

    for item in pending:
        if item.get("fired"):
            continue
        if item.get("fires_at_day", 9999) > day:
            remaining.append(item)
            continue

        item["fired"] = True
        effects = item.get("effects") or {}
        fired_notes.append(item.get("summary", "Something from your past catches up."))

        tid = item.get("target_id")
        npc = npcs.get(tid, {}) if tid else {}

        if effects.get("relationship_kind") and tid:
            apply_npc_toward_player(
                tid,
                effects["relationship_kind"],
                intensity=effects.get("relationship_intensity", 0.7),
            )

        if effects.get("faction_standing_delta"):
            fid = None
            inst_ref = npc.get("institution")
            if isinstance(inst_ref, dict):
                inst = institutions.get(inst_ref.get("id"), {})
                fid = institution_faction(inst, factions)
            if not fid:
                for f in factions.values():
                    if f.get("type") in ("empire", "order"):
                        fid = f.get("id")
                        break
            if fid:
                adjust_standing(
                    player, fid, effects["faction_standing_delta"],
                    reason=item.get("summary", ""),
                )

        if effects.get("story_flag"):
            player.setdefault("story_flags", {})[effects["story_flag"]] = True

        player.setdefault("delayed_directives", []).append({
            "summary": item.get("summary"),
            "directive": effects.get("narrator_directive", ""),
            "day": day,
        })

    player["pending_consequences"] = remaining[-40:]
    player["delayed_directives"] = (player.get("delayed_directives") or [])[-10:]
    return fired_notes


def pop_delayed_directive(player):
    """Consume one delayed narrator hook for the next scene."""
    dirs = player.get("delayed_directives") or []
    if not dirs:
        return ""
    d = dirs.pop(0)
    player["delayed_directives"] = dirs
    return d.get("directive") or d.get("summary", "")
