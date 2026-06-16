"""
Local sub-places within a district — doors, offices, sanctuaries (not map travel).
"""

import re

# (pattern, sub_id, label_template or callable)
_LOCAL_POI = (
    (re.compile(r"\b(heavy\s+)?oak\s+door|\b(?:the\s+)?(?:oak|iron|wooden)\s+door\b|\bdoor\b.*\b(temple|chapel|sanctuary)\b", re.I),
     "door", "the heavy door"),
    (re.compile(r"\b(gate|portal|archway|threshold|entrance)\b", re.I),
     "entrance", "the entrance"),
    (re.compile(r"\b(clerk|clerks|records?\s+office|ledger\s+office|tithes?\s+office)\b", re.I),
     "clerk_office", "the clerk's office"),
    (re.compile(r"\b(sanctuary|inner\s+hall|sanctum|nave|choir\s+loft)\b", re.I),
     "sanctuary", "the sanctuary"),
    (re.compile(r"\b(chapel|shrine|altar|high\s+temple|temple\s+interior|inside\s+the\s+temple)\b", re.I),
     "temple_interior", "inside the temple"),
    (re.compile(r"\b(inn|tavern|common\s+room|taproom)\b", re.I),
     "inn_interior", "the common room"),
    (re.compile(r"\b(market\s+stall|stall|booth)\b", re.I),
     "market_stall", "a market stall"),
    (re.compile(r"\b(alley|passage|lane|side\s+street)\b", re.I),
     "alley", "a narrow alley"),
    (re.compile(r"\b(wharf|pier|dock\s+side|quay)\b", re.I),
     "wharf", "the wharf"),
    (re.compile(r"\bcellar\b.*\bfishmonger|\bfishmonger\b.*\bcellar\b", re.I),
     "cellar_fishmonger", "the cellar behind the fishmonger"),
    (re.compile(r"\bcellar\b|\bbasement\b|\bunder(?:ground|croft)\b", re.I),
     "cellar", "a cellar nearby"),
    (re.compile(r"\bstable[- ]?yard\b|\b(?:lower|upper)\s+stable\b", re.I),
     "stable_yard", "the stable-yard"),
    (re.compile(r"\bcistern\b", re.I),
     "cistern", "the cistern"),
)

_APPROACH_VERBS = re.compile(
    r"\b(enter|go inside|step into|walk into|go in to|go in|approach|"
    r"go to|head to|walk to|move to|make for|follow(?:\s+the\s+)?(?:noise|sound|trail)?)\b",
    re.I,
)

_NAV_DEST = re.compile(
    r"\b(?:(?:lower|upper|old|new|inner|outer)\s+)?"
    r"(?:stable[- ]?yard|stableyard|cistern|armory|barracks|guardroom|"
    r"watchhouse|granary|foundry|smithy|infirmary|"
    r"[\w][\w\s'-]{2,22}(?:yard|gatehouse|court|hall))\b",
    re.I,
)

_BY_AT_DEST = re.compile(
    r"\b(?:by|at|toward|towards|into|to|near|down by|up at)\s+(?:the\s+)?"
    r"((?:lower|upper|old|new|inner|outer\s+)?[a-z][a-z\s'-]{2,40}?)"
    r"(?:\s+at\s|\s+by\s|[.,\"]|$)",
    re.I,
)

_TRAVEL_DEST = frozenset({
    "docks", "dock", "harbor", "harbour", "port", "district", "quarter",
    "market", "city", "road", "journey", "travel", "town", "village",
})

_DEST_STOP = frozenset({
    "gate", "wall", "street", "lane", "corner", "end", "morning", "midnight",
    "night", "deep night", "horns", "glass", "noise", "ridge", "horizon",
    "captain", "watch", "garrison", "quarter", "district", "lane's mouth",
})


def _slugify(text):
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (s[:40] or "place")


def _token_set(text):
    return {w for w in re.split(r"[\W_]+", (text or "").lower()) if len(w) > 2}


def _clean_place_label(raw):
    label = (raw or "").strip(" .,\"'")
    label = re.sub(r"\s+at\s+.*$", "", label, flags=re.I).strip()
    label = re.sub(r"\s+by\s+.*$", "", label, flags=re.I).strip()
    return label


def extract_narrator_destinations(scene):
    """Pull navigable-sounding place names from prose for later pursuit."""
    if not scene:
        return []
    found = []
    seen = set()

    def _add(raw):
        label = _clean_place_label(raw)
        key = label.lower()
        if len(key) < 4 or key in _DEST_STOP or key in seen:
            return
        seen.add(key)
        display = label if label.lower().startswith(("the ", "a ")) else f"the {label}"
        found.append({
            "id": _slugify(label),
            "label": display,
            "tokens": sorted(_token_set(label)),
        })

    for m in _NAV_DEST.finditer(scene):
        _add(m.group(0))
    for m in _BY_AT_DEST.finditer(scene):
        _add(m.group(1))

    return found[:8]


def record_narrator_places(player, scene, area_id):
    """Cache place names the narrator mentioned so movement can resolve them later."""
    places = extract_narrator_destinations(scene)
    if not places or not area_id:
        return False
    store = player.setdefault("narrator_places", {}).setdefault(area_id, {})
    changed = False
    for p in places:
        if p["id"] not in store:
            store[p["id"]] = p
            changed = True
    return changed


def _destination_query(action):
    if not action:
        return None
    m = re.search(
        r"\b(?:go to|head to|walk to|move to|make for|enter|approach|"
        r"turn back toward|turn toward|follow(?:\s+the\s+)?(?:noise|sound|trail)?)\s+"
        r"(?:the\s+)?(.+?)(?:\s*$|\.|,)",
        action.strip(),
        re.I,
    )
    if not m:
        return None
    return _clean_place_label(m.group(1))


