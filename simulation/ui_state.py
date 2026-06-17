"""
Structured game state for the web UI — read-only views of player/world data.
"""

from storage import load
from generation.descriptor_generator import brief_appearance, gender_label
from simulation.progression_engine import skill_level
from simulation.travel_engine import list_destinations
from simulation.player_goals import active_goal_hint
from simulation.storyline_engine import arc_for_area
from simulation.item_engine import ensure_equipment, equipment_bonuses, apply_equipment_to_entity
from simulation.relationship_thresholds import relationship_state
from simulation.faction_reputation import ensure_faction_standing, _label as faction_label
from simulation.institution_membership import ensure_institution_standing, INST_TYPE_LABELS
from simulation.district_state import ensure_district_state
from simulation.area_discovery import get_discovered_places_view, migrate_discovered_areas
from simulation.scene_coherence import place_label

PLAYER_FILE = "player/player.json"
WORLD_FILE = "world/world_state.json"
AREAS_FILE = "world/areas.json"
LOC_FILE = "world/locations.json"
NPC_FILE = "characters/npcs.json"
REL_FILE = "characters/relationships.json"
INST_FILE = "world/institutions.json"
FACTION_FILE = "world/factions.json"
RUMOR_FILE = "rumors/rumors.json"

HELP_COMMANDS = [
    {"cmd": "status", "aliases": ["sheet"], "desc": "Overview — stats, place, goals"},
    {"cmd": "stats", "aliases": [], "desc": "Health, stamina, attributes"},
    {"cmd": "skills", "aliases": [], "desc": "Skill levels and XP"},
    {"cmd": "inventory", "aliases": ["inv"], "desc": "Equipped gear and pack"},
    {"cmd": "equip", "aliases": [], "desc": "Wear item — equip 2"},
    {"cmd": "unequip", "aliases": [], "desc": "Remove gear — unequip weapon"},
    {"cmd": "use", "aliases": [], "desc": "Use consumable — use 1"},
    {"cmd": "goals", "aliases": ["objectives"], "desc": "What you're trying to achieve"},
    {"cmd": "map", "aliases": [], "desc": "Travel destinations from here"},
    {"cmd": "where", "aliases": [], "desc": "City, district, time, weather"},
    {"cmd": "journal", "aliases": [], "desc": "Recent story beats"},
    {"cmd": "bonds", "aliases": ["relationships"], "desc": "How people feel about you"},
    {"cmd": "factions", "aliases": ["reputation"], "desc": "Faction standing"},
    {"cmd": "guilds", "aliases": ["institutions", "lodge"], "desc": "Guild / lodge membership"},
    {"cmd": "bounties", "aliases": [], "desc": "Posted monster hunts"},
    {"cmd": "bestiary", "aliases": [], "desc": "Beasts seen or slain"},
    {"cmd": "case", "aliases": ["investigation"], "desc": "Active investigation"},
    {"cmd": "check", "aliases": [], "desc": "Last skill check result"},
    {"cmd": "hints", "aliases": [], "desc": "Toggle suggestions — off / subtle / plain"},
    {"cmd": "help", "aliases": ["?"], "desc": "Command list"},
]


def _bar_pct(val, max_val=100):
    if not max_val:
        return 0
    return max(0, min(100, int(100 * val / max_val)))


def _serialize_item(item, index=None):
    if not isinstance(item, dict):
        return {"index": index, "name": str(item), "raw": True}
    stat_mods = item.get("stat_mods") or {}
    skill_mods = item.get("skill_mods") or {}
    effect = item.get("effect")
    return {
        "index": index,
        "id": item.get("id"),
        "name": item.get("name", "item"),
        "category": item.get("category"),
        "rarity": item.get("rarity", "common"),
        "slot": item.get("slot"),
        "value": item.get("value"),
        "stat_mods": stat_mods,
        "skill_mods": skill_mods,
        "effect": effect,
        "equippable": bool(item.get("slot")),
        "consumable": item.get("category") == "consumable",
        "mod_summary": _mod_summary(stat_mods, skill_mods, effect),
    }


