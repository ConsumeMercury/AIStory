"""
Parse player input into intent, spoken words, and novel-style scene directives.
"""

import re

from generation.descriptor_generator import short_descriptor

# Order matters — specific before general
_PATTERNS = [
    (re.compile(r"\b(your name|who are you|what.s your name|what are you called|ask .*name|name is what)\b", re.I), "ask_name"),
    (re.compile(r"\b(my name is|i'?m called|call me\b|i am \w+)\b", re.I), "talk"),
    (re.compile(r"\b(tell me about|your past|about yourself|about you|your story|where you come from|who you were)\b", re.I), "personal_talk"),
    (re.compile(r"\bgive\s+(him|her|them)\s+fear\b", re.I), "threaten"),
    (re.compile(r"\bgive\s+(him|her|them)\s+respect\b", re.I), "show_respect"),
    (re.compile(r"\b(show|give)\s+(respect|honor|deference)\b", re.I), "show_respect"),
    (re.compile(r"\b(blackmail|leverage against| expose them)\b", re.I), "blackmail"),
    (re.compile(r"\b(accuse|call out|denounce|you did it)\b", re.I), "accuse"),
    (re.compile(r"\b(ask about|ask around about|what do you know about|who killed|who stole|about the murder|about the theft)\b", re.I), "ask_about"),
    (re.compile(r"^\s*ask\s+[A-Za-z][A-Za-z'-]{1,28}\s+about\s+", re.I), "ask_about"),
    (re.compile(r"^\s*ask\s+.+\b(why|what|how|where|when|who|whether|if)\b", re.I), "ask_about"),
    (re.compile(
        r"^\s*(?:the|a|an)\s+(?:[\w'-]+\s+){0,5}?"
        r"(why|what|how|where|when|who|whether|if)\s+",
        re.I,
    ), "ask_about"),
    (re.compile(r"\b(stake out|wait for|watch for|keep watch)\b", re.I), "wait"),
    (re.compile(r"\b(hunt|track|stalk|trail|follow tracks|follow the trail)\b", re.I), "hunt"),
    (re.compile(r"\bfollow\s+(?:the\s+)?(?:noise|sound|them|him|her)\b", re.I), "approach"),
    (re.compile(r"\b(ask for work|looking for work|need work|any work|hire me|find work)\b", re.I), "guild"),
    (re.compile(r"\b(guild contract|join the guild|guild work|take the contract|bounty board)\b", re.I), "guild"),
    (re.compile(r"\b(pressure|lean on|push him|push her|demand)\b", re.I), "threaten"),
    (re.compile(r"\b(investigate|look into|dig into|crime scene|search for clues)\b", re.I), "investigate"),
    (re.compile(r"\b(i killed|i have killed|i'?ve killed|murdered|confess)\b", re.I), "confess"),
    (re.compile(r"\b(find|look for|search for)\s+(?:a|an|the|some)?\s*(sword|blade|dagger|knife|weapon|axe|bow|armor|armour|steel)\b", re.I), "search"),
    (re.compile(r"\b(pick up|take|grab|loot)\s+(?:a|an|the|some)?\s*\w", re.I), "search"),
    (re.compile(r"\bfind someone\b", re.I), "find"),
    (re.compile(r"\bfind (?:the |a )?(?:red[\s-]?haired|captain|priest|cleric|scholar|tutor|merchant|sailor|woman|man|guard|blacksmith)\b", re.I), "find"),
    (re.compile(
        r"\b(?:find|look for|locate)\s+(?:the\s+)?"
        r"(?!a\s+(?:sword|blade|dagger|knife|weapon|axe|bow|armor|armour|steel)\b)"
        r"[A-Za-z][a-z'-]+(?:\s+[A-Za-z][a-z'-]+)?\b",
        re.I,
    ), "find"),
    (re.compile(r"\bfollow\s+(?:the\s+)?(?:smear|trail|grease|tracks|scrap|line|blood)\b", re.I), "approach"),
    (re.compile(r"\b(attack|strike|kill|fight|stab|swing at|draw .*blade|cut down)\b", re.I), "attack"),
    (re.compile(
        r"\b(enter|go inside|step into|walk into|go in to|go in)\b", re.I,
    ), "approach"),
    (re.compile(
        r"\b(go to|head to|approach|walk to|move to|make for)\s+(?:the\s+)?"
        r"(?:door|gate|oak|portal|office|clerk|clerks|sanctuary|chapel|altar|"
        r"temple|shrine|inn|tavern|cellar|alley|wharf|stall|entrance|archway)\b",
        re.I,
    ), "approach"),
    (re.compile(r"\b(travel|go to|head to|journey|ride to|set out for)\b", re.I), "travel"),
    (re.compile(r"\b(walk around|wander|stroll|look around|explore|roam|amble)\b", re.I), "explore"),
    (re.compile(r"\b(give|offer|pay|hand over|gift|donate)\b", re.I), "give"),
    (re.compile(r"\b(help|assist|aid|bandage|heal|save|protect|rescue)\b", re.I), "help"),
    (re.compile(r"\b(threaten|threathen|intimidate|menace|scare)\b", re.I), "threaten"),
    (re.compile(r"\b(insult|mock|taunt|spit at|belittle)\b", re.I), "insult"),
    (re.compile(r"\b(steal|pickpocket|snatch|take from)\b", re.I), "steal"),
    (re.compile(r"\b(buy|purchase|trade for|barter|haggle)\b", re.I), "trade"),
    (re.compile(r"\b(examine|inspect|look at|study closely|search)\b", re.I), "examine"),
    (re.compile(r"\b(listen|eavesdrop|overhear|watch quietly|observe)\b", re.I), "observe"),
    (re.compile(r"\b(rest|sleep|sit down|eat|drink)\b", re.I), "rest"),
    (re.compile(r"\b(talk to|speak to|speak with|talk with|greet|chat with|ask |say to|tell )\b", re.I), "talk"),
    (re.compile(r"\b(leave|back away|retreat|ignore|turn away|walk away)\b", re.I), "withdraw"),
]

