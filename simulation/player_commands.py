"""
Player meta-commands — status, inventory, skills, map, goals (no LLM).
"""

from storage import load, save
from simulation.progression_engine import skill_level
from simulation.travel_engine import list_destinations
from simulation.player_goals import active_goal_hint, build_player_goals
from simulation.faction_reputation import format_faction_standing
from simulation.institution_membership import format_institution_standing, ensure_institution_standing
from simulation.hunting_engine import format_bestiary, format_bounties
from simulation.action_hints import format_hint_setting, set_hint_mode
from simulation.investigation_cases import format_case_status
from simulation.npc_schedule import schedule_hint, next_appearance
from simulation.storyline_engine import arc_for_area

PLAYER_FILE = "player/player.json"
AREAS_FILE = "world/areas.json"
LOC_FILE = "world/locations.json"
NPC_FILE = "characters/npcs.json"
REL_FILE = "characters/relationships.json"
INST_FILE = "world/institutions.json"

_HELP = """
Commands (type any of these instead of roleplay):

  status / sheet     — overview (stats, health, wealth, place)
  stats              — attributes and health
  skills             — your skill levels
  inventory / inv    — equipped gear, pack, and coin
  equip <#>          — wear weapon, armor, or trinket from pack
  unequip weapon     — remove gear from a slot
  use <#>            — drink or apply a consumable
  goals              — what you're trying to achieve + local story hook
  map                — places you can travel to from here
  where              — current city, district, time, weather
  journal            — recent story beats
  bonds              — how key people feel about you (if known)
  case               — active investigation progress
  factions           — your standing with major factions
  guilds             — guild / lodge / temple membership
  bounties           — posted monster hunts
  bestiary           — beasts you've seen or slain
  check              — last skill check result
  hints              — toggle contextual suggestions (off / subtle / plain)
  help               — this list

Roleplay anything else normally (talk to..., explore, threaten, etc.).
"""


def _bar(val, max_val=100, width=12):
    filled = int(width * min(val, max_val) / max(max_val, 1))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _cmd_help():
    return _HELP.strip()


def _cmd_stats(player):
    stats = player.get("stats", {})
    attrs = stats.get("attributes", {})
    lines = [
        f"  {player.get('name', 'You')} — level {player.get('level', 1)}",
        f"  Health  {stats.get('health', '?')}/{stats.get('max_health', '?')}  {_bar(stats.get('health', 0), stats.get('max_health', 100))}",
        f"  Stamina {stats.get('stamina', '?')}/{stats.get('max_stamina', '?')}  {_bar(stats.get('stamina', 0), stats.get('max_stamina', 30))}",
        f"  Stress  {stats.get('stress', 0)}/{stats.get('max_stress', 100)}",
    ]
    if player.get("injuries"):
        lines.append(f"  Injuries: {', '.join(player['injuries'])}")
    lines.append("  Attributes:")
    for k, v in sorted(attrs.items()):
        lines.append(f"    {k:12} {v}")
    return "\n".join(lines)


def _cmd_skills(player):
    skills = player.get("skills", {})
    if not skills:
        return "  No skills recorded."
    lines = ["  Skills:"]
    for name in sorted(skills.keys()):
        node = skills[name]
        lvl = node.get("level", skill_level(player, name))
        xp = node.get("xp", 0)
        lines.append(f"    {name:16} Lv {lvl}  ({xp} xp)")
    return "\n".join(lines)


def _cmd_inventory(player):
    from simulation.item_engine import format_item_line, format_equipment_block, ensure_equipment
    ensure_equipment(player)
    inv = player.get("inventory") or []
    lines = [format_equipment_block(player), "", f"  Coin: {player.get('wealth', 0)}", "  Pack:"]
    if not inv:
        lines.append("    (empty)")
    else:
        for idx, item in enumerate(inv, 1):
            lines.append(f"  [{idx}] {format_item_line(item).strip()}")
    lines.append("  (equip <#> · use <#> · unequip weapon|armor|trinket)")
    return "\n".join(lines)


def _resolve_inv_item(player, arg):
    inv = player.get("inventory") or []
    if not arg:
        return None, "Specify a pack number (see inventory)."
    try:
        idx = int(arg) - 1
        if 0 <= idx < len(inv):
            return inv[idx], None
    except ValueError:
        pass
    needle = arg.lower()
    for item in inv:
        if not isinstance(item, dict):
            continue
        if item.get("id", "").startswith(needle) or needle in item.get("name", "").lower():
            return item, None
    return None, f"No item matching '{arg}' in your pack."


def _cmd_equip(player, arg=""):
    from simulation.item_engine import equip_item, ensure_equipment
    ensure_equipment(player)
    item, err = _resolve_inv_item(player, arg.strip())
    if err:
        return f"  {err}"
    if not item:
        return "  Usage: equip <#>  (see inventory for numbers)"
    msg = equip_item(player, item["id"])
    save(PLAYER_FILE, player)
    return f"  {msg}"


