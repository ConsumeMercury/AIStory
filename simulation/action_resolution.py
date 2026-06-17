"""
Hard-logic resolution for combat targets, item pickup, explore hooks, and confessions.
Simulation decides facts; the narrator renders them.
"""

import logging
import re

from generation.descriptor_generator import short_descriptor, appearance_notes, gender_label
from generation.item_generator import generate_item
from simulation.item_engine import resolve_loot_to_player, equip_item, ensure_equipment
from simulation.narrator_items import match_narrator_item_pickup, consume_narrator_item
from simulation.target_resolution import find_npc_by_name_in_text

log = logging.getLogger(__name__)

_ACQUIRE_VERBS = re.compile(
    r"\b(find|look for|search for|take|pick up|pickup|grab|loot|strip|pull)\b", re.I,
)
_CONFESS = re.compile(
    r"\b(i killed|i have killed|i've killed|murdered|confess|admit i killed)\b", re.I,
)

_ITEM_KEYWORDS = (
    (re.compile(r"\b(sword|blade|cutlass|sabre|saber)\b", re.I), "weapon", "sword", "notched blade"),
    (re.compile(r"\b(dagger|knife|stiletto)\b", re.I), "weapon", "dagger", None),
    (re.compile(r"\b(axe|hatchet)\b", re.I), "weapon", "axe", None),
    (re.compile(r"\b(bow|arrow)\b", re.I), "weapon", "bow", None),
    (re.compile(r"\b(armor|armour|coat|vest|jack)\b", re.I), "armor", "leather coat", None),
    (re.compile(r"\b(weapon|blade|steel)\b", re.I), "weapon", "sword", "notched blade"),
)

_NON_LOOT_REFERENTS = re.compile(
    r"\b(bodies|body|corpse|corpses|remains|cadaver|dead|person|people|"
    r"priest|priestess|cleric|monk|child|friend|enemy|victim|"
    r"man|woman|girl|boy|hunter|guard|soldier|merchant|herbalist)\b",
    re.I,
)
_PICKUP_VERBS = re.compile(r"\b(pick up|pickup|take|grab|loot|carry)\b", re.I)

_FIND_PERSON = re.compile(
    r"\bfind(?:\s+(?:the|a|an))?\s+(.+)$", re.I,
)
_FIND_PERSON_QUERY = re.compile(
    r"\b(?:find|look for|search for|locate)\s+(?:the\s+)?"
    r"(?!a\s+(?:sword|blade|dagger|knife|weapon|axe|bow|armor|armour|steel)\b)"
    r"(?:[A-Za-z][a-z'-]+(?:\s+[A-Za-z][a-z'-]+)?|"
    r"someone|(?:a\s+)?person)\b",
    re.I,
)
_PERSON_QUERY_STOP = frozenset({
    "work", "someone", "person", "clues", "proof", "answers", "help", "way", "out",
    "a", "an", "the",
    "sword", "blade", "dagger", "knife", "weapon", "axe", "bow", "armor", "armour", "steel",
})
_COMBAT_ROLE = re.compile(
    r"\b(knight|knights|guard|guards|soldier|soldiers|levy|watchman|pikeman|captain)\b", re.I,
)
_DESC_HINTS = (
    (re.compile(r"\bred[\s-]?hair(?:ed)?|\bauburn\b", re.I), lambda n: _hair_match(n, ("red", "auburn", "copper"))),
    (re.compile(r"\b(grey|gray)[\s-]?hair|\bsilver[\s-]?hair\b", re.I), lambda n: _hair_match(n, ("grey", "gray", "silver", "white"))),
    (re.compile(r"\b(knight|knights|guard|guards|soldier|soldiers|levy|watchman|pikeman)\b", re.I), lambda n: n.get("role") in ("guard", "soldier")),
    (re.compile(r"\b(captain|sailor|dockmaster|harbour master|harbor master)\b", re.I), lambda n: n.get("role") in ("sailor", "merchant", "guard")),
    (re.compile(r"\b(priest|cleric|monk|clerk|clerics)\b", re.I), lambda n: n.get("role") == "priest"),
    (re.compile(r"\b(merchant|trader)\b", re.I), lambda n: n.get("role") in ("merchant", "innkeeper")),
    (re.compile(r"\b(hunter|hunters)\b", re.I), lambda n: n.get("role") == "hunter"),
    (re.compile(r"\b(scholar|scholars)\b", re.I), lambda n: n.get("role") == "scholar"),
    (re.compile(r"\b(scribe|scribes)\b", re.I), lambda n: n.get("role") == "scribe"),
    (re.compile(r"\b(herbalist|herbalists)\b", re.I), lambda n: n.get("role") in ("herbalist", "priest", "merchant")),
    (re.compile(r"\b(woman|lady|girl)\b", re.I), lambda n: n.get("gender") == "female"),
    (re.compile(r"\b(man|fellow|bloke)\b", re.I), lambda n: n.get("gender") == "male"),
)


