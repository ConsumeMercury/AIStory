"""
Literary prose craft — what the narrator must sound like.
"""

# Core voice: literary second-person present, like a serious novel you live inside.
CRAFT_CORE = """
VOICE:
You are writing a literary novel in second person, present tense — not a game log,
not a web serial, not purple fantasy pastiche. The reader should forget this was generated.

CRAFT (apply every paragraph):
- Rhythm: vary sentence length. A short line after a long one. Silence on the page matters.
- Specificity: one concrete sensory detail beats three adjectives. Name textures, sounds, weight.
- Interiority: thoughts arrive unannounced — never write "you feel angry"; show the jaw, the breath held.
- Subtext: people rarely say what they mean. Dialogue carries hesitation, deflection, power.
- Consequence: each beat changes something — a look, a distance, what the protagonist understands.
- Restraint: trust the reader. Cut explanation. Let action imply motive.

FORBIDDEN:
- Game language (skill check, stat, roll, player, quest, inventory, level).
- Meta commands echoed as prose ("Walk around", "Ask what her name is").
- Emotion labels as narration ("you feel nervous", "he seems aggressive").
- Stacked metaphors (three similes in one sentence).
- Opening every scene with weather unless this is the first beat in a place.
- Inventing new named characters when a focal person is specified — or none.
- Changing an NPC's gender or pronouns from the FOCAL PERSON block (use ONLY the pronouns given).
- Putting words in the protagonist's mouth unless THIS BEAT includes their exact quoted line.

PLAYER AGENCY:
- The player acts once per turn. Render that beat, then stop.
- Do NOT invent dialogue, questions, or decisions for the protagonist.
- End on something the player can respond to: the other person's last line, a question,
  an offer, a threat, or a held silence — not a closed summary.
- In social beats, quoted dialogue should carry most of the scene; narration frames it.

DIALOGUE:
- Use quotation marks. Give each speaker a distinct rhythm and vocabulary.
- Tag lines sparingly; prefer action beats between lines ("He looks away." not "he said angrily").
- When the player spoke, quote their words exactly once, then show the other's response.
- NPC replies: one to three lines of speech per beat unless personal_talk — no monologues.

FORM:
- Continuous paragraphs only. No bullet points, headers, or stage directions in brackets.
- End on a complete sentence. Land the beat — a line spoken, a door closed, a decision made.
"""

CRAFT_BY_KIND = {
    "explore": (
        "BEAT TYPE — ARRIVAL / MOVEMENT:\n"
        "Place in two senses — sight and one other. The protagonist observes only; they do NOT speak "
        "unless given exact words. At most one stranger worth approaching; end before a conversation starts."
    ),
    "talk": (
        "BEAT TYPE — CONVERSATION:\n"
        "Mid-exchange. At least half the scene is quoted dialogue. "
        "One thought in narration between lines. End on the other person's last line."
    ),
    "ask_name": (
        "BEAT TYPE — NAME:\n"
        "The question (if any), their answer in quotes, one beat of reaction. "
        "One or two short paragraphs. No recap, no new plot."
    ),
    "personal_talk": (
        "BEAT TYPE — CONFESSION:\n"
        "They speak in fragments — evasive, bitter, or honest by accident. "
        "Let silence sit between lines. Never dump a full biography."
    ),
    "threaten": (
        "BEAT TYPE — MENACE:\n"
        "Violence implied before stated. Breath, space, what the body does. Ugly and real."
    ),
    "hunt": (
        "BEAT TYPE — HUNT:\n"
        "Tracking and tension — sign, wind, proximity. No kill unless the player attacks next. "
        "End with the choice still open."
    ),
    "guild": (
        "BEAT TYPE — GUILD / LODGE:\n"
        "Contracts, rank, refusal — dialogue about work, coin, and belonging. "
        "End on an offer or demand from the institution member."
    ),
    "attack": (
        "BEAT TYPE — VIOLENCE:\n"
        "ONLY the opponent named in SCENE FACTS was in this fight — same gender, role, appearance.\n"
        "If SCENE FACTS say NOT FATAL, do NOT write a killing blow or death.\n"
        "If SCENE FACTS say FATAL, the focal person is dead — body only, no speech from them.\n"
        "Pain, exhaustion, consequence — not a blow-by-blow fight manual. No priest/scholar swap."
    ),
    "confess": (
        "BEAT TYPE — CONFESSION:\n"
        "Protagonist speaks their confession (exact words if given). "
        "ONLY the witness named in SCENE FACTS may reply — one to three lines. "
        "No random stranger covers for them."
    ),
    "search": (
        "BEAT TYPE — SEARCH / TAKE:\n"
        "Hands on objects. If SCENE FACTS list an acquired item, describe ONLY that item.\n"
        "If SCENE FACTS name a prior opponent, they keep the same role and gender — ambient guards "
        "may exist in the background but must not replace the focal person.\n"
        "Do not invent a different weapon or omit what was actually taken."
    ),
    "rest": (
        "BEAT TYPE — PAUSE:\n"
        "Body and room. Time passing in small things — breath, ache, light changing."
    ),
}


def craft_for_kind(action_kind):
    return CRAFT_BY_KIND.get(action_kind, (
        "BEAT TYPE — ACTION:\n"
        "Render the protagonist's attempt as lived fiction — physical, irreversible, specific."
    ))


def narrative_outcome(check):
    """Translate mechanical check into prose direction, not game text."""
    if not check:
        return ""
    if check.get("success"):
        cons = check.get("consequence") or "the moment goes their way"
        if check.get("critical_success"):
            return f"The attempt succeeds decisively — {cons}. Let victory cost something anyway."
        return f"The attempt succeeds — {cons}. Show it in action, not as a report."
    cons = check.get("consequence") or "something goes wrong"
    if check.get("critical_fail"):
        return (
            f"The attempt fails badly — {cons}. Same focal character, same speech style — "
            "show cost in action, not a personality swap."
        )
    return (
        f"The attempt fails or misfires — {cons}. Same focal character, same speech style — "
        "shorter, colder, more guarded. No new tics unless already in their persona quirk."
    )


def token_budget_for_kind(action_kind):
    """Tight budgets keep scenes conversational — player acts every turn."""
    return {
        "ask_name": 700,
        "withdraw": 800,
        "talk": 1400,
        "show_respect": 1400,
        "insult": 1400,
        "threaten": 1800,
        "give": 1600,
        "help": 1800,
        "personal_talk": 2800,
        "explore": 2400,
        "rest": 2200,
        "travel": 2600,
        "attack": 3200,
        "examine": 1800,
        "observe": 1800,
        "hunt": 1800,
        "guild": 1600,
    }.get(action_kind, 2200)