_QUOTED = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_ASK_NAMED = re.compile(
    r"^\s*ask\s+([A-Za-z][A-Za-z'-]{1,28})\s+about\s+(.+)$", re.I,
)

_INTENT_WORDS = {
    "careful": re.compile(r"\b(careful|cautiously|quietly|softly|gently)\b", re.I),
    "urgent": re.compile(r"\b(quick|fast|urgent|now|hurry|rush)\b", re.I),
    "hostile": re.compile(r"\b(angry|furious|cold|harsh|cruel)\b", re.I),
    "friendly": re.compile(r"\b(friendly|warm|kind|polite|smile)\b", re.I),
}


def speech_for_ask_name(action):
    """Canonical name question unless the player used explicit quotes."""
    text = (action or "").strip()
    if not text:
        return "What is your name?"
    m = _QUOTED.search(text)
    if m:
        quoted = (m.group(1) or m.group(2)).strip()
        if quoted:
            return quoted
    return "What is your name?"


_ASK_WH = re.compile(
    r"^\s*ask\s+(?:(?:the|a|an)\s+(?:[\w'-]+\s+)*)*"
    r"(?:[\w'-]+\s+){0,4}?"
    r"(why|what|how|where|when|who|whether|if)\s+(.+)$",
    re.I,
)
_MANGLED_ASK_WH = re.compile(
    r"^\s*(?:the|a|an)\s+(?:[\w'-]+\s+){0,5}?"
    r"(why|what|how|where|when|who|whether|if)\s+(.+)$",
    re.I,
)


def _second_person_question(rest):
    """Rewrite she/he third-person question tail into direct address."""
    q = rest.strip().rstrip("?.!")
    q = re.sub(r"\b(she|he)\s+meant\b", "you meant", q, flags=re.I)
    q = re.sub(r"\b(she|he)\s+(warned|said|told|mentioned)\b", r"you \2", q, flags=re.I)
    q = re.sub(r"\bher\b", "your", q, flags=re.I)
    q = re.sub(r"\bhis\b", "your", q, flags=re.I)
    q = re.sub(r"\bhim\b", "you", q, flags=re.I)
    return q


def _clause_has_unresolved_subject(rest, *, wh=None):
    """True when a wh-clause is not a clean second-person question."""
    text = (rest or "").strip()
    if re.match(r"^(she|he|they)\b", text, re.I):
        return True
    if re.search(r"\b(she|he|they)\s+\w", text, re.I):
        return True
    # Noun-phrase subjects break wh reconstruction ("what the boy found", "when the proctors will...").
    if wh in ("what", "why", "when", "how", "where", None):
        if re.match(r"^(the|a|an|this|that|next|last|each|every)\s+\w", text, re.I):
            if not re.search(r"\byou\b", text, re.I):
                return True
    return False


