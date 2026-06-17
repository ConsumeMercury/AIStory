"""
Turns a typed player action into a narrated scene with mechanical and memory effects.
"""

import random
import re

from generation.descriptor_generator import short_descriptor
from storage import load, save
from simulation.narrator_protocol import get_narrator
from simulation.event_logger import log_event, all_events
from simulation.progression_engine import add_skill_xp
from simulation.relationship_engine import (
    apply_impression_nudge, apply_player_action_relationship,
)
from simulation.combat_engine import resolve_combat
from simulation.storyline_engine import arc_for_city, arc_for_area
from simulation.memory_retrieval import get_relevant_memories
from simulation.action_interpreter import interpret_action
from simulation.scene_coherence import (
    sync_scene_focus,
    resolve_target_and_absence,
    resolve_travel_destination,
    place_label,
    DIALOGUE_KINDS,
)
from simulation.local_places import resolve_local_movement, record_narrator_places
from simulation.generation_guardrails import build_hard_constraints_block, build_misname_directive
from simulation.prose_validator import (
    log_scene_prose_issues,
    validate_scene_prose,
    build_prose_correction_block,
    queue_prose_correction,
    prose_retry_limit,
)
from simulation.npc_continuity import ensure_npc_continuity_locks
from simulation.journal_summary import maybe_compact_journal
from simulation.narrative_continuity import update_npc_narrative_cache
from simulation.npc_memory_engine import record_player_action
from simulation.skill_check import run_action_check, apply_check_costs
from simulation.player_identity import (
    detect_self_introduction, mark_name_revealed_to_present, locals_know_name,
)
from simulation.appearance_impression import record_first_impression
from simulation.scene_cast import select_scene_cast, pick_name_target
from simulation.scene_events import maybe_scene_event
from simulation.immersion_context import (
    format_rumor_whispers, build_player_inner_voice,
)
from simulation.economy_engine import resolve_trade, resolve_give, validate_trade, validate_give
from simulation.travel_digest import snapshot_before_travel, build_arrival_digest
from simulation.area_discovery import record_area_arrival, area_intro_directive
from simulation.player_goals import update_player_goals, active_goal_hint
from simulation.player_commands import try_meta_command
from simulation.npc_schedule import apply_schedules_to_npcs, next_appearance, schedule_hint
from simulation.investigation_engine import build_investigation_context, validate_accuse
from simulation.faction_reputation import apply_action_standing, ensure_faction_standing, check_faction_invitations
from simulation.institution_membership import (
    apply_institution_standing, check_institution_invitations, apply_guild_work_standing,
)
from simulation.hunting_engine import process_hunt_action
from simulation.consequence_queue import register_from_action, pop_delayed_directive
from simulation.npc_drama import format_drama_block
from simulation.rival_engine import bump_notoriety, maybe_spawn_rival, rival_directive
from simulation.player_legacy import legacy_from_action, legacy_narrator_block
from simulation.investigation_cases import ensure_case, advance_case, case_narrator_block, sanitize_active_case
from simulation.storyline_behavior import narrator_storyline_block
from game.starting_placement import starting_pipeline_narrator_block
from game.state_context import state_lock
from game.undo import push_undo_snapshot
from simulation.district_state import district_narrator_block
from simulation.institution_politics import politics_narrator_block
from generation.world_history import history_block
from generation.location_generator import city_check_modifier
from simulation.world_clock import advance_for_action, advance_clock, resolve_wait_advance
from simulation.scheduled_events import (
    record_scheduled_events,
    fire_due_events,
    event_fired_directive,
    build_scheduled_events_block,
    strip_schedule_tags,
)
from simulation import simulation_runner
from simulation.action_resolution import (
    resolve_combat_target,
    pick_explore_hook,
    try_acquire_item,
    validate_acquire_item,
    resolve_find_person,
    build_scene_presence_facts,
    build_find_facts,
    build_find_failed_facts,
    resolve_npc_by_name_query,
    extract_find_name_query,
    resolve_confession_respondent,
    build_combat_facts,
    build_inventory_facts,
    build_confession_facts,
    build_post_combat_facts,
    resolve_pronoun_target,
)
from simulation.target_ambiguity import (
    detect_target_ambiguity,
    resolve_clarification_pick,
    set_pending_clarification,
    clear_pending_clarification,
    build_clarification_scene,
)

WORLD_FILE = "world/world_state.json"
NPC_FILE = "characters/npcs.json"
MON_FILE = "characters/monsters.json"
PLAYER_FILE = "player/player.json"
RUMOR_FILE = "rumors/rumors.json"
LOC_FILE = "world/locations.json"
AREAS_FILE = "world/areas.json"


def _present_npcs(npcs, player):
    loc = player.get("location")
    area = player.get("area")
    here = []
    for n in npcs.values():
        if n.get("status") != "alive":
            continue
        ts = n.get("travel_state") or {}
        if ts.get("hours_remaining", 0) > 0:
            continue
        if (area and n.get("area") == area) or n.get("location") == loc:
            here.append(n)
    return here


def _update_known(player, present, tick):
    known = player.setdefault("known_npcs", {})
    newcomers = []
    for n in present:
        nid = n["id"]
        rec = known.get(nid)
        if rec is None:
            known[nid] = {
                "name_known": False, "seen_before": False,
                "first_seen_tick": tick, "times_seen": 1,
            }
            newcomers.append(n)
            player.setdefault("met_npcs", [])
            if nid not in player["met_npcs"]:
                player["met_npcs"].append(nid)
            imp = record_first_impression(player, n)
            apply_impression_nudge(n["id"], "player", imp)
        else:
            rec["times_seen"] = rec.get("times_seen", 0) + 1
    to_introduce = newcomers[:1]
    for n in present:
        known[n["id"]]["seen_before"] = True
    return to_introduce


