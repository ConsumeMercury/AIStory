"""
Player standing with factions — one choice ripples across many future interactions.
"""

from storage import load, save

FACTION_FILE = "world/factions.json"
PLAYER_FILE = "player/player.json"
INST_FILE = "world/institutions.json"

STANDING_LABELS = [
    (40, "allied", "Allied — doors open, aid offered"),
    (20, "respected", "Respected — fair hearing"),
    (5, "neutral", "Neutral — neither friend nor foe"),
    (-10, "distrusted", "Distrusted — cold reception"),
    (-30, "hostile", "Hostile — turned away or watched"),
    (-999, "hunted", "Hunted — violence or arrest likely"),
]


MEMBERSHIP_RANKS = [
    (60, "inner_circle", "Inner circle"),
    (45, "officer", "Officer"),
    (30, "member", "Member"),
    (20, "initiate", "Initiate"),
]


def _rank_value(rid):
    order = {"outsider": 0, "initiate": 1, "member": 2, "officer": 3, "inner_circle": 4}
    return order.get(rid, 0)


def _label(score):
    for cutoff, lid, desc in STANDING_LABELS:
        if score >= cutoff:
            return lid, desc
    return "hunted", STANDING_LABELS[-1][2]


def ensure_faction_standing(player, factions=None):
    factions = factions or load(FACTION_FILE, {})
    book = player.setdefault("faction_standing", {})
    for fid in factions:
        if fid not in book:
            book[fid] = {"score": 0, "label": "neutral", "rank": "outsider", "rank_label": "Outsider"}
        book[fid].setdefault("rank", "outsider")
    return book


def check_faction_invitations(player, factions=None):
    """Promote standing to membership when thresholds crossed."""
    factions = factions or load(FACTION_FILE, {})
    book = ensure_faction_standing(player)
    notes = []
    for fid, f in factions.items():
        entry = book.get(fid, {"score": 0, "rank": "outsider"})
        score = entry.get("score", 0)
        rank = entry.get("rank", "outsider")
        for cutoff, rid, rlabel in MEMBERSHIP_RANKS:
            if score >= cutoff and _rank_value(rid) > _rank_value(rank):
                entry["rank"] = rid
                entry["rank_label"] = rlabel
                if rank == "outsider":
                    notes.append(f"{f.get('name', fid)} invites you to join as {rlabel}.")
                else:
                    notes.append(f"{f.get('name', fid)} promotes you to {rlabel}.")
                break
        book[fid] = entry
    player["faction_standing"] = book
    return notes


def institution_faction(inst, factions):
    """Map institution to a faction by type overlap or random link."""
    if inst.get("faction_id") and inst["faction_id"] in factions:
        return inst["faction_id"]
    itype = inst.get("type", "")
    type_map = {
        "guild": "guild",
        "temple": "order",
        "garrison": "empire",
        "academy": "order",
        "hunters_lodge": "guild",
    }
    want = type_map.get(itype)
    if want:
        for fid, f in factions.items():
            if f.get("type") == want:
                return fid
    return next(iter(factions.keys()), None)


def adjust_standing(player, faction_id, delta, reason=""):
    if not faction_id:
        return None
    book = ensure_faction_standing(player)
    entry = book.setdefault(faction_id, {"score": 0, "label": "neutral"})
    entry["score"] = max(-100, min(100, entry["score"] + delta))
    lid, desc = _label(entry["score"])
    entry["label"] = lid
    if reason:
        entry["last_reason"] = reason[:120]
    check_faction_invitations(player)
    return entry


def apply_action_standing(player, action_kind, target_npc=None, factions=None, institutions=None):
    """Shift faction rep from player actions toward institution members."""
    if not target_npc:
        return []
    inst_ref = target_npc.get("institution")
    if not inst_ref:
        return []
    factions = factions or load(FACTION_FILE, {})
    institutions = institutions or load(INST_FILE, {})
    inst = institutions.get(inst_ref.get("id"), {})
    fid = institution_faction(inst, factions)
    if not fid:
        return []

    deltas = {
        "help": 8,
        "give": 6,
        "show_respect": 5,
        "trade": 2,
        "talk": 1,
        "personal_talk": 2,
        "insult": -10,
        "threaten": -12,
        "attack": -25,
        "steal": -15,
    }
    d = deltas.get(action_kind)
    if d is None:
        return []
    adjust_standing(player, fid, d, reason=f"{action_kind} toward {inst.get('name', 'member')}")
    return [(fid, d)]


def format_faction_standing(player, factions=None):
    factions = factions or load(FACTION_FILE, {})
    book = player.get("faction_standing") or {}
    lines = []
    for fid, f in factions.items():
        entry = book.get(fid, {"score": 0, "label": "neutral"})
        _, desc = _label(entry.get("score", 0))
        rank = entry.get("rank_label", entry.get("rank", "Outsider"))
        lines.append(
            f"  {f.get('name', fid)}: {entry.get('score', 0):+.0f} ({desc}) — {rank}"
        )
    return lines
