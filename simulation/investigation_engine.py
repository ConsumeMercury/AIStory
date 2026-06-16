"""
Investigation — ask about crimes, follow rumors, accuse, blackmail using secrets.
"""

import random
import re

from storage import load
from generation.npc_secrets import hidden_secrets, reveal_one_secret, expose_secret
from simulation.memory_retrieval import get_relevant_memories

EVENT_FILE = "events/event_log.json"
RUMOR_FILE = "rumors/rumors.json"


def validate_accuse(action, player, target, npcs):
    """
    Refuse accusations with no active case before simulation advances mystery state.
    Returns (ok, refusal_directive).
    """
    case = player.get("active_case")
    if not case or case.get("solved"):
        return False, (
            "ACCUSE REFUSED — there is no active investigation to accuse anyone of. "
            "Do NOT treat this as a solved crime or confirmed guilt. "
            "One short beat: confusion, dismissal, or deflection — then stop."
        )

    victim_name = (case.get("victim_name") or "").lower()
    if victim_name and action:
        text = action.lower()
        if re.search(r"\b(kill|killed|murder|murdered|slay|slain)\b", text):
            if victim_name not in text and not any(
                victim_name.split()[0] in w for w in text.split() if len(w) > 3
            ):
                return False, (
                    f"ACCUSE REFUSED — no case links anyone here to that death. "
                    f"The active case concerns {case.get('victim_name', 'another victim')}. "
                    f"Do NOT invent a verdict. The focal NPC may react to a baseless charge."
                )

    if not target:
        return False, (
            "ACCUSE REFUSED — no one present to accuse. "
            "Do NOT invent a confrontation."
        )

    return True, ""


def _match_rumor(action, rumors):
    text = action.lower()
    for r in reversed(rumors or []):
        rt = (r.get("text") or "").lower()
        words = [w for w in rt.split() if len(w) > 4]
        if any(w in text for w in words[:6]):
            return r
    if rumors:
        return rumors[-1]
    return None


def build_investigation_context(action, player, present, world, action_ctx):
    """
    Returns (story_directive, extra_facts, secret_reveal dict or None)
    """
    kind = action_ctx.get("kind", "")
    check = action_ctx.get("skill_check") or {}
    success = check.get("success", True)
    margin = check.get("margin", 0)
    target = None
    tid = action_ctx.get("target_id")
    if tid:
        target = next((n for n in present if n.get("id") == tid), None)

    events = load(EVENT_FILE, [])
    rumors = load(RUMOR_FILE, [])

    if kind == "investigate":
        relevant = get_relevant_memories(events, action, limit=5)
        facts = [f"{e.get('action', e.get('type', ''))} at {e.get('location', '?')}" for e in relevant[:3]]
        base = "The protagonist investigates — compare details, notice contradictions."
        if facts:
            base += " Known facts: " + "; ".join(facts) + "."
        if target and success:
            sec = reveal_one_secret(target, partial=margin < 3)
            if sec:
                if sec.get("full"):
                    return base + f" They uncover: {sec['full']}.", sec, sec
                return base + f" Partial lead: {sec.get('hint', '')}.", sec, None
        return base, {}, None

    if kind == "ask_about":
        topic = action_ctx.get("player_speech") or action
        if target:
            mems = target.get("secrets") or []
            if success and hidden_secrets(target):
                sec = reveal_one_secret(target, partial=not check.get("critical_success"))
                if sec and sec.get("full"):
                    return (
                        f"They press {target.get('name', 'them')} about: {topic}. "
                        f"Something slips: {sec['full']}.",
                        sec, sec,
                    )
            return (
                f"They ask about '{topic[:80]}'. "
                f"{'Evasion and half-truths.' if not success else 'Useful fragments, not the whole story.'}",
                {}, None,
            )
        rumor = _match_rumor(action, rumors)
        if rumor:
            return (
                f"They follow gossip: \"{rumor.get('text', '')[:90]}\". "
                f"{'Leads somewhere real.' if success else 'Dead end or misdirection.'}",
                {"rumor": rumor.get("text")}, None,
            )
        return "They ask around — few want to talk.", {}, None

    if kind == "accuse":
        if action_ctx.get("accuse_refused"):
            return action_ctx.get("story_directive", ""), {}, None
        if not target:
            return "Accusation with no one to accuse — awkward silence.", {}, None
        if success:
            hidden = hidden_secrets(target)
            if hidden and random.random() < 0.5 + margin * 0.05:
                sec = hidden[0]
                expose_secret(target, sec["id"], to_player=True)
                return (
                    f"They accuse {target.get('name', 'them')} — and hit truth: {sec['text']}. "
                    f"Scene explodes with denial or confession.",
                    sec, sec,
                )
            return (
                f"They accuse wrongly or without proof — backlash, resentment, witnesses.",
                {}, None,
            )
        return "The accusation lands flat — no one believes them.", {}, None

    if kind == "blackmail":
        if not target:
            return "No target for leverage.", {}, None
        hidden = hidden_secrets(target)
        if not hidden:
            return "They have nothing to leverage.", {}, None
        sec = hidden[0]
        if success:
            sec["blackmail_used"] = True
            sec["exposed_to_player"] = True
            return (
                f"Blackmail: they know {target.get('name', 'they')} {sec['text']}. "
                f"Demand compliance — show the ugliness of power.",
                sec, sec,
            )
        return "Blackmail attempt fails — target calls their bluff or turns violent.", {}, None

    return "", {}, None
