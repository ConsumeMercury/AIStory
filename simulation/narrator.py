"""
The narrator builds the prompt for the local model (Ollama) and returns prose.

Design goals encoded here:
  * Identity through description, not labels. A person the player hasn't been
    introduced to is referred to ONLY by a physical descriptor. The name is
    passed to the model exclusively for NPCs the player already knows.
  * Pronouns are LOCKED and stated explicitly, so the model can't drift.
  * Personality is conveyed as behavioural CUES (derived from traits) plus a
    private mannerism/want — never named adjectives. "Show, don't tell."
  * Slow burn: the relationship toward the player is summarised qualitatively
    so dialogue can reflect it without numbers, and without lurching.
  * Novel feel: long output, continuity with remembered events, end on tension.
  * Restraint with introductions: at most one or two newcomers per scene.
"""

import requests

from generation.descriptor_generator import short_descriptor
from generation.trait_generator import dominant_traits
from simulation.npc_memory_engine import top_memories

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:14b"

# trait -> behaviour the model should SHOW (never name)
TRAIT_CUES = {
    "aggression":     "takes up more space than needed; quick to close distance",
    "kindness":       "drifts toward whoever in the room is worst off",
    "greed":          "prices everything with a glance, including people",
    "ambition":       "watches the room for whoever matters most",
    "loyalty":        "keeps placing themselves between trouble and one particular person",
    "honesty":        "answers plainly even when a lie would serve better",
    "pride":          "will not be seen to need anything",
    "curiosity":      "leans in at the wrong moments, asks one question too many",
    "patience":       "lets silences run long without filling them",
    "temper":         "a muscle works in the jaw before they speak",
    "discipline":     "everything about them is squared away, nothing wasted",
    "humor":          "finds the joke a half-second before it's appropriate",
    "vanity":         "checks reflections, adjusts cuffs, minds the angle of their face",
    "paranoia":       "maps the exits, keeps their back to the wall",
    "generosity":     "the first to put coin or bread on the table",
    "sentimentality": "touches a worn keepsake when they think no one sees",
    "vindictiveness": "keeps a ledger of slights behind a pleasant face",
    "piety":          "marks small rituals, a touched amulet, a murmured word",
    "wit":            "two steps ahead in conversation, lays small traps",
    "courage":        "doesn't step back when a wiser person would",
    "impulsiveness":  "acts on the first instinct, words out before the thought finishes",
    "secretiveness":  "gives nothing away, deflects questions onto you",
    "superstition":   "reads the room for omens, won't sit thirteen to a table",
    "gregariousness": "fills silences, knows everyone's name, works the room",
    "ruthlessness":   "weighs people as means, discards them without heat",
}


def _relationship_tone(rel):
    """Turn relationship numbers into a quiet behavioural hint for dialogue."""
    if not rel:
        return "no particular feeling toward you yet"
    fam = rel.get("familiarity", 0)
    if fam < 5:
        return "treats you as a stranger"
    parts = []
    if rel.get("resentment", 0) > 40 or rel.get("fear", 0) > 50:
        parts.append("guarded and cold toward you")
    if rel.get("trust", 0) > 45:
        parts.append("has come to trust you")
    if rel.get("affection", 0) > 40:
        parts.append("warm toward you, though they'd not say so")
    if rel.get("attraction", 0) > 45:
        parts.append("more aware of you than they let on")
    if rel.get("respect", 0) > 45:
        parts.append("has started to respect you")
    return "; ".join(parts) or "still taking your measure"


