"""
Turns a typed player action into a narrated scene, while maintaining all the
state that makes the world feel continuous:

  * Identity memory: player.json["known_npcs"] records, per NPC, whether the
    player has been introduced (seen_before) and whether they've learned the
    name (name_known). The narrator only gets names the player has earned.
  * Introduction restraint: at most ONE never-before-seen NPC is flagged for
    physical introduction per scene.
  * Light command routing: travel and combat are handled mechanically (real
    stat/time changes) and then narrated; everything else is pure narration.
  * Player progression + slow-burn relationships from what the player does.
  * Journal/event memory so nothing is forgotten.
"""

import re

from storage import load, save
from simulation.narrator import generate_scene
from simulation.event_logger import log_event
from simulation.progression_engine import add_skill_xp
from simulation.relationship_engine import apply_interaction, relationship
from simulation.combat_engine import resolve_combat
from simulation.storyline_engine import arc_for_city
from simulation import simulation_runner

WORLD_FILE = "world/world_state.json"
NPC_FILE = "characters/npcs.json"
MON_FILE = "characters/monsters.json"
PLAYER_FILE = "player/player.json"
EVENT_FILE = "events/event_log.json"
RUMOR_FILE = "rumors/rumors.json"


# ---------- identity bookkeeping ----------
def _present_npcs(npcs, player):
    loc = player.get("location")
    area = player.get("area")
    here = []
    for n in npcs.values():
        if n.get("status") != "alive":
            continue
        # present if same area (preferred) or, lacking areas, same city
        if (area and n.get("area") == area) or n.get("location") == loc:
            here.append(n)
    return here


def _update_known(player, present, tick):
    """Mark NPCs as seen; choose at most one newcomer to introduce."""
    known = player.setdefault("known_npcs", {})
    newcomers = []
    for n in present:
        nid = n["id"]
        rec = known.get(nid)
        if rec is None:
            known[nid] = {"name_known": False, "seen_before": False,
                          "first_seen_tick": tick, "times_seen": 1}
            newcomers.append(n)
        else:
            rec["times_seen"] = rec.get("times_seen", 0) + 1

    # introduce at most one newcomer physically this scene
    to_introduce = newcomers[:1]
    for n in present:
        known[n["id"]]["seen_before"] = True
    return to_introduce


def _learn_name(player, present):
    """Player asked for a name: reveal the most salient present NPC's name."""
    if not present:
        return None
    known = player.setdefault("known_npcs", {})
    # prefer someone seen before but whose name isn't known
    candidates = [n for n in present if not known.get(n["id"], {}).get("name_known")]
    if not candidates:
        return None
    target = candidates[0]
    known.setdefault(target["id"], {})["name_known"] = True
    return target


# ---------- action classification ----------
_TRAVEL = re.compile(r"\b(travel|go to|head to|journey|ride to|walk to|set out)\b", re.I)
_ASKNAME = re.compile(r"\b(your name|who are you|what.s your name|ask .*name|introduce)\b", re.I)
_ATTACK = re.compile(r"\b(attack|strike|kill|fight|stab|swing at|draw .*blade|cut down)\b", re.I)


def _classify(action):
    if _ASKNAME.search(action):
        return "ask_name"
    if _ATTACK.search(action):
        return "attack"
    if _TRAVEL.search(action):
        return "travel"
    return "narrate"


# ---------- combat handling ----------
def _do_combat(player, npcs, monsters, present, action, tick):
    # pick a target: a present monster first, else a present NPC
    mon_here = [m for m in monsters.values()
                if m.get("status") == "alive" and m.get("location") and
                (m.get("area") == player.get("area") or m.get("location") == player.get("location"))]
    target = None
    target_kind = None
    if mon_here:
        target, target_kind = mon_here[0], "monster"
    elif present:
        target, target_kind = present[0], "npc"

    if target is None:
        return None, "There is no one here to fight."

    result = resolve_combat(player, target, max_rounds=3)

    if target_kind == "npc":
        # violence is remembered, and it costs you with them and onlookers
        apply_interaction(target["id"], "violence", intensity=1.5, actor_id="player")
        npcs[target["id"]] = target
    else:
        monsters[target["id"]] = target

    save(PLAYER_FILE, player)
    save(NPC_FILE, npcs)
    save(MON_FILE, monsters)

    directive = (
        f"The player attacks. Combat resolved over {result['rounds']} exchanges. "
        f"Player now at {player['stats']['health']}/{player['stats']['max_health']} health; "
        f"the target at {target['stats']['health']} health"
        + (" and is dead." if result["fatal"] and result["loser"] == target["id"]
           else ". The fight breaks off, unresolved." if not result["winner"] else ".")
        + " Narrate the violence concretely and its cost; do not soften it."
    )
    log_event("combat", "player", "attack", target=target.get("id"),
              location=player.get("location"),
              effects=["fatal"] if result["fatal"] else [], tick=tick)
    return directive, None