def _cmd_unequip(player, arg=""):
    from simulation.item_engine import unequip_item
    slot = (arg or "").strip().lower()
    if not slot:
        return "  Usage: unequip weapon | armor | trinket"
    msg = unequip_item(player, slot)
    save(PLAYER_FILE, player)
    return f"  {msg}"


def _cmd_use(player, arg=""):
    from simulation.item_engine import use_consumable
    item, err = _resolve_inv_item(player, arg.strip())
    if err:
        return f"  {err}"
    if not item:
        return "  Usage: use <#>  (consumables only)"
    msg, ok = use_consumable(player, item["id"])
    if ok:
        save(PLAYER_FILE, player)
    return f"  {msg}"


def _cmd_where(player, world):
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    area = areas.get(player.get("area"), {})
    city_key = player.get("location", "?")
    city_name = locs.get("cities", {}).get(city_key, {}).get("name", city_key)
    lines = [
        f"  City:     {city_name}",
        f"  District: {area.get('name', player.get('area', '?'))}",
        f"  Time:     Day {world.get('day', '?')}, {world.get('hour', '?')}:00 — {world.get('time_of_day', '')}",
        f"  Weather:  {world.get('weather', '?')}, {world.get('season', '')}",
    ]
    sl = area.get("storyline")
    if sl:
        lines.append(f"  Story here: {sl.get('title', '')} — {sl.get('current', sl.get('hook', ''))[:100]}")
    return "\n".join(lines)


def _cmd_map(player):
    dests = list_destinations(player.get("area"))
    if not dests:
        return "  Nowhere obvious to travel from here."
    areas = load(AREAS_FILE, {})
    lines = ["  You can travel to:"]
    for aid, hours in sorted(dests.items(), key=lambda x: x[1]):
        name = areas.get(aid, {}).get("name", aid.split(":")[-1])
        lines.append(f"    • {name} ({hours} hours) — try: go to {aid.split(':')[-1]}")
    return "\n".join(lines)


def _cmd_factions(player):
    lines = ["  Faction standing:"]
    fl = format_faction_standing(player)
    lines.extend(fl if fl else ["    (no factions tracked)"])
    return "\n".join(lines)


def _cmd_guilds(player):
    institutions = load(INST_FILE, {})
    ensure_institution_standing(player, institutions)
    lines = ["  Institutions:"]
    gl = format_institution_standing(player, institutions)
    lines.extend(gl)
    primary = player.get("primary_institution")
    if primary:
        lines.append(
            f"\n  Primary affiliation: {primary.get('name')} "
            f"({primary.get('rank_label', '?')})"
        )
    return "\n".join(lines)


def _cmd_bounties(player, world):
    return format_bounties(player, world)


def _cmd_bestiary(player):
    return format_bestiary(player)


def _cmd_case(player):
    npcs = load(NPC_FILE, {})
    return format_case_status(player, npcs)


def _cmd_routines(player):
    npcs = load(NPC_FILE, {})
    world = load("world/world_state.json", {})
    areas = load(AREAS_FILE, {})
    here = [
        n for n in npcs.values()
        if n.get("status") == "alive" and n.get("area") == player.get("area")
    ]
    if not here:
        return "  No one with a known routine in this district right now."
    lines = ["  Routines nearby:"]
    for n in here[:5]:
        lines.append(f"    • {n.get('name', '?')}: {schedule_hint(n, world)}")
        nxt = next_appearance(n, world, areas)
        if nxt and nxt.get("area") != player.get("area"):
            lines.append(f"      Next: {nxt['area_name']} in ~{nxt['in_hours']}h ({nxt.get('label', '')})")
    return "\n".join(lines)


def _cmd_goals(player):
    goals = player.get("goals") or []
    if not goals and player.get("motivation"):
        goals = build_player_goals(player.get("motivation"), player.get("background"))
    lines = ["  Your goals:"]
    if not goals:
        lines.append("    (none set — pick a direction through play)")
    for g in goals:
        mark = "✓" if g.get("complete") else "○"
        lines.append(f"    {mark} {g.get('text', '')}")
        lines.append(f"       Progress: {g.get('progress', 0)}/{g.get('target', '?')}  —  {g.get('hint', '')}")
    area_arc = arc_for_area(player.get("area"))
    if area_arc:
        lines.append(f"\n  Local storyline: {area_arc.get('title', '')}")
        lines.append(f"    Now: {area_arc.get('current', '')}")
        if area_arc.get("key_npcs"):
            npcs = load(NPC_FILE, {})
            names = []
            for nid in area_arc["key_npcs"][:3]:
                n = npcs.get(nid, {})
                kn = player.get("known_npcs", {}).get(nid, {})
                names.append(n["name"] if kn.get("name_known") else "someone important here")
            lines.append(f"    Key figures: {', '.join(names)}")
    return "\n".join(lines)


def _cmd_journal(player):
    journal = player.get("journal") or []
    if not journal:
        return "  Nothing written yet."
    lines = ["  Recent events:"]
    for entry in journal[-6:]:
        lines.append(f"    • [{entry.get('kind', '?')}] {entry.get('action', '')[:60]}")
        ex = (entry.get("excerpt") or "")[:100]
        if ex:
            lines.append(f"      \"{ex}...\"")
    return "\n".join(lines)