def _mod_summary(stat_mods, skill_mods, effect):
    parts = [f"+{v} {k}" for k, v in stat_mods.items()]
    parts += [f"+{v} {k}" for k, v in skill_mods.items()]
    if effect:
        parts += [f"{v} {k}" for k, v in effect.items()]
    return ", ".join(parts)


def get_equipment_view(player):
    ensure_equipment(player)
    inv_by_id = {
        i.get("id"): i
        for i in (player.get("inventory") or [])
        if isinstance(i, dict) and i.get("id")
    }
    slots = {}
    for slot in ("weapon", "armor", "trinket"):
        iid = player["equipment"].get(slot)
        item = inv_by_id.get(iid) if iid else None
        slots[slot] = _serialize_item(item) if item else None
    return slots


def get_inventory_view(player):
    inv = player.get("inventory") or []
    return [_serialize_item(item, index=i + 1) for i, item in enumerate(inv)]


def get_scene_labels(player, world=None):
    world = world or load(WORLD_FILE, {})
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    area = areas.get(player.get("area"), {})
    city_key = player.get("location", "?")
    loc_city = locs.get("cities", {}).get(city_key, {})
    city_name = loc_city.get("name") or (
        city_key.replace("_", " ").title() if city_key and city_key != "unknown" else ""
    )
    district = place_label(player, area) or area.get("name", "")
    if not district and player.get("area"):
        district = str(player.get("area")).split(":")[-1].replace("_", " ").title()
    day = world.get("day", "?")
    tod = world.get("time_of_day", "")
    time_label = f"Day {day}"
    if tod:
        time_label += f" · {tod.title()}"
    location_label = f"{city_name} — {district}" if district and city_name else (district or city_name or "Unplaced")
    place_short = district or city_name or "Unplaced"
    return {
        "time": time_label,
        "location": location_label,
        "place_short": place_short,
        "weather": world.get("weather", ""),
        "season": world.get("season", ""),
    }


def _npc_known_facts(npc, known_rec, areas):
    facts = []
    role = npc.get("role") or npc.get("occupation")
    if role:
        facts.append(f"Works as {role.replace('_', ' ')}")
    area_id = npc.get("area") or npc.get("location")
    if area_id and areas.get(area_id):
        facts.append(f"Seen near {areas[area_id].get('name', area_id.split(':')[-1])}")
    elif npc.get("location"):
        facts.append(f"Based in {npc.get('location', '').replace('_', ' ')}")
    imp = (known_rec or {}).get("impression") or {}
    if imp.get("hint") and imp.get("hint") != "no strong first read":
        facts.append(imp["hint"].capitalize())
    injuries = npc.get("injuries") or []
    if injuries:
        facts.append(f"Injured: {', '.join(injuries[:2])}")
    inst = npc.get("institution") or {}
    if inst.get("name"):
        facts.append(f"Affiliated with {inst['name']}")
    return facts[:5]


def _relation_bars(rel):
    if not rel:
        return {}
    return {
        "trust": {"value": rel.get("trust", 0), "pct": _bar_pct(rel.get("trust", 0))},
        "respect": {"value": rel.get("respect", 0), "pct": _bar_pct(rel.get("respect", 0))},
        "fear": {"value": rel.get("fear", 0), "pct": _bar_pct(rel.get("fear", 0))},
        "affection": {"value": rel.get("affection", 0), "pct": _bar_pct(rel.get("affection", 0))},
        "familiarity": {"value": rel.get("familiarity", 0), "pct": _bar_pct(rel.get("familiarity", 0))},
    }


def _city_display(city_key, locs):
    if not city_key:
        return ""
    return locs.get("cities", {}).get(city_key, {}).get("name", city_key.replace("_", " ").title())


def _format_destination(aid, hours, areas, locs):
    area = areas.get(aid, {})
    name = area.get("name", aid.split(":")[-1].replace("_", " ").title())
    prefix = aid.split(":")[0] if ":" in aid else ""
    area_type = area.get("area_type") or area.get("type") or ""

    if prefix == "wild" or area.get("type") == "wilderness":
        slug = aid.split(":", 1)[-1]
        parts = slug.split("_")
        if len(parts) >= 2:
            route = f"{_city_display(parts[0], locs)} → {_city_display(parts[-1], locs)}"
        else:
            route = slug.replace("_", " → ")
        kind_label = {
            "road": "Road",
            "forest": "Forest",
            "moor": "Moor",
            "hills": "Hills",
        }.get(area_type, "Wilderness")
        detail = f"{kind_label} · {route}"
        region = "Wilderness"
    else:
        city_key = area.get("city") or prefix
        city_name = _city_display(city_key, locs)
        kind_label = "District" if area.get("type") == "district" else area_type.replace("_", " ").title()
        detail = f"{city_name} · {kind_label}"
        region = city_name

    return {
        "id": aid,
        "name": name,
        "hours": hours,
        "detail": detail,
        "region": region,
        "label": f"{name} — {detail}",
    }