def _hair_match(npc, colors):
    hair = (npc.get("appearance") or {}).get("hair", "").lower()
    return any(c in hair for c in colors)


def match_npc_by_description(action, present, player=None):
    """Match present NPCs by role/appearance hints in player text."""
    if not action or not present:
        return None
    scores = {}
    for pattern, matcher in _DESC_HINTS:
        if not pattern.search(action):
            continue
        for n in present:
            try:
                if matcher(n):
                    scores[n["id"]] = scores.get(n["id"], 0) + 1
            except Exception:
                log.debug("description matcher failed for npc %s", n.get("id"), exc_info=True)
    if scores:
        best = max(scores.values())
        top_ids = [nid for nid, score in scores.items() if score == best]
        if len(top_ids) == 1:
            top_id = top_ids[0]
            return next(n for n in present if n["id"] == top_id)
        focus = player.get("scene_focus") if player else None
        if focus and focus in top_ids:
            return next(n for n in present if n["id"] == focus)
        return None
    m = _FIND_PERSON.match(action.strip())
    if m:
        query = m.group(1).lower()
        for n in present:
            name = (n.get("name") or "").lower()
            role = (n.get("role") or "").lower()
            if query in name or query in role or name.split()[0].lower() in query:
                return n
    return None


_PRONOUN_REF = re.compile(
    r"\b(her|him|them|they|she|he|that one|this one|the same one)\b", re.I,
)


def resolve_pronoun_target(action, player, present):
    """Resolve her/him/them to a present NPC — only when the action uses pronouns."""
    if not present:
        return None
    text = (action or "").lower()
    if not _PRONOUN_REF.search(text):
        return None
    focus = player.get("scene_focus")
    last = player.get("last_combat_target")

    female_hint = bool(re.search(r"\b(her|she|woman|girl|lady)\b", text))
    male_hint = bool(re.search(r"\b(him|he|man|boy)\b", text)) and not re.search(r"\b(her|she|woman)\b", text)

    if female_hint:
        cands = [n for n in present if n.get("gender") == "female"]
        if focus:
            for n in cands:
                if n["id"] == focus:
                    return n
        if len(cands) == 1:
            return cands[0]
        return None

    if male_hint:
        cands = [n for n in present if n.get("gender") == "male"]
        if last:
            for n in cands:
                if n["id"] == last:
                    return n
        if focus:
            for n in cands:
                if n["id"] == focus:
                    return n
        if len(cands) == 1:
            return cands[0]
        return None

    if last:
        for n in present:
            if n["id"] == last:
                return n
    if focus:
        for n in present:
            if n["id"] == focus:
                return n
    return None


def _action_requests_specific_combat_target(action, npcs, player, present):
    """True when the player named a role, descriptor, or NPC — not a generic fight."""
    if not action:
        return False
    if find_npc_by_name_in_text(action, npcs, player):
        return True
    if _COMBAT_ROLE.search(action):
        return True
    for pattern, _matcher in _DESC_HINTS:
        if pattern.search(action):
            return True
    from simulation.target_resolution import action_mentions_role_or_descriptor
    return action_mentions_role_or_descriptor(action, present=present)


