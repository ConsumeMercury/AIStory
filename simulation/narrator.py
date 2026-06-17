"""
Novel-style scene generation — one person, one moment, literary prose.
"""

import logging
import os

from generation.descriptor_generator import short_descriptor, appearance_notes, gender_noun, gender_label as npc_gender_label
from simulation.npc_memory_engine import top_memories, memory_behavior, player_memories
from simulation.narrator_variety import (
    build_avoid_repeating, compress_npc_memories, speech_hint,
    scene_mode_rules, scene_length_hint, build_continuity_note,
)
from simulation.scene_coherence import (
    build_conversation_ledger,
    stable_persona_block,
    place_label,
    DIALOGUE_KINDS,
)
from simulation.action_resolution import build_inventory_facts, build_post_combat_facts
from simulation.trait_cues import pick_scene_focus, pick_trait_cues
from simulation.player_identity import player_alias
from simulation.immersion_context import (
    institution_affiliation, npc_active_want,
)
from simulation.novel_craft import (
    CRAFT_CORE, craft_for_kind, narrative_outcome, token_budget_for_kind,
    temperature_for_kind, frequency_penalty_for_kind,
)
from simulation.narrative_continuity import build_narrative_continuity_block
from simulation.beat_structure import build_beat_structure_block, build_narrative_thread_directive
from simulation.local_places import build_known_places_block, build_place_lock
from simulation.generation_guardrails import guardrails_prompt_block, build_hard_constraints_block
from simulation.gemini_client import generate_text, generate_text_stream
from simulation.memory_context import build_memory_context
from simulation.story_manager import build_story_manager_block
from simulation.player_reputation import reputation_narrator_block
from simulation.prompt_profiler import profile_prompt_sections
from simulation.directive_validator import validate_directives
from simulation.story_graph import story_graph_narrator_block
from simulation.scene_objectives import build_scene_objectives_block
from simulation.narrative_causality import causality_narrator_block
from simulation.narrative_promises import unresolved_promises_block
from simulation.story_entropy import entropy_narrator_block
from simulation.belief_model import focal_belief_block
from simulation.beat_structure import classify_beat_structure
from simulation.npc_emotions import focal_emotion_block
from simulation.social_circles import focal_circle_block
from simulation.institution_memory import institution_memory_block
from simulation.secret_activity import secret_narrator_pressure
from simulation.reputation_layers import reputation_layers_block
from simulation.cultural_identity import cultural_reaction_block
from simulation.economy_pressure import economy_narrator_block
from simulation.world_pressure import world_pressure_block
from storage import load

DEBUG_TOKENS = os.environ.get("AISTORY_DEBUG_TOKENS", "").lower() in ("1", "true", "yes")

log = logging.getLogger(__name__)

_BACKGROUND_FOCUS = ("childhood", "formative_event", "current_situation", "belief", "hope", "secret")


from simulation.relationship_thresholds import format_bond_summary
from simulation.npc_schedule import schedule_hint


def _relationship_tone(rel):
    if not rel:
        return "stranger — guarded, no bond yet"
    return format_bond_summary(rel)


def _background_snippet(bg, focus_key):
    val = (bg or {}).get(focus_key)
    if not val:
        return ""
    return f"  (private history — never recite): {val[:120]}"


