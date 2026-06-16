"""
Helpers to keep narration fresh: rotate what we tell the model each scene and
explicitly forbid recycling recent prose beats.
"""

import re

_APPEARANCE_WORDS = re.compile(
    r"\b(glasses|hair|robe|cloak|scholar|bookworm|round|black hair|fogging|eighteen|18)\b",
    re.I,
)
_PLOT_REPEAT = re.compile(
    r"\b(crate|manifest|ledger|tea|birthmark|dock|harbor|fog|snow|theft|pattern|cleric|priest)\b",
    re.I,
)


def _sentences(text, max_n=3):
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()][:max_n]


def build_avoid_repeating(journal, limit=3):
    """Extract recent scene fingerprints so the model knows what NOT to reuse."""
    entries = (journal or [])[-limit:]
    if not entries:
        return ""

    lines = []
    banned_motifs = set()

    for entry in entries:
        excerpt = (entry.get("excerpt") or "").strip()
        if not excerpt:
            continue
        for sent in _sentences(excerpt, 2):
            lines.append(sent[:180])
        for word in _APPEARANCE_WORDS.findall(excerpt):
            banned_motifs.add(word.lower())
        for word in _PLOT_REPEAT.findall(excerpt):
            banned_motifs.add(word.lower())
        action = entry.get("action", "")
        if action:
            lines.append(f"(player already did: {action[:80]})")

    motif_line = ""
    if banned_motifs:
        motif_line = (
            "\nBANNED MOTIFS this session (do not mention again unless the player asks): "
            + ", ".join(sorted(banned_motifs)[:20])
        )

    body = "\n".join(f"- {s}" for s in lines[-8:])
    return (
        "DO NOT REPEAT from recent scenes — no second opening, no re-explaining the same mystery:\n"
        f"{body}"
        f"{motif_line}\n"
        "Start this beat from the NEXT moment. No weather opener. No re-introducing yourself visually."
    )


def build_continuity_note(journal, action_kind, player_action, player=None, action_context=None):
    """Tell the model what just happened — outcome only, not prose to copy."""
    if not journal:
        return ""

    last = journal[-1]
    last_kind = last.get("kind", "")
    last_action = (last.get("action") or "")[:100]
    focus_id = (action_context or {}).get("target_id") or (player or {}).get("scene_focus")
    last_focus = last.get("focus_npc")
    same_thread = (
        focus_id and last_focus and focus_id == last_focus
        and last.get("area") == (player or {}).get("area")
    )

    name_lock = ""
    if player and focus_id:
        known = player.get("known_npcs", {}).get(focus_id, {})
        if known.get("name_known"):
            from storage import load
            npc = load("characters/npcs.json", {}).get(focus_id, {})
            nm = npc.get("name", "")
            if nm:
                name_lock = (
                    f" Name {nm} is ALREADY known — do NOT re-introduce them or repeat their name "
                    "unless the player explicitly asks again."
                )

    if action_context and action_context.get("absent_npc"):
        absent = action_context["absent_npc"]
        label = absent.get("name") or absent.get("descriptor") or "They"
        return (
            f"CONTINUITY: {label} is absent from this location. "
            f"Player tried: {player_action[:80]}. "
            "Show empty result — no invented dialogue from the absent person."
        )

    if action_kind == "ask_name":
        return (
            "CONTINUITY: Same place, same people, immediately after the last exchange. "
            f"The player now asks for a name (not a new investigation). "
            f"Previous action was: {last_action}. "
            "Do NOT re-narrate the dock, theft, weather, or the protagonist's looks."
            + name_lock
        )

    if action_kind in ("talk", "personal_talk", "show_respect", "threaten", "insult", "give", "help", "guild"):
        thread = (
            "Same conversation thread — pick up mid-exchange, no scene reset."
            if same_thread else
            "Conversation continues with the same focal person."
        )
        return (
            f"CONTINUITY: {thread} "
            f"Previous beat ({last_kind}): {last_action}. "
            "Do not reset the scene or repeat establishing description."
            + name_lock
        )

    if last_kind == action_kind == "explore":
        return (
            "CONTINUITY: Still exploring the same area. "
            "Show something NEW — do not repeat the last paragraph's images."
        )

    return (
        f"CONTINUITY: Follows '{last_action}'. "
        "Advance time by seconds or minutes, not a fresh chapter opening."
    )