def resolve_combat_target(action, player, present, npcs, monsters, area, city):
    """
    Who the player actually fights. NPC targeting beats random present[0].
    Returns (target_entity, kind) where kind is 'npc' or 'monster'.
    """
    from simulation.hunting_engine import monsters_in_area

    mon_here = monsters_in_area(area, monsters, city=city) if area else []
    text = (action or "").lower()
    specific = _action_requests_specific_combat_target(action, npcs, player, present)

    named = find_npc_by_name_in_text(action, npcs, player)
    if named:
        for n in present:
            if n["id"] == named["id"]:
                return n, "npc"
        return None, None

    desc = match_npc_by_description(action, present)
    if desc:
        return desc, "npc"

    if specific:
        return None, None

    pron = resolve_pronoun_target(action, player, present)
    if pron:
        return pron, "npc"

    last = player.get("last_combat_target")
    if last and re.search(r"\b(again|anyway|still|finish|keep fighting)\b", text):
        for n in present:
            if n["id"] == last:
                return n, "npc"
        return None, None

    focus = player.get("scene_focus")
    if focus:
        for n in present:
            if n["id"] == focus:
                return n, "npc"

    if re.search(r"\b(monster|beast|wolf|creature|ghoul|stalker)\b", text) and mon_here:
        return mon_here[0], "monster"

    if _COMBAT_ROLE.search(text):
        return None, None

    if len(present) == 1:
        return present[0], "npc"

    if present:
        return None, None

    if mon_here:
        return mon_here[0], "monster"

    return None, None


def pick_explore_hook(present, player, action_ctx=None):
    """One real NPC to anchor first explore beat — must be in scene cast, not whole district."""
    if not present:
        return None
    ctx = action_ctx or {}
    exclude = set(ctx.get("left_behind_cast") or [])
    candidates = [n for n in present if n["id"] not in exclude]
    if not candidates:
        return None
    focus = player.get("scene_focus")
    if focus and focus not in exclude:
        for n in candidates:
            if n["id"] == focus:
                return n
    keyed = [n for n in candidates if n.get("key_npc")]
    if keyed:
        return keyed[0]
    return candidates[0]


def _area_id(area, player):
    if isinstance(area, dict):
        return area.get("id") or player.get("area")
    return player.get("area")


def _acquire_from_narrator_item(rec, player, area, tick, skill_success=True):
    """Materialize a previously narrator-registered item into inventory."""
    if not skill_success:
        return (
            "The search fails — nothing useful in reach, or someone notices you looking.",
            None,
        )
    category = rec.get("category") or "material"
    template = rec.get("template_name")
    source = "wilderness"
    area_id = _area_id(area, player)
    if area and isinstance(area, dict) and area.get("type") == "district":
        if area.get("city"):
            source = "merchant"
        if "docks" in (area_id or ""):
            source = "bandit"
    kwargs = {"category": category, "source": source, "created_tick": tick}
    if template:
        kwargs["template_name"] = template
    elif rec.get("label"):
        kwargs["template_name"] = _normalize_narrator_template(rec.get("label"))
    _iid, item = generate_item(**kwargs)
    item["owner"] = "player"
    summary = resolve_loot_to_player(player, [item])
    ensure_equipment(player)
    if category == "weapon" and not player.get("equipment", {}).get("weapon"):
        equip_item(player, item["id"])
    consume_narrator_item(player, area_id, rec.get("id"))
    label = rec.get("label") or item.get("name")
    directive = (
        f"MECHANICAL FACT: {summary} "
        f"The protagonist NOW HAS {label} in inventory — describe picking it up once, "
        f"do not invent a different item."
    )
    action_ctx_item = {
        "id": item["id"],
        "name": item["name"],
        "category": item.get("category"),
        "rarity": item.get("rarity"),
    }
    player["last_acquired_item"] = action_ctx_item
    return directive, item


def _normalize_narrator_template(label):
    """Map prose label to item generator template when possible."""
    lower = (label or "").lower()
    if "parchment" in lower or "scrap" in lower or "letter" in lower:
        return "folded letter"
    if "beetle" in lower:
        return "dead beetle"
    if "coin" in lower:
        return "silver coin"
    return None