def _npc_line(npc, known, is_new, rel):
    pron = npc.get("pronouns", {})
    label = npc["name"] if known else short_descriptor(npc)
    role = npc.get("role", "stranger")
    age = npc.get("age", "?")
    cues = [TRAIT_CUES[t] for t in dominant_traits(npc.get("traits", {}), 3) if t in TRAIT_CUES]
    mannerism = npc.get("background", {}).get("mannerism", "")
    want = (npc.get("goals") or ["get through the day"])[0]
    last = npc.get("last_action") or "none"
    phys = npc.get("physique", {})
    persona = npc.get("persona", {})
    inst = npc.get("institution") or {}

    # what this person remembers (their strongest memories), incl. of the player
    mems = top_memories(npc.get("id"), 3)
    mem_str = "; ".join(m["summary"] for m in mems) or "nothing that weighs on them yet"

    if known:
        head = f"{label} ({role}, ~{age}) — already known to you."
        desc = ""
    elif is_new:
        head = f"[FIRST ENCOUNTER — describe physically, do NOT give a name] {label} ({role}, looks {phys.get('apparent_age','grown')})."
        desc = (f"  Appearance to weave in (2 sentences): {phys.get('build','')}, {phys.get('height','')}, "
                f"{phys.get('hair','')}, {phys.get('eyes','')}, {phys.get('skin','')} skin, "
                f"{phys.get('distinguishing_mark','')}; wears {phys.get('attire','')}, "
                f"carries {phys.get('accessory','')}.\n")
    else:
        head = f"{label} ({role}) — present, but you have not learned {pron.get('possessive','their')} name."
        desc = ""

    inst_line = ""
    if inst:
        inst_line = f"  Belongs to an institution as a {inst.get('role','member')}.\n"

    return (
        f"{head}\n{desc}"
        f"  Pronouns (USE EXACTLY): {pron.get('subject','they')}/{pron.get('object','them')}/{pron.get('possessive','their')}\n"
        f"  Show through behaviour, never name: {'; '.join(cues) if cues else 'reserved, hard to read'}\n"
        f"  Mannerism (private, show don't state): {mannerism}\n"
        f"  Speech: {persona.get('speech_style','plain')}; {persona.get('voice_quirk','')}. "
        f"Holds the value: \"{persona.get('core_value','')}\". Current mood: {persona.get('mood','even')}.\n"
        f"{inst_line}"
        f"  Remembers (let this shape how they treat you — do not have them recite it): {mem_str}\n"
        f"  Quietly wants: {want}. Last seen doing: {last}.\n"
        f"  Feeling toward you (let it colour dialogue subtly): {_relationship_tone(rel)}"
    )


def _build_npc_context(present, known_ids, new_ids, rels):
    if not present:
        return "You are alone here. Let the place itself carry the scene."
    lines = []
    for npc in present[:3]:  # max 3 on stage; restraint
        nid = npc.get("id")
        rel = rels.get(nid, {})
        lines.append(_npc_line(npc, nid in known_ids, nid in new_ids, rel))
    return "\n\n".join(lines)


