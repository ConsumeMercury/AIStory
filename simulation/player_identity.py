"""
Player identity: locals should not know the protagonist's name until introduced.
"""

import re

_INTRO = re.compile(
    r"\b(my name is|i'?m called|call me|i am|name'?s)\s+([A-Za-z][A-Za-z \'-]{1,30})",
    re.I,
)


def default_identity(player):
    return player.setdefault("identity", {
        "alias": "a stranger",
        "revealed_to": [],       # npc ids who know the player's true name
        "revealed_areas": [],    # area ids where reputation uses true name
    })


def player_alias(player):
    ident = default_identity(player)
    bg = player.get("background", "wanderer")
    if ident.get("alias") == "a stranger":
        return f"a {bg} stranger"
    return ident["alias"]


def locals_know_name(player, present_npc_ids):
    ident = default_identity(player)
    revealed = set(ident.get("revealed_to", []))
    if not present_npc_ids:
        return False
    return any(nid in revealed for nid in present_npc_ids)


def mark_name_revealed_to_present(player, present_npc_ids):
    ident = default_identity(player)
    revealed = set(ident.get("revealed_to", []))
    revealed.update(present_npc_ids)
    ident["revealed_to"] = list(revealed)


def detect_self_introduction(action, player):
    """If player introduces themselves, reveal name to present NPCs."""
    m = _INTRO.search(action)
    if m:
        spoken = m.group(2).strip().title()
        true = player.get("name", "").strip()
        if true and spoken.lower().startswith(true.split()[0].lower()):
            return True
        if spoken:
            return True
    text = (action or "").strip()
    true = (player.get("name") or "").strip()
    if true and len(text.split()) == 1:
        if text.lower() in {true.lower(), true.split()[0].lower()}:
            return True
    return None