def validate_acquire_item(action, player, area):
    """
    Refuse loot fabrication when the referent is not a valid takeable item.
    Returns (ok, refusal_message).
    """
    if not _ACQUIRE_VERBS.search(action or ""):
        return True, ""
    if re.search(r"\b(find someone|find work|find a person)\b", action, re.I):
        return True, ""
    if _FIND_PERSON_QUERY.search(action or ""):
        return True, ""

    names_item = any(p.search(action or "") for p, _, _, _ in _ITEM_KEYWORDS)
    narr_item = match_narrator_item_pickup(action, player, _area_id(area, player))
    if narr_item:
        return True, ""
    if _NON_LOOT_REFERENTS.search(action or "") and not names_item:
        return False, (
            "ACQUIRE REFUSED — there is nothing like that here to take. "
            "Do NOT invent a substitute item or add anything to inventory."
        )

    if _PICKUP_VERBS.search(action or "") and not names_item:
        return False, (
            "ACQUIRE REFUSED — nothing here to pick up. "
            "Do NOT add items to inventory this beat."
        )

    if re.search(r"\b(search|look for|find)\b", action or "", re.I) and not names_item:
        return False, (
            "SEARCH REFUSED — nothing tangible to find here. "
            "Do NOT invent loot."
        )

    return True, ""


def try_acquire_item(action, player, area, tick, skill_success=True):
    """
    If action searches for or takes an item, add it to inventory before narration.
    Returns (directive_text or None, item_dict or None).
    """
    if not _ACQUIRE_VERBS.search(action or ""):
        return None, None
    if re.search(r"\b(find someone|find work|find a person)\b", action, re.I):
        return None, None
    if _FIND_PERSON_QUERY.search(action or ""):
        return None, None

    matched = None
    narr = match_narrator_item_pickup(action, player, _area_id(area, player))
    if narr:
        return _acquire_from_narrator_item(narr, player, area, tick, skill_success=skill_success)
    for pattern, category, item_type, template in _ITEM_KEYWORDS:
        if pattern.search(action):
            matched = (category, item_type, template)
            break
    if not matched:
        return None, None

    category, item_type, template = matched
    source = "wilderness"
    if area and area.get("type") == "district":
        if area.get("city"):
            source = "merchant"
        if "docks" in (area.get("id") or ""):
            source = "bandit"

    kwargs = {"category": category, "source": source, "created_tick": tick}
    if template:
        kwargs["template_name"] = template
    _iid, item = generate_item(**kwargs)
    item["owner"] = "player"

    if not skill_success:
        return (
            "The search fails — nothing useful in reach, or someone notices you looking.",
            None,
        )

    summary = resolve_loot_to_player(player, [item])
    ensure_equipment(player)
    if category == "weapon" and not player.get("equipment", {}).get("weapon"):
        equip_item(player, item["id"])

    directive = (
        f"MECHANICAL FACT: {summary} "
        f"The protagonist NOW HAS this in inventory — describe picking it up once, "
        f"do not invent a different item."
    )
    action_ctx_item = {
        "id": item["id"],
        "name": item["name"],
        "category": item.get("category"),
        "rarity": item.get("rarity"),
    }
    player["last_acquired_item"] = action_ctx_item
    return directive, item


def resolve_find_person(action, player, present, npcs):
    """Target for find/talk to described person."""
    if action and present:
        for pattern, matcher in _DESC_HINTS:
            if pattern.search(action):
                hits = []
                for n in present:
                    try:
                        if matcher(n):
                            hits.append(n)
                    except Exception:
                        log.debug("find-person matcher failed for npc %s", n.get("id"), exc_info=True)
                if len(hits) == 1:
                    return hits[0]
                if len(hits) > 1:
                    return None
                return None

    named = resolve_npc_by_name_query(action, npcs, player) or find_npc_by_name_in_text(action, npcs, player)
    if named:
        for n in present:
            if n["id"] == named["id"]:
                return named
    pron = resolve_pronoun_target(action, player, present)
    if pron:
        return pron
    focus = player.get("scene_focus")
    if focus:
        for n in present:
            if n["id"] == focus:
                return n
    return match_npc_by_description(action, present)