def _npc_line(npc, known, is_new, rel, tick, name_reveal=None, institutions=None,
              action_kind=None, player=None):
    nid = npc.get("id", "")
    pron = npc.get("pronouns", {})
    g_noun = gender_noun(npc)
    g_label = npc_gender_label(npc)
    revealing = name_reveal and name_reveal.get("npc_id") == nid
    label = (npc.get("name") or short_descriptor(npc)) if (known and not revealing) else short_descriptor(npc)
    role = npc.get("role", "stranger")
    age = npc.get("age", "?")
    persona = npc.get("persona", {})
    bg = npc.get("background", {})
    focus = pick_scene_focus(nid, tick)
    bg_focus = _BACKGROUND_FOCUS[(tick + hash(nid)) % len(_BACKGROUND_FOCUS)]
    cues = pick_trait_cues(npc.get("traits", {}), nid, tick, count=1)
    mem_behaviour = memory_behavior(nid)
    player_mems = player_memories(nid, 2)
    mem_str = compress_npc_memories(player_mems or top_memories(nid, 1), focus)
    affil = institution_affiliation(npc, institutions)
    want_line = npc_active_want(npc) if focus == "want" else ""
    dead_line = ""
    if npc.get("status") == "dead":
        dead_line = (
            "  STATUS: DEAD — describe the body only. They do NOT speak, move, or react.\n"
        )

    if revealing:
        head = f"FOCAL PERSON — must speak name \"{name_reveal['name']}\" in dialogue this scene. Until then: {label}."
    elif known:
        head = f"FOCAL PERSON — {label}, {g_noun}, {role}, about {age}. You know their name."
    elif is_new:
        head = (
            f"FOCAL PERSON — a {g_noun}, {role}, about {age}. "
            f"Describe once: {appearance_notes(npc, 'face')}. No name yet."
        )
    else:
        head = f"FOCAL PERSON — {label}, {g_noun}, {role}. Unnamed to you."

    gender_lock = (
        f"  GENDER LOCK ({g_label}): use ONLY {pron.get('subject')}/{pron.get('object')}/"
        f"{pron.get('possessive')} — never swap gender or pronouns.\n"
    )
    role_lock = ""
    if action_kind in ("attack", "search", "confess"):
        role_lock = (
            f"  ROLE LOCK ({role}): describe them as a {role}; "
            f"never label them guard/sailor/priest/scholar unless role={role}.\n"
        )

    imp = rel.get("_impression_hint") if isinstance(rel, dict) else ""
    imp_line = f"  How they see you: {imp}\n" if imp else ""
    mem_detail = f"  Specific memory to echo: {mem_str}\n" if mem_str and focus == "memory" else ""
    affil_line = f"  {affil}\n" if affil else ""
    want_block = f"  {want_line}\n" if want_line else ""
    sched = schedule_hint(npc, None)
    sched_line = f"  {sched}\n" if sched else ""
    lock = None
    if player and known and not revealing:
        lock = (player.get("known_npcs", {}).get(nid) or {}).get("narration_lock")
    continuity_block = ""
    if lock:
        continuity_block = (
            f"  APPEARANCE LOCK: {lock['appearance']}\n"
            f"  VOICE LOCK: {lock['voice']}\n"
            "  Do NOT redesign face, hair, or speech register.\n"
        )
    if action_kind in DIALOGUE_KINDS:
        if lock:
            voice_block = f"  Voice (fixed): {lock['voice']}\n"
        else:
            voice_block = stable_persona_block(npc)
    else:
        voice_block = f"  Voice: {speech_hint(persona, focus)}\n"

    return (
        f"{head}\n"
        f"{dead_line}"
        f"{gender_lock}"
        f"{role_lock}"
        f"{continuity_block}"
        f"  Pronouns: {pron.get('subject')}/{pron.get('object')}/{pron.get('possessive')}\n"
        f"  Behaviour this beat: {cues[0] if cues else 'reserved'}\n"
        f"{_background_snippet(bg, bg_focus)}\n"
        f"{affil_line}{want_block}{sched_line}{imp_line}{mem_detail}"
        f"  Memory of you: {mem_behaviour}\n"
        f"{voice_block}"
        f"  Bond: {_relationship_tone(rel)}"
    )