def _format_wh_question(wh, rest):
    """Build a second-person question from wh-word + rewritten tail."""
    rest = _second_person_question(rest)
    if wh in ("why", "what", "how", "where", "when", "who", "if", "whether"):
        if _clause_has_unresolved_subject(rest, wh=wh):
            return None
    if wh == "why":
        if not re.match(r"^(did|do|were|was|have|has)\b", rest, re.I):
            rest = re.sub(r"^you\s+", "", rest, flags=re.I)
            rest = f"did you {rest}"
        rest = re.sub(r"\byou (\w+)ed\b", lambda m: f"you {m.group(1)}", rest)
        return f"Why {rest.rstrip('?.!')}?"
    if wh == "what":
        if re.match(r"^you meant\b", rest, re.I):
            return f"What {rest.rstrip('?.!')}?"
        if not re.match(r"^(did|do|is|are|was|were|you)\b", rest, re.I):
            rest = f"did you mean {rest}" if "mean" in rest else f"is {rest}"
        return f"What {rest.rstrip('?.!')}?"
    if wh == "how":
        return f"How {rest.rstrip('?.!')}?"
    if wh == "where":
        return f"Where {rest.rstrip('?.!')}?"
    if wh == "when":
        rest = rest.rstrip("?.!")
        if not re.match(r"^(did|do|does|will|are|is|was|were|you)\b", rest, re.I):
            rest = re.sub(r"\bcomes\b", "come", rest, flags=re.I)
            rest = re.sub(r"\bgoes\b", "go", rest, flags=re.I)
            rest = re.sub(r"\barrives\b", "arrive", rest, flags=re.I)
            rest = re.sub(r"\bstarts\b", "start", rest, flags=re.I)
            if not rest.lower().startswith(("does ", "will ", "do ")):
                rest = f"does {rest}"
        return f"When {rest}?"
    if wh == "who":
        return f"Who {rest.rstrip('?.!')}?"
    if wh in ("if", "whether"):
        return f"{'Whether' if wh == 'whether' else 'If'} {rest.rstrip('?.!')}?"
    return None


def speech_for_ask_about(action):
    """Reconstruct a clean spoken question from 'Ask X why/what/how …' commands."""
    text = (action or "").strip()
    if not text:
        return None

    m = _QUOTED.search(text)
    if m:
        return (m.group(1) or m.group(2)).strip()

    m_named = _ASK_NAMED.match(text)
    if m_named:
        topic = m_named.group(2).strip().rstrip("?.!")
        if topic:
            return f"What can you tell me about {topic}?"

    m = _ASK_WH.match(text)
    if m:
        q = _format_wh_question(m.group(1).lower(), m.group(2))
        if q:
            return q

    if not re.match(r"^\s*ask\s+", text, re.I):
        m_mangled = _MANGLED_ASK_WH.match(text)
        if m_mangled:
            q = _format_wh_question(m_mangled.group(1).lower(), m_mangled.group(2))
            if q:
                return q
        prefixed = speech_for_ask_about(f"Ask {text.rstrip('?.!')}")
        if prefixed:
            return prefixed

    return None


def extract_player_speech(action, player=None, *, kind=None):
    """Words the protagonist actually says aloud, if any."""
    text = (action or "").strip()
    if not text:
        return None

    if kind == "ask_name":
        return speech_for_ask_name(action)

    if kind in ("ask_about", "talk") and re.match(r"^\s*ask\s+", text, re.I):
        ask_q = speech_for_ask_about(action)
        if ask_q:
            return ask_q

    if kind in ("ask_about", "talk", "general"):
        ask_q = speech_for_ask_about(action)
        if ask_q:
            return ask_q

    m = _QUOTED.search(text)
    if m:
        return (m.group(1) or m.group(2)).strip()

    m_named = _ASK_NAMED.match(text)
    if m_named:
        topic = m_named.group(2).strip().rstrip("?.!")
        if topic:
            return f"What can you tell me about {topic}?"

    lower = text.lower()
    if lower.startswith("ask ") and "for work" not in lower:
        ask_q = speech_for_ask_about(action)
        if ask_q:
            return ask_q

    m_intro = re.match(r"^\s*(my name is|i'?m called|call me|i am)\s+(.+)$", text, re.I)
    if m_intro:
        return text.strip()

    if player and len(text.split()) == 1:
        word = text.strip()
        true = (player.get("name") or "").strip()
        if true and word.lower() in {true.lower(), true.split()[0].lower()}:
            return f"My name is {true}."

    return None