def get_relations_view(player, limit=None, named_only=True):
    rels = load(REL_FILE, {})
    known = player.get("known_npcs", {})
    npcs = load(NPC_FILE, {})
    areas = load(AREAS_FILE, {})
    focus_id = player.get("scene_focus")

    cards = []
    for nid, rec in known.items():
        if not rec.get("seen_before"):
            continue
        name_known = rec.get("name_known", False)
        if named_only and not name_known:
            continue
        npc = npcs.get(nid, {})
        if npc.get("status") != "alive":
            continue
        rel = rels.get(nid, {}).get("player", {})
        fam = rel.get("familiarity", 0) if rel else 0
        name = npc.get("name", "Someone") if name_known else "A stranger you've met"
        state_id, state_label = relationship_state(rel)
        cards.append({
            "id": nid,
            "name": name,
            "name_known": name_known,
            "gender": gender_label(npc),
            "description": brief_appearance(npc),
            "state": state_label,
            "state_id": state_id,
            "is_focus": nid == focus_id,
            "familiarity": fam,
            "bars": _relation_bars(rel),
            "facts": _npc_known_facts(npc, rec, areas) if name_known or fam >= 5 else [],
        })

    cards.sort(key=lambda c: (c["is_focus"], c["familiarity"]), reverse=True)
    if limit:
        cards = cards[:limit]
    return cards


