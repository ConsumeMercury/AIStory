"""
Hidden truths per NPC — fuel for investigation, blackmail, and rumor exposure.
"""

import random
import uuid

SECRET_TEMPLATES = {
    "priest": [
        "embezzles temple donations into a private cache",
        "performs rites the high priest forbids after midnight",
        "is sheltering someone the law wants",
    ],
    "merchant": [
        "is deeply in debt to a syndicate collector",
        "sells goods that fell off the back of a wagon — knowingly",
        "forged a partner's signature on a contract",
    ],
    "guard": [
        "takes bribes to look away at the docks",
        "works for a rival faction on the side",
        "buried evidence of a beating that killed a prisoner",
    ],
    "soldier": [
        "deserted once and was never caught",
        "sells armour from the garrison stores",
        "is the captain's illegitimate sibling",
    ],
    "thief": [
        "informed on a crew to save their own skin",
        "owes a blood debt to someone in the warrens",
        "is not who their papers claim",
    ],
    "scholar": [
        "plagiarised a dead mentor's work",
        "keeps a forbidden text in a hollow book",
        "was expelled from another city under another name",
    ],
    "innkeeper": [
        "runs a back room for illegal deals",
        "knows which guests never checked out",
        "launders coin for the syndicate",
    ],
    "default": [
        "hides a shameful debt from their family",
        "lied about where they were the night of a fire",
        "carries letters that would ruin someone if opened",
    ],
}


def generate_secrets(npc, factions=None, institutions=None):
    """
    Return 1-2 secrets for an NPC. severity: minor | major | deadly
    """
    role = npc.get("role", "merchant")
    pool = list(SECRET_TEMPLATES.get(role, SECRET_TEMPLATES["default"]))
    random.shuffle(pool)
    count = 2 if random.random() < 0.35 else 1
    secrets = []
    for text in pool[:count]:
        severity = random.choices(
            ["minor", "major", "deadly"],
            weights=[0.45, 0.4, 0.15],
            k=1,
        )[0]
        sec = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "severity": severity,
            "exposed": False,
            "exposed_to_player": False,
            "blackmail_used": False,
        }
        inst = npc.get("institution") or {}
        if inst.get("type") == "garrison" and "captain" in text:
            sec["text"] = "the captain takes bribes to look away at the gate"
        if factions and random.random() < 0.25:
            fid = random.choice(list(factions.keys()))
            fname = factions[fid].get("name", "a faction")
            sec["text"] = f"secretly reports to {fname}"
            sec["linked_faction"] = fid
        secrets.append(sec)
    return secrets


def attach_secrets(npcs, factions=None, institutions=None):
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if not npc.get("secrets"):
            npc["secrets"] = generate_secrets(npc, factions, institutions)
    return npcs


def hidden_secrets(npc):
    return [s for s in (npc.get("secrets") or []) if not s.get("exposed_to_player")]


def expose_secret(npc, secret_id, to_player=True):
    for s in npc.get("secrets") or []:
        if s.get("id") == secret_id:
            s["exposed"] = True
            if to_player:
                s["exposed_to_player"] = True
            return s
    return None


def reveal_one_secret(npc, partial=False):
    """Return a secret for investigation success; partial = vague hint only."""
    hidden = hidden_secrets(npc)
    if not hidden:
        return None
    sec = random.choice(hidden)
    if partial:
        return {
            "hint": f"Something about {sec['text'].split()[0]}… — not the full truth yet.",
            "secret_id": sec["id"],
        }
    sec["exposed_to_player"] = True
    return {
        "full": sec["text"],
        "severity": sec.get("severity", "major"),
        "secret_id": sec["id"],
    }
