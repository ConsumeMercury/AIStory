"""
Narrator-foregrounded takeable objects — registered from prose, resolved on pickup.

Mirrors narrator_places: if the narrator describes an object, the player can pick it up.
"""

import re

MAX_ITEMS_PER_AREA = 12

_ITEM_NOUN = re.compile(
    r"\b(?:the|a|an)\s+"
    r"(?P<label>(?:[\w'-]+\s+){0,4}?"
    r"(?:parchment(?:\s+scrap)?|scrap(?:\s+of\s+[\w'-]+)?|letter|seal|token|"
    r"iron key|brass key|key|coin|shard|note|ledger|receipt|beetle|charm|ring|"
    r"amulet|locket|map|bundle|pouch|flask|vial|medallion|strip of [\w'-]+|"
    r"piece of [\w'-]+|shard of [\w'-]+|scrap of [\w'-]+|"
    r"notched blade|rusty blade|dagger|knife|sword|blade))"
    r"\b",
    re.I,
)

_FOREGROUND = re.compile(
    r"\b(?:you (?:see|notice|spot|find)|lies? (?:on|at|in|half-)|"
    r"at your feet|protruding|tucked|half-hidden|glint(?:ing|s)?|"
    r"clutched|discarded|abandoned|forgotten)\b",
    re.I,
)

_PICKUP_QUERY = re.compile(
    r"\b(?:pick up|pickup|take|grab|loot|carry|get)\s+(?:the\s+)?(.+?)(?:\s*$|\.|,)",
    re.I,
)

_CATEGORY_MAP = (
    (re.compile(r"\b(sword|blade|dagger|knife|axe|bow|weapon)\b", re.I), "weapon", "sword"),
    (re.compile(r"\b(armor|armour|coat|vest|jack)\b", re.I), "armor", "leather coat"),
    (re.compile(r"\b(parchment|letter|note|ledger|receipt|scrap|map|document)\b", re.I), "material", None),
    (re.compile(r"\b(key|token|seal|ring|amulet|locket|charm|medallion|beetle|coin)\b", re.I), "trinket", None),
)


def _infer_category(label):
    for pat, category, template in _CATEGORY_MAP:
        if pat.search(label):
            return category, template
    return "material", None


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:48]


def _token_set(text):
    stop = {"the", "a", "an", "of", "on", "in", "at", "your", "my", "his", "her"}
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in stop and len(t) > 1}


def _normalize_label(raw):
    label = (raw or "").strip(" .,\"'")
    label = re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.I).strip()
    return label


def extract_narrator_items(scene):
    """Pull takeable object names foregrounded in narrator prose."""
    if not scene:
        return []
    found = []
    seen = set()
    text = scene[:2400]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sent in sentences:
        if not _FOREGROUND.search(sent) and not _ITEM_NOUN.search(sent):
            continue
        for m in _ITEM_NOUN.finditer(sent):
            label = _normalize_label(m.group("label"))
            key = label.lower()
            if len(key) < 3 or key in seen:
                continue
            seen.add(key)
            category, template = _infer_category(label)
            found.append({
                "id": _slug(label) or "narrator_item",
                "label": label if label.lower().startswith(("the ", "a ")) else f"the {label}",
                "tokens": sorted(_token_set(label)),
                "category": category,
                "template_name": template,
            })
    return found[:MAX_ITEMS_PER_AREA]


def record_narrator_items(player, scene, area_id, *, tick=None):
    """Cache foreground items from prose so later pickup actions can resolve them."""
    items = extract_narrator_items(scene)
    if not items or not area_id:
        return False
    store = player.setdefault("narrator_items", {}).setdefault(area_id, {})
    changed = False
    for item in items:
        iid = item["id"]
        if iid not in store:
            rec = dict(item)
            if tick is not None:
                rec["registered_tick"] = tick
            store[iid] = rec
            changed = True
    if len(store) > MAX_ITEMS_PER_AREA:
        ordered = sorted(store.items(), key=lambda kv: kv[1].get("registered_tick") or 0)
        player["narrator_items"][area_id] = dict(ordered[-MAX_ITEMS_PER_AREA:])
        changed = True
    return changed


def _area_store(player, area_id):
    if not area_id:
        return {}
    return (player.get("narrator_items") or {}).get(area_id, {})


def match_narrator_item_pickup(action, player, area_id):
    """Return a registered narrator item record matching a pickup/search query."""
    if not action or not area_id:
        return None
    m = _PICKUP_QUERY.search(action.strip())
    if not m and not re.search(r"\b(?:find|look for|search for)\b", action, re.I):
        return None
    query = _normalize_label(m.group(1) if m else action)
    if not query or len(query) < 3:
        return None
    if re.search(r"\b(?:someone|person|body|corpse|priest|guard|merchant)\b", query, re.I):
        return None

    query_tokens = _token_set(query)
    ql = query.lower()
    store = _area_store(player, area_id)
    best = None
    best_score = 0
    for rec in store.values():
        label = (rec.get("label") or "").lower()
        label_tokens = set(rec.get("tokens") or []) or _token_set(label)
        overlap = len(query_tokens & label_tokens)
        if ql in label or label in ql:
            overlap += 10
        if overlap > best_score:
            best_score = overlap
            best = rec
    if best and (best_score >= 2 or ql in (best.get("label") or "").lower()):
        return dict(best)
    return None


def consume_narrator_item(player, area_id, item_id):
    """Remove a registered item after the player picks it up."""
    store = player.get("narrator_items", {}).get(area_id, {})
    if item_id in store:
        del store[item_id]
        return True
    return False


def prune_narrator_items(player, area_id):
    """Drop registered items when leaving an area."""
    areas = player.get("narrator_items") or {}
    if area_id in areas:
        del areas[area_id]
        return True
    return False