def get_rumors_view(player, limit=20):
    rumors = load(RUMOR_FILE, [])
    if not rumors:
        return []
    locs = load(LOC_FILE, {})
    city_key = player.get("location", "")
    city_name = locs.get("cities", {}).get(city_key, {}).get("name", city_key)
    city_l = (city_name or city_key).lower().replace("_", " ")

    seen = set()
    out = []
    for r in reversed(rumors):
        text = (r.get("text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        local = city_l and city_l in text.lower()
        out.append({
            "text": text,
            "interpretation": r.get("interpretation", ""),
            "local": local,
        })
        if len(out) >= limit:
            break
    out.sort(key=lambda x: (not x["local"], x["text"]))
    return out[:limit]


def get_codex_view(player):
    npcs = load(NPC_FILE, {})
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    institutions = load(INST_FILE, {})
    factions = load(FACTION_FILE, {})
    world = load(WORLD_FILE, {})
    known = player.get("known_npcs", {})
    city_key = player.get("location")

    people = []
    for nid, rec in known.items():
        if not rec.get("seen_before"):
            continue
        npc = npcs.get(nid, {})
        if rec.get("name_known"):
            people.append({
                "id": nid,
                "name": npc.get("name", nid),
                "role": (npc.get("role") or "").replace("_", " "),
            })
        elif rec.get("times_seen", 0) >= 5:
            people.append({"id": nid, "name": "Unknown face", "role": "seen often"})

    people.sort(key=lambda p: p["name"])
    people = people[:40]

    migrate_discovered_areas(player)
    places = get_discovered_places_view(player)

    inst_book = ensure_institution_standing(player, institutions)
    inst_entries = []
    for iid, inst in institutions.items():
        if inst.get("city") and inst.get("city") != city_key:
            continue
        entry = inst_book.get(iid, {})
        rank = entry.get("rank", "outsider")
        if rank != "outsider" or inst.get("city") == city_key:
            inst_entries.append({
                "id": iid,
                "name": inst.get("name", iid),
                "type": INST_TYPE_LABELS.get(inst.get("type"), inst.get("type", "")),
                "rank": entry.get("rank_label", "Outsider"),
            })
    inst_entries.sort(key=lambda x: x["name"])

    fac_book = ensure_faction_standing(player, factions)
    fac_entries = []
    for fid, fac in factions.items():
        entry = fac_book.get(fid, {})
        score = entry.get("score", 0)
        _, desc = faction_label(score)
        if score != 0 or entry.get("rank", "outsider") != "outsider":
            fac_entries.append({
                "id": fid,
                "name": fac.get("name", fid),
                "standing": desc.split(" — ")[0] if " — " in desc else desc,
                "score": score,
            })
    fac_entries.sort(key=lambda x: -abs(x["score"]))

    history = []
    if player.get("journal"):
        for h in (world.get("history") or [])[:8]:
            history.append({
                "when": h.get("when", ""),
                "official": h.get("official", ""),
                "folk": h.get("folk", ""),
            })

    return {
        "people": people,
        "places": places,
        "institutions": inst_entries,
        "factions": fac_entries,
        "history": history,
    }


def get_timeline_view(player):
    journal = player.get("journal") or []
    by_day = {}
    for entry in journal:
        day = entry.get("day", 0)
        by_day.setdefault(day, []).append({
            "action": entry.get("action", ""),
            "kind": entry.get("kind", ""),
            "hour": entry.get("hour"),
            "excerpt": (entry.get("excerpt") or "")[:120],
        })
    timeline = []
    for day in sorted(by_day.keys()):
        timeline.append({"day": day, "events": by_day[day]})
    return timeline


def get_story_history(player, limit=60):
    """Past turns for the web story pane (from journal)."""
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    blocks = []
    for entry in player.get("journal") or []:
        text = (entry.get("scene") or entry.get("excerpt") or "").strip()
        if not text or text == "[scene ok]":
            continue
        area = areas.get(entry.get("area"), {})
        city_key = entry.get("location") or player.get("location", "")
        city_name = locs.get("cities", {}).get(city_key, {}).get("name", city_key)
        district = area.get("name") or entry.get("area", "")
        place = entry.get("place") or district or city_name
        day = entry.get("day", "?")
        hour = entry.get("hour")
        time_label = f"Day {day}"
        if hour is not None:
            time_label += f" · {hour}:00"
        blocks.append({
            "action": entry.get("action", ""),
            "time": time_label,
            "location": place.split(":")[-1] if place else city_name,
            "scene": text,
            "meta": text.startswith("  ") or text.startswith("Commands"),
        })
    return blocks[-limit:]


def get_header_bar(player, world=None):
    world = world or load(WORLD_FILE, {})
    labels = get_scene_labels(player, world)
    stats = player.get("stats") or {}
    return {
        **labels,
        "health": {
            "current": stats.get("health", 0),
            "max": stats.get("max_health", 100),
            "pct": _bar_pct(stats.get("health", 0), stats.get("max_health", 100)),
        },
        "stamina": {
            "current": stats.get("stamina", 0),
            "max": stats.get("max_stamina", 30),
            "pct": _bar_pct(stats.get("stamina", 0), stats.get("max_stamina", 30)),
        },
        "wealth": player.get("wealth", 0),
    }


def get_world_sidebar(player, world=None):
    world = world or load(WORLD_FILE, {})
    areas = load(AREAS_FILE, {})
    factions = load(FACTION_FILE, {})
    area = areas.get(player.get("area"), {})
    st = ensure_district_state(area) if area else {}

    fac_book = ensure_faction_standing(player, factions)
    top_factions = []
    for fid, entry in sorted(fac_book.items(), key=lambda x: -abs(x[1].get("score", 0)))[:3]:
        fac = factions.get(fid, {})
        score = entry.get("score", 0)
        if score == 0:
            continue
        _, desc = faction_label(score)
        top_factions.append({"name": fac.get("name", fid), "standing": desc.split(" — ")[0]})

    return {
        "weather": world.get("weather", "?"),
        "season": world.get("season", ""),
        "district_mood": st.get("mood", "uneasy") if st else "unknown",
        "prosperity": int(st.get("prosperity", 0)) if st else None,
        "crime": int(st.get("crime_level", 0)) if st else None,
        "factions": top_factions,
        "storyline": (area.get("storyline") or {}).get("title"),
    }


def get_player_panel(player):
    ensure_equipment(player)
    stat_mods, skill_mods = equipment_bonuses(player)
    stats = player.get("stats") or {}
    base = stats
    effective = apply_equipment_to_entity(player) if player.get("journal") is not None else base

    goals = []
    for g in player.get("goals") or []:
        goals.append({
            "text": g.get("text", ""),
            "hint": g.get("hint", ""),
            "progress": g.get("progress", 0),
            "target": g.get("target", 0),
        })

    lc = player.get("last_check")
    last_check = None
    if lc:
        last_check = {
            "kind": lc.get("kind"),
            "skill": lc.get("skill"),
            "success": lc.get("success"),
            "roll": lc.get("roll"),
            "total": lc.get("total"),
            "difficulty": lc.get("difficulty"),
            "margin": lc.get("margin"),
            "consequence": lc.get("consequence"),
        }

    attrs = stats.get("attributes") or {}
    skills = {}
    for sk, node in sorted((player.get("skills") or {}).items()):
        if isinstance(node, dict):
            skills[sk] = {"level": node.get("level", skill_level(player, sk)), "xp": node.get("xp", 0)}
        else:
            skills[sk] = {"level": skill_level(player, sk), "xp": 0}

    return {
        "name": player.get("name", "You"),
        "level": player.get("level", 1),
        "background": player.get("background"),
        "appearance": player.get("appearance"),
        "motivation": player.get("motivation"),
        "skills": skills,
        "health": {
            "current": stats.get("health", 0),
            "max": stats.get("max_health", 100),
        },
        "stamina": {
            "current": stats.get("stamina", 0),
            "max": stats.get("max_stamina", 30),
        },
        "stress": {
            "current": stats.get("stress", 0),
            "max": stats.get("max_stress", 100),
        },
        "combat": {
            "attack": effective.get("attack", base.get("attack", 0)),
            "defense": effective.get("defense", base.get("defense", 0)),
            "speed": effective.get("speed", base.get("speed", 0)),
        },
        "attributes": dict(sorted(attrs.items())),
        "injuries": list(player.get("injuries") or []),
        "wealth": player.get("wealth", 0),
        "goals": goals,
        "goal_hint": active_goal_hint(player, arc_for_area(player.get("area"))),
        "last_check": last_check,
        "needs_opening": not bool(player.get("journal")),
    }


def get_inventory_panel(player):
    ensure_equipment(player)
    stat_mods, skill_mods = equipment_bonuses(player)
    return {
        "wealth": player.get("wealth", 0),
        "equipment": get_equipment_view(player),
        "inventory": get_inventory_view(player),
        "bonuses": {"stats": stat_mods, "skills": skill_mods},
    }


def get_world_panel(player):
    world = load(WORLD_FILE, {})
    areas = load(AREAS_FILE, {})
    locs = load(LOC_FILE, {})
    area = areas.get(player.get("area"), {})
    city_key = player.get("location", "?")
    city_name = locs.get("cities", {}).get(city_key, {}).get("name", city_key)

    dests = []
    for aid, hours in sorted(list_destinations(player.get("area")).items(), key=lambda x: x[1]):
        dests.append(_format_destination(aid, hours, areas, locs))

    sl = area.get("storyline")
    storyline = None
    if sl:
        storyline = {
            "title": sl.get("title", ""),
            "current": (sl.get("current") or sl.get("hook") or "")[:160],
        }

    labels = get_scene_labels(player, world)
    return {
        "city": city_name,
        "city_key": city_key,
        "district": area.get("name", player.get("area", "?")),
        "area_key": player.get("area"),
        "day": world.get("day"),
        "hour": world.get("hour"),
        "time_of_day": world.get("time_of_day", ""),
        "weather": world.get("weather", "?"),
        "season": world.get("season", ""),
        "destinations": dests,
        "storyline": storyline,
        "labels": labels,
    }


def _check_snapshot(lc):
    if not lc:
        return None
    return {
        "kind": lc.get("kind"),
        "skill": lc.get("skill"),
        "success": lc.get("success"),
        "roll": lc.get("roll"),
        "total": lc.get("total"),
        "difficulty": lc.get("difficulty"),
        "margin": lc.get("margin"),
    }


def _player_delta_rows(before, player):
    stats = player.get("stats") or {}
    rows = []
    for label, key in (("Health", "health"), ("Stamina", "stamina"), ("Stress", "stress")):
        prev = before.get(key, 0)
        after = stats.get(key, 0)
        if prev != after:
            rows.append({"label": label, "delta": after - prev, "after": after})
    scalar_fields = (
        ("Wealth", "wealth", lambda p: p.get("wealth", 0)),
        ("Level", "level", lambda p: p.get("level", 1)),
        ("XP", "xp", lambda p: p.get("xp", 0)),
    )
    for label, key, getter in scalar_fields:
        prev = before.get(key, 0)
        after = getter(player)
        if prev != after:
            rows.append({"label": label, "delta": after - prev, "after": after})
    return rows


def _npc_delta_rows(before, player):
    rows = []
    old_rel = {c["id"]: c for c in before.get("relations_full", [])}
    for card in get_relations_view(player):
        prev = old_rel.get(card["id"])
        if not prev:
            if card["familiarity"] >= 3:
                rows.append({
                    "name": card["name"],
                    "stat": "met",
                    "delta": 0,
                    "after": card["familiarity"],
                    "new": True,
                })
            continue
        prev_bars = prev.get("bars") or {}
        for key in ("trust", "respect", "fear", "affection", "familiarity"):
            pv = prev_bars.get(key, {}).get("value", 0)
            av = card["bars"][key]["value"]
            if pv != av:
                rows.append({
                    "name": card["name"],
                    "stat": key,
                    "delta": av - pv,
                    "after": av,
                    "focus": card.get("is_focus", False),
                })
    rows.sort(key=lambda r: (not r.get("focus"), -abs(r.get("delta", 0))))
    return rows


def compute_turn_deltas(before, player, world):
    """Stat and relationship changes since the start of the turn."""
    if not before:
        return {
            "player": [],
            "npcs": [],
            "items": [],
            "rumors": [],
            "other": [],
            "skill_check": None,
            "empty": True,
        }

    player_rows = _player_delta_rows(before, player)
    npc_rows = _npc_delta_rows(before, player)

    old_ids = set(before.get("inventory_ids") or [])
    items = []
    for item in get_inventory_view(player):
        iid = item.get("id") or item.get("name")
        if iid and iid not in old_ids:
            items.append({"name": item.get("name", "item"), "rarity": item.get("rarity", "common")})

    old_rumor_texts = {r.get("text") for r in before.get("rumors", [])}
    rumors = []
    for r in get_rumors_view(player, limit=10):
        if r["text"] not in old_rumor_texts:
            rumors.append(r["text"])

    other = []
    if before.get("area") != player.get("area"):
        labels = get_scene_labels(player, world)
        other.append({"label": "Location", "text": labels["place_short"]})

    skill_check = None
    lc = player.get("last_check")
    if lc and _check_snapshot(lc) != before.get("last_check"):
        skill_check = {
            "kind": lc.get("kind"),
            "skill": lc.get("skill"),
            "success": lc.get("success"),
            "roll": lc.get("roll"),
            "total": lc.get("total"),
            "difficulty": lc.get("difficulty"),
            "margin": lc.get("margin"),
            "consequence": lc.get("consequence"),
        }

    empty = not (player_rows or npc_rows or items or rumors or other or skill_check)
    return {
        "player": player_rows,
        "npcs": npc_rows[:10],
        "items": items[:6],
        "rumors": rumors[:4],
        "other": other,
        "skill_check": skill_check,
        "empty": empty,
    }


def build_turn_metadata(player, world, action_text, before=None):
    """Structured turn payload for the web UI (CLI ignores this)."""
    from simulation.turn_trace import get_last_turn

    labels = get_scene_labels(player, world)
    journal = player.get("journal") or []
    journal_entry = journal[-1] if journal else None
    deltas = compute_turn_deltas(before, player, world)

    new_rumors = deltas.get("rumors") or []
    rel_changes = []
    codex_entries = []

    if before:
        old_rel = {c["id"]: c["bars"] for c in before.get("relations_full", [])}
        for card in get_relations_view(player):
            prev = old_rel.get(card["id"])
            if not prev:
                if card["familiarity"] >= 3:
                    codex_entries.append({"category": "people", "name": card["name"]})
                continue
            for key in ("trust", "respect", "fear", "affection"):
                pv = prev.get(key, {}).get("value", 0)
                av = card["bars"][key]["value"]
                if abs(av - pv) >= 3:
                    rel_changes.append({
                        "name": card["name"],
                        "stat": key,
                        "value": av,
                        "delta": av - pv,
                    })
                    break

    new_place = None
    arr = get_last_turn().get("area_arrival")
    if arr and arr.get("first_visit"):
        new_place = {
            "id": arr.get("id"),
            "name": arr.get("name"),
            "subtitle": arr.get("subtitle"),
            "description": arr.get("description"),
        }

    return {
        "action": action_text,
        "time": labels["time"],
        "location": labels["place_short"],
        "weather": labels.get("weather"),
        "journal_entry": journal_entry,
        "new_rumors": new_rumors[:3],
        "relationship_changes": rel_changes[:3],
        "codex_entries": codex_entries[:3],
        "new_place": new_place,
        "deltas": deltas,
    }


def snapshot_for_delta(player):
    stats = player.get("stats") or {}
    inv_ids = []
    for item in player.get("inventory") or []:
        if isinstance(item, dict):
            inv_ids.append(item.get("id") or item.get("name"))
    return {
        "health": stats.get("health", 0),
        "stamina": stats.get("stamina", 0),
        "stress": stats.get("stress", 0),
        "wealth": player.get("wealth", 0),
        "level": player.get("level", 1),
        "xp": player.get("xp", 0),
        "area": player.get("area"),
        "inventory_ids": inv_ids,
        "last_check": _check_snapshot(player.get("last_check")),
        "rumors": get_rumors_view(player, limit=30),
        "relations_full": get_relations_view(player),
    }


def get_investigation_panel(player, npcs=None):
    case = player.get("active_case")
    if not case:
        return None
    npcs = npcs or load(NPC_FILE, {})
    stage = case.get("stage", 0)
    stages = case.get("stages") or []
    stage_label = stages[min(stage, len(stages) - 1)] if stages else ""
    clues = [
        {"text": ev.get("text", ""), "type": ev.get("type", "")}
        for ev in case.get("evidence", [])
        if ev.get("discovered")
    ]
    suspects = [
        {"id": sid, "name": npcs.get(sid, {}).get("name", "?")}
        for sid in case.get("suspect_ids", [])
    ]
    accused_id = case.get("accused_id")
    return {
        "active": not case.get("solved"),
        "title": case.get("title", "Mystery"),
        "kind": case.get("kind", "murder"),
        "stage": stage + 1,
        "stage_total": len(stages) or 4,
        "stage_label": stage_label,
        "victim_name": case.get("victim_name"),
        "clues": clues[:6],
        "suspects": suspects[:4],
        "solved": bool(case.get("solved")),
        "accused_name": npcs.get(accused_id, {}).get("name") if accused_id else None,
    }


def get_full_state():
    from config.debug import debug_enabled
    from game.state_context import state_lock
    from game.undo import can_undo
    from simulation.gemini_client import api_key
    from simulation.investigation_cases import sanitize_active_case

    with state_lock():
        player = load(PLAYER_FILE, {})
        if not player:
            return None
        world = load(WORLD_FILE, {})
        npcs = load(NPC_FILE, {})
        areas = load(AREAS_FILE, {})
        return {
        "header": get_header_bar(player, world),
        "player": get_player_panel(player),
        "world": get_world_panel(player),
        "world_sidebar": get_world_sidebar(player, world),
        "inventory_panel": get_inventory_panel(player),
        "relations": get_relations_view(player, limit=4),
        "relations_full": get_relations_view(player),
        "rumors": get_rumors_view(player, limit=5),
        "rumors_full": get_rumors_view(player, limit=25),
        "codex": get_codex_view(player),
        "timeline": get_timeline_view(player),
        "story_history": get_story_history(player),
        "investigation": get_investigation_panel(player, npcs),
        "help": HELP_COMMANDS,
        "session": {
            "can_undo": can_undo(),
            "gemini_configured": bool(api_key()),
            "debug_enabled": debug_enabled(),
        },
    }
