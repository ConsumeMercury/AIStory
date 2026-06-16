"""
Physical descriptions + LOCKED pronouns.

Builds a rich, correlated physique block (role-appropriate dress, posture,
voice, scent) so strangers feel like individuals before names are known.
"""

import random

PRONOUNS = {
    "male":   {"subject": "he",  "object": "him", "possessive": "his", "reflexive": "himself"},
    "female": {"subject": "she", "object": "her", "possessive": "her", "reflexive": "herself"},
}

_BUILD = [
    "lean", "wiry", "broad-shouldered", "heavyset", "slight", "rangy",
    "barrel-chested", "gaunt", "compact", "powerfully built", "stooped", "willowy",
    "narrow-chested", "thick-wristed", "knotted with old muscle", "softened by age",
]
_HEIGHT = ["short", "below average height", "average height", "tall", "very tall", "barely five foot"]
_HAIR_COLOR = [
    "black", "dark brown", "chestnut", "auburn", "copper-red", "ash-blond",
    "flaxen", "iron-grey", "silver", "white", "jet-black streaked with grey",
    "dyed an unconvincing brown", "sun-bleached at the tips",
]
_HAIR_STYLE = [
    "close-cropped", "shoulder-length", "tied back", "matted", "braided",
    "shaved at the sides", "wild and uncombed", "neatly oiled", "hidden under a hood",
    "thinning on top", "cropped unevenly as if self-cut", "elaborately pinned",
]
_EYES = [
    "pale grey", "dark brown", "hazel", "green", "ice-blue", "amber", "near-black",
    "one clouded white", "deep-set and bloodshot", "heavy-lidded", "widely spaced",
    "asymmetric — one larger than the other", "watery from smoke or age",
]
_SKIN = [
    "weathered", "pale", "sun-darkened", "olive", "ruddy", "ash-pale",
    "scarred along one cheek", "pockmarked", "smooth", "tattooed at the throat",
    "freckled across the nose", "wind-cracked at the lips", "sallow from indoor work",
]
_MARKS = [
    "a jagged scar across the jaw", "a missing earlobe", "ink-stained fingers",
    "burn scars up both forearms", "a brand on the back of one hand", "a broken nose set crooked",
    "calloused, oversized hands", "a limp favouring the left leg", "no marks worth noting",
    "a faded tattoo of a coiled serpent", "three fingers on the right hand",
    "a split eyebrow from an old cut", "teeth filed to points on one side",
    "a birthmark like a wine stain at the temple", "rope burns at the wrists",
]
_POSTURE = [
    "stands with weight on the back foot", "carries shoulders forward, ready to push",
    "holds the spine very straight — military or trained", "slouches as if apologizing for height",
    "keeps arms close, elbows tucked", "occupies space without seeming to try",
    "favours the right hip when still", "head tilted, listening before looking",
]
_GAIT = [
    "walks quickly, as if late for something", "drags the left foot slightly",
    "steps lightly for someone their size", "heavy tread that announces them early",
    "weaves through crowds without breaking stride", "pauses at every threshold",
]
_VOICE = [
    "a low gravel", "a reedy tenor", "a voice roughened by smoke",
    "surprisingly soft for the frame", "carries farther than intended",
    "drops consonants at the ends of words", "a coastal lilt buried under city speech",
    "flat and careful, as if measured before speaking",
]
_SCENT = [
    "soap and iron", "pipe smoke and wool", "fish and tar",
    "herbs and crushed leaf", "sweat and honest labour", "perfume over unwashed linen",
    "incense that clings to robes", "nothing distinctive", "stale ale and bread",
]

_ROLE_ATTIRE = {
    "merchant": ["layered silks gone shiny at the elbows", "a merchant's coat with too many pockets",
                 "travel-stained but expensive boots", "a ledger pouch on a braided cord"],
    "guard": ["boiled-leather armour over a faded tabard", "a soldier's surplus kit, maintained",
              "a city watch cloak, hem muddy", "ring mail that rattles when they turn"],
    "scholar": ["robes grey at the hem from floor dust", "ink on the cuffs of a scholar's robe",
                "spectacles on a chain, lenses scratched", "a threadbare academic's cloak"],
    "thief": ["dark clothes that don't quite fit", "soft boots, soles worn thin",
              "a hood kept up out of habit", "clothes too clean for the district"],
    "soldier": ["campaign kit with old repairs", "a pauldron dented and never fixed",
                "military boots, laces replaced twice", "a regimental sash faded to pink"],
    "priest": ["the plain habit of a temple servant", "vestments simplified for the street",
               "a prayer cord at the wrist", "sandals worn thin on the inner edge"],
    "herbalist": ["apron stained with green and brown", "sleeves rolled, dried herbs in the hair",
                  "bandages in a belt pouch", "gloves with resin under the nails"],
    "blacksmith": ["a leather apron scarred with sparks", "forearms bare, soot in the creases",
                   "heavy boots, toe caps worn", "a hammer loop on the belt, empty"],
    "innkeeper": ["a good apron over practical wool", "sleeves permanently rolled to the elbow",
                  "keys at the hip, loud when they walk", "a smile-ready face, tired eyes"],
    "sailor": ["tar-stained trousers", "a sailor's knife on a lanyard",
               "a wool coat that smells of salt", "rope-calloused palms, gloves tucked in belt"],
    "mercenary": ["mixed kit from a dozen campaigns", "no insignia, everything functional",
                  "a scarred breastplate over ordinary clothes", "weapons maintained better than clothes"],
    "hunter": ["leathers patched with fur", "a quiver worn smooth at the lip",
               "mud to the knee on one leg", "feathers or claws on a cord — trophies or charms"],
    "farmer": ["patched workman's wool", "boots cracked at the ankle",
               "straw in the hair despite brushing", "hands that won't come fully clean"],
    "scribe": ["ink under the fingernails", "a careful, narrow-cut coat",
               "spectacles, a stylus behind the ear", "sleeves protected by thin linen guards"],
    "apothecary": ["a stained work coat", "glass vials clicking in an inner pocket",
                   "smells of vinegar and lavender", "gloves of thin leather"],
    "default": ["travel-stained leathers", "patched workman's wool", "clothes that don't fit the body wearing them",
                "rags barely fit for the season", "a guildsman's good coat gone shabby at the cuffs"],
}