def _build_npc_context(focus_npcs, known_ids, new_ids, rels, tick, name_reveal, player, crowd_note, action_kind=None):
    if not focus_npcs:
        return crowd_note + "\n\nNO FOCAL CHARACTER. Do not invent one."
    institutions = load("world/institutions.json", {})
    lines = []
    for npc in focus_npcs[:1]:
        nid = npc.get("id")
        rel = dict(rels.get(nid, {}))
        imp = player.get("known_npcs", {}).get(nid, {}).get("impression")
        if imp:
            rel["_impression_hint"] = imp.get("hint")
        lines.append(_npc_line(
            npc, nid in known_ids, nid in new_ids, rel, tick, name_reveal, institutions,
            action_kind=action_kind, player=player,
        ))
    return lines[0] + "\n\n" + crowd_note


def _novel_action_block(action_context, player_speech):
    if not action_context:
        return "Continue from the protagonist's latest action — as a lived moment, not a summary."
    directive = action_context.get("story_directive", "")
    check = action_context.get("skill_check")
    outcome = narrative_outcome(check)
    speech_line = ""
    if player_speech:
        speech_line = (
            f'The protagonist says ONLY this (quote exactly, once): "{player_speech}"\n'
            "Do not add other lines for them.\n"
        )
    elif action_context.get("player_speech"):
        ps = action_context["player_speech"]
        speech_line = (
            f'The protagonist says ONLY this (quote exactly, once): "{ps}"\n'
            "Do not add other lines for them.\n"
        )
    else:
        speech_line = (
            "The protagonist does NOT speak this beat unless they are only observing or moving.\n"
            "Do not invent dialogue for them.\n"
        )
    parts = [p for p in (speech_line, directive, outcome) if p]
    return "\n".join(parts)


def _novel_player_block(player, locals_know_name, action_kind=None, has_journal=False):
    motivation = player.get("motivation", "")
    mot_line = f" Why they are here: {motivation}." if motivation else ""
    alias = player_alias(player)
    name_note = (
        f"Others may call them {player.get('name')}."
        if locals_know_name else
        f"Others do NOT know the name {player.get('name')}. Use \"you\" or \"{alias}\" only."
    )
    appearance = player.get("appearance", "unremarkable")
    if has_journal and action_kind in (
        "ask_name", "talk", "personal_talk", "threaten", "show_respect", "insult",
        "give", "help", "attack", "confess", "search", "find",
    ):
        look_line = "Do NOT re-describe your appearance this beat."
    else:
        look_line = f"You look like: {appearance}."
    return (
        f"You are {player.get('age', '?')}, a {player.get('background', 'wanderer')}. "
        f"{look_line}{mot_line} {name_note}"
    )


def _join_prompt_sections(*parts):
    return "\n\n".join(p.strip() for p in parts if p and str(p).strip())


