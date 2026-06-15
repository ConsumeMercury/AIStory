"""
Physical descriptions + LOCKED pronouns.

Two jobs:
  1. Build a rich `physique` block (build, height, hair, eyes, skin, marks,
     accessories, attire, apparent age) so the narrator can describe a
     person before the player knows their name.
  2. Lock pronouns at generation time into an explicit dict. The narrator
     is then *told* the exact pronouns, which stops the model drifting
     between "he" and "she" mid-scene.
"""

import random

PRONOUNS = {
    "male":   {"subject": "he",  "object": "him", "possessive": "his", "reflexive": "himself"},
    "female": {"subject": "she", "object": "her", "possessive": "her", "reflexive": "herself"},
}

_BUILD = ["lean", "wiry", "broad-shouldered", "heavyset", "slight", "rangy",
          "barrel-chested", "gaunt", "compact", "powerfully built", "stooped", "willowy"]
_HEIGHT = ["short", "below average height", "average height", "tall", "very tall"]
_HAIR_COLOR = ["black", "dark brown", "chestnut", "auburn", "copper-red", "ash-blond",
               "flaxen", "iron-grey", "silver", "white", "jet-black streaked with grey"]
_HAIR_STYLE = ["close-cropped", "shoulder-length", "tied back", "matted", "braided",
               "shaved at the sides", "wild and uncombed", "neatly oiled", "hidden under a hood"]
_EYES = ["pale grey", "dark brown", "hazel", "green", "ice-blue", "amber", "near-black",
         "one clouded white", "deep-set and bloodshot", "heavy-lidded"]
_SKIN = ["weathered", "pale", "sun-darkened", "olive", "ruddy", "ash-pale",
         "scarred along one cheek", "pockmarked", "smooth", "tattooed at the throat"]
_MARKS = ["a jagged scar across the jaw", "a missing earlobe", "ink-stained fingers",
          "burn scars up both forearms", "a brand on the back of one hand", "a broken nose set crooked",
          "calloused, oversized hands", "a limp favouring the left leg", "no marks worth noting",
          "a faded tattoo of a coiled serpent", "three fingers on the right hand"]
_ACCESSORY = ["a heavy iron ring", "a chipped bone amulet", "a faded military sash",
              "a money pouch worn openly", "a dagger never out of reach", "a string of prayer beads",
              "spectacles of ground glass", "a fur-lined cloak too fine for the district",
              "nothing of obvious value", "a tarnished signet on a cord"]
_ATTIRE = ["travel-stained leathers", "a guildsman's good coat", "patched workman's wool",
           "robes gone grey at the hem", "boiled-leather armour", "a merchant's layered silks",
           "rags barely fit for the season", "the plain habit of a temple servant",
           "a soldier's surplus kit", "clothes that don't fit the body wearing them"]


def generate_physique(age):
    if age < 25:
        apparent = "young"
    elif age < 45:
        apparent = "in their prime"
    elif age < 60:
        apparent = "middle-aged"
    else:
        apparent = "old"
    return {
        "apparent_age": apparent,
        "build": random.choice(_BUILD),
        "height": random.choice(_HEIGHT),
        "hair": f"{random.choice(_HAIR_STYLE)} {random.choice(_HAIR_COLOR)} hair",
        "eyes": f"{random.choice(_EYES)} eyes",
        "skin": random.choice(_SKIN),
        "distinguishing_mark": random.choice(_MARKS),
        "accessory": random.choice(_ACCESSORY),
        "attire": random.choice(_ATTIRE),
    }


def lock_pronouns(gender):
    return dict(PRONOUNS.get(gender, PRONOUNS["male"]))


def short_descriptor(npc):
    """
    A compact noun-phrase the narrator can use INSTEAD of a name when the
    player doesn't know the NPC yet, e.g.
    'the broad-shouldered woman with burn scars up both forearms'.
    Deterministic, so the same stranger is referred to consistently.
    """
    p = npc.get("physique", {})
    gender_noun = {"male": "man", "female": "woman"}.get(npc.get("gender"), "figure")
    build = p.get("build", "")
    mark = p.get("distinguishing_mark", "")
    pieces = ["the"]
    if build:
        pieces.append(build)
    pieces.append(gender_noun)
    if mark and mark != "no marks worth noting":
        pieces.append(f"with {mark}")
    return " ".join(pieces)
