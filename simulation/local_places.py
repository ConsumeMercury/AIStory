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
)

_APPROACH_VERBS = re.compile(
    r"\b(enter|go inside|step into|walk into|go in to|go in|approach|"
    r"go to|head to|walk to|move to|make for)\b",
    re.I,
)


def looks_like_local_movement(action):
    if not action:
        return False
    if not _APPROACH_VERBS.search(action):
        return False
    text = action.lower()
    for pattern, _sid, _label in _LOCAL_POI:
        if pattern.search(text):
            return True
    return False


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

    return None, None


def build_place_lock(player, area, action_context=None):
    """Prompt fragment anchoring the protagonist's physical location."""
    from simulation.scene_coherence import place_label

    place = place_label(player, area) or player.get("location", "")
    lines = [f"LOCATION LOCK: The protagonist is at {place}. Do NOT move them elsewhere this beat."]
    ctx = action_context or {}
    if ctx.get("travel_failed") or ctx.get("approach_failed"):
        lines.append(
            "NO MOVEMENT occurred — they remain exactly where they were. "
            "Do NOT describe entering buildings, crossing districts, or finding new rooms."
        )
    sub = player.get("scene_subplace") or {}
    if sub.get("label"):
        lines.append(
            f"Sub-place: {sub['label']}. Crowd and weather may differ slightly but the district is unchanged."
        )
    return "\n".join(lines)