def _target_hint(action, present_npcs, player, npcs=None, kind="general"):
    from simulation.target_resolution import resolve_action_target
    return resolve_action_target(
        action, player, present_npcs, npcs=npcs, kind=kind,
    )


def interpret_action(action, player, present_npcs, world, npcs=None, scene_state=None):
    kind = "general"
    for pattern, k in _PATTERNS:
        if pattern.search(action):
            kind = k
            break

    intents = []
    for name, pat in _INTENT_WORDS.items():
        if pat.search(action):
            intents.append(name)
    if not intents:
        intents = ["neutral"]

    target = _target_hint(action, present_npcs, player, npcs=npcs, kind=kind)
    target_descriptor = short_descriptor(target) if target else None
    speech = extract_player_speech(action, player, kind=kind)
    if kind == "general" and speech and speech.lower().startswith("my name is"):
        kind = "talk"

    from simulation.local_places import looks_like_local_movement
    if kind == "travel" and looks_like_local_movement(action):
        kind = "approach"

    time_of_day = world.get("time_of_day", "day")
    weather = world.get("weather", "Clear")

    ctx = {
        "kind": kind,
        "intents": intents,
        "target_id": target.get("id") if target else None,
        "target_descriptor": target_descriptor,
        "player_speech": speech,
        "memory_tag": kind if kind != "personal_talk" else "socialise",
        "relationship": None,
        "skill_xp": None,
        "stamina_delta": 0,
        "story_directive": "",
        "action_summary": action.strip()[:200],
    }

    if kind == "explore":
        ctx["stamina_delta"] = -2
        ctx["skill_xp"] = ("navigation", 4)
        ctx["story_directive"] = (
            f"You move through the place at {time_of_day}. "
            f"Literary arrival: one place made specific — texture, sound, one wrong detail. "
            f"Your attention drifts; one private thought. "
            f"No protagonist dialogue. No full conversation — someone may be visible, not yet engaged. "
            f"End before the scene resolves."
        )

    elif kind == "talk":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("charm", 0.6)
        ctx["skill_xp"] = ("persuasion", 6)
        if speech:
            ctx["player_speech"] = speech
            ctx["story_directive"] = (
                f"The protagonist says ONLY: \"{speech}\" "
                f"{'to ' + target_descriptor if target_descriptor else ''}. "
                f"Quote that line once. The other's reply: one to three spoken lines. "
                f"End on their last line — do not invent further protagonist dialogue."
            )
        else:
            ctx["story_directive"] = (
                f"The protagonist approaches"
                f"{' ' + target_descriptor if target_descriptor else ' someone nearby'}. "
                f"One beat of movement, then the other speaks first or waits. "
                f"No invented lines for the protagonist."
            )

    elif kind == "personal_talk":
        ctx["relationship"] = ("charm", 0.5)
        ctx["skill_xp"] = ("empathy", 8)
        ctx["story_directive"] = (
            f"The protagonist asks about someone's history"
            f"{' (' + target_descriptor + ')' if target_descriptor else ''}. "
            f"They answer in fragments — evasive, bitter, or unexpectedly honest — never a full life story. "
            f"One person only. Dialogue may run slightly longer here (3-4 lines total) but stay literary."
        )

    elif kind == "ask_name":
        ctx["relationship"] = ("charm", 0.35)
        ctx["skill_xp"] = ("empathy", 6)
        speech = speech_for_ask_name(action)
        ctx["player_speech"] = speech
        ctx["story_directive"] = (
            f"The protagonist asks: \"{speech}\" "
            f"{'to ' + target_descriptor if target_descriptor else ''}. "
            "SAME SCENE as the previous moment — do NOT re-describe the location, weather, "
            "crime, crates, or the protagonist's appearance. "
            "The focal person answers with their spoken full name in dialogue, then one reaction line. "
            "No new mysteries or crowd scenes."
        )

    elif kind == "attack":
        ctx["memory_tag"] = "attack"
        ctx["relationship"] = ("violence", 1.5)
        ctx["skill_xp"] = ("brawling", 14)
        ctx["stamina_delta"] = -8
        ctx["story_directive"] = "Violence. Physical, costly, ugly. One opponent in focus."

    elif kind == "help":
        ctx["memory_tag"] = "help"
        ctx["relationship"] = ("kindness", 1.0)
        ctx["skill_xp"] = ("empathy", 8)
        ctx["story_directive"] = "An offer of help — wanted or not. Show hands, hesitation, consequence."

    elif kind == "examine":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("appraisal", 5)
        ctx["story_directive"] = "Close looking. What you notice. What you miss. No lecture."

    elif kind == "observe":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("empathy", 4)
        ctx["story_directive"] = "Watching without being seen. Overheard half-phrases, not staged scenes."

    elif kind == "rest":
        ctx["memory_tag"] = "rest"
        ctx["stamina_delta"] = 12
        ctx["story_directive"] = f"Pause. Body and weather. {weather} at {time_of_day}."

    elif kind == "threaten":
        ctx["memory_tag"] = "threat"
        ctx["relationship"] = ("threat", 1.25)
        ctx["skill_xp"] = ("intimidation", 10)
        ctx["story_directive"] = (
            f"The protagonist threatens"
            f"{' ' + target_descriptor if target_descriptor else ' someone'}. "
            f"Show the line, the stillness after, whether fear or defiance answers."
        )

    elif kind == "insult":
        ctx["memory_tag"] = "insult"
        ctx["relationship"] = ("insult", 0.95)
        ctx["skill_xp"] = ("intimidation", 6)
        ctx["story_directive"] = (
            f"A deliberate insult"
            f"{' aimed at ' + target_descriptor if target_descriptor else ''}. "
            f"Words land or miss — consequence in a look, not a lecture."
        )

    elif kind == "steal":
        ctx["memory_tag"] = "theft"
        ctx["relationship"] = ("betrayal", 1.0)
        ctx["skill_xp"] = ("lockpicking", 12)
        ctx["stamina_delta"] = -3
        ctx["story_directive"] = (
            "A theft attempted — hands, pockets, the moment of almost caught. "
            "One person in focus if anyone notices."
        )

    elif kind == "give":
        ctx["memory_tag"] = "gift"
        ctx["relationship"] = ("kindness", 0.9)
        ctx["skill_xp"] = ("persuasion", 5)
        ctx["story_directive"] = (
            f"An offer given"
            f"{' to ' + target_descriptor if target_descriptor else ''} — "
            f"coin, food, or something carried. Show what it costs the giver."
        )

    elif kind == "trade":
        ctx["memory_tag"] = "trade"
        ctx["relationship"] = ("charm", 0.4)
        ctx["skill_xp"] = ("haggling", 8)
        ctx["story_directive"] = (
            f"Bargaining"
            f"{' with ' + target_descriptor if target_descriptor else ''}. "
            f"Goods and coin are real stakes — tension in small numbers and glances."
        )

    elif kind == "withdraw":
        ctx["memory_tag"] = "withdrawal"
        ctx["story_directive"] = (
            "The protagonist disengages — turns away, ends the moment. "
            "Show what is left unsaid in the other person's posture."
        )

    elif kind == "show_respect":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("respect", 1.0)
        ctx["skill_xp"] = ("persuasion", 5)
        ctx["story_directive"] = (
            f"The protagonist shows respect"
            f"{' to ' + target_descriptor if target_descriptor else ''} — "
            f"a bow, lowered eyes, careful words, or offered courtesy. "
            f"The other person should react in line with their personality."
        )

    elif kind == "find":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("charm", 0.35)
        ctx["skill_xp"] = ("persuasion", 4)
        ctx["story_directive"] = (
            "The protagonist looks for a specific person in this place. "
            "If they are present, approach and engage — one focal person only. "
            "If not present, show the search failing — no invented meeting."
        )

    elif kind == "search":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("appraisal", 6)
        ctx["stamina_delta"] = -1
        ctx["story_directive"] = (
            "The protagonist searches for something tangible here — hands, pockets, crates. "
            "Outcome is fixed by simulation; describe only what they actually find."
        )

    elif kind == "confess":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("threat", 0.8)
        ctx["skill_xp"] = ("persuasion", 4)
        speech = extract_player_speech(action, player) or action.strip()[:120]
        ctx["player_speech"] = speech
        ctx["story_directive"] = (
            f'The protagonist confesses aloud: "{speech[:100]}". '
            "Only the designated witness or focal person may answer — not a random stranger. "
            "One to three lines of reply, then stop."
        )

    elif kind == "approach":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("navigation", 3)
        ctx["stamina_delta"] = -1
        ctx["story_directive"] = (
            "Local movement within the same district — a few steps to a door, office, or corner. "
            "Describe arriving at the specific sub-place only. "
            "No district travel, no hours passing, no new city quarters. "
            "Do NOT invent items, documents, or NPC dialogue unless SCENE FACTS provide them."
        )

    elif kind == "travel":
        ctx["skill_xp"] = ("navigation", 8)
        ctx["stamina_delta"] = -5
        ctx["story_directive"] = (
            "The road — hours passing in the body, the world thinning then thickening again. "
            "Arrival, not a travelogue of every mile."
        )

    elif kind == "investigate":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("appraisal", 8)
        ctx["story_directive"] = (
            "Environment-only investigation — physical evidence, overheard fragments, "
            "contradictions in objects and surroundings. "
            "No focal NPC dialogue; clues are found, not told."
        )

    elif kind == "ask_about":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("charm", 0.4)
        ctx["skill_xp"] = ("empathy", 7)
        speech = extract_player_speech(action, player, kind=kind) or speech_for_ask_about(action)
        if speech:
            ctx["player_speech"] = speech[:120]
        ctx["story_directive"] = (
            f"The protagonist asks"
            + (f' aloud: "{speech[:100]}"' if speech else " — intent only, no quoted line")
            + ". Answers may lie, deflect, or trade truth for trust."
        )

    elif kind == "accuse":
        ctx["memory_tag"] = "threat"
        ctx["relationship"] = ("insult", 1.1)
        ctx["skill_xp"] = ("intimidation", 10)
        ctx["story_directive"] = (
            f"A public or private accusation"
            f"{' against ' + target_descriptor if target_descriptor else ''}. "
            f"Denial, rage, or guilty silence — consequences immediate."
        )

    elif kind == "blackmail":
        ctx["memory_tag"] = "threat"
        ctx["relationship"] = ("threat", 1.3)
        ctx["skill_xp"] = ("deception", 12)
        ctx["story_directive"] = (
            f"Leverage a secret for compliance"
            f"{' from ' + target_descriptor if target_descriptor else ''}. "
            f"Ugly power — show what it costs both sides."
        )

    elif kind == "wait":
        ctx["memory_tag"] = "observation"
        ctx["skill_xp"] = ("survival", 4)
        ctx["story_directive"] = (
            "Waiting — time passes; watch who comes and goes. "
            "Patience, boredom, a routine revealed or a meeting missed."
        )

    elif kind == "hunt":
        ctx["memory_tag"] = "hunt"
        ctx["skill_xp"] = ("archery", 10)
        ctx["stamina_delta"] = -4
        ctx["story_directive"] = (
            "Tracking prey — sign, wind, patience. "
            "Do NOT invent a kill; reveal threat or close distance only. "
            "End with the hunter's choice: attack, withdraw, or keep stalking."
        )

    elif kind == "guild":
        ctx["memory_tag"] = "socialise"
        ctx["relationship"] = ("charm", 0.5)
        ctx["skill_xp"] = ("haggling", 8)
        ctx["story_directive"] = (
            f"Guild or lodge business"
            f"{' with ' + target_descriptor if target_descriptor else ''} — "
            "contracts, bounties, rank, or refusal. Dialogue-heavy; end on their offer or demand."
        )

    else:
        ctx["skill_xp"] = ("empathy", 3)
        ctx["story_directive"] = (
            f"The protagonist: {action}. Render as fiction — physical action and consequence, "
            f"not a game log. One person in focus if anyone is involved."
        )

    if "careful" in intents:
        ctx["story_directive"] += " They move carefully."
    if "urgent" in intents:
        ctx["story_directive"] += " Urgency tightens the prose."

    if scene_state is not None:
        from simulation.action_classifier import apply_classifier_to_ctx
        apply_classifier_to_ctx(action, player, present_npcs, npcs, ctx, scene_state)

    return ctx