def _apply_action_mechanics(player, action_ctx, kind, check=None):
    stats = player.setdefault("stats", {})
    delta = action_ctx.get("stamina_delta", 0)
    if delta:
        stats["stamina"] = max(0, min(
            stats.get("max_stamina", 30),
            stats.get("stamina", 0) + delta,
        ))
    tid = action_ctx.get("target_id")
    if tid and kind != "attack":
        apply_player_action_relationship(kind, tid, action_ctx, check=check)
    xp = action_ctx.get("skill_xp")
    if xp:
        add_skill_xp(player, xp[0], xp[1])


def _area_context(player):
    areas = load(AREAS_FILE, {})
    area = areas.get(player.get("area"), {})
    if area:
        return area
    locs = load(LOC_FILE, {})
    mod = city_check_modifier(player.get("location"), locs)
    return {"check_modifier": mod}


def _generate_scene_with_validation(
    *,
    action,
    world,
    player,
    focus_npcs,
    events,
    rumors,
    intro_for_scene,
    known_ids,
    rels_toward_player,
    extra_directive,
    area_arc,
    tick,
    action_ctx,
    name_reveal,
    focus_id_list,
    crowd_note,
    scene_event,
    immersion_block,
    focal_id,
    scene_place,
    hard_constraints,
    on_prose_chunk,
    npcs,
):
    """Generate scene prose; retry once when post-validation finds fact violations."""
    kwargs = dict(
        player_action=action,
        world=world,
        player=player,
        present_npcs=focus_npcs,
        memories=get_relevant_memories(
            events, action, limit=15,
            player=player, area=player.get("area"),
            focal_npc_id=focal_id,
        ),
        rumors=rumors[-5:] if rumors else [],
        new_npcs=intro_for_scene,
        known_ids=known_ids,
        relationships=rels_toward_player,
        extra_directive=extra_directive,
        local_arc=area_arc,
        tick=tick,
        action_context=action_ctx,
        name_reveal=name_reveal,
        locals_know_player_name=locals_know_name(player, focus_id_list),
        crowd_note=crowd_note,
        scene_event=scene_event,
        immersion_block=immersion_block,
        focal_npc_id=focal_id,
        scene_place=scene_place,
        hard_constraints=hard_constraints,
        on_prose_chunk=on_prose_chunk,
    )

    scene = get_narrator().generate_scene(**kwargs)
    if not scene or len(scene) < 40:
        return scene, []

    issues = validate_scene_prose(
        scene,
        player=player,
        npcs=npcs,
        action_ctx=action_ctx,
        focal_npc_id=focal_id,
        scene_place=scene_place,
        present_npcs=focus_npcs,
        known_ids=known_ids,
    )
    retries = prose_retry_limit()
    attempt = 0
    while issues and attempt < retries:
        attempt += 1
        correction = build_prose_correction_block(issues)
        merged = ((extra_directive or "") + "\n\n" + correction).strip()
        action_ctx["prose_retry"] = attempt
        scene = get_narrator().generate_scene(
            **{**kwargs, "extra_directive": merged, "on_prose_chunk": None},
        )
        issues = validate_scene_prose(
            scene,
            player=player,
            npcs=npcs,
            action_ctx=action_ctx,
            focal_npc_id=focal_id,
            scene_place=scene_place,
            present_npcs=focus_npcs,
            known_ids=known_ids,
        )

    if issues:
        log_scene_prose_issues(
            scene,
            player=player,
            npcs=npcs,
            action_ctx=action_ctx,
            focal_npc_id=focal_id,
            scene_place=scene_place,
            present_npcs=focus_npcs,
            known_ids=known_ids,
        )
        with state_lock():
            pl = load(PLAYER_FILE, {})
            queue_prose_correction(pl, issues)
            save(PLAYER_FILE, pl)
    return scene, issues


def _do_combat(player, npcs, monsters, present, tick, action, action_ctx):
    from simulation.hunting_engine import resolve_monster_loot, record_kill

    target, target_kind = resolve_combat_target(
        action, player, present, npcs, monsters,
        player.get("area"), player.get("location"),
    )

    if target is None:
        return None, None, "There is no one here to fight.", None, None

    action_lower = (action or "").lower()
    repeat_finisher = (
        target_kind == "npc"
        and target.get("id") == player.get("last_combat_target")
        and not player.get("last_combat_fatal")
        and target.get("status") == "alive"
        and (player.get("equipment") or {}).get("weapon")
        and re.search(r"\b(anyway|again|still|finish|kill)\b", action_lower)
    )

    if repeat_finisher:
        target["stats"]["health"] = 0
        target["status"] = "dead"
        stats = player.setdefault("stats", {})
        stats["stamina"] = max(0, stats.get("stamina", 0) - 6)
        result = {
            "rounds": 1,
            "log": [],
            "winner": "player",
            "loser": target.get("id"),
            "a_health": stats.get("health"),
            "b_health": 0,
            "fatal": True,
            "consequences": ["fatal blow with drawn weapon"],
            "player_injuries": list(player.get("injuries") or []),
        }
    else:
        max_rounds = 8 if (player.get("equipment") or {}).get("weapon") else 6
        result = resolve_combat(player, target, max_rounds=max_rounds)

    witness_ids = [
        n["id"] for n in present
        if target_kind == "npc" and n["id"] != target.get("id")
    ]
    player["combat_witnesses"] = witness_ids[-6:]
    player["last_combat_target"] = target.get("id")
    player["last_combat_fatal"] = bool(result.get("fatal"))

    cons = "; ".join(result.get("consequences") or [])
    if target_kind == "npc":
        from simulation.relationship_engine import apply_npc_toward_player
        apply_npc_toward_player(target["id"], "violence", 1.5)
        npcs[target["id"]] = target
    else:
        monsters[target["id"]] = target
        if result["fatal"]:
            world = load(WORLD_FILE, {})
            loot_note = resolve_monster_loot(player, target, tick=tick)
            bounty_notes = record_kill(player, target, tick=tick, world=world)
            extra = " ".join([loot_note] + bounty_notes)
            cons = (cons + " " + extra).strip() if cons else extra

    save(PLAYER_FILE, player)
    save(NPC_FILE, npcs)
    save(MON_FILE, monsters)

    combat_snap = dict(target) if target_kind == "npc" else None
    action_ctx["combat_snapshot"] = combat_snap
    action_ctx["combat_fatal"] = result.get("fatal")
    action_ctx["combat_target_kind"] = target_kind

    injuries = ", ".join(result.get("player_injuries") or []) or "none new"
    facts = build_combat_facts(target, result, target_kind, npcs)
    directive = (
        f"{facts}\n"
        f"Combat over {result['rounds']} exchanges. "
        f"Player health {player['stats']['health']}/{player['stats']['max_health']}, "
        f"stamina {player['stats'].get('stamina', '?')}. "
        f"Target health {target['stats']['health']}. "
        + ("Fatal." if result["fatal"] else "Fight ended — both may still be standing; do NOT invent a kill.")
        + f" Consequences: {cons}. Player injuries: {injuries}. "
        "Narrate pain, exhaustion, and aftermath — not a blow-by-blow list. "
        "ONLY the opponent named in SCENE FACTS was in this fight."
    )
    log_event("combat", "player", "attack", target=target.get("id"),
              location=player.get("location"),
              effects=["fatal"] if result["fatal"] else [], tick=tick)
    return directive, target.get("id"), None, combat_snap, result


