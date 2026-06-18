"""
Kind-aware narrator prompt block selection and env profiles.

Profiles (AISTORY_NARRATOR_BLOCKS):
  full     — all tier blocks (debug / bisection baseline)
  standard — default; kind-gated tier blocks
  minimal  — core craft + facts + focal dialogue only
"""

import os

from simulation.scene_coherence import DIALOGUE_KINDS

# Section keys used by assemble_scene_prompt
ALWAYS_BLOCKS = frozenset({
    "craft_core",
    "narrative_thread",
    "prose_structure",
    "craft_kind",
    "length",
    "scene_mode",
    "continuity",
    "narrative_continuity",
    "memory",
    "known_places",
    "place_lock",
    "scene_facts",
    "setting",
    "protagonist",
    "this_beat",
    "npc_context",
    "avoid_repeat",
    "guardrails",
    "hard_constraints",
    "closing",
})

TIER_BLOCKS = frozenset({
    "story_manager",
    "scene_objectives",
    "story_graph",
    "causality",
    "promises",
    "entropy",
    "focal_beliefs",
    "focal_emotion",
    "social_circle",
    "institution_memory",
    "secret_pressure",
    "culture",
    "economy",
    "world_pressure",
    "reputation",
    "local_arc",
    "scene_event",
    "immersion",
    "conversation_ledger",
    "name_rule",
    "extra_directive",
})

SECTION_ORDER = (
    "arbitration",
    "craft_core",
    "narrative_thread",
    "story_manager",
    "scene_objectives",
    "story_graph",
    "prose_structure",
    "craft_kind",
    "length",
    "scene_mode",
    "continuity",
    "narrative_continuity",
    "causality",
    "promises",
    "culture",
    "economy",
    "world_pressure",
    "memory",
    "conversation_ledger",
    "known_places",
    "place_lock",
    "scene_facts",
    "setting",
    "local_arc",
    "scene_event",
    "name_rule",
    "protagonist",
    "this_beat",
    "extra_directive",
    "npc_context",
    "focal_beliefs",
    "focal_emotion",
    "social_circle",
    "institution_memory",
    "secret_pressure",
    "avoid_repeat",
    "reputation",
    "entropy",
    "guardrails",
    "immersion",
    "hard_constraints",
    "closing",
)

# Per-kind omissions under standard profile (tier / optional blocks)
_STANDARD_OMIT = {
    "ask_name": frozenset({
        "story_graph", "entropy", "economy", "culture", "world_pressure",
        "causality", "promises", "scene_objectives", "scene_event", "local_arc",
        "immersion", "institution_memory", "secret_pressure",
    }),
    "withdraw": frozenset({
        "story_graph", "entropy", "economy", "culture", "world_pressure",
        "causality", "promises", "scene_objectives", "scene_event", "local_arc",
        "immersion", "focal_beliefs", "focal_emotion", "social_circle",
        "institution_memory", "secret_pressure", "reputation",
    }),
    "attack": frozenset({
        "culture", "economy", "story_graph", "entropy", "promises",
        "scene_event", "local_arc", "immersion", "scene_objectives",
    }),
    "confess": frozenset({
        "culture", "economy", "story_graph", "entropy", "promises",
        "scene_event", "local_arc", "immersion", "scene_objectives",
    }),
    "search": frozenset({
        "story_graph", "entropy", "culture", "economy", "world_pressure",
        "causality", "promises", "scene_event", "immersion",
    }),
    "observe": frozenset({
        "story_graph", "entropy", "causality", "promises", "scene_objectives",
        "focal_beliefs", "focal_emotion", "social_circle", "institution_memory",
        "secret_pressure", "conversation_ledger",
    }),
    "rest": frozenset({
        "story_graph", "entropy", "causality", "promises", "scene_objectives",
        "focal_beliefs", "focal_emotion", "social_circle", "institution_memory",
        "secret_pressure", "conversation_ledger", "economy",
    }),
    "wait": frozenset({
        "story_graph", "entropy", "causality", "promises", "scene_objectives",
        "culture", "economy", "world_pressure", "immersion", "scene_event",
    }),
    "approach": frozenset({
        "story_graph", "entropy", "causality", "promises", "scene_objectives",
        "culture", "economy", "world_pressure", "immersion", "scene_event",
        "local_arc", "focal_beliefs", "focal_emotion", "social_circle",
        "institution_memory", "secret_pressure", "reputation",
    }),
}

