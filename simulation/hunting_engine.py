"""
Monster hunting — bounties, loot, tracking, and lodge standing.
"""

import random
import uuid

from storage import load, save
from simulation.event_logger import log_event
from generation.monster_generator import SPECIES_DISPLAY, SPECIES_BOUNTY

MON_FILE = "characters/monsters.json"
AREAS_FILE = "world/areas.json"
WORLD_FILE = "world/world_state.json"
INST_FILE = "world/institutions.json"


def monsters_in_area(area_id, monsters, city=None):
    """Alive monsters co-located with a district or wilderness area."""
    if not area_id:
        return []
    out = []
    for m in monsters.values():
        if m.get("status") != "alive":
            continue
        if m.get("area") == area_id or m.get("location") == area_id:
            out.append(m)
        elif city and m.get("location") == city and not m.get("area"):
            out.append(m)
    return out


def wilderness_threat_block(player, monsters, areas):
    """Narrator hint when beasts are near."""
    area_id = player.get("area")
    area = areas.get(area_id, {}) if area_id else {}
    if area.get("type") != "wilderness" and area.get("area_type") not in (
        "wilderness", "forest", "marsh", "ruins", "crypt", "road",
    ):
        here = monsters_in_area(area_id, monsters)
        if not here:
            return ""
    here = monsters_in_area(area_id, monsters, city=player.get("location"))
    if not here:
        return ""
    m = here[0]
    species = SPECIES_DISPLAY.get(m.get("species"), m.get("species", "beast"))
    extra = len(here) - 1
    tail = f" ({extra} more nearby)" if extra else ""
    return (
        f"WILDERNESS THREAT: {species} — {m.get('descriptor', 'something dangerous')}{tail}. "
        f"Temperament: {m.get('temperament', 'unknown')}. "
        "Weave as tension; do not resolve combat unless the player attacks or hunts."
    )


def ensure_bestiary(player):
    book = player.setdefault("bestiary", {})
    book.setdefault("kills", {})
    book.setdefault("seen", [])
    return book


def record_sighting(player, monster):
    book = ensure_bestiary(player)
    sp = monster.get("species")
    if sp and sp not in book["seen"]:
        book["seen"].append(sp)


def record_kill(player, monster, tick=None, world=None):
    """Track kills, lodge standing, bounty claims."""
    book = ensure_bestiary(player)
    sp = monster.get("species", "unknown")
    book["kills"][sp] = book["kills"].get(sp, 0) + 1
    if sp not in book["seen"]:
        book["seen"].append(sp)

    notes = []
    world = world or load(WORLD_FILE, {})
    board = world.get("bounty_board") or []
    for entry in board:
        if entry.get("claimed") or entry.get("species") != sp:
            continue
        if entry.get("monster_id") and entry["monster_id"] != monster.get("id"):
            continue
        payout = entry.get("reward", SPECIES_BOUNTY.get(sp, 10))
        player["wealth"] = player.get("wealth", 0) + payout
        entry["claimed"] = True
        entry["claimed_by"] = player.get("name", "hunter")
        notes.append(f"Bounty collected: {payout} coin for {SPECIES_DISPLAY.get(sp, sp)}.")
        log_event("bounty", "player", f"claimed {sp}", tick=tick, effects=[f"{payout}_coin"])

    world["bounty_board"] = board
    save(WORLD_FILE, world)

    from simulation.institution_membership import adjust_institution_standing, hunters_lodge_id
    lid = hunters_lodge_id(player.get("location"))
    if lid:
        adjust_institution_standing(
            player, lid, 6,
            reason=f"slain {SPECIES_DISPLAY.get(sp, sp)}",
        )
        notes.append("The hunters' lodge will hear of this kill.")

    return notes


def resolve_monster_loot(player, monster, tick=None):
    """Drop loot after a fatal kill."""
    from simulation.item_engine import roll_monster_loot, resolve_loot_to_player
    elite = monster.get("species") in ("wraith", "dire_boar", "bog_lurker", "bone_stalker")
    drops = roll_monster_loot(monster.get("species"), elite=elite)
    summary = resolve_loot_to_player(player, drops)
    sp = SPECIES_DISPLAY.get(monster.get("species"), "the beast")
    if summary.startswith("You find nothing"):
        return f"You take nothing useful from {sp}."
    return f"From {sp}: {summary.replace('Taken: ', '', 1)}"