def assemble_scene_prompt(player_action, world, player, present_npcs,
                          memories, rumors=None, new_npcs=None,
                          known_ids=None, relationships=None, extra_directive=None,
                          local_arc=None, tick=0, action_context=None,
                          name_reveal=None, locals_know_player_name=False,
                          crowd_note="", scene_event=None,
                          immersion_block="",
                          focal_npc_id=None, scene_place=None, hard_constraints=""):
    """Build the narrator prompt; returns (prompt, token_budget, resolved_focal_id)."""
    known_ids = set(known_ids or [])
    new_ids = {n.get("id") for n in (new_npcs or [])}
    rels = relationships or {}
    journal = player.get("journal") or []
    has_journal = bool(journal)
    kind = (action_context or {}).get("kind", "general")

    setting = (
        f"{world.get('world_name', 'Unknown')}, day {world.get('day', 1)}, "
        f"{world.get('time_of_day', 'day')}, {world.get('season', '')}, {world.get('weather', '')}."
    )

    aid = player.get("area")
    areas = load("world/areas.json", {})
    area = areas.get(aid, {}) if aid else {}
    place = scene_place or place_label(player, area) or player.get("location", "")
    if not scene_place and area.get("atmosphere") and kind in ("explore", "travel", "rest") and not has_journal:
        place += " — " + (area["atmosphere"][0] if area["atmosphere"] else "")

    focal_npc = present_npcs[0] if present_npcs else None
    if focal_npc_id and focal_npc and focal_npc.get("id") != focal_npc_id:
        msg = (
            f"focal_npc_id {focal_npc_id!r} != present_npcs[0] {focal_npc.get('id')!r}"
        )
        if DEBUG_TOKENS or os.environ.get("AISTORY_STRICT", "").lower() in ("1", "true", "yes"):
            raise ValueError(msg)
        log.warning("Focal id mismatch (using cast decision): %s", msg)
        focal_npc_id = focal_npc.get("id")

    npc_block = _build_npc_context(
        present_npcs, known_ids, new_ids, rels, tick, name_reveal, player, crowd_note,
        action_kind=kind,
    )
    ledger_block = build_conversation_ledger(player, journal, focal_npc_id, action_context)
    present_ids = [n.get("id") for n in (present_npcs or []) if n.get("id")]
    npcs_all = load("characters/npcs.json", {})
    memory_block, memory_debug = build_memory_context(
        player,
        npcs_all,
        memories,
        focal_npc_id=focal_npc_id,
        present_ids=present_ids,
    )
    inv_facts = build_inventory_facts(player, action_context or {})
    facts_parts = [p for p in (inv_facts,) if p]
    if action_context:
        presence = action_context.get("presence_facts")
        if presence:
            facts_parts.insert(0, presence)
        if action_context.get("confession_facts") and kind == "confess":
            facts_parts.insert(0, action_context["confession_facts"])
        if kind in ("search", "confess") and player.get("last_combat_target"):
            npcs_all = load("characters/npcs.json", {})
            post = build_post_combat_facts(player, npcs_all)
            if post:
                facts_parts.append(post)
    scene_facts = "\n\n".join(p for p in facts_parts if p)
    action_block = _novel_action_block(action_context, action_context.get("player_speech") if action_context else None)
    player_block = _novel_player_block(player, locals_know_player_name, kind, has_journal)
    avoid_block = build_avoid_repeating(journal, player=player, focal_npc_id=focal_npc_id)
    continuity_block = build_continuity_note(
        journal, kind, player_action, player=player, action_context=action_context,
    )
    narrative_block = build_narrative_continuity_block(
        player, journal, focal_npc_id, npcs_all,
        known_ids=known_ids, area_id=aid, action_kind=kind,
        action_context=action_context,
    )
    thread_block = build_narrative_thread_directive(
        player, npcs_all,
        focal_npc_id=focal_npc_id,
        present_ids=present_ids,
        kind=kind,
        action_context=action_context,
    )
    story_manager_block = build_story_manager_block(
        player, npcs_all,
        focal_npc_id=focal_npc_id,
        kind=kind,
        areas=areas,
    )
    reputation_block = reputation_narrator_block(player)
    focal_npc = npcs_all.get(focal_npc_id) if focal_npc_id else None
    institutions = load("world/institutions.json", {})
    layers_block = reputation_layers_block(
        player, target_npc=focal_npc, institutions=institutions,
    )
    if layers_block:
        reputation_block = (
            (reputation_block + "\n" + layers_block).strip() if reputation_block else layers_block
        )
    emotion_block = focal_emotion_block(focal_npc_id, npcs_all) if focal_npc_id else ""
    circle_block = focal_circle_block(focal_npc_id, npcs_all) if focal_npc_id else ""
    inst_mem_block = institution_memory_block(player, institutions, target_npc=focal_npc)
    secret_block = secret_narrator_pressure(focal_npc) if focal_npc else ""
    culture_block = cultural_reaction_block(player, areas=areas)
    economy_block = economy_narrator_block(player, areas)
    pressure_block = world_pressure_block(player, areas=areas, world=world)
    structure_mode = classify_beat_structure(
        kind, action_context, player, journal, aid, focal_npc_id,
    )
    objectives_block = build_scene_objectives_block(
        player, kind, action_context, structure_mode=structure_mode,
    )
    graph_block = story_graph_narrator_block(player, npcs_all, areas=areas)
    causality_block = causality_narrator_block(player)
    promises_block = unresolved_promises_block(player)
    entropy_block = entropy_narrator_block(player, npcs_all, areas=areas)
    belief_block = focal_belief_block(focal_npc_id, npcs_all) if focal_npc_id else ""
    structure_block = build_beat_structure_block(
        kind, action_context, player, journal, aid, focal_npc_id,
    )
    mode_block = scene_mode_rules(kind, has_journal)
    length_block = scene_length_hint(kind, opening=not has_journal and kind == "explore")

    event_block = ""
    if scene_event and kind not in ("ask_name", "talk", "personal_talk", "withdraw", "attack", "confess"):
        block = (
            f"\nSOMETHING HAPPENS (weave in naturally): {scene_event['text']}\n"
            f"Outcome hint: {scene_event.get('narrative_outcome', '')}"
        )
        if scene_event.get("goal_note"):
            block += f"\nGoal tie-in: {scene_event['goal_note']}"
        event_block = block

    arc = ""
    if local_arc and local_arc.get("current") and kind not in (
        "ask_name", "talk", "withdraw", "show_respect", "insult", "threaten", "give", "help",
        "attack", "confess", "search",
    ):
        title = local_arc.get("title") or local_arc.get("institution", "")
        arc = f"Local story ({title}): {local_arc['current']}."

    name_rule = ""
    if name_reveal:
        name_rule = (
            f"\nIMPORTANT: {name_reveal['descriptor']} must say \"{name_reveal['name']}\" "
            f"in spoken dialogue this scene before narration uses the name."
        )

    immersion = f"\n{immersion_block}\n" if immersion_block else ""
    if not immersion_block:
        extras = []
        if rumors:
            from simulation.immersion_context import format_rumor_whispers
            whisper = format_rumor_whispers(
                rumors[-3:],
                city=player.get("location"),
                area_name=area.get("name"),
            )
            if whisper:
                extras.append(whisper)
        if extras:
            immersion = "\n" + "\n\n".join(extras) + "\n"

    craft_kind = craft_for_kind(kind)
    token_budget = token_budget_for_kind(kind)

    hard_block = hard_constraints or build_hard_constraints_block(
        focal_npc_id, focal_npc, place, action_context,
    )
    known_places_block = build_known_places_block(player, aid)
    place_lock_block = build_place_lock(player, area, action_context)

    section_map = {
        "craft_core": CRAFT_CORE,
        "narrative_thread": thread_block,
        "story_manager": story_manager_block,
        "scene_objectives": objectives_block,
        "story_graph": graph_block,
        "causality": causality_block,
        "promises": promises_block,
        "entropy": entropy_block,
        "focal_beliefs": belief_block,
        "focal_emotion": emotion_block,
        "social_circle": circle_block,
        "institution_memory": inst_mem_block,
        "secret_pressure": secret_block,
        "culture": culture_block,
        "economy": economy_block,
        "world_pressure": pressure_block,
        "prose_structure": structure_block,
        "craft_kind": craft_kind,
        "length": length_block,
        "scene_mode": mode_block,
        "continuity": continuity_block,
        "narrative_continuity": narrative_block,
        "memory": memory_block,
        "conversation_ledger": ledger_block,
        "known_places": known_places_block,
        "place_lock": place_lock_block,
        "scene_facts": scene_facts,
        "setting": f"SCENE:\nSetting: {setting}. Place: {place}.",
        "local_arc": arc,
        "scene_event": event_block,
        "name_rule": name_rule,
        "protagonist": f"PROTAGONIST: {player_block}",
        "this_beat": f"THIS BEAT: {action_block}",
        "extra_directive": f"Note: {extra_directive}" if extra_directive else "",
        "npc_context": npc_block,
        "avoid_repeat": avoid_block,
        "reputation": reputation_block,
        "guardrails": guardrails_prompt_block(),
        "immersion": immersion,
        "hard_constraints": hard_block,
    }
    prompt = _join_prompt_sections(
        CRAFT_CORE,
        thread_block,
        story_manager_block,
        objectives_block,
        graph_block,
        structure_block,
        craft_kind,
        length_block,
        mode_block,
        continuity_block,
        narrative_block,
        causality_block,
        promises_block,
        culture_block,
        economy_block,
        pressure_block,
        memory_block,
        ledger_block,
        known_places_block,
        place_lock_block,
        scene_facts,
        f"SCENE:\nSetting: {setting}. Place: {place}.",
        arc,
        event_block,
        name_rule,
        f"PROTAGONIST: {player_block}",
        f"THIS BEAT: {action_block}",
        f"Note: {extra_directive}" if extra_directive else "",
        npc_block,
        belief_block,
        emotion_block,
        circle_block,
        inst_mem_block,
        secret_block,
        avoid_block,
        reputation_block,
        entropy_block,
        guardrails_prompt_block(),
        immersion,
        hard_block,
        "Write the scene now. Literary novel prose only — obey HARD CONSTRAINTS, "
        "NARRATIVE THREAD, PROSE STRUCTURE, SCENE MODE, and DO NOT REPEAT.",
    )
    if DEBUG_TOKENS:
        profile_prompt_sections(section_map, label="assemble_scene_prompt")
    validate_directives(prompt)
    return prompt, token_budget, focal_npc_id, memory_debug


