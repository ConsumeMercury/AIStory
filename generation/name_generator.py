"""
Names with CULTURE and SURNAMES.

A culture is chosen (often by region/city later) and gives both a given
name and a family name, so members of a family can share a surname and the
world feels like it has peoples rather than random syllables.
"""

import random

NAME_STYLES = {
    "imperial": {
        "prefix": ["val", "mar", "cor", "ael", "sol", "ter", "lor", "cas", "dre"],
        "suffix": ["ion", "ius", "ar", "en", "us", "ath", "ena", "ia"],
        "surnames": ["Valcorin", "Maric", "Aelthus", "Soren", "Castaval", "Dremar"],
    },
    "northern": {
        "prefix": ["grim", "ragn", "ulf", "bjorn", "karl", "hark", "sig", "ed"],
        "suffix": ["son", "var", "rik", "dun", "gar", "helm", "a", "i"],
        "surnames": ["Frosthal", "Ulfgar", "Stonehand", "Bjornsen", "Harrow", "Kveld"],
    },
    "desert": {
        "prefix": ["za", "ka", "sha", "ra", "fa", "lu", "na", "ami"],
        "suffix": ["hir", "muk", "zar", "dal", "sah", "mun", "ya", "im"],
        "surnames": ["al-Zahir", "Karim", "Suleima", "Nadir", "Faroud", "Amri"],
    },
    "mystic": {
        "prefix": ["ae", "ny", "xi", "ul", "io", "ze", "syl", "vae"],
        "suffix": ["thar", "vex", "mora", "lith", "nox", "veil", "wyn", "ra"],
        "surnames": ["Nightveil", "Sylthar", "Moranox", "Vaelith", "Duskwyn", "Iorae"],
    },
    "common": {
        "prefix": ["jon", "wil", "tam", "bess", "rob", "mar", "hal", "ned", "gwen"],
        "suffix": ["", "kin", "et", "wyn", "ric", "a", "el", "ow"],
        "surnames": ["Fletcher", "Mason", "Carter", "Thatch", "Brook", "Ashby",
                     "Cole", "Marsh", "Webb", "Tanner", "Quill", "Reed"],
    },
}

CULTURES = list(NAME_STYLES.keys())


def generate_given_name(culture=None):
    culture = culture or random.choice(CULTURES)
    s = NAME_STYLES[culture]
    name = random.choice(s["prefix"]) + random.choice(s["suffix"])
    return name.capitalize()


def generate_surname(culture=None):
    culture = culture or random.choice(CULTURES)
    return random.choice(NAME_STYLES[culture]["surnames"])


def generate_name(culture=None, surname=None):
    """Full 'Given Surname'. If surname is passed (family), reuse it."""
    culture = culture or random.choice(CULTURES)
    given = generate_given_name(culture)
    fam = surname if surname is not None else generate_surname(culture)
    return f"{given} {fam}"


# back-compat: some old code expects generate_full_name()
def generate_full_name(culture=None):
    return generate_name(culture)