def refresh_bounty_board(world=None, monsters=None, areas=None):
    """Seed/update posted bounties from live monsters."""
    world = world or load(WORLD_FILE, {})
    monsters = monsters or load(MON_FILE, {})
    areas = areas or load(AREAS_FILE, {})
    board = [e for e in (world.get("bounty_board") or []) if not e.get("claimed")]
    board = board[-12:]

    wild = [a for a in areas.values() if a.get("type") == "wilderness"]
    if not wild or random.random() > 0.55:
        world["bounty_board"] = board
        save(WORLD_FILE, world)
        return board

    area = random.choice(wild)
    here = monsters_in_area(area["id"], monsters)
    if not here:
        world["bounty_board"] = board
        save(WORLD_FILE, world)
        return board

    mon = random.choice(here)
    sp = mon.get("species")
    reward = SPECIES_BOUNTY.get(sp, 10) + random.randint(2, 12)
    entry = {
        "id": str(uuid.uuid4())[:8],
        "species": sp,
        "display": SPECIES_DISPLAY.get(sp, sp),
        "area_id": area["id"],
        "area_name": area.get("name", "the wilds"),
        "monster_id": mon.get("id"),
        "reward": reward,
        "claimed": False,
        "note": random.choice([
            "Locals want it dead before the next caravan.",
            "A farmer lost livestock — pay for proof of kill.",
            "The lodge posted this; pelts or word of mouth.",
        ]),
    }
    board.append(entry)
    world["bounty_board"] = board[-15:]
    save(WORLD_FILE, world)
    return board


def process_hunt_action(player, action_ctx, monsters, areas, world=None):
    """After a successful hunt check — reveal or escalate nearby threat."""
    check = action_ctx.get("skill_check") or {}
    if not check.get("success"):
        return "Tracks fade, or you misread them — nothing closes in."

    area_id = player.get("area")
    here = monsters_in_area(area_id, monsters, city=player.get("location"))
    if not here:
        return (
            "You read the land — old sign, no fresh kill. "
            "Whatever hunted here has moved on, or not arrived yet."
        )

    target = random.choice(here)
    record_sighting(player, target)
    target["tracked"] = True
    sp = SPECIES_DISPLAY.get(target.get("species"), "something")
    if check.get("critical_success"):
        return (
            f"You find {sp} — close, wind wrong, it has not scented you yet. "
            f"{target.get('descriptor', '')} Attack now, withdraw, or circle wide."
        )
    return (
        f"Sign fresh: {sp} near — {target.get('descriptor', 'danger in the brush')}. "
        "You could attack, keep tracking, or leave it be."
    )


def hunt_narrator_block(player, monsters, areas):
    block = wilderness_threat_block(player, monsters, areas)
    board = load(WORLD_FILE, {}).get("bounty_board") or []
    open_b = [b for b in board if not b.get("claimed")][:2]
    if open_b and random.random() < 0.4:
        lines = [f"  • {b['display']} — {b['reward']} coin ({b.get('area_name', '?')})" for b in open_b]
        bounty_bit = "OPEN BOUNTIES (background):\n" + "\n".join(lines)
        return "\n\n".join(p for p in (block, bounty_bit) if p)
    return block


def format_bestiary(player):
    book = ensure_bestiary(player)
    kills = book.get("kills") or {}
    seen = book.get("seen") or []
    if not seen and not kills:
        return "  No beasts recorded yet. Hunt in the wilds or ask at a hunters' lodge."
    lines = ["  Bestiary:"]
    for sp in sorted(set(list(seen) + list(kills.keys()))):
        name = SPECIES_DISPLAY.get(sp, sp)
        k = kills.get(sp, 0)
        status = f"{k} slain" if k else "seen only"
        lines.append(f"    {name:18} {status}")
    return "\n".join(lines)


def format_bounties(player, world=None):
    world = world or load(WORLD_FILE, {})
    board = [b for b in (world.get("bounty_board") or []) if not b.get("claimed")]
    if not board:
        return "  No open bounties posted. Check wilderness districts or a hunters' lodge."
    lines = ["  Posted bounties:"]
    for b in board[:8]:
        lines.append(
            f"    • {b.get('display', '?')} — {b.get('reward', '?')} coin "
            f"({b.get('area_name', '?')}): {b.get('note', '')[:50]}"
        )
    return "\n".join(lines)


def guild_contract_block(player, institutions=None):
    """Narrator texture when player has guild standing."""
    institutions = institutions or load(INST_FILE, {})
    book = player.get("institution_standing") or {}
    lines = []
    for iid, entry in book.items():
        inst = institutions.get(iid, {})
        if inst.get("type") != "guild" or entry.get("score", 0) < 15:
            continue
        arc = (inst.get("arc") or {}).get("current", "")
        if arc:
            lines.append(f"{inst.get('name')}: {arc[:80]}")
    if not lines:
        return ""
    return "GUILD CONTRACT PRESSURE:\n" + "\n".join(f"- {l}" for l in lines[:2])