def generate_scene(player_action, world, player, present_npcs,
                   memories, rumors=None, new_npcs=None,
                   known_ids=None, relationships=None, extra_directive=None,
                   local_arc=None, tick=0, action_context=None,
                   name_reveal=None, locals_know_player_name=False,
                   crowd_note="", scene_event=None,
                   immersion_block="",
                   focal_npc_id=None, scene_place=None, hard_constraints="",
                   on_prose_chunk=None):
    prompt, token_budget, _focal_id, _memory_debug = assemble_scene_prompt(
        player_action, world, player, present_npcs,
        memories, rumors=rumors, new_npcs=new_npcs,
        known_ids=known_ids, relationships=relationships, extra_directive=extra_directive,
        local_arc=local_arc, tick=tick, action_context=action_context,
        name_reveal=name_reveal, locals_know_player_name=locals_know_player_name,
        crowd_note=crowd_note, scene_event=scene_event,
        immersion_block=immersion_block,
        focal_npc_id=focal_npc_id, scene_place=scene_place, hard_constraints=hard_constraints,
    )

    if DEBUG_TOKENS:
        print("\n===== TOKEN DEBUG =====")
        print("Prompt chars:", len(prompt))
        print("Model:", os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"))
        print("======================\n")

    kind = (action_context or {}).get("kind", "general")
    gen_temp = temperature_for_kind(kind)
    gen_penalty = frequency_penalty_for_kind(kind)
    from simulation.gemini_client import effective_sampling_params, model_name

    effective = effective_sampling_params(
        model_name(),
        temperature=gen_temp,
        top_p=0.9,
        frequency_penalty=gen_penalty,
    )
    gen_kwargs = dict(
        max_tokens=token_budget,
        temperature=gen_temp,
        top_p=0.9,
        frequency_penalty=gen_penalty,
    )
    if action_context is not None:
        action_context["memory_debug"] = _memory_debug
        action_context["generation_settings"] = {
            "kind": kind,
            "temperature": effective["temperature"],
            "top_p": effective["top_p"],
            "frequency_penalty": effective["frequency_penalty"],
            "frequency_penalty_requested": gen_penalty if gen_penalty > 0 else None,
            "model_family": effective["model_family"],
        }
    if on_prose_chunk:
        return generate_text_stream(prompt, on_chunk=on_prose_chunk, **gen_kwargs)
    return generate_text(prompt, **gen_kwargs)