def extract_find_name_query(action):
    """First/last name from 'find Edvar' / 'locate Edvar Dremar'."""
    m = re.search(
        r"\b(?:find|look for|locate)\s+(?:the\s+)?([A-Za-z][a-z'-]+(?:\s+[A-Za-z][a-z'-]+)?)\b",
        action or "",
        re.I,
    )
    if not m:
        return None
    query = m.group(1).lower().strip()
    query = re.sub(r"^(?:a|an|the)\s+", "", query)
    first = query.split()[0] if query else ""
    if first in _PERSON_QUERY_STOP or query in _PERSON_QUERY_STOP:
        return None
    return query


def _name_matches_query(npc, query):
    name = (npc.get("name") or "").lower()
    if not name or not query:
        return False
    if query in name:
        return True
    parts = name.split()
    if parts[0] == query:
        return True
    if len(query.split()) > 1 and all(tok in parts for tok in query.split()):
        return True
    return False


def resolve_npc_by_name_query(action, npcs, player):
    """Match NPC by name fragment — case suspects first, then known/all during investigations."""
    query = extract_find_name_query(action)
    if not query:
        return None

    case = player.get("active_case") or {}
    priority_ids = []
    if case and not case.get("solved"):
        priority_ids.extend(case.get("suspect_ids") or [])
        priority_ids.extend(case.get("witness_ids") or [])
        if case.get("victim_id"):
            priority_ids.append(case["victim_id"])

    seen = set()
    for nid in priority_ids:
        if nid in seen:
            continue
        seen.add(nid)
        npc = npcs.get(nid)
        if npc and _name_matches_query(npc, query):
            return npc

    known = player.get("known_npcs", {})
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if known.get(npc["id"], {}).get("name_known") and _name_matches_query(npc, query):
            return npc

    if case and not case.get("solved"):
        for npc in npcs.values():
            if npc.get("status") == "alive" and _name_matches_query(npc, query):
                return npc

    return None


def build_find_failed_facts(target_npc=None, *, query=None):
    if target_npc:
        name = target_npc.get("name") or "them"
        return (
            "SCENE FACTS — FIND PERSON (obey exactly):\n"
            f"- {name} is NOT in this scene — the protagonist searched but they are elsewhere.\n"
            "- Do NOT invent meeting them here. Do NOT give the protagonist a weapon or loot instead.\n"
            "- Others present may mention where they usually are, if already established in the ledger.\n"
        )
    if query:
        return (
            "SCENE FACTS — FIND PERSON (obey exactly):\n"
            f"- No one matching '{query}' is here — search fails.\n"
            "- Do NOT invent finding a blade, sword, or loot unless inventory facts say so.\n"
        )
    return (
        "SCENE FACTS — FIND PERSON (obey exactly):\n"
        "- Search failed — no matching person in scene.\n"
        "- Do NOT substitute a weapon pickup for finding someone.\n"
    )


def build_find_facts(target):
    """Lock narrator to the person the simulation actually matched."""
    if not target:
        return ""
    desc = short_descriptor(target)
    role = target.get("role", "stranger")
    g_label = gender_label(target)
    name = target.get("name") or desc
    return (
        "SCENE FACTS — FIND PERSON (obey exactly):\n"
        f"- Target found: {name}, {g_label}, role={role}.\n"
        f"- ONLY this person is the match — describe them with role={role}.\n"
        "- Dock guards, watchmen, patrols may appear in background but are NOT this person.\n"
    )


def resolve_confession_respondent(player, present, action_ctx, npcs, relationships):
    """
    Who responds to 'I killed him' — witness, focus, or nearest guard — not random blacksmith.
    """
    tid = action_ctx.get("target_id")
    if tid:
        for n in present:
            if n["id"] == tid:
                return n

    witnesses = player.get("combat_witnesses") or []
    for wid in witnesses:
        for n in present:
            if n["id"] == wid and n.get("status") == "alive":
                return n

    focus = player.get("scene_focus")
    for n in present:
        if n["id"] == focus:
            return n

    guards = [n for n in present if n.get("role") in ("guard", "soldier")]
    if guards:
        return guards[0]

    if len(present) == 1:
        return present[0]
    return None


def _forbidden_role_labels(role):
    labels = [r for r in (
        "guard", "watchman", "soldier", "sailor", "priest", "scholar",
        "blacksmith", "merchant", "hunter", "dockhand",
    ) if r != role]
    return ", ".join(labels[:8])