_SOCIAL_KINDS = frozenset({
    "talk", "personal_talk", "ask_about", "show_respect", "insult",
    "threaten", "give", "help", "accuse", "blackmail", "guild",
})

_COMPACT_CRAFT_KINDS = frozenset({
    "talk", "ask_about", "personal_talk", "withdraw", "show_respect",
    "insult", "threaten", "give", "help", "ask_name",
})


def narrator_block_profile():
    raw = (os.environ.get("AISTORY_NARRATOR_BLOCKS") or "standard").strip().lower()
    if raw in ("minimal", "standard", "full"):
        return raw
    return "standard"


def rumor_whisper_limit(kind):
    """How many recent rumors to inject into immersion."""
    if kind in _SOCIAL_KINDS or kind in ("explore", "observe", "personal_talk"):
        return 3
    return 1


def craft_core_for_beat(*, has_journal, kind):
    from simulation.novel_craft import CRAFT_CORE, CRAFT_CORE_COMPACT
    if has_journal and kind in _COMPACT_CRAFT_KINDS:
        return CRAFT_CORE_COMPACT
    return CRAFT_CORE


def should_include_block(name, kind, *, has_focal, has_journal, profile=None, structure_hint=None):
    profile = profile or narrator_block_profile()
    kind = kind or "general"

    if name in ALWAYS_BLOCKS:
        return True

    if profile == "full":
        return bool(name in TIER_BLOCKS or name == "arbitration")

    if profile == "minimal":
        if name in {
            "story_graph", "entropy", "economy", "culture", "world_pressure",
            "causality", "promises", "scene_objectives", "scene_event", "local_arc",
            "immersion", "institution_memory", "secret_pressure",
        }:
            return False
        if name in {"focal_beliefs", "focal_emotion", "social_circle"}:
            return has_focal and kind in DIALOGUE_KINDS
        if name == "story_manager":
            return kind in ("explore", "investigate", "talk", "personal_talk", "accuse")
        if name == "reputation":
            return kind in _SOCIAL_KINDS or kind in ("attack", "confess", "accuse")
        if name == "conversation_ledger":
            return kind in DIALOGUE_KINDS and has_journal
        if name in TIER_BLOCKS:
            return False
        return True

    # standard
    if structure_hint == "continuation" and not has_focal:
        if name in {"story_manager", "causality", "promises"}:
            return False
    omit = _STANDARD_OMIT.get(kind, frozenset())
    if name in omit:
        return False
    if name in {"focal_beliefs", "focal_emotion", "social_circle", "institution_memory", "secret_pressure"}:
        return has_focal
    if name == "conversation_ledger":
        return kind in DIALOGUE_KINDS or (has_journal and kind in _SOCIAL_KINDS)
    if name == "local_arc":
        return kind in ("explore", "travel", "investigate", "observe", "wait")
    if name == "scene_event":
        return kind not in DIALOGUE_KINDS and kind not in ("attack", "confess", "search", "ask_name", "withdraw")
    if name == "immersion":
        return kind in ("explore", "talk", "personal_talk", "observe", "rest", "travel") or kind in _SOCIAL_KINDS
    if name == "story_manager":
        return kind not in ("ask_name", "withdraw", "wait")
    if name in TIER_BLOCKS:
        return True
    return True


def list_included_blocks(kind, *, has_focal, has_journal, profile=None, structure_hint=None):
    """Block keys that would ship for this beat (for boundary trace)."""
    profile = profile or narrator_block_profile()
    included = []
    for key in SECTION_ORDER:
        if key == "arbitration":
            if profile != "minimal":
                included.append(key)
            continue
        if should_include_block(
            key, kind, has_focal=has_focal, has_journal=has_journal, profile=profile,
            structure_hint=structure_hint,
        ):
            included.append(key)
    return included


def join_sections(sections, *, kind, has_focal, has_journal, profile=None, structure_hint=None):
    """Filter and join prompt sections in canonical order."""
    profile = profile or narrator_block_profile()
    parts = []
    for key in SECTION_ORDER:
        if key == "arbitration":
            text = sections.get("arbitration", "")
        elif not should_include_block(
            key, kind, has_focal=has_focal, has_journal=has_journal, profile=profile,
            structure_hint=structure_hint,
        ):
            continue
        else:
            text = sections.get(key, "")
        if text and str(text).strip():
            parts.append(str(text).strip())
    return "\n\n".join(parts)
