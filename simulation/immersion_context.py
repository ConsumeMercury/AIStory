"""
Build narrator-facing context from simulation state the model should feel
but not recite as game mechanics.
"""

from storage import load

INST_FILE = "world/institutions.json"
RUMOR_FILE = "rumors/rumors.json"

_INTERPRETATION_TONE = {
    "dangerous": "spoken with unease",
    "heroic": "exaggerated admiration",
    "suspicious": "half-believed accusation",
    "mysterious": "hushed speculation",
    "false": "probably wrong",
    "worrying": "anxious undertone",
    "scandalous": "delighted malice",
    "hushed": "whispered secrecy",
}


def format_rumor_whispers(rumors, city=None, area_name=None, limit=3):
    """Local gossip the protagonist might overhear — unreliable by design."""
    if not rumors:
        return ""
    pool = list(reversed(rumors[-20:]))
    if city:
        city_l = city.lower().replace("_", " ")
        local = [r for r in pool if city_l in (r.get("text") or "").lower()]
        if local:
            pool = local + [r for r in pool if r not in local]
    lines = []
    for r in pool[:limit]:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        tone = _INTERPRETATION_TONE.get(r.get("interpretation", ""), "uncertain")
        lines.append(f"- \"{text}\" ({tone})")
    if not lines:
        return ""
    place = area_name or (city or "here").replace("_", " ").title()
    return (
        f"WHISPERS IN {place.upper()} (may be distorted — weave as overheard fragments, "
        f"not exposition):\n" + "\n".join(lines)
    )


def format_world_echoes(relevant_events, limit=3):
    """Recent world events that colour the atmosphere."""
    if not relevant_events:
        return ""
    lines = []
    for e in relevant_events[:limit]:
        actor = e.get("actor", "someone")
        action = e.get("action", e.get("type", "something"))
        loc = e.get("location", "")
        loc_bit = f" near {loc}" if loc else ""
        lines.append(f"- {actor} {action}{loc_bit}")
    return (
        "RECENT WORLD NOISE (background tension — do not explain as a list):\n"
        + "\n".join(lines)
    )


def build_player_inner_voice(player, world, action_context=None, journal=None):
    """
    Subtle internal state for literary second person — not stats, but felt life.
    """
    stats = player.get("stats", {})
    health = stats.get("health", 100)
    max_h = stats.get("max_health", 100)
    stamina = stats.get("stamina", stats.get("max_stamina", 30))
    max_s = stats.get("max_stamina", 30)
    bg = player.get("background", "wanderer")
    motivation = player.get("motivation", "")

    threads = []
    if health < max_h * 0.45:
        threads.append("pain or old hurt keeps tugging at attention")
    elif health < max_h * 0.75:
        threads.append("a dull ache you have learned to work around")

    if stamina < max_s * 0.25:
        threads.append("exhaustion making every step deliberate")
    elif stamina < max_s * 0.5:
        threads.append("tiredness at the edges of thought")

    check = (action_context or {}).get("skill_check")
    if check and not check.get("success"):
        threads.append("the last attempt still stings — doubt, embarrassment, or anger")

    recent = (journal or [])[-3:]
    kinds = [e.get("kind") for e in recent if e.get("kind")]
    if kinds.count("attack") >= 1:
        threads.append("violence still humming in the hands")
    if kinds.count("personal_talk") >= 1:
        threads.append("someone else's history still sitting in the chest")

    bg_lens = {
        "scholar": "noticing patterns, asking silent questions",
        "soldier": "mapping exits, measuring threat without meaning to",
        "merchant": "weighing cost against risk in every glance",
        "thief": "aware of pockets, shadows, and who is watching",
        "wanderer": "the road's habit of never quite arriving",
    }
    threads.append(bg_lens.get(bg, "the weight of being unknown here"))

    if motivation and len(motivation) > 12:
        threads.append(f"purpose: {motivation[:100]}")

    weather = world.get("weather", "")
    tod = world.get("time_of_day", "")
    if weather and tod:
        threads.append(f"{weather.lower()} {tod.lower()} on the skin")

    if not threads:
        return ""
    picked = threads[:4]
    return (
        "INNER LIFE (thread these as fleeting thought — never label emotions):\n"
        + "; ".join(picked)
    )


def institution_affiliation(npc, institutions=None):
    """One line about where this person belongs in the world's structures."""
    inst_ref = npc.get("institution")
    if not inst_ref:
        return ""
    institutions = institutions or load(INST_FILE, {})
    inst = institutions.get(inst_ref.get("id"), {})
    name = inst.get("name", "an institution")
    role = inst_ref.get("role", "member")
    arc = (inst.get("arc") or {}).get("current", "")
    line = f"Affiliation: {role} at {name}."
    if arc and len(arc) > 10:
        line += f" Their world is touched by: {arc[:90]}."
    return line


def npc_active_want(npc):
    """What this person is reaching for — one goal, not a biography."""
    goals = npc.get("goals") or []
    if not goals:
        return ""
    primary = goals[0]
    fears = npc.get("fears") or []
    fear_bit = ""
    if fears:
        fear_bit = f" They flinch from: {fears[0][:60]}."
    return f"What they want (private): {primary}.{fear_bit}"


def scene_continuity(journal, action_kind, player_action=""):
    """Bridge from the last beat — outcome only, discourages re-narration."""
    from simulation.narrator_variety import build_continuity_note
    return build_continuity_note(journal, action_kind, player_action)