def _match_promoted_place(action, player, current_area):
    query = _destination_query(action)
    if not query:
        return None
    query_tokens = _token_set(query)
    ql = query.lower()

    store = (player.get("narrator_places") or {}).get(current_area, {})
    best = None
    best_score = 0
    for rec in store.values():
        label = rec.get("label", "")
        label_tokens = set(rec.get("tokens") or []) or _token_set(label)
        overlap = len(query_tokens & label_tokens)
        if ql in label.lower() or label.lower() in ql:
            overlap += 10
        if overlap > best_score:
            best_score = overlap
            best = rec

    if best and (best_score >= 2 or ql in best.get("label", "").lower()):
        return dict(best)

    for entry in reversed((player.get("journal") or [])[-12:]):
        if entry.get("area") != current_area:
            continue
        scene = (entry.get("scene") or entry.get("excerpt") or "").lower()
        if ql in scene:
            label = query if query.lower().startswith("the ") else f"the {query}"
            return {
                "id": _slugify(query),
                "label": label,
                "tokens": sorted(query_tokens),
            }
    return None


def _promote_subplace(player, current_area, place_rec):
    sub_id = place_rec["id"]
    label = place_rec["label"]
    sub = {"id": sub_id, "label": label, "area": current_area, "narrator_promoted": True}
    player["scene_subplace"] = sub
    player.setdefault("story_flags", {})[f"subplace_{sub_id}"] = True
    store = player.setdefault("narrator_places", {}).setdefault(current_area, {})
    store[sub_id] = {
        "id": sub_id,
        "label": label,
        "tokens": sorted(place_rec.get("tokens") or _token_set(label)),
    }
    directive = (
        f"LOCAL MOVEMENT: The protagonist reaches {label} — still in the same district, "
        f"NOT a new city quarter. This place was named in prior narration; treat it as real here. "
        f"Describe arriving and what they find. Do NOT refuse entry or bolt gates against them. "
        f"Do NOT invent loot, documents, or NPC dialogue unless SCENE FACTS list them."
    )
    return sub, directive


def looks_like_local_movement(action):
    if not action:
        return False
    if not _APPROACH_VERBS.search(action):
        return False
    text = action.lower()
    for pattern, _sid, _label in _LOCAL_POI:
        if pattern.search(text):
            return True
    query = _destination_query(action)
    if not query:
        return False
    qtokens = _token_set(query)
    if qtokens & _TRAVEL_DEST:
        return False
    if _NAV_DEST.search(query):
        return True
    return len(qtokens) <= 3 and len(query.split()) >= 2


def resolve_local_movement(action, player, current_area):
    """
    Set player scene_subplace when the player moves within the current district.
    Returns (subplace_dict|None, directive_message|None).
    """
    if not action or not current_area:
        return None, None

    text = action.lower()
    flags = player.setdefault("story_flags", {})

    for pattern, sub_id, label in _LOCAL_POI:
        if not pattern.search(text):
            continue
        if sub_id == "cellar_fishmonger" and ":docks" not in (current_area or ""):
            return None, (
                "There is no fishmonger's cellar here — you are not at the docks. "
                "Do NOT invent a cellar or basement."
            )
        sub = {"id": sub_id, "label": label, "area": current_area}
        player["scene_subplace"] = sub
        flags[f"subplace_{sub_id}"] = True
        directive = (
            f"LOCAL MOVEMENT: The protagonist goes to {label} — still in the same district, "
            f"NOT a new city quarter. Describe only this sub-place. "
            f"Do NOT invent loot, documents, or NPC dialogue unless SCENE FACTS list them. "
            f"Do NOT teleport to a different building than requested."
        )
        return sub, directive

    promoted = _match_promoted_place(action, player, current_area)
    if promoted:
        return _promote_subplace(player, current_area, promoted)

    return None, None


def build_known_places_block(player, area_id):
    """Tell the narrator which sub-places exist and warn against inventing new navigable nodes."""
    subs = list((player.get("narrator_places") or {}).get(area_id, {}).values())
    lines = ["NAVIGABLE PLACES (simulation — only these may be named as go-to destinations):"]
    if subs:
        names = ", ".join(s["label"] for s in subs[:8])
        lines.append(f"- Known here: {names}.")
    else:
        lines.append("- None registered yet — use vague direction only ('toward the wall', 'down the lane').")
    lines.append(
        "- Do NOT name specific buildings, yards, rooms, or courtyards as places the protagonist "
        "can walk to unless listed above or in SCENE FACTS. Vague atmosphere is fine; "
        "specific navigable nodes are not."
    )
    return "\n".join(lines)


def build_place_lock(player, area, action_context=None):
    """Prompt fragment anchoring the protagonist's physical location."""
    from simulation.scene_coherence import place_label

    place = place_label(player, area) or player.get("location", "")
    lines = [f"LOCATION LOCK: The protagonist is at {place}. Do NOT move them elsewhere this beat."]
    ctx = action_context or {}
    if ctx.get("travel_failed") or ctx.get("approach_failed"):
        lines.append(
            "NO MOVEMENT occurred — they remain exactly where they were. "
            "Do NOT describe entering buildings, crossing districts, or finding new rooms. "
            "Do NOT bolt gates against a place named in prior beats. "
            "Do NOT repeat the focal NPC's prior line verbatim — react to the stall or go quiet."
        )
    sub = player.get("scene_subplace") or {}
    if sub.get("label"):
        lines.append(
            f"Sub-place: {sub['label']}. Crowd and weather may differ slightly but the district is unchanged."
        )
    return "\n".join(lines)
