"""
Institution membership — guilds, garrisons, lodges beyond abstract faction rep.
"""

from storage import load, save

INST_FILE = "world/institutions.json"

INST_RANKS = [
    (55, "master", "Master"),
    (40, "officer", "Officer"),
    (25, "journeyman", "Journeyman"),
    (12, "apprentice", "Apprentice"),
    (5, "initiate", "Initiate"),
]

INST_TYPE_LABELS = {
    "guild": "Guild",
    "hunters_lodge": "Hunters' lodge",
    "garrison": "Garrison",
    "temple": "Temple",
    "academy": "Academy",
}


def _rank_value(rid):
    order = {"outsider": 0, "initiate": 1, "apprentice": 2, "journeyman": 3,
             "officer": 4, "master": 5}
    return order.get(rid, 0)


def ensure_institution_standing(player, institutions=None):
    institutions = institutions or load(INST_FILE, {})
    book = player.setdefault("institution_standing", {})
    for iid in institutions:
        if iid not in book:
            book[iid] = {
                "score": 0, "rank": "outsider", "rank_label": "Outsider",
                "type": institutions[iid].get("type", ""),
            }
        book[iid].setdefault("rank", "outsider")
    return book


def hunters_lodge_id(city=None):
    institutions = load(INST_FILE, {})
    for iid, inst in institutions.items():
        if inst.get("type") == "hunters_lodge":
            if not city or inst.get("city") == city:
                return iid
    return None


def adjust_institution_standing(player, inst_id, delta, reason=""):
    if not inst_id:
        return None
    institutions = load(INST_FILE, {})
    book = ensure_institution_standing(player, institutions)
    entry = book.setdefault(inst_id, {"score": 0, "rank": "outsider"})
    entry["score"] = max(-100, min(100, entry.get("score", 0) + delta))
    if reason:
        entry["last_reason"] = reason[:120]
    check_institution_invitations(player, institutions)
    return entry


def check_institution_invitations(player, institutions=None):
    institutions = institutions or load(INST_FILE, {})
    book = ensure_institution_standing(player, institutions)
    notes = []
    for iid, inst in institutions.items():
        entry = book.get(iid, {"score": 0, "rank": "outsider"})
        score = entry.get("score", 0)
        rank = entry.get("rank", "outsider")
        for cutoff, rid, rlabel in INST_RANKS:
            if score >= cutoff and _rank_value(rid) > _rank_value(rank):
                entry["rank"] = rid
                entry["rank_label"] = rlabel
                label = INST_TYPE_LABELS.get(inst.get("type"), "Institution")
                if rank == "outsider":
                    notes.append(
                        f"{inst.get('name', iid)} ({label}) offers you rank: {rlabel}."
                    )
                else:
                    notes.append(
                        f"{inst.get('name')} promotes you to {rlabel}."
                    )
                break
        book[iid] = entry
    player["institution_standing"] = book
    player["primary_institution"] = _primary_institution(player, institutions)
    return notes


def _primary_institution(player, institutions):
    book = player.get("institution_standing") or {}
    best = None
    best_score = 0
    for iid, entry in book.items():
        if entry.get("rank", "outsider") == "outsider":
            continue
        sc = entry.get("score", 0)
        if sc > best_score:
            best_score = sc
            best = iid
    if not best:
        return None
    inst = institutions.get(best, {})
    return {
        "id": best,
        "name": inst.get("name"),
        "type": inst.get("type"),
        "rank": book[best].get("rank"),
        "rank_label": book[best].get("rank_label"),
    }


def apply_institution_standing(player, action_kind, target_npc=None, institutions=None):
    """Per-institution rep when acting toward members."""
    if not target_npc:
        return []
    inst_ref = target_npc.get("institution")
    if not inst_ref:
        return []
    institutions = institutions or load(INST_FILE, {})
    inst = institutions.get(inst_ref.get("id"), {})
    iid = inst.get("id")
    if not iid:
        return []

    deltas = {
        "help": 10,
        "give": 8,
        "show_respect": 6,
        "trade": 4,
        "talk": 2,
        "personal_talk": 3,
        "hunt": 3,
        "insult": -12,
        "threaten": -14,
        "attack": -30,
        "steal": -18,
    }
    d = deltas.get(action_kind)
    if d is None:
        return []
    adjust_institution_standing(
        player, iid, d,
        reason=f"{action_kind} toward {inst.get('name', 'member')}",
    )
    return [(iid, d)]


def apply_guild_work_standing(player, target_npc=None):
    """Extra bump when discussing contracts with guild members."""
    if not target_npc:
        return
    inst_ref = target_npc.get("institution")
    if not inst_ref or inst_ref.get("type") != "guild":
        return
    adjust_institution_standing(
        player, inst_ref.get("id"), 4, reason="guild business discussed",
    )


def format_institution_standing(player, institutions=None):
    institutions = institutions or load(INST_FILE, {})
    book = player.get("institution_standing") or {}
    lines = []
    for iid, inst in institutions.items():
        entry = book.get(iid, {"score": 0, "rank": "outsider"})
        if entry.get("score", 0) == 0 and entry.get("rank") == "outsider":
            continue
        tlabel = INST_TYPE_LABELS.get(inst.get("type"), inst.get("type", "?"))
        lines.append(
            f"  {inst.get('name', iid)} ({tlabel}): "
            f"{entry.get('score', 0):+.0f} — {entry.get('rank_label', 'Outsider')}"
        )
    if not lines:
        return ["  No institution membership yet — earn trust with members."]
    return lines


def institution_narrator_block(player, area_id=None, institutions=None):
    institutions = institutions or load(INST_FILE, {})
    book = player.get("institution_standing") or {}
    here = []
    for iid, inst in institutions.items():
        if area_id and inst.get("area") != area_id:
            continue
        entry = book.get(iid, {})
        if entry.get("score", 0) >= 20:
            here.append(f"{inst.get('name')}: they know you as {entry.get('rank_label', 'associate')}.")
    if not here:
        return ""
    return "INSTITUTION REPUTATION HERE:\n" + "\n".join(f"- {h}" for h in here[:2])
