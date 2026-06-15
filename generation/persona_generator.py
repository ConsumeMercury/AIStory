"""
The 'persona' layer: surface characteristics that make dialogue and presence
vary between two people with similar traits — speech style, core values,
quirks of voice, current mood, and a manner of address. These are cheap,
high-immersion details the narrator can use directly.
"""

import random

SPEECH_STYLES = [
    "terse, clipped sentences", "florid and over-formal", "blunt to the point of rudeness",
    "soft-spoken, trails off", "wry and ironic", "warm and talkative",
    "guarded, answers in questions", "old-fashioned, full of proverbs",
    "crude, peppered with oaths", "precise, lawyerly", "sing-song, regional lilt",
]

VOICE_QUIRKS = [
    "drops the ends of words", "a stammer on hard consonants", "a low, gravelled voice",
    "laughs mid-sentence", "uses your name too often", "never uses your name at all",
    "a foreign vowel that surfaces when tired", "speaks slowly, as if to a child",
    "a habit of repeating your last word", "long pauses before anything important",
]

VALUES = [
    "family above all", "debts must be paid", "the strong owe the weak nothing",
    "loyalty to the guild before the crown", "the gods are watching",
    "coin is the only honest thing", "blood remembers", "knowledge is worth any price",
    "the old ways were better", "no master, no master's rules",
    "mercy is a debt the world repays", "a name is worth dying for",
]

MOODS = ["even", "frayed", "grieving", "elated", "wary", "restless", "numb", "hopeful", "bitter"]


def generate_persona(traits):
    # mood baseline biased a little by temperament
    mood = random.choice(MOODS)
    if traits.get("temper", 50) > 70 and random.random() < 0.5:
        mood = "frayed"
    return {
        "speech_style": random.choice(SPEECH_STYLES),
        "voice_quirk": random.choice(VOICE_QUIRKS),
        "core_value": random.choice(VALUES),
        "mood": mood,
        "literacy": random.random() < (0.4 + traits.get("discipline", 50) / 250),
    }