def build_combat_facts(target, result, target_kind, npcs):
    """Structured facts for narrator — identity locked to simulation target."""
    if not target:
        return ""
    if target_kind == "monster":
        label = target.get("species", "creature")
        fatal = result.get("fatal", False)
        return (
            f"SCENE FACTS — COMBAT (obey exactly):\n"
            f"- Opponent: {label} (monster, not a person).\n"
            f"- Outcome: {'FATAL — creature slain.' if fatal else 'Fight ended — both may still stand.'}\n"
            f"- Do NOT describe a priest, scholar, or dockworker unless they match this target.\n"
        )

    desc = short_descriptor(target)
    g_label = gender_label(target)
    role = target.get("role", "stranger")
    pron = target.get("pronouns", {})
    fatal = result.get("fatal", False)
    alive = target.get("status") == "alive" and not fatal
    name = target.get("name") if target.get("name") else desc

    lines = [
        "SCENE FACTS — COMBAT (obey exactly):",
        f"- Opponent: {desc}, {g_label}, role={role}, age ~{target.get('age', '?')}.",
        f"- Pronouns ONLY: {pron.get('subject')}/{pron.get('object')}/{pron.get('possessive')}.",
        f"- Appearance (fixed): {appearance_notes(target, 'face')[:100]}.",
        f"- Role lock: opponent is a {role} — never call them {_forbidden_role_labels(role)}.",
    ]
    if fatal:
        lines.append(f"- Outcome: FATAL — {name} is DEAD. Body may be described; they do NOT speak.")
        lines.append("- No other NPC may pretend to be this person. No priest/scholar swap.")
    else:
        lines.append(
            f"- Outcome: NOT FATAL — {name} is alive (health {target.get('stats', {}).get('health', '?')}). "
            "They may speak briefly if focal — same person, same voice."
        )
    lines.append("- ONLY this opponent was in the fight. Do not invent a different combatant.")
    rounds = result.get("log") or []
    if rounds:
        lines.append("- Round log (fixed order):")
        for entry in rounds[:8]:
            if isinstance(entry, str):
                lines.append(f"  · {entry[:120]}")
            elif isinstance(entry, dict):
                lines.append(f"  · {entry.get('summary', entry)}"[:140])
    return "\n".join(lines)


_AMBIENT_ROLE_CHECKS = (
    ("guard", ("guard", "soldier"), "guard or soldier"),
    ("priest", ("priest",), "priest or cleric"),
    ("merchant", ("merchant", "innkeeper"), "merchant or trader"),
    ("sailor", ("sailor",), "sailor or dockhand"),
)


def build_scene_presence_facts(present, action_ctx=None):
    """Who is actually in scene — and common roles that are NOT present."""
    lines = ["SCENE FACTS — WHO IS HERE (obey exactly):"]
    if present:
        for npc in present[:10]:
            desc = short_descriptor(npc)
            role = npc.get("role", "stranger")
            lines.append(f"- PRESENT: {desc}, role={role}.")
    else:
        lines.append("- PRESENT: no named NPCs in this scene.")

    roles_here = {(n.get("role") or "").lower() for n in (present or [])}
    for _key, role_set, label in _AMBIENT_ROLE_CHECKS:
        if not roles_here.intersection(role_set):
            lines.append(
                f"- NOT PRESENT: no {label} NPC in this scene — "
                "do not give them dialogue, combat, or named interaction."
            )

    ctx = action_ctx or {}
    if ctx.get("target_ambiguous"):
        lines.append(
            "- NO ACTION RESOLVED: protagonist has not chosen a target yet — "
            "no violence or directed dialogue toward a specific person."
        )
    if ctx.get("approach_failed") or ctx.get("travel_failed"):
        lines.append("- NO MOVEMENT this beat.")
    return "\n".join(lines)


def build_inventory_facts(player, action_ctx):
    """Tell narrator what the player actually carries after this beat."""
    acquired = action_ctx.get("acquired_item") or player.get("last_acquired_item")
    if not acquired:
        return ""
    eq = player.get("equipment") or {}
    weapon = eq.get("weapon")
    wname = ""
    if weapon:
        for it in player.get("inventory") or []:
            if isinstance(it, dict) and it.get("id") == weapon:
                wname = it.get("name", "")
                break
    parts = [
        "SCENE FACTS — INVENTORY (obey exactly):",
        f"- Just acquired: {acquired.get('name')} [{acquired.get('rarity', 'common')}].",
    ]
    if wname:
        parts.append(f"- Equipped weapon: {wname}.")
    parts.append("- Do NOT describe finding a different weapon than listed.")
    return "\n".join(parts)