def _skip_ambient_event(kind, player, journal):
    """Dialogue follow-ups in the same place don't need a new random event."""
    if kind == "ask_name":
        return True
    dialogue = {"talk", "personal_talk", "show_respect", "threaten", "insult", "give", "help", "withdraw"}
    if kind in dialogue and journal:
        last = journal[-1]
        if last.get("area") == player.get("area"):
            return True
    return False


def _immersion_block(kind, player, world, action_ctx, rumors, events, action, *, present_ids=None):
    """Lighter context on dialogue beats; minimal on first arrival."""
    journal = player.get("journal") or []
    if action_ctx.get("absent_npc"):
        return build_player_inner_voice(player, world, action_ctx, journal)
    if kind in ("attack", "confess", "search"):
        inner = build_player_inner_voice(player, world, action_ctx, journal)
        return inner or ""
    if kind in DIALOGUE_KINDS and journal:
        return build_player_inner_voice(player, world, action_ctx, journal)

    if not journal and kind == "explore":
        areas = load(AREAS_FILE, {})
        area = areas.get(player.get("area"), {})
        sl = (area.get("storyline") or {}).get("hook") or (area.get("storyline") or {}).get("title")
        if sl:
            return f"Local tension (background only — do not dump): {sl[:120]}"
        return ""

    areas = load(AREAS_FILE, {})
    area = areas.get(player.get("area"), {})
    from simulation.goal_events import goal_narrator_note
    from simulation.hunting_engine import hunt_narrator_block, guild_contract_block
    from simulation.institution_membership import institution_narrator_block
    monsters = load(MON_FILE, {})
    parts = [
        goal_narrator_note(player),
        hunt_narrator_block(player, monsters, areas) if kind in ("explore", "hunt", "observe") else "",
        institution_narrator_block(player, player.get("area"), load("world/institutions.json", {})),
        guild_contract_block(player) if kind in ("guild", "trade", "talk") else "",
        format_rumor_whispers(rumors, city=player.get("location"), area_name=area.get("name")),
        build_player_inner_voice(player, world, action_ctx, journal),
        format_drama_block(player.get("area"), load(NPC_FILE, {})),
        history_block(world),
        narrator_storyline_block(player.get("area"), areas),
        starting_pipeline_narrator_block(player),
        district_narrator_block(player.get("area"), areas),
        politics_narrator_block(player.get("area"), load("world/institutions.json", {}), load(NPC_FILE, {})),
        case_narrator_block(player, load(NPC_FILE, {}), present_ids=present_ids or []),
        legacy_narrator_block(player),
    ]
    return "\n\n".join(p for p in parts if p)


