"""
Contextual action suggestions — optional, off by default.

Subtle mode frames hints as fleeting thoughts (keeps novel tone).
Plain mode shows a short mechanical list (better for learning the parser).
"""

import os

from storage import load
from simulation.hunting_engine import monsters_in_area

CFG_FILE = "system/config.json"
PLAYER_FILE = "player/player.json"
NPC_FILE = "characters/npcs.json"
MON_FILE = "characters/monsters.json"
AREAS_FILE = "world/areas.json"
WORLD_FILE = "world/world_state.json"

VALID_MODES = ("off", "subtle", "plain")


def _config_mode():
    cfg = load(CFG_FILE, {})
    env = os.environ.get("AISTORY_HINTS", "").strip().lower()
    if env in ("1", "true", "yes", "plain"):
        return "plain"
    if env in ("subtle", "thought"):
        return "subtle"
    if env in ("0", "false", "no", "off"):
        return "off"
    mode = (cfg.get("action_hints") or "off").lower()
    return mode if mode in VALID_MODES else "off"


def get_hint_mode(player=None):
    """Player setting overrides config/env default."""
    player = player or load(PLAYER_FILE, {})
    settings = player.get("settings") or {}
    if settings.get("action_hints") in VALID_MODES:
        return settings["action_hints"]
    return _config_mode()


def set_hint_mode(player, mode):
    if mode not in VALID_MODES:
        return False
    player.setdefault("settings", {})["action_hints"] = mode
    return True


def _dedupe(items, limit=3):
    seen = set()
    out = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def collect_action_suggestions(player=None, last_kind=None, limit=4, force=False):
    """Plain suggestion strings for the web UI chip bar."""
    player = player or load(PLAYER_FILE, {})
    pending = player.get("pending_target_clarification")
    if pending:
        return _dedupe(
            [opt.get("chip") for opt in (pending.get("options") or []) if opt.get("chip")],
            limit=limit,
        )

    if not force and get_hint_mode(player) == "off":
        return []

    world = load(WORLD_FILE, {})
    npcs = load(NPC_FILE, {})
    monsters = load(MON_FILE, {})
    areas = load(AREAS_FILE, {})
    area_id = player.get("area")
    area = areas.get(area_id, {})
    journal = player.get("journal") or []

    suggestions = []

    if len(journal) <= 2:
        suggestions.append("look around")
        suggestions.append("find someone to talk to")

    focus_id = player.get("scene_focus")
    focus = npcs.get(focus_id) if focus_id else None
    known = player.get("known_npcs", {}).get(focus_id, {}) if focus_id else {}

    if focus and focus.get("status") == "alive":
        name = focus.get("name", "them")
        if not known.get("name_known"):
            suggestions.append('ask "what is your name?"')
        else:
            first = name.split()[0]
            suggestions.append(f"ask {first} about the trouble here")
            suggestions.append(f"talk to {first}")
            if last_kind in ("talk", "ask_name", "explore"):
                suggestions.append("show respect")
                suggestions.append("leave")

    here = monsters_in_area(area_id, monsters, city=player.get("location"))
    if here or area.get("type") == "wilderness":
        if here:
            suggestions.append("track the beast")
        suggestions.append("look around")

    if player.get("active_case") and not player["active_case"].get("solved"):
        suggestions.append("investigate")

    board = world.get("bounty_board") or []
    if any(not b.get("claimed") for b in board):
        suggestions.append("ask about bounties")

    stats = player.get("stats", {})
    if stats.get("health", 100) < stats.get("max_health", 100) * 0.45:
        suggestions.append("rest")
    if stats.get("stamina", 30) < 8:
        suggestions.append("rest")

    if focus and (focus.get("institution") or {}).get("type") in ("guild", "hunters_lodge"):
        suggestions.append("ask about guild work")

    if last_kind == "explore" and len(journal) >= 3:
        last_areas = {e.get("area") for e in journal[-4:]}
        if len(last_areas) == 1:
            suggestions.append("map")

    if not suggestions:
        suggestions.append("look around")
        suggestions.append("find someone to talk to")

    return _dedupe(suggestions, limit=limit)


def build_action_hints(player=None, last_kind=None):
    """Return hint string to print after a scene, or \"\" if disabled."""
    player = player or load(PLAYER_FILE, {})
    mode = get_hint_mode(player)
    if mode == "off":
        return ""

    picks = collect_action_suggestions(player, last_kind=last_kind, limit=3)
    if not picks:
        return ""

    if mode == "subtle":
        joined = "; ".join(picks)
        return f"\n(A thought: you could {joined}.)"

    return "\n— " + " · ".join(picks)


def format_hint_setting(player):
    mode = get_hint_mode(player)
    labels = {
        "off": "off — no suggestions after scenes",
        "subtle": "subtle — brief in-character thoughts",
        "plain": "plain — short command list after each scene",
    }
    return f"  Action hints: {labels.get(mode, mode)}"
