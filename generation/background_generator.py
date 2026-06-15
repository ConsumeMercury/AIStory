"""
Backgrounds that make each NPC a specific person with history, a wound,
a secret, and a mannerism. Composed from parts so we get variety, but
the parts are written as prose fragments so the result reads like a
character note rather than a stat block.

The narrator receives the background as private context to inform
behaviour and dialogue — it is NOT to be recited at the player.
"""

import random

_ORIGINS = [
    "born to net-menders on the harbour and never quite scrubbed the salt out",
    "the third child of a minor house, raised on promises that went to the eldest",
    "orphaned by a border war and passed between relatives who counted the cost aloud",
    "raised in a temple dormitory on cold porridge and colder discipline",
    "grew up in a caravan, with no town owning them and them owing no town",
    "apprenticed young to a trade the body still remembers",
    "born in a debtors' quarter, where everyone was always owed something",
    "the bastard of someone important enough to pay for silence",
    "raised by a grandmother who told the truth only in stories",
    "came up in a mercenary baggage-train, fed when the company was paid",
]

_WOUNDS = [
    "lost someone to a winter that the histories don't bother to name",
    "was betrayed once by the person they trusted most, and learned the lesson too well",
    "failed at the one thing they were certain they were made for",
    "watched a place they loved emptied by fire and never rebuilt",
    "owes a debt that can't be paid in coin",
    "was made an example of, in a square, in front of people they knew",
    "buried a child and tells anyone who asks that they never had one",
    "broke a vow and has been keeping smaller ones ever since to make up for it",
    "carries the blame for something that was only half their fault",
    "outlived a war and isn't sure that was a mercy",
]

_SECRETS = [
    "is not who their papers say they are",
    "is quietly skimming from someone dangerous",
    "is in love with a person they will never be allowed to have",
    "knows where a body is, in the literal sense",
    "is dying slowly and hasn't told a soul",
    "informs for a faction nobody would guess",
    "is hoarding coin for a single, secret purpose",
    "killed someone the law still thinks vanished",
    "is more educated, or more highborn, than they let on",
    "still keeps a token from the life they pretend to have left behind",
]

_MANNERISMS = [
    "answers questions with questions",
    "never sits with their back to a door",
    "laughs a half-second after everyone else",
    "counts things under their breath when nervous",
    "touches a particular object before deciding anything",
    "is too polite when they mean you harm",
    "goes very still instead of flinching",
    "repeats the last word you said before replying",
    "won't meet your eyes but watches your hands",
    "smiles most when they're furthest from amused",
]


def generate_background(role, traits):
    origin = random.choice(_ORIGINS)
    wound = random.choice(_WOUNDS)
    secret = random.choice(_SECRETS)
    mannerism = random.choice(_MANNERISMS)

    prose = (
        f"Works as a {role}; {origin}. "
        f"In the past, {wound}. "
        f"Has a mannerism: {mannerism}."
    )
    return {
        "summary": prose,
        "origin": origin,
        "wound": wound,
        "secret": secret,          # private: drives behaviour, never recited
        "mannerism": mannerism,
    }