# ---------- main entry ----------
def process_player_action(action):
    lock = simulation_runner.get_tick_lock()
    tick = simulation_runner.get_current_tick()
    kind = _classify(action)

    with lock:
        log_event("player_action", "player", action, tick=tick)
        world = load(WORLD_FILE, {})
        npcs = load(NPC_FILE, {})
        monsters = load(MON_FILE, {})
        player = load(PLAYER_FILE, {})
        events = load(EVENT_FILE, [])
        rumors = load(RUMOR_FILE, [])
        relationships = load("characters/relationships.json", {})

    present = _present_npcs(npcs, player)
    extra_directive = None

    # --- TRAVEL: hand off to the travel engine (advances hours + runs ticks) ---
    if kind == "travel":
        from simulation.travel_engine import travel, list_destinations
        dests = list_destinations(player.get("area"))
        # try to match a named destination in the typed text
        chosen = None
        for aid in dests:
            leaf = aid.split(":")[-1].replace("_", " ")
            if leaf in action.lower() or aid.lower() in action.lower():
                chosen = aid
                break
        if chosen is None and dests:
            chosen = min(dests, key=dests.get)  # nearest if unspecified
        if chosen:
            ok, msg, hours, _ = travel(chosen, simulation_runner._run_tick)
            with lock:
                world = load(WORLD_FILE, {})
                player = load(PLAYER_FILE, {})
                npcs = load(NPC_FILE, {})
                monsters = load(MON_FILE, {})
                events = load(EVENT_FILE, [])
                rumors = load(RUMOR_FILE, [])
                relationships = load("characters/relationships.json", {})
            present = _present_npcs(npcs, player)
            extra_directive = (msg + " Open the scene on arrival; convey that time has "
                               "passed and the place is mid-life, not waiting for you.")
        else:
            extra_directive = "There is nowhere obvious to travel from here."

    # --- ASK NAME: reveal one name, narrate the small social moment ---
    if kind == "ask_name":
        learned = _learn_name(player, present)
        if learned:
            with lock:
                save(PLAYER_FILE, player)
            extra_directive = (f"The player asks who they are. The character may give their "
                               f"name — it is {learned['name']} — or deflect, in keeping with "
                               f"their manner. From now on the player knows this name.")
        else:
            extra_directive = "There is no one here whose name remains to be learned."

    # mark seen / choose at most one newcomer to physically introduce
    with lock:
        player = load(PLAYER_FILE, {})
        to_introduce = _update_known(player, present, tick)
        save(PLAYER_FILE, player)

    known_ids = {nid for nid, rec in player.get("known_npcs", {}).items()
                 if rec.get("name_known")}
    rels_toward_player = {nid: relationships.get("player", {}).get(nid, {})
                          for nid in [n["id"] for n in present]}
    # also fold in how THEY feel about the player (actor=npc -> player) for tone
    for n in present:
        r = relationships.get(n["id"], {}).get("player")
        if r:
            rels_toward_player[n["id"]] = r

    # --- COMBAT resolves before narration so the scene reflects the outcome ---
    if kind == "attack":
        with lock:
            directive, err = _do_combat(player, npcs, monsters, present, action, tick)
            player = load(PLAYER_FILE, {})
            npcs = load(NPC_FILE, {})
        extra_directive = directive or err

    scene = generate_scene(
        player_action=action,
        world=world,
        player=player,
        present_npcs=present,
        memories=events[-15:],
        rumors=rumors[-5:] if rumors else [],
        new_npcs=to_introduce,
        known_ids=known_ids,
        relationships=rels_toward_player,
        extra_directive=extra_directive,
        local_arc=arc_for_city(player.get("location")),
    )

    # player earns a little skill xp for acting, and we never forget the scene
    with lock:
        player = load(PLAYER_FILE, {})
        _player_progress(player, kind)
        player.setdefault("journal", []).append({
            "tick": tick, "day": world.get("day"), "hour": world.get("hour"),
            "action": action, "excerpt": scene[:240],
            "location": player.get("location"), "area": player.get("area"),
        })
        player["journal"] = player["journal"][-300:]   # long memory
        save(PLAYER_FILE, player)

    return scene


def _player_progress(player, kind):
    mapping = {"attack": ("brawling", 14), "travel": ("navigation", 8),
               "narrate": ("empathy", 4), "ask_name": ("empathy", 6)}
    skill, amt = mapping.get(kind, ("empathy", 3))
    add_skill_xp(player, skill, amt)
