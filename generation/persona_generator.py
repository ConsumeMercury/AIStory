"""
Persona layer: speech, values, mood, and example lines the model can echo
without repeating the same adjectives every scene.
"""

import random

SPEECH_STYLES = [
    "terse, clipped sentences", "florid and over-formal", "blunt to the point of rudeness",
    "soft-spoken, trails off", "wry and ironic", "warm but brief",
    "guarded, answers in questions", "old-fashioned, full of proverbs",
    "crude, peppered with oaths", "precise, lawyerly", "sing-song, regional lilt",
    "measured, each word weighed", "flat, as if reporting weather",
    "storyteller's cadence, almost anecdote", "whispers even in noise",
    "military brevity", "merchant's patter without the sales pitch",
]

VOICE_QUIRKS = [
    "drops the ends of words", "a stammer on hard consonants", "a low, gravelled voice",
    "laughs mid-sentence", "never uses your name", "speaks slowly, as if to a child",
    "long pauses before anything important", "clears the throat before disagreeing",
    "mispronounces one common word", "talks with hands, stops when noticed",
    "ends statements like questions", "never finishes a thought aloud",
    "hums old tunes between clauses", "switches language for curses only",
    "addresses the room, not the person",
]

VALUES = [
    "family above all", "debts must be paid", "the strong owe the weak nothing",
    "loyalty to the guild before the crown", "the gods are watching",
    "coin is the only honest thing", "blood remembers", "knowledge is worth any price",
    "the old ways were better", "no master, no master's rules",
    "mercy is a debt the world repays", "a name is worth dying for",
    "truth before comfort", "everyone lies; read the lie they need",
]

MOODS = [
    "even", "frayed", "grieving", "elated", "wary", "restless", "numb", "hopeful", "bitter",
    "suspicious", "indifferent", "reckless", "penitent", "vindictive", "lonely", "content",
]

# Example lines keyed by speech register — narrator may echo rhythm, not text
_EXAMPLE_LINES = {
    "terse": ["\"No.\"", "\"Later.\"", "\"You lost me at the price.\""],
    "blunt": ["\"That's not my problem.\"", "\"Say what you want or go.\""],
    "soft": ["\"I... suppose that could work.\"", "\"If you don't mind waiting.\""],
    "wry": ["\"Brave plan. I give it till noon.\"", "\"Gods help us — you included.\""],
    "formal": ["\"If I may — the matter requires care.\"", "\"Your pardon, but that is irregular.\""],
    "crude": ["\"Sod that for a lark.\"", "\"You hear me or you hear thunder?\""],
    "plain": ["\"Fair enough.\"", "\"I've heard worse.\""],
}

_DIALOGUE_DENSITY = ["sparse — speaks only when necessary", "normal", "reluctant — prefers silence or gesture"]


def _speech_bucket(style):
    s = style.lower()
    if "terse" in s or "military" in s or "blunt" in s:
        return "terse" if "terse" in s or "military" in s else "blunt"
    if "soft" in s or "whisper" in s:
        return "soft"
    if "wry" in s or "ironic" in s:
        return "wry"
    if "formal" in s or "courtly" in s or "florid" in s:
        return "formal"
    if "crude" in s or "oath" in s:
        return "crude"
    return "plain"


def generate_persona(traits, role=None):
    mood = random.choice(MOODS)
    if traits.get("temper", 50) > 70 and random.random() < 0.5:
        mood = random.choice(["frayed", "vindictive", "restless"])
    elif traits.get("sentimentality", 50) > 70 and random.random() < 0.4:
        mood = random.choice(["grieving", "hopeful", "lonely"])

    speech_style = random.choice(SPEECH_STYLES)
    bucket = _speech_bucket(speech_style)
    examples = list(_EXAMPLE_LINES.get(bucket, _EXAMPLE_LINES["plain"]))
    random.shuffle(examples)

    density = "sparse — speaks only when necessary"
    if traits.get("gregariousness", 50) > 70:
        density = random.choice(["normal", "normal"])
    elif traits.get("secretiveness", 50) > 65:
        density = "reluctant — prefers silence or gesture"

    return {
        "speech_style": speech_style,
        "voice_quirk": random.choice(VOICE_QUIRKS),
        "core_value": random.choice(VALUES),
        "mood": mood,
        "literacy": random.random() < (0.4 + traits.get("discipline", 50) / 250),
        "dialogue_density": density,
        "example_lines": examples[:2],
        "avoids_topics": random.sample(
            ["politics", "family", "money", "the war", "religion", "their past", "rumours"],
            k=random.randint(1, 2),
        ),
    }