def scene_length_hint(action_kind, opening=False):
    """Paragraph count — favor dialogue and player turns over set pieces."""
    if opening:
        return "LENGTH: 3–4 paragraphs. Arrival only — no conversation yet, no protagonist dialogue."
    if action_kind in ("ask_name", "withdraw"):
        return "LENGTH: 1–2 paragraphs. Dialogue-forward; cut all filler."
    if action_kind in ("talk", "show_respect", "insult", "threaten", "give", "help"):
        return "LENGTH: 2–3 paragraphs. Most words in quotation marks. End on their last line."
    if action_kind == "personal_talk":
        return "LENGTH: 3–5 paragraphs. Fragments and pauses — still not a speech."
    if action_kind in ("explore", "travel", "rest"):
        return "LENGTH: 3–4 paragraphs. One detail per paragraph; stop before the scene resolves."
    if action_kind == "attack":
        return "LENGTH: 2–4 paragraphs. Aftermath weighs more than the swing."
    if action_kind in ("confess", "search"):
        return "LENGTH: 1–3 paragraphs. Dialogue-forward where applicable."
    return "LENGTH: 2–4 paragraphs."


def scene_mode_rules(action_kind, has_journal):
    """Hard rules per beat type."""
    if action_kind == "ask_name":
        return (
            "SCENE MODE — NAME REQUEST:\n"
            "- The focal person MUST speak their full name in quoted dialogue.\n"
            "- One or two paragraphs: question, answer, beat of silence.\n"
            "- No new plot, no recap of the previous scene's mystery.\n"
            "- Do not re-describe your face, clothes, or the weather.\n"
            "- Do NOT invent anything the protagonist says beyond the given line."
        )
    if action_kind in ("talk", "show_respect", "insult", "threaten", "give", "help", "confess"):
        return (
            "SCENE MODE — SOCIAL BEAT:\n"
            "- Conversation, not narration about conversation.\n"
            "- Quote the protagonist's line if given; then the other's reply (1–3 lines max).\n"
            "- End on the other person speaking or waiting — leave the floor open.\n"
            "- Do NOT invent protagonist dialogue or actions beyond what was typed.\n"
            "- ONLY the focal person from SCENE FACTS may speak — no role/gender swap."
        )
    if action_kind == "attack":
        return (
            "SCENE MODE — COMBAT AFTERMATH:\n"
            "- Obey SCENE FACTS for who was hit and whether they died.\n"
            "- Same opponent identity as prior beats if same person.\n"
            "- Dead focal NPC: body only — no dialogue from them.\n"
            "- Do NOT introduce priest, scholar, blacksmith, or other new speakers."
        )
    if action_kind == "search":
        return (
            "SCENE MODE — SEARCH:\n"
            "- Describe finding ONLY items listed in SCENE FACTS.\n"
            "- No invented loot. Protagonist does not speak unless given words."
        )
    if action_kind == "explore" and has_journal:
        return (
            "SCENE MODE — EXPLORE:\n"
            "- New detail or angle only. The place is established; deepen it, don't repeat it.\n"
            "- Protagonist does not speak unless given exact words."
        )
    if action_kind == "explore" and not has_journal:
        return (
            "SCENE MODE — FIRST ARRIVAL:\n"
            "- You have just arrived. Place, mood, one wrong detail.\n"
            "- No protagonist dialogue. No full conversation — at most someone visible in the distance.\n"
            "- End with the place still open, not a solved scene."
        )
    return ""


def compress_npc_memories(mems, focus, max_items=1):
    """Return memory text sized to the scene focus — not always three bullets."""
    if not mems:
        return ""
    if focus == "memory":
        return "; ".join(m["summary"] for m in mems[:2])
    return mems[0]["summary"]


def speech_hint(persona, focus):
    """Rotate speech guidance — style OR quirk, not both every time."""
    style = persona.get("speech_style", "plain")
    quirk = persona.get("voice_quirk", "")
    if focus == "speech":
        return f"Voice this scene: {style}. Quirk: {quirk}."
    if focus == "mannerism":
        return f"Speech register: {style}."
    return f"Speak {style.split(',')[0].strip()} — do not announce it."