def _cmd_bonds(player):
    rels = load(REL_FILE, {})
    known = player.get("known_npcs", {})
    npcs = load(NPC_FILE, {})
    lines = ["  Bonds (how they feel about you):"]
    found = False
    for nid, rec in known.items():
        if not rec.get("seen_before"):
            continue
        rel = rels.get(nid, {}).get("player", {})
        if not rel or rel.get("familiarity", 0) < 3:
            continue
        found = True
        name = npcs.get(nid, {}).get("name", nid) if rec.get("name_known") else "a stranger you've met"
        lines.append(
            f"    {name}: trust {rel.get('trust', 0):.0f}, fear {rel.get('fear', 0):.0f}, "
            f"respect {rel.get('respect', 0):.0f}, affection {rel.get('affection', 0):.0f}"
        )
    if not found:
        lines.append("    No one knows you well enough yet.")
    return "\n".join(lines)


def _cmd_check(player):
    lc = player.get("last_check")
    if not lc:
        return "  No skill check yet this session."
    result = "SUCCESS" if lc.get("success") else "FAIL"
    lines = [
        f"  Last check ({lc.get('kind', '?')}): {result}",
        f"  Skill: {lc.get('skill', '?')}  Roll: {lc.get('roll', '?')} + modifiers = {lc.get('total', '?')} vs DC {lc.get('difficulty', '?')}",
        f"  Margin: {lc.get('margin', '?')}",
    ]
    if lc.get("consequence"):
        lines.append(f"  Outcome: {lc['consequence']}")
    return "\n".join(lines)


def _cmd_status(player, world):
    parts = [
        "=" * 48,
        _cmd_stats(player),
        "",
        _cmd_skills(player),
        "",
        _cmd_inventory(player),
        "",
        _cmd_where(player, world),
        "",
        active_goal_hint(player, arc_for_area(player.get("area"))),
        "=" * 48,
    ]
    return "\n".join(parts)


_ALIASES = {
    "help": lambda p, w: _cmd_help(),
    "?": lambda p, w: _cmd_help(),
    "stats": lambda p, w: _cmd_stats(p),
    "status": lambda p, w: _cmd_status(p, w),
    "sheet": lambda p, w: _cmd_status(p, w),
    "skills": lambda p, w: _cmd_skills(p),
    "inventory": lambda p, w: _cmd_inventory(p),
    "inv": lambda p, w: _cmd_inventory(p),
    "goals": lambda p, w: _cmd_goals(p),
    "objectives": lambda p, w: _cmd_goals(p),
    "map": lambda p, w: _cmd_map(p),
    "where": lambda p, w: _cmd_where(p, w),
    "journal": lambda p, w: _cmd_journal(p),
    "bonds": lambda p, w: _cmd_bonds(p),
    "relationships": lambda p, w: _cmd_bonds(p),
    "factions": lambda p, w: _cmd_factions(p),
    "reputation": lambda p, w: _cmd_factions(p),
    "guilds": lambda p, w: _cmd_guilds(p),
    "institutions": lambda p, w: _cmd_guilds(p),
    "lodge": lambda p, w: _cmd_guilds(p),
    "bounties": lambda p, w: _cmd_bounties(p, w),
    "bestiary": lambda p, w: _cmd_bestiary(p),
    "case": lambda p, w: _cmd_case(p),
    "investigation": lambda p, w: _cmd_case(p),
    "routines": lambda p, w: _cmd_routines(p),
    "schedule": lambda p, w: _cmd_routines(p),
    "check": lambda p, w: _cmd_check(p),
}


def try_meta_command(action):
    """
    If action is a meta-command, return formatted output.
    Otherwise return None (caller should run normal story processing).
    """
    raw = (action or "").strip()
    if not raw:
        return None

    cmd = raw.lower()
    if cmd.startswith("/"):
        cmd = cmd[1:].split()[0] if cmd[1:] else "help"

    if cmd == "hints" or cmd.startswith("hints "):
        player = load(PLAYER_FILE, {})
        parts = raw.lower().split()
        if len(parts) == 1:
            return format_hint_setting(player)
        mode_word = parts[1]
        mode_map = {"on": "plain", "plain": "plain", "subtle": "subtle", "off": "off", "0": "off", "1": "plain"}
        mode = mode_map.get(mode_word)
        if not mode:
            return format_hint_setting(player) + "\n  Usage: hints off | subtle | plain"
        set_hint_mode(player, mode)
        save(PLAYER_FILE, player)
        return format_hint_setting(player)

    parts = raw.lower().split(maxsplit=1)
    verb = parts[0].lstrip("/")
    arg = parts[1] if len(parts) > 1 else ""
    if verb in ("equip", "use", "unequip"):
        player = load(PLAYER_FILE, {})
        if verb == "equip":
            return _cmd_equip(player, arg)
        if verb == "use":
            return _cmd_use(player, arg)
        return _cmd_unequip(player, arg)

    handler = _ALIASES.get(cmd)
    if not handler:
        return None

    player = load(PLAYER_FILE, {})
    world = load("world/world_state.json", {})
    return handler(player, world)
