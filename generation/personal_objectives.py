"""
Specific personal objectives — plots, not just broad goal weights.
"""

import random

OBJECTIVE_TEMPLATES = {
    "merchant": [
        "recover a stolen ledger before the guild audit closes the books",
        "ruin {rival} before they ruin me at the scales",
        "marry into the high quarter before the season ends",
        "become guildmaster of the local lodge without buying every vote",
        "find who is shaving silver off eastern caravan coin",
        "sell the silent-auction lot before the runner names me",
        "keep my stall from being marked with chalk after curfew",
        "prove the weighmaster's daughter wears silk bought with my coin",
        "outbid the honey cartel without poisoning my own customers",
    ],
    "guard": [
        "prove the captain takes bribes from the night pier",
        "avenge a partner lost on the docks when the watch looked away",
        "catch the smuggler before the garrison replaces my post",
        "learn who runs the press gang without ending up on a ship",
        "hold the gate when forged papers flood the warrens",
        "survive the captain's purge with my badge intact",
        "find out why the lighthouse burns green on wreck nights",
        "protect a witness who saw the customs clerk disappear",
    ],
    "priest": [
        "expose embezzlement in the temple coffers before tithe week",
        "save a penitent who knows too much about diverted relics",
        "stop the heretic preaching in the alleys without blood on the steps",
        "learn whether the penitent engine sells confessions to merchants",
        "keep the reliquary room sealed until the high priest explains the second bone",
        "broker peace between chapel sects before the inquisitors arrive",
        "prove miracles for hire are fraud without breaking the faithful",
        "find who stole the lenten coin before the vault opens empty",
    ],
    "thief": [
        "steal back a family heirloom from a fence in the warrens",
        "pay off a blood debt to the chalk-mark boss before my door is marked",
        "disappear before the last dock job catches up at the gate",
        "sell forged papers without the real clerk's ghost finding me",
        "win the basement pit without owing the ledger more than coin",
        "rob the silent auction without the buyers' circle noticing",
        "learn who the whisper broker sells my secrets to",
        "escape the rat king's toll with both legs and reputation",
    ],
    "scholar": [
        "publish proof that a dead mentor was plagiarized before examination",
        "find the forbidden text before the academy burns every copy",
        "ruin a rival tutor's reputation at examination without becoming them",
        "decode the drowned manifest letters before the harbour master does",
        "expose the rigged examination without expulsion",
        "translate the cipher dialect before foreign agents recruit my students",
        "recover a missing student's notes from a tutor who won't speak",
        "prove the clockwork grader favours whoever oils it",
    ],
    "soldier": [
        "earn the captain's trust before the next desertion purge",
        "desert without the garrison noticing the roll is wrong",
        "protect a civilian who saw the captain take smuggler coin",
        "find who forged the pay roll before mutiny becomes massacre",
        "hold the wall when scouts cry wolf and fire is real",
        "keep my standard when colours change overnight",
        "refuse a mercenary charter without ending up in the pit",
        "learn what moves beyond the wall before the recruit's false alarm kills us all",
    ],
    "sailor": [
        "jump ship before the press gang lists me as volunteer",
        "find who ordered the weapons crate on the night pier",
        "deliver a sealed letter from the nets without the harbour master seeing",
        "survive the salt-curse hold without naming the wrong captain",
        "prove the bride-ship carries papers not a bride",
        "keep my crew off Pier Three when the lanterns die",
    ],
    "innkeeper": [
        "learn which guest pays the press gang without losing the tavern",
        "hide a deserter without the garrison burning my sign",
        "find who poisons honey cakes sold outside my door",
        "keep basement fighters from killing each other on fight night",
    ],
    "default": [
        "settle an old score with someone in this city before they settle mine",
        "accumulate enough coin to leave forever before rent chalk reaches my door",
        "learn a secret that could buy safety from the whisper broker",
        "follow the local storyline to its end without becoming its victim",
        "choose a side in the district plot before it chooses for me",
        "find who runs the trouble in this district and decide what they're worth",
    ],
}


def generate_personal_objective(npc, npcs=None):
    role = npc.get("role", "merchant")
    pool = list(OBJECTIVE_TEMPLATES.get(role, OBJECTIVE_TEMPLATES["default"]))
    text = random.choice(pool)
    if "{rival}" in text and npcs:
        others = [
            n for n in npcs.values()
            if n.get("id") != npc.get("id") and n.get("status") == "alive"
            and n.get("location") == npc.get("location")
        ]
        if others:
            text = text.format(rival=random.choice(others).get("name", "a rival"))
        else:
            text = text.replace("{rival}", "a rival merchant")
    return {
        "text": text,
        "progress": 0,
        "target": 100,
        "complete": False,
    }


def attach_personal_objectives(npcs):
    for npc in npcs.values():
        if npc.get("status") != "alive":
            continue
        if npc.get("personal_objective"):
            continue
        npc["personal_objective"] = generate_personal_objective(npc, npcs)
        if npc.get("goals"):
            npc["goals"] = [npc["personal_objective"]["text"]] + [
                g for g in npc["goals"] if g != npc["personal_objective"]["text"]
            ][:2]
    return npcs


def objective_narrator_line(npc):
    obj = npc.get("personal_objective") or {}
    if not obj or obj.get("complete"):
        return ""
    return f"Personal drive: {obj.get('text', '')[:100]}."