def build_post_combat_facts(player, npcs):
    """Remind narrator of combat outcome on later beats (search, confess)."""
    fatal = player.get("last_combat_fatal", False)
    tid = player.get("last_combat_target")
    victim = npcs.get(tid, {}) if tid else {}
    v_label = victim.get("name") or short_descriptor(victim) if victim else "the last opponent"
    v_role = victim.get("role", "stranger")
    v_gender = gender_label(victim) if victim else ""
    alive = victim.get("status") == "alive" and not fatal
    lines = ["SCENE FACTS — PRIOR COMBAT (obey exactly):"]
    if victim:
        lines.append(
            f"- Last opponent: {v_label}, {v_gender}, role={v_role}. "
            f"Role lock: {v_role} only — not {_forbidden_role_labels(v_role)}."
        )
    if fatal or victim.get("status") == "dead":
        lines.append(f"- {v_label} was killed in the last fight. A body may exist — they do NOT speak.")
    elif alive:
        hp = victim.get("stats", {}).get("health", "?")
        lines.append(
            f"- {v_label} is STILL ALIVE (health {hp}). "
            "Do NOT write a corpse, execution, or confirmed murder. "
            "Injuries and exhaustion only."
        )
    else:
        lines.append("- Last fight was non-lethal. No confirmed death.")
    return "\n".join(lines)


def build_confession_facts(player, respondent, victim_id, npcs):
    victim = npcs.get(victim_id, {}) if victim_id else {}
    v_label = victim.get("name") or short_descriptor(victim) if victim else "the one you fought"
    fatal = player.get("last_combat_fatal", False) or victim.get("status") == "dead"
    if not respondent:
        return (
            "SCENE FACTS — CONFESSION:\n"
            f"- Protagonist claims they killed {v_label}.\n"
            + (f"- Truth: {v_label} is DEAD.\n" if fatal else f"- Truth: {v_label} is still ALIVE.\n")
            + "- No one suitable is close enough to answer — show silence, distance, or overheard murmurs only.\n"
            "- Do NOT invent a new character to respond."
        )
    r_desc = short_descriptor(respondent)
    r_role = respondent.get("role", "stranger")
    r_gender = gender_label(respondent)
    if respondent.get("id") == victim_id and not fatal:
        return (
            "SCENE FACTS — CONFESSION (obey exactly):\n"
            f"- Protagonist claims to have killed {v_label}.\n"
            f"- Truth: {v_label} is the person speaking TO — they are STILL ALIVE and present.\n"
            f"- ONLY {r_desc} ({r_role}, {r_gender}) responds — disbelief, anger, or dark humor. "
            "One to three lines. No corpse. No 'scholar' unless role=scholar.\n"
        )
    v_role = victim.get("role", "stranger")
    rel_note = "They witnessed the violence." if respondent.get("id") in (player.get("combat_witnesses") or []) else "They did not witness it directly."
    if fatal:
        truth = f"- Truth: {v_label} IS dead (role={v_role}). Victim may be named in third person."
    else:
        truth = (
            f"- Truth: {v_label} is STILL ALIVE — the confession is false, premature, or delusion. "
            f"Respondent must NOT agree they are dead; show disbelief, fear, or 'look — {v_label.split()[0] if v_label else 'they'} is right there'."
        )
    return (
        f"SCENE FACTS — CONFESSION (obey exactly):\n"
        f"- Protagonist says they killed {v_label} (role={v_role}).\n"
        f"{truth}\n"
        f"- ONLY {r_desc} may speak — role={r_role}, {r_gender}. "
        f"Do NOT call the RESPONDENT {_forbidden_role_labels(r_role)}.\n"
        f"- {rel_note} One to three lines of reply, then stop.\n"
        f"- Do NOT swap in a new face or gender."
    )