_ROLE_ACCESSORY = {
    "merchant": ["a money pouch worn openly", "a tarnished signet on a cord", "a scale hook at the belt"],
    "guard": ["a whistle on a cord", "a badge of office, dented", "manacles hanging from the belt — unused, hopefully"],
    "priest": ["a string of prayer beads", "a small holy symbol, thumb-worn", "a book of hours, spine cracked"],
    "scholar": ["spectacles of ground glass", "a scroll case, cap missing", "chalk dust on everything"],
    "default": ["a heavy iron ring", "a chipped bone amulet", "a dagger never out of reach",
                "nothing of obvious value", "a fur-lined cloak too fine for the district"],
}


def _apparent_age(age):
    if age < 22:
        return "young"
    if age < 35:
        return "in their prime"
    if age < 50:
        return "mature"
    if age < 62:
        return "middle-aged"
    return "old"


def generate_physique(age, role=None, gender=None):
    apparent = _apparent_age(age)
    build_pool = _BUILD
    if age > 55:
        build_pool = [b for b in _BUILD if b not in ("powerfully built", "rangy")] + ["stooped", "gaunt"]
    elif age < 22:
        build_pool = [b for b in _BUILD if b not in ("stooped", "heavyset")] + ["slight", "wiry"]

    attire_pool = _ROLE_ATTIRE.get(role, _ROLE_ATTIRE["default"])
    acc_pool = _ROLE_ACCESSORY.get(role, _ROLE_ACCESSORY["default"])

    primary_mark = random.choice(_MARKS)
    secondary = random.choice(_MARKS)
    while secondary == primary_mark:
        secondary = random.choice(_MARKS)

    return {
        "apparent_age": apparent,
        "build": random.choice(build_pool),
        "height": random.choice(_HEIGHT),
        "hair": f"{random.choice(_HAIR_STYLE)} {random.choice(_HAIR_COLOR)} hair",
        "eyes": f"{random.choice(_EYES)} eyes",
        "skin": random.choice(_SKIN),
        "distinguishing_mark": primary_mark,
        "secondary_mark": secondary if secondary != "no marks worth noting" else "",
        "posture": random.choice(_POSTURE),
        "gait": random.choice(_GAIT),
        "voice": random.choice(_VOICE),
        "scent": random.choice(_SCENT),
        "accessory": random.choice(acc_pool),
        "attire": random.choice(attire_pool),
        "hands": random.choice([
            "broad, scarred knuckles", "long-fingered, ink-stained",
            "cracked and dry", "surprisingly delicate", "missing a nail on one thumb",
            "always in motion", "hidden in sleeves",
        ]),
        "presentation": random.randint(40, 72),
    }


def brief_appearance(npc):
    """One-line physical sketch for UI bonds and codex."""
    p = npc.get("physique", {})
    gender_word = {"male": "man", "female": "woman"}.get(npc.get("gender"), "person")
    age_phrase = p.get("apparent_age") or _apparent_age(npc.get("age", 30))
    build = p.get("build", "")
    head = f"{age_phrase} {build} {gender_word}".strip()
    head = " ".join(head.split())
    details = []
    if p.get("hair"):
        details.append(p["hair"])
    if p.get("eyes"):
        details.append(p["eyes"])
    mark = p.get("distinguishing_mark")
    if mark and mark != "no marks worth noting":
        details.append(mark)
    if details:
        return f"{head.capitalize()} — {', '.join(details[:2])}"
    return head.capitalize()


def gender_label(npc):
    return {"male": "Male", "female": "Female"}.get(npc.get("gender"), "Unknown")


def gender_noun(npc):
    return {"male": "man", "female": "woman"}.get(npc.get("gender"), "person")


def lock_pronouns(gender):
    return dict(PRONOUNS.get(gender, PRONOUNS["male"]))


def short_descriptor(npc):
    p = npc.get("physique", {})
    noun = gender_noun(npc)
    build = p.get("build", "")
    mark = p.get("distinguishing_mark", "")
    pieces = ["the"]
    if build:
        pieces.append(build)
    pieces.append(noun)
    if mark and mark != "no marks worth noting":
        pieces.append(f"with {mark}")
    return " ".join(pieces)


def appearance_notes(npc, focus="full"):
    """Compact appearance strings for narrator rotation."""
    p = npc.get("physique", {})
    lock = p.get("appearance_lock")
    if lock and focus in ("full", "face"):
        return lock
    if focus == "posture":
        return f"{p.get('posture', '')}; {p.get('gait', '')}"
    if focus == "face":
        return f"{p.get('eyes', '')}, {p.get('skin', '')} skin, {p.get('hair', '')}"
    if focus == "dress":
        return f"wears {p.get('attire', '')}; carries {p.get('accessory', '')}"
    if focus == "sensory":
        return f"voice: {p.get('voice', '')}; scent: {p.get('scent', '')}"
    return (
        f"{p.get('build', '')}, {p.get('height', '')}, {p.get('hair', '')}, "
        f"{p.get('eyes', '')}, {p.get('distinguishing_mark', '')}"
    )