def process_player_action(action, *, on_prose_chunk=None):
    from simulation.turn_trace import record_turn

    meta = try_meta_command(action)
    if meta is not None:
        record_turn(action=action, kind="meta", meta=True, scene_preview=(meta or "")[:200])
        return meta

    tick = simulation_runner.get_current_tick()

    with state_lock():
        push_undo_snapshot()
        log_event("player_action", "player", action, tick=tick)
        world = load(WORLD_FILE, {})
        npcs = load(NPC_FILE, {})
        monsters = load(MON_FILE, {})
        player = load(PLAYER_FILE, {})
        events = all_events()
        rumors = load(RUMOR_FILE, [])

    area_before = player.get("area")
    present = _present_npcs(npcs, player)
    sync_scene_focus(player, present, npcs)

    forced_kind = None
    forced_target_id = None
    pending_clarification = player.get("pending_target_clarification")
    clarified_kind, clarified_id = resolve_clarification_pick(action, player, present, npcs)
    replay_action = action
    if clarified_id:
        forced_kind = clarified_kind
        forced_target_id = clarified_id
        original = (pending_clarification or {}).get("original_action")
        if original:
            replay_action = original
        player["scene_focus"] = clarified_id
        clear_pending_clarification(player)
        with state_lock():
            save(PLAYER_FILE, player)

    if player.get("active_case") and not player["active_case"].get("solved"):
        areas_for_case = load(AREAS_FILE, {})
        _, case_changed = sanitize_active_case(
            player, npcs, areas_for_case, present_ids=[n["id"] for n in present],
        )
        if case_changed:
            with state_lock():
                save(PLAYER_FILE, player)
                save(NPC_FILE, npcs)

    action_ctx = interpret_action(replay_action, player, present, world, npcs=npcs)
    kind = action_ctx["kind"]
    if forced_kind:
        action_ctx["kind"] = forced_kind
        kind = forced_kind
    if forced_target_id:
        action_ctx["target_id"] = forced_target_id
        action_ctx["clarification_resolved"] = True
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "")
            + " CLARIFICATION RESOLVED — answer the protagonist's question now; "
            "do NOT repeat your prior speech verbatim."
        ).strip()

    with state_lock():
        world = load(WORLD_FILE, {})
        if kind == "wait":
            wait_info = resolve_wait_advance(action, world, player, player.get("area"))
            if wait_info.get("refused"):
                action_ctx["wait_no_change"] = True
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "")
                    + " "
                    + wait_info.get("refusal_message", "WAIT REFUSED — no time passes.")
                ).strip()
            else:
                hours = wait_info.get("hours") or 0
                if hours > 0:
                    world = advance_clock(hours)
                action_ctx["wait_hours"] = hours
                if wait_info.get("target_label"):
                    action_ctx["wait_target"] = wait_info["target_label"]
                if wait_info.get("event"):
                    action_ctx["wait_event"] = wait_info["event"].get("id")
                fired = fire_due_events(player, world, player.get("area"))
                if fired:
                    action_ctx["events_fired"] = fired
                    action_ctx["story_directive"] = (
                        action_ctx.get("story_directive", "")
                        + " "
                        + event_fired_directive(fired)
                    ).strip()
                elif hours > 0 and wait_info.get("target_label"):
                    action_ctx["story_directive"] = (
                        action_ctx.get("story_directive", "")
                        + f" TIME PASSED: {hours} hour(s) — now {world.get('time_of_day', '?')}."
                    ).strip()
                save(PLAYER_FILE, player)
        else:
            advance_for_action(kind)
        world = load(WORLD_FILE, {})
        save(WORLD_FILE, world)

    areas_data = load(AREAS_FILE, {})
    resolve_target_and_absence(action, player, present, npcs, action_ctx, world, areas_data)
    kind = action_ctx["kind"]

    if kind == "explore" and present:
        hook = pick_explore_hook(present, player)
        if hook and not action_ctx.get("target_id"):
            action_ctx["target_id"] = hook["id"]
            action_ctx["explore_hook"] = True
            player["scene_focus"] = hook["id"]
            with state_lock():
                save(PLAYER_FILE, player)

    if kind == "find":
        found = resolve_find_person(action, player, present, npcs)
        if found:
            action_ctx["target_id"] = found["id"]
            facts = build_find_facts(found)
            if facts:
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "") + " " + facts
                ).strip()
        else:
            action_ctx["target_id"] = None
            from simulation.target_ambiguity import collect_description_matches
            query_npc = resolve_npc_by_name_query(action, npcs, player)
            if len(collect_description_matches(action, present)) <= 1:
                action_ctx["find_failed"] = True
                query = extract_find_name_query(action)
                fail_facts = build_find_failed_facts(query_npc, query=query)
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "")
                    + " "
                    + fail_facts
                    + " Show a failed search — do not award weapons or loot."
                ).strip()
                if query_npc:
                    action_ctx["find_target_absent"] = query_npc.get("id")

    if kind == "investigate":
        action_ctx["target_id"] = None
        player["scene_focus"] = None
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "")
            + " Environment-only — physical clues, overheard fragments, contradictions in objects. "
            "No focal NPC dialogue; do not resume the last conversation."
        ).strip()
        with state_lock():
            save(PLAYER_FILE, player)

    if kind == "withdraw":
        prev_focus = player.get("scene_focus")
        if prev_focus and any(n["id"] == prev_focus for n in present):
            action_ctx["target_id"] = prev_focus
            action_ctx["withdraw_from"] = prev_focus
        player["scene_focus"] = None
        with state_lock():
            save(PLAYER_FILE, player)

    if kind == "confess":
        relationships = load("characters/relationships.json", {})
        respondent = resolve_confession_respondent(
            player, present, action_ctx, npcs, relationships,
        )
        if respondent:
            action_ctx["target_id"] = respondent["id"]
        victim = player.get("last_combat_target")
        action_ctx["confession_facts"] = build_confession_facts(
            player, respondent, victim, npcs,
        )
        if action_ctx.get("confession_facts"):
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "")
                + " " + action_ctx["confession_facts"]
            ).strip()

    if kind == "attack" and not action_ctx.get("target_id"):
        pron = resolve_pronoun_target(action, player, present)
        if pron:
            action_ctx["target_id"] = pron["id"]

    if (
        not action_ctx.get("target_id")
        and not action_ctx.get("absent_npc")
        and not action_ctx.get("clarification_resolved")
    ):
        ambiguity = detect_target_ambiguity(
            action, player, present, npcs, kind,
            target_id=action_ctx.get("target_id"),
        )
        if ambiguity:
            action_ctx["target_ambiguous"] = True
            action_ctx.pop("find_failed", None)
            set_pending_clarification(player, ambiguity)
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "")
                + " TARGET UNCLEAR — no violence or directed dialogue resolved yet. "
                "Protagonist must choose who they mean."
            ).strip()
            with state_lock():
                save(PLAYER_FILE, player)

    area_arrival = None
    delayed = pop_delayed_directive(player)
    extra_directive = delayed if delayed else None
    if delayed:
        with state_lock():
            save(PLAYER_FILE, player)
    name_reveal = None
    combat_target = None

    if detect_self_introduction(action, player):
        mark_name_revealed_to_present(player, [n["id"] for n in present])
        with state_lock():
            save(PLAYER_FILE, player)

    if kind == "approach":
        sub, local_msg = resolve_local_movement(action, player, player.get("area"))
        if sub:
            extra_directive = local_msg
            player["scene_focus"] = None
            action_ctx["target_id"] = None
            action_ctx["relocated"] = True
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "")
                + " RELOCATION — prior focal NPC does NOT follow into this sub-place. "
                "They remain behind unless SCENE FACTS list them present here."
            ).strip()
            with state_lock():
                save(PLAYER_FILE, player)
        else:
            action_ctx["approach_failed"] = True
            fail_msg = local_msg or (
                "That place isn't reachable from here on foot — stay in the district. "
                "Describe the failed attempt without inventing barred gates."
            )
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "")
                + " APPROACH FAILED — no movement. Protagonist stays put. "
                "Do NOT describe iron gates blocking a place named in prior beats. "
                "Do NOT repeat the focal NPC's last line — react to the stall or go quiet."
            ).strip()
            extra_directive = fail_msg

    if kind == "travel":
        from simulation.travel_engine import travel, list_destinations
        dests = list_destinations(player.get("area"))
        chosen, subplace, travel_msg = resolve_travel_destination(
            action, player, player.get("area"), dests, areas_data,
        )
        if subplace:
            extra_directive = travel_msg
            with state_lock():
                save(PLAYER_FILE, player)
        elif chosen:
            travel_before = snapshot_before_travel()
            ok, msg, hours, _ = travel(chosen, simulation_runner._run_tick)
            with state_lock():
                world = load(WORLD_FILE, {})
                player = load(PLAYER_FILE, {})
                npcs = load(NPC_FILE, {})
                monsters = load(MON_FILE, {})
                events = all_events()
                rumors = load(RUMOR_FILE, [])
            present = _present_npcs(npcs, player)
            sync_scene_focus(player, present, npcs)
            digest = build_arrival_digest(travel_before, chosen)
            extra_directive = msg + " " + digest
        else:
            action_ctx["travel_failed"] = True
            fail_msg = travel_msg or "Nowhere reachable from here."
            action_ctx["story_directive"] = (
                "TRAVEL FAILED — the destination is not on the map from here. "
                "The protagonist does NOT move. Do NOT invent doors, interiors, new districts, "
                "or conversations with strangers. One short beat of re-orientation only."
            )
            extra_directive = fail_msg

    if kind == "wait":
        with state_lock():
            world = load(WORLD_FILE, {})
            npcs = load(NPC_FILE, {})
            areas = load(AREAS_FILE, {})
            apply_schedules_to_npcs(npcs, world, areas)
            save(NPC_FILE, npcs)
            save(WORLD_FILE, world)
        present = _present_npcs(npcs, player)
        tid = action_ctx.get("target_id")
        target_npc = npcs.get(tid) if tid else None
        if target_npc and target_npc.get("area") == player.get("area"):
            action_ctx["story_directive"] += (
                f" After waiting, {target_npc.get('name', 'they')} is here — "
                f"{schedule_hint(target_npc, world)}"
            )
        elif target_npc:
            nxt = next_appearance(target_npc, world, areas)
            if nxt:
                action_ctx["story_directive"] += (
                    f" They are not here. Routine puts them at {nxt['area_name']} "
                    f"in ~{nxt['in_hours']} hour(s) ({nxt.get('label', '')})."
                )

    if kind == "ask_name":
        if not action_ctx.get("target_id"):
            target = pick_name_target(player, present, action)
            if target:
                action_ctx["target_id"] = target["id"]
        target_id = action_ctx.get("target_id")
        if target_id:
            target_npc = next((n for n in present if n["id"] == target_id), None)
            if not target_npc:
                target_npc = npcs.get(target_id)
            known = player.get("known_npcs", {}).get(target_id, {})
            if target_npc and not known.get("name_known"):
                name_reveal = {
                    "npc_id": target_id,
                    "name": target_npc["name"],
                    "descriptor": short_descriptor(target_npc),
                }

    with state_lock():
        player = load(PLAYER_FILE, {})
        if action_ctx.get("target_id") and kind in (
            "talk", "personal_talk", "help", "give", "ask_name",
            "threaten", "insult", "trade", "show_respect", "find", "guild",
            "explore", "attack", "confess", "search",
            "ask_about", "accuse", "blackmail",
        ):
            player["scene_focus"] = action_ctx["target_id"]
        to_introduce = _update_known(player, present, tick)
        save(PLAYER_FILE, player)

    area_ctx = _area_context(player)
    journal = player.get("journal") or []
    scene_event = None
    if not _skip_ambient_event(kind, player, journal):
        scene_event = maybe_scene_event(kind, area=area_ctx, player=player)
    if scene_event:
        from simulation.skill_check import resolve_check as _rc
        sk, dc = scene_event["check"]
        ev_check = _rc(player, sk, dc)
        ev_check["skill"] = sk
        ev_check["kind"] = f"scene:{scene_event['id']}"
        scene_event["narrative_outcome"] = (
            scene_event["success"] if ev_check["success"] else scene_event["fail"]
        )
        action_ctx.setdefault("skill_check", ev_check)
        player["last_check"] = {
            "kind": kind,
            "skill": ev_check.get("skill"),
            "roll": ev_check.get("roll"),
            "total": ev_check.get("total"),
            "difficulty": ev_check.get("difficulty"),
            "margin": ev_check.get("margin"),
            "success": ev_check.get("success"),
            "consequence": scene_event.get("narrative_outcome"),
        }
        if not ev_check["success"]:
            if scene_event["id"] == "pickpocket":
                loss = random.randint(2, 8)
                player["wealth"] = max(0, player.get("wealth", 0) - loss)
                scene_event["narrative_outcome"] += f" You lose {loss} coin."
            elif scene_event["id"] == "accident":
                stats = player.setdefault("stats", {})
                stats["health"] = max(1, stats.get("health", 100) - random.randint(2, 6))
            with state_lock():
                save(PLAYER_FILE, player)

    if kind not in ("travel", "attack", "rest", "search") and not action_ctx.get("skill_check"):
        check = run_action_check(
            player, kind, world=world, area=area_ctx, intents=action_ctx.get("intents"),
        )
        if check:
            action_ctx["skill_check"] = check
            apply_check_costs(player, check, kind)
            player["last_check"] = {
                "kind": kind,
                "skill": check.get("skill"),
                "roll": check.get("roll"),
                "total": check.get("total"),
                "difficulty": check.get("difficulty"),
                "margin": check.get("margin"),
                "success": check.get("success"),
                "consequence": check.get("consequence"),
            }
            if not check["success"] and kind == "steal" and present:
                tid = action_ctx.get("target_id") or present[0]["id"]
                from simulation.relationship_engine import apply_npc_toward_player
                apply_npc_toward_player(tid, "betrayal", 1.0)
            with state_lock():
                save(PLAYER_FILE, player)

    if kind in ("search", "examine") or (
        kind == "general" and not extract_find_name_query(action)
    ):
        ok_acquire, acquire_refusal = validate_acquire_item(action, player, area_ctx)
        if not ok_acquire:
            action_ctx["search_refused"] = True
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "") + " " + acquire_refusal
            ).strip()
        else:
            check = action_ctx.get("skill_check")
            success = True if kind == "search" else (check["success"] if check else True)
            item_note, item = try_acquire_item(
                action, player, area_ctx, tick, skill_success=success,
            )
            if item_note:
                action_ctx["acquired_item"] = {
                    "id": item["id"], "name": item["name"],
                    "category": item.get("category"), "rarity": item.get("rarity"),
                } if item else None
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "") + " " + item_note
                ).strip()
                with state_lock():
                    save(PLAYER_FILE, player)

    if kind in ("search", "confess") and player.get("last_combat_target"):
        post = build_post_combat_facts(player, npcs)
        action_ctx["story_directive"] = (action_ctx.get("story_directive", "") + " " + post).strip()

    if kind in ("investigate", "ask_about", "accuse", "blackmail"):
        areas_data = load(AREAS_FILE, {})
        present_ids = [n["id"] for n in present]
        target_npc = None
        tid = action_ctx.get("target_id")
        if tid:
            target_npc = next((n for n in present if n["id"] == tid), None)

        if kind == "investigate":
            _, npcs_changed = ensure_case(
                player, player.get("area"), npcs, areas_data, present_ids=present_ids,
            )
        else:
            npcs_changed = False

        if kind == "accuse":
            accuse_ok, accuse_refusal = validate_accuse(action, player, target_npc, npcs)
            if not accuse_ok:
                action_ctx["accuse_refused"] = True
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "") + " " + accuse_refusal
                ).strip()
            else:
                case_note = advance_case(player, kind, action_ctx, npcs)
                inv_dir, _, _sec = build_investigation_context(
                    action, player, present, world, action_ctx,
                )
                parts = [p for p in (inv_dir, case_note) if p]
                if parts:
                    action_ctx["story_directive"] = (
                        action_ctx.get("story_directive", "") + " " + " ".join(parts)
                    ).strip()
        else:
            case_note = advance_case(player, kind, action_ctx, npcs)
            inv_dir, _, _sec = build_investigation_context(
                action, player, present, world, action_ctx,
            )
            parts = [p for p in (inv_dir, case_note) if p]
            if parts:
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "") + " " + " ".join(parts)
                ).strip()
        with state_lock():
            save(PLAYER_FILE, player)
            if npcs_changed:
                save(NPC_FILE, npcs)

    if kind == "hunt":
        areas_data = load(AREAS_FILE, {})
        hunt_note = process_hunt_action(player, action_ctx, monsters, areas_data, world)
        if hunt_note:
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "") + " " + hunt_note
            ).strip()
        with state_lock():
            save(PLAYER_FILE, player)
            save(MON_FILE, monsters)

    with state_lock():
        player = load(PLAYER_FILE, {})
        check = action_ctx.get("skill_check")
        _apply_action_mechanics(player, action_ctx, kind, check=check)
        target_npc = npcs.get(action_ctx.get("target_id")) if action_ctx.get("target_id") else None
        register_from_action(player, kind, action_ctx, world, target_npc)
        apply_action_standing(player, kind, target_npc)
        apply_institution_standing(player, kind, target_npc)
        if kind == "guild":
            apply_guild_work_standing(player, target_npc)
        ensure_faction_standing(player)
        invites = check_faction_invitations(player)
        inst_invites = check_institution_invitations(player)
        for note in invites + inst_invites:
            player.setdefault("journal", []).append({
                "tick": tick, "day": world.get("day"), "kind": "faction",
                "action": note, "excerpt": note[:200],
            })
        legacy_from_action(player, kind, action_ctx, world, target_npc)
        if check and check.get("success") and kind in (
            "attack", "steal", "talk", "show_respect", "help", "trade", "hunt",
        ):
            bump_notoriety(player, 1, kind)
        maybe_spawn_rival(player, npcs, world, tick=tick)
        save(PLAYER_FILE, player)

    economy_directive = None
    if kind in ("trade", "give") and action_ctx.get("target_id"):
        tid = action_ctx["target_id"]
        target_npc = npcs.get(tid)
        check = action_ctx.get("skill_check")
        success = check["success"] if check else True
        if target_npc:
            if kind == "trade":
                trade_ok, trade_refusal, sale_item = validate_trade(action, target_npc)
                if not trade_ok:
                    action_ctx["trade_refused"] = True
                    action_ctx["story_directive"] = (
                        action_ctx.get("story_directive", "")
                        + " TRADE REFUSED — "
                        + trade_refusal
                        + " No coin deducted; no goods acquired."
                    ).strip()
                else:
                    economy_directive, p_chg, n_chg = resolve_trade(
                        player, target_npc, success, tick=tick,
                        location=player.get("area") or player.get("location"),
                        sale_item=sale_item,
                    )
            else:
                give_ok, give_refusal, amount = validate_give(action, player, target_npc)
                if not give_ok:
                    action_ctx["give_refused"] = True
                    action_ctx["story_directive"] = (
                        action_ctx.get("story_directive", "")
                        + " GIVE REFUSED — "
                        + give_refusal
                        + " Wealth unchanged."
                    ).strip()
                else:
                    economy_directive, p_chg, n_chg = resolve_give(
                        player, target_npc, success, tick=tick,
                        location=player.get("area") or player.get("location"),
                        amount=amount,
                    )
            if economy_directive and not action_ctx.get("trade_refused") and not action_ctx.get("give_refused"):
                if p_chg or n_chg:
                    npcs[tid] = target_npc
                    with state_lock():
                        save(PLAYER_FILE, player)
                        save(NPC_FILE, npcs)
                action_ctx["story_directive"] = (
                    action_ctx.get("story_directive", "") + " " + economy_directive
                ).strip()

    if kind == "attack" and not action_ctx.get("target_ambiguous"):
        with state_lock():
            out = _do_combat(player, npcs, monsters, present, tick, action, action_ctx)
            directive, combat_target, err, combat_snap, _result = out
            player = load(PLAYER_FILE, {})
            npcs = load(NPC_FILE, {})
            present = _present_npcs(npcs, player)
            if combat_target:
                action_ctx["target_id"] = combat_target
                action_ctx["memory_tag"] = "attack"
                player["scene_focus"] = combat_target
                if player.get("last_combat_fatal"):
                    dead = npcs.get(combat_target, {})
                    if dead.get("status") == "dead":
                        action_ctx["combat_snapshot"] = dict(dead)
                save(PLAYER_FILE, player)
        extra_directive = directive or err or extra_directive

    focus_npcs, crowd_note, focal_id = select_scene_cast(present, player, action_ctx)
    with state_lock():
        save(PLAYER_FILE, player)
    combat_snap = action_ctx.get("combat_snapshot")
    if kind == "attack" and combat_snap:
        snap_id = combat_snap.get("id")
        if not any(n.get("id") == snap_id for n in focus_npcs):
            focus_npcs = [combat_snap]
            focal_id = snap_id
            crowd_note = (
                "Others nearby are background only — do NOT give them dialogue this beat."
            )
    intro_for_scene = []
    if kind != "explore":
        focus_ids_set = {n["id"] for n in focus_npcs}
        intro_for_scene = [n for n in to_introduce if not focus_ids_set or n["id"] in focus_ids_set][:1]

    # memory only for focus + witnesses (not entire crowd)
    focus_ids = [n["id"] for n in focus_npcs]
    mem_ids = focus_ids if focus_ids else []
    if not mem_ids and present:
        mem_ids = [present[0]["id"]]
    mem_tag = action_ctx.get("memory_tag", "general")
    mem_target = action_ctx.get("target_id")
    if kind == "attack" and mem_target:
        mem_ids = list(set(mem_ids + [mem_target]))
    if mem_ids:
        record_player_action(
            mem_ids, mem_tag, action,
            player.get("area") or player.get("location"),
            tick, world.get("day"), target_id=mem_target,
            intensity=1.2 if kind in ("threaten", "help", "insult") else 1.0,
        )

    log_event(
        "player_interaction", "player", action_ctx.get("memory_tag", "general"),
        target=action_ctx.get("target_id"), location=player.get("location"),
        effects=[kind], tick=tick,
    )

    known_ids = {nid for nid, rec in player.get("known_npcs", {}).items() if rec.get("name_known")}
    focus_id_list = [n["id"] for n in focus_npcs]
    relationships = load("characters/relationships.json", {})
    rels_toward_player = {nid: relationships.get(nid, {}).get("player", {}) for nid in focus_id_list}

    immersion_block = _immersion_block(
        kind, player, world, action_ctx, rumors, events, action,
        present_ids=[n["id"] for n in present],
    )
    rival_note = rival_directive(player, npcs)
    if rival_note:
        immersion_block = (immersion_block + "\n\n" + rival_note).strip() if immersion_block else rival_note

    area_arc = arc_for_area(player.get("area")) or arc_for_city(player.get("location"))
    if kind not in ("ask_name", "talk", "withdraw", "attack", "confess", "search"):
        goal_hint = active_goal_hint(player, area_arc)
        if goal_hint:
            action_ctx["story_directive"] = (action_ctx.get("story_directive", "") + " " + goal_hint).strip()

    journal = player.get("journal") or []
    if journal and kind in ("trade", "give", "search", "rest", "explore", "travel"):
        prior_kind = journal[-1].get("kind")
        if prior_kind in ("accuse", "blackmail", "confess"):
            action_ctx["story_directive"] = (
                action_ctx.get("story_directive", "")
                + " THIS BEAT ONLY — resolve the current action; "
                "do NOT continue prior accusation or confession framing."
            ).strip()

    with state_lock():
        player = load(PLAYER_FILE, {})
        current_area = player.get("area")
        book = player.get("discovered_areas") or {}
        if current_area and (current_area != area_before or current_area not in book):
            area_arrival = record_area_arrival(player, current_area, world)
            if area_arrival and area_arrival.get("first_visit"):
                intro = area_intro_directive(area_arrival)
                extra_directive = ((extra_directive or "") + " " + intro).strip()
            save(PLAYER_FILE, player)

    areas_for_place = load(AREAS_FILE, {})
    area_for_place = areas_for_place.get(player.get("area"), {})
    scene_place = place_label(player, area_for_place)
    if (
        area_for_place.get("atmosphere")
        and kind in ("explore", "travel", "rest")
        and not (player.get("journal"))
    ):
        scene_place += " — " + (area_for_place["atmosphere"][0] if area_for_place["atmosphere"] else "")

    focal_npc = focus_npcs[0] if focus_npcs else None
    misname = build_misname_directive(
        action, focal_npc, npcs, action_ctx.get("target_id") or focal_id,
    )
    if misname:
        action_ctx["story_directive"] = (
            action_ctx.get("story_directive", "") + " " + misname
        ).strip()

    hard_constraints = build_hard_constraints_block(
        focal_id, focal_npc, scene_place, action_ctx, present=present,
    )
    sched_block = build_scheduled_events_block(player, player.get("area"), world)
    if sched_block:
        hard_constraints = (hard_constraints + "\n" + sched_block).strip()

    with state_lock():
        player = load(PLAYER_FILE, {})
        if ensure_npc_continuity_locks(player, focus_npcs):
            save(PLAYER_FILE, player)

    action_ctx["presence_facts"] = build_scene_presence_facts(present, action_ctx)

    if action_ctx.get("target_ambiguous"):
        pending = player.get("pending_target_clarification") or {}
        scene = build_clarification_scene(pending)
        prose_issues = []
    else:
        scene, prose_issues = _generate_scene_with_validation(
            action=action,
            world=world,
            player=player,
            focus_npcs=focus_npcs,
            events=events,
            rumors=rumors,
            intro_for_scene=intro_for_scene,
            known_ids=known_ids,
            rels_toward_player=rels_toward_player,
            extra_directive=extra_directive,
            area_arc=area_arc,
            tick=tick,
            action_ctx=action_ctx,
            name_reveal=name_reveal,
            focus_id_list=focus_id_list,
            crowd_note=crowd_note,
            scene_event=scene_event,
            immersion_block=immersion_block,
            focal_id=focal_id,
            scene_place=scene_place,
            hard_constraints=hard_constraints,
            on_prose_chunk=on_prose_chunk,
            npcs=npcs,
        )

    if name_reveal:
        with state_lock():
            player = load(PLAYER_FILE, {})
            player.setdefault("known_npcs", {}).setdefault(name_reveal["npc_id"], {})["name_known"] = True
            player["scene_focus"] = name_reveal["npc_id"]
            save(PLAYER_FILE, player)

    with state_lock():
        player = load(PLAYER_FILE, {})
        world = load(WORLD_FILE, {})
        update_player_goals(player, kind, action_ctx, world)
        if scene:
            if record_narrator_places(player, scene, player.get("area")):
                save(PLAYER_FILE, player)
            if record_scheduled_events(player, scene, player.get("area"), world):
                save(PLAYER_FILE, player)
            scene = strip_schedule_tags(scene)
        cache_id = focal_id or action_ctx.get("target_id") or player.get("scene_focus")
        if cache_id and scene:
            if update_npc_narrative_cache(
                player, cache_id, scene, npcs,
                player_speech=action_ctx.get("player_speech"),
            ):
                save(PLAYER_FILE, player)
        if kind == "investigate":
            focus_npc = None
        elif kind == "attack":
            focus_npc = (
                action_ctx.get("target_id")
                or player.get("last_combat_target")
                or focal_id
                or player.get("scene_focus")
            )
        else:
            focus_npc = action_ctx.get("target_id")
            if not focus_npc and not action_ctx.get("find_failed"):
                focus_npc = player.get("scene_focus")
        if (
            kind in ("explore", "talk", "find", "ask_about", "help", "give", "show_respect")
            and action_ctx.get("target_id")
            and not action_ctx.get("target_ambiguous")
        ):
            player["scene_focus"] = action_ctx["target_id"]
        journal_areas = load(AREAS_FILE, {})
        journal_area = journal_areas.get(player.get("area"), {})
        journal_place = place_label(player, journal_area)
        player.setdefault("journal", []).append({
            "tick": tick, "day": world.get("day"), "hour": world.get("hour"),
            "action": action, "kind": kind,
            "excerpt": scene[:400],
            "scene": scene,
            "location": player.get("location"), "area": player.get("area"),
            "place": journal_place,
            "subplace": (player.get("scene_subplace") or {}).get("id"),
            "focus_npc": focus_npc,
            "focus_cast": [n["id"] for n in focus_npcs],
            "present_ids": [n["id"] for n in present],
            "approach_failed": bool(action_ctx.get("approach_failed")),
            "travel_failed": bool(action_ctx.get("travel_failed")),
            "target_ambiguous": bool(action_ctx.get("target_ambiguous")),
            "combat_fatal": action_ctx.get("combat_fatal") if kind == "attack" else player.get("last_combat_fatal"),
        })
        maybe_compact_journal(player, npcs)
        player["journal"] = player["journal"][-300:]
        save(PLAYER_FILE, player)

    record_turn(
        action=action,
        kind=kind,
        meta=False,
        tick=tick,
        area_before=area_before,
        area_after=player.get("area"),
        target=action_ctx.get("target_id"),
        focus_npcs=[n["id"] for n in focus_npcs],
        skill_check=player.get("last_check"),
        scene_preview=(scene or "")[:240],
        area_arrival=area_arrival,
        prose_issues=prose_issues or None,
        memory_debug=action_ctx.get("memory_debug"),
        generation_settings=action_ctx.get("generation_settings"),
    )

    return scene


def generate_opening_scene():
    """First narrative beat after character creation — atmosphere, not a crowd."""
    player = load(PLAYER_FILE, {})
    if player.get("journal"):
        return None
    return process_player_action("look around")
