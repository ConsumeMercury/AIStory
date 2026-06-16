"""
Layered backgrounds: each NPC is assembled from correlated life fragments
(childhood, turning point, daily life, beliefs, secrets) so no two read alike.

The narrator receives fragments rotated over time — never the full biography at once.
"""

import random

# --- fragment pools (compositional, not pick-one-of-four) ---

_CHILDHOODS = [
    "a harbour tenement where sleep came in shifts",
    "a farmhouse that smelled of wet hay and unpaid rent",
    "a temple dormitory on cold porridge and stricter prayers",
    "a caravan route with no town that claimed them",
    "a debtors' quarter where everyone counted what they were owed",
    "a minor house's third wing, full of promises meant for the eldest",
    "a border village erased once by soldiers and rebuilt thinner",
    "a mining camp where lungs learned dust before language",
    "a river town that flooded every seventh spring without fail",
    "a mercenary baggage train where meals depended on victory",
    "a weaver's loft above a shop that never turned a profit",
    "a coastal lighthouse tended by a aunt who spoke to storms",
]

_FORMATIVE = [
    "lost someone in a winter the histories never named",
    "was betrayed by the one person they would have died for",
    "failed publicly at the craft they believed was their calling",
    "watched their home emptied by fire and never rebuilt it",
    "was made an example in a square before people they knew",
    "broke a vow and has kept smaller ones ever since",
    "survived a plague year that took half their neighbours",
    "fled a marriage arranged for coin, not comfort",
    "spent a year in a cell for a crime they only half committed",
    "saw a miracle they cannot explain and will not discuss",
    "walked away from a fortune to keep their name clean",
    "carried a dying message across three borders and delivered it too late",
]

_CURRENT = [
    "works the trade honestly but counts every hour",
    "keeps two ledgers — one for the taxman, one for truth",
    "is one bad month from ruin and knows it",
    "has a patron they despise but cannot refuse",
    "is saving for a journey they have not told anyone about",
    "maintains respectability while scrambling underneath",
    "trains an apprentice who may surpass them soon",
    "owes favours up and down the district",
    "is being slowly replaced by someone younger and cheaper",
    "runs a side business the guild must never learn of",
    "nurses an injury that will not heal and hides the limp",
    "feeds dependents who do not know how thin the margins are",
]

_BELIEFS = [
    "the gods notice small cruelties more than grand piety",
    "coin is honest because it never pretends to love you",
    "family debt outlives the debtor",
    "mercy is a luxury paid for in advance",
    "a name, once stained, never fully washes",
    "the law is a story told by people with walls",
    "luck is what the brave call preparation",
    "every kindness is a loan with hidden interest",
    "the dead listen if you speak plainly enough",
    "no one is as alone as they pretend",
]

_SECRETS = [
    "is not who their papers say they are",
    "skims from someone dangerous and sleeps badly for it",
    "loves someone they can never be allowed to have",
    "knows where a body is buried — literally",
    "is dying slowly and has told no one",
    "reports to a faction no one would suspect",
    "hoards coin for one secret purpose",
    "killed someone the law still lists as missing",
    "is better born or better read than they let on",
    "keeps a token from the life they pretend to have left",
    "forged a document that could hang them",
    "is hiding a child somewhere safe",
    "sold information once and would again if pressed",
]

_MANNERISMS = [
    "answers questions with questions",
    "never sits with their back to a door",
    "laughs a half-second after everyone else",
    "counts things under their breath when nervous",
    "touches a worn object before deciding anything",
    "is too polite when they mean harm",
    "goes very still instead of flinching",
    "repeats your last word before replying",
    "watches hands, not faces",
    "smiles most when least amused",
    "rolls a coin between knuckles when thinking",
    "sniffs the air before entering a room",
    "stands slightly to your left, never explained",
    "tucks hair behind one ear only when lying",
    "hums one note when impatient",
    "straightens objects that are not theirs",
    "speaks to animals before speaking to people",
    "keeps one glove on, one off",
    "bows wrong for their station — too much or too little",
    "finishes your sentences incorrectly on purpose",
]

_ROLE_HOOKS = {
    "merchant": ("learned prices before letters", "a contract that ruined their partner"),
    "guard": ("grew up watching gates decide who mattered", "once looked away from a beating"),
    "scholar": ("found a book that should have been burned", "was expelled for asking one question"),
    "thief": ("was taught to steal before they were taught to read", "still owes the guild a debt"),
    "soldier": ("marched before they were grown", "carries a medal for a day they won't describe"),
    "priest": ("heard a confession that changed their faith", "doubts aloud only when alone"),
    "herbalist": ("was healed by a stranger who asked for nothing", "knows which plants end pain and which end lives"),
    "blacksmith": ("has burns that tell their apprenticeship year", "forged something they refuse to name"),
    "innkeeper": ("knows everyone's business and sells none of it — yet", "once hid fugitives in the cellar"),
    "sailor": ("lost a ship in a storm with names still spoken at night", "has sailed farther than they admit"),
    "mercenary": ("fought for both sides of the same war", "will not work for one name again"),
    "hunter": ("tracked a beast for nine days alone", "found something human in the deep woods"),
    "farmer": ("lost a harvest to locusts and kept the farm anyway", "knows which neighbour steals eggs"),
    "scribe": ("copied a letter that got someone killed", "can forge any hand but chooses not to — usually"),
    "apothecary": ("survived an poisoning attempt", "keeps antidotes for poisons they hope never to see"),
}

_HOPES = [
    "leave this city before the year turns",
    "see a child safe through apprenticeship",
    "pay off the last of their father's debt",
    "find out who betrayed them",
    "die somewhere quiet, with a name intact",
    "earn enough to stop lying about their past",
    "be forgiven by someone who is not here",
    "witness one honest thing before the end",
]


def generate_background(role, traits):
    childhood = random.choice(_CHILDHOODS)
    formative = random.choice(_FORMATIVE)
    current = random.choice(_CURRENT)
    belief = random.choice(_BELIEFS)
    secret = random.choice(_SECRETS)
    mannerism = random.choice(_MANNERISMS)
    hope = random.choice(_HOPES)

    role_child, role_event = _ROLE_HOOKS.get(role, ("learned their trade young", "has a day they won't revisit"))
    if random.random() < 0.65:
        childhood = f"{role_child}; spent early years in {childhood}"
    if random.random() < 0.5:
        formative = f"{formative}; {role_event}"

    # trait-correlated colour
    if traits.get("piety", 50) > 70:
        belief = random.choice(_BELIEFS[:4] + ["suffering is a ledger the gods keep"])
    if traits.get("greed", 50) > 70:
        current = random.choice(_CURRENT[:4] + ["counts coin twice and trust once"])
    if traits.get("secretiveness", 50) > 75:
        secret = random.choice(_SECRETS)

    summary = (
        f"A {role}: raised in {childhood}. "
        f"Life turned when {formative}. "
        f"Now {current}. "
        f"Believes {belief}. "
        f"Privately hopes to {hope}."
    )

    return {
        "summary": summary,
        "childhood": childhood,
        "formative_event": formative,
        "current_situation": current,
        "belief": belief,
        "hope": hope,
        "origin": childhood,
        "wound": formative,
        "secret": secret,
        "mannerism": mannerism,
        "role_history": role_event,
    }
