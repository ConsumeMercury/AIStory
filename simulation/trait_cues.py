"""
Behavioural cues derived from traits — multiple variants per trait so the
narrator prompt does not feed the model the same phrasing every scene.

Pick cues with pick_trait_cues() using npc_id + tick so rotation is stable
within a scene but shifts over time.
"""

import hashlib

# Each trait maps to several SHOW-don't-tell cues; only one is picked per scene.
TRAIT_CUE_VARIANTS = {
    "aggression": [
        "takes up more space than needed; quick to close distance",
        "rests a hand where a weapon would be, even when unarmed",
        "stands too close when speaking, as if measuring you",
    ],
    "kindness": [
        "drifts toward whoever in the room is worst off",
        "notices small hurts — a loose strap, a empty cup — and fixes them without comment",
        "lowers their voice when someone nearby is ashamed",
    ],
    "greed": [
        "prices everything with a glance, including people",
        "weighs your clothes and boots the way others weigh faces",
        "answers slowly when coin is not yet on the table",
    ],
    "ambition": [
        "watches the room for whoever matters most",
        "positions themselves where important eyes might land",
        "remembers names of people above their station",
    ],
    "loyalty": [
        "keeps placing themselves between trouble and one particular person",
        "deflects blame from their own before it can stick",
        "goes quiet when their people are spoken ill of",
    ],
    "honesty": [
        "answers plainly even when a lie would serve better",
        "winces at evasions the way others wince at pain",
        "states uncomfortable facts as if reading weather",
    ],
    "pride": [
        "will not be seen to need anything",
        "refuses help with a courtesy that feels like a wall",
        "straightens when watched, even when exhausted",
    ],
    "curiosity": [
        "leans in at the wrong moments, asks one question too many",
        "opens doors that were left politely closed",
        "picks up objects to read the maker's mark",
    ],
    "patience": [
        "lets silences run long without filling them",
        "waits out anger in others like a tide going out",
        "moves unhurried, as if time owes them nothing",
    ],
    "temper": [
        "a muscle works in the jaw before they speak",
        "colour rises fast and is fought down just as fast",
        "sets down cups harder than necessary",
    ],
    "discipline": [
        "everything about them is squared away, nothing wasted",
        "eats, sleeps, and speaks on a schedule only they can see",
        "corrects small disorder in the room without thinking",
    ],
    "humor": [
        "finds the joke a half-second before it's appropriate",
        "uses laughter to change the subject when cornered",
        "smiles at grim things as if that makes them lighter",
    ],
    "vanity": [
        "checks reflections, adjusts cuffs, minds the angle of their face",
        "turns the better cheek toward any light source",
        "fusses with a collar when nervous",
    ],
    "paranoia": [
        "maps the exits, keeps their back to the wall",
        "mirrors your movements a beat late, testing",
        "never sits where they cannot see the door",
    ],
    "generosity": [
        "the first to put coin or bread on the table",
        "offers what they cannot spare and pretends otherwise",
        "feeds stray animals before feeding themselves",
    ],
    "sentimentality": [
        "touches a worn keepsake when they think no one sees",
        "keeps a name on their lips that no longer belongs in the room",
        "goes soft at old songs, old streets, old weather",
    ],
    "vindictiveness": [
        "keeps a ledger of slights behind a pleasant face",
        "remembers favours as debts and slights as contracts",
        "is gracious in victory and precise in revenge",
    ],
    "piety": [
        "marks small rituals, a touched amulet, a murmured word",
        "flinches at blasphemy others treat as colour",
        "counts blessings under breath when afraid",
    ],
    "wit": [
        "two steps ahead in conversation, lays small traps",
        "answers a question with one that costs more to ignore",
        "uses politeness like a blade wrapped in linen",
    ],
    "courage": [
        "doesn't step back when a wiser person would",
        "walks toward shouting when others walk away",
        "meets bad news without changing pace",
    ],
    "impulsiveness": [
        "acts on the first instinct, words out before the thought finishes",
        "reaches for solutions before the problem is fully named",
        "commits to a path before weighing the cost aloud",
    ],
    "secretiveness": [
        "gives nothing away, deflects questions onto you",
        "answers the question they wish you had asked",
        "changes subject with a skill that feels practiced",
    ],
    "superstition": [
        "reads the room for omens, won't sit thirteen to a table",
        "touches wood, spits over a shoulder, avoids certain numbers",
        "treats coincidence as instruction",
    ],
    "gregariousness": [
        "fills silences, knows everyone's name, works the room",
        "collects introductions the way others collect coin",
        "speaks to strangers as if they were owed a greeting",
    ],
    "ruthlessness": [
        "weighs people as means, discards them without heat",
        "chooses outcomes over apologies every time",
        "shows mercy only when it buys something",
    ],
}


def _stable_index(key, modulo):
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def pick_trait_cues(traits, npc_id, tick, dominant=None, count=1):
    """
    Return `count` behavioural cues for this scene. Rotates by tick so the
    same NPC reads differently visit to visit without changing who they are.
    """
    from generation.trait_generator import dominant_traits

    tops = dominant or dominant_traits(traits, 5)
    cues = []
    for i, trait in enumerate(tops):
        variants = TRAIT_CUE_VARIANTS.get(trait)
        if not variants:
            continue
        idx = _stable_index(f"{npc_id}:{tick}:{trait}:{i}", len(variants))
        cues.append(variants[idx])
        if len(cues) >= count:
            break
    return cues


def pick_scene_focus(npc_id, tick):
    """Which private detail to foreground this scene (one only)."""
    focuses = ("mannerism", "speech", "memory", "want", "last_action", "physique")
    return focuses[_stable_index(f"{npc_id}:focus:{tick}", len(focuses))]