def generate_scene(player_action, world, player, present_npcs,
                   memories, rumors=None, new_npcs=None,
                   known_ids=None, relationships=None, extra_directive=None,
                   local_arc=None):
    known_ids = set(known_ids or [])
    new_ids = {n.get("id") for n in (new_npcs or [])}
    rels = relationships or {}

    world_line = (
        f"{world.get('world_name','Unknown')} — Day {world.get('day',1)}, "
        f"{world.get('time_of_day','day')} ({world.get('hour',0)}:00), "
        f"{world.get('season','')}, {world.get('weather','')}. "
        f"Regional stability {world.get('global_stability',50)}/100."
    )

    s = player.get("stats", {})
    skills = player.get("skills", {})
    top_skills = sorted(skills, key=lambda k: skills[k].get("level", 0), reverse=True)[:3]
    skills_str = ", ".join(f"{k} L{skills[k]['level']}" for k in top_skills) or "none of note"
    player_block = (
        f"Name: {player.get('name','Unknown')}  ({player.get('background','wanderer')}, age {player.get('age','?')})\n"
        f"Appearance: {player.get('appearance','unremarkable')}\n"
        f"Where: {player.get('location','unknown')} / {player.get('area','')}\n"
        f"Health {s.get('health','?')}/{s.get('max_health','?')}  "
        f"Stamina {s.get('stamina','?')}/{s.get('max_stamina','?')}  Wealth {player.get('wealth',0)}\n"
        f"Best skills: {skills_str}"
    )

    npc_block = _build_npc_context(present_npcs, known_ids, new_ids, rels)

    mem_lines = []
    for m in (memories or [])[-8:]:
        if isinstance(m, dict) and m.get("actor") != "player":
            mem_lines.append(f"- {m.get('actor','someone')} {m.get('action','').replace('_',' ')}"
                             f" in {m.get('location','somewhere')}")
    memory_block = "\n".join(mem_lines) or "Nothing of note has reached you yet."

    rumor_block = "\n".join(
        f"- {r.get('text','')}" for r in (rumors or [])[-3:]
        if isinstance(r, dict) and r.get("text")
    ) or "None worth repeating."

    arc_block = "Nothing of institutional note here."
    if local_arc and local_arc.get("current"):
        arc_block = (f"At {local_arc['institution']} ({local_arc['type']}): "
                     f"{local_arc['current']}. (tension {local_arc.get('tension',0)}/100) "
                     f"Let this hang in the air of the place; surface it only if it fits.")

    prompt = f"""You are the narrator of a long, slow-burn dark-fantasy novel. Second person, present tense, literary register.

NON-NEGOTIABLE RULES:
1. Prose only. No questions to the reader, no "What do you do?", no lists, no headers.
2. The player's action HAPPENS. Begin in the middle of it; never restate it as a heading.
3. People the player has NOT been introduced to are referred to ONLY by physical description (e.g. "the broad-shouldered woman with burn-scarred forearms"). NEVER invent or reveal their name. Use a name ONLY for characters explicitly marked "already known to you."
4. Use each character's stated pronouns EXACTLY and consistently. Never switch a character's pronouns within or across scenes.
5. Reveal personality ONLY through behaviour, posture, objects, and what characters do with their hands and eyes. NEVER name a trait ("aggressive", "kind", "proud"). Show the clenched jaw, not the anger.
6. This is a slow burn. Trust, fear, and affection shift by inches, not leaps. Let the relationship notes colour tone and dialogue subtly — do not announce feelings.
7. Continuity is sacred. Honour the remembered events and rumours; let consequences linger. Nothing is forgotten.
8. Characters ACT on what they personally remember (see each one's "Remembers" note) and speak in their own voice (see "Speech"). A person who remembers you attacking them does not greet you warmly. Never have them recite their memories like a report — let memory shape behaviour.
9. At most ONE new person may be meaningfully introduced this scene. Do not crowd the stage.
10. Dialogue is sparse and load-bearing — at most two short exchanges, voiced to each speaker's manner. Silence usually says more.
11. End on motion, tension, or an unanswered weight. No tidy resolution.
12. Write FIVE to SEVEN full paragraphs. Let the world breathe.

WORLD: {world_line}

WHAT HANGS OVER THIS PLACE:
{arc_block}

YOU:
{player_block}

PRESENT (only those actually here):
{npc_block}

WHAT HAS BEEN HAPPENING (remembered, may surface):
{memory_block}

RUMOURS DRIFTING AROUND:
{rumor_block}
{('SPECIAL DIRECTIVE: ' + extra_directive) if extra_directive else ''}

THE PLAYER NOW: {player_action}

Write the scene."""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "repeat_penalty": 1.18,
                "num_predict": 1100,   # longer, novel-length scenes
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    
    result = response.json()

    print("\n===== TOKEN DEBUG =====")
    print("Prompt chars:", len(prompt))
    print("Estimated prompt tokens:", len(prompt) // 4)
    print("Response chars:", len(result["response"]))
    print("Estimated response tokens:", len(result["response"]) // 4)

    # Some Ollama builds also include real counts:
    if "prompt_eval_count" in result:
        print("REAL prompt tokens:", result["prompt_eval_count"])
    if "eval_count" in result:
        print("REAL response tokens:", result["eval_count"])

    print("======================\n")

    return result["response"]
    
