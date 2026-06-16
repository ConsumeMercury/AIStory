"""
Build-time narrative enrichment — optional LLM pass over procedural world data.
"""

import logging
import uuid

from generation.llm_content import (
    ai_worldgen_enabled,
    llm_json,
    npc_batch_size,
    validate_background_spec,
    validate_history_events,
    validate_name_spec,
    validate_npc_profile,
    validate_objective_spec,
    validate_persona_spec,
    validate_secrets_list,
    validate_storyline_spec,
    call_llm_json,
)

log = logging.getLogger(__name__)

_SYSTEM = (
    "You write grounded fantasy city fiction for a text RPG. "
    "Return ONLY valid JSON matching the requested schema. "
    "No markdown fences. Keep prose concrete and playable — no purple prose."
)


def maybe_enrich_world_history(events, cities):
    if not ai_worldgen_enabled() or not events:
        return events
    city_names = ", ".join(c.get("name", "Unknown") for c in (cities or [])[:4])
    template = events[0] if events else {}
    prompt = f"""Rewrite this city's recent history as JSON array of 5 events.
Cities in region: {city_names}
Each event: {{ "when": string, "official": string, "folk": string, "rumor": string }}
Tone: political, mercantile, slightly grim. Events should interconnect.
Template example (do not copy verbatim): {template}
Return JSON array only."""
    enriched = llm_json(prompt, validate_history_events, system=_SYSTEM, temperature=0.75)
    if enriched:
        log.info("AI worldgen: enriched world history (%d events)", len(enriched))
        return enriched
    return events


def maybe_enrich_storyline_spec(spec, *, district_name="", city_name="", area_name=""):
    if not ai_worldgen_enabled() or not spec:
        return spec
    prompt = f"""Create a district storyline for a fantasy city RPG.
Location: {district_name or area_name}, city {city_name}
Theme hint: {spec.get('theme', 'intrigue')}
Return JSON object:
{{ "title": string, "theme": string, "hooks": [2-4 short player-facing hooks], "stages": [exactly 5 escalation beats] }}
Do not reference places not in: {district_name}, {city_name}."""
    enriched = llm_json(prompt, validate_storyline_spec, system=_SYSTEM, temperature=0.85)
    if enriched:
        log.info("AI worldgen: enriched storyline %s", enriched.get("title", district_name))
        return enriched
    return spec


def maybe_enrich_institution_arc(spec, *, inst_type="", inst_name="", city_name=""):
    if not ai_worldgen_enabled() or not spec:
        return spec
    prompt = f"""Create an institution arc for a fantasy city RPG.
Institution: {inst_name} ({inst_type}) in {city_name}
Return JSON object:
{{ "title": string, "theme": string, "hooks": [2-3 hooks], "stages": [exactly 5 beats] }}
The arc should fit guild/church/court politics, not epic fantasy."""
    enriched = llm_json(prompt, validate_storyline_spec, system=_SYSTEM, temperature=0.85)
    if enriched:
        log.info("AI worldgen: enriched institution arc %s", enriched.get("title", inst_name))
        return enriched
    return spec


def maybe_enrich_persona(npc, *, city_name="", area_name=""):
    if not ai_worldgen_enabled():
        return npc.get("persona")
    role = npc.get("role", "citizen")
    age = npc.get("age", 30)
    prompt = f"""Write a speech persona for an NPC in a fantasy city.
Role: {role}, age {age}, district {area_name}, city {city_name}
Return JSON:
{{ "speech_style": string, "voice_quirk": string, "core_value": string, "mood": string,
   "example_lines": [2 short lines this NPC might say], "avoids_topics": [1-2 topics] }}"""
    return llm_json(prompt, validate_persona_spec, system=_SYSTEM, temperature=0.88)


def maybe_enrich_background(npc, *, city_name="", area_name=""):
    if not ai_worldgen_enabled():
        return npc.get("background")
    role = npc.get("role", "citizen")
    faction = (npc.get("faction") or {}).get("name", "none")
    prompt = f"""Write a compact character background for a fantasy city NPC.
Role: {role}, faction: {faction}, lives in {area_name}, {city_name}
Return JSON:
{{ "summary": string (2-3 sentences), "childhood": string, "formative_event": string,
   "current_situation": string, "belief": string, "secret": string, "mannerism": string, "hope": string }}"""
    return llm_json(prompt, validate_background_spec, system=_SYSTEM, temperature=0.88)


def maybe_enrich_objective(npc, npcs=None):
    if not ai_worldgen_enabled():
        return None
    name = npc.get("name", "they")
    role = npc.get("role", "citizen")
    prompt = f"""Write one personal objective for NPC {name} ({role}) in a fantasy city.
Return JSON: {{ "text": string (one sentence, actionable, not heroic epic) }}"""
    result = llm_json(prompt, validate_objective_spec, system=_SYSTEM, temperature=0.9)
    return result.get("text") if result else None


def maybe_enrich_secrets(npc, count=1):
    if not ai_worldgen_enabled() or count < 1:
        return None
    name = npc.get("name", "they")
    role = npc.get("role", "citizen")
    prompt = f"""Write {count} secrets for NPC {name} ({role}) in a fantasy city.
Return JSON array of {{ "text": string, "severity": "minor"|"major"|"deadly" }}"""
    result = llm_json(prompt, validate_secrets_list, system=_SYSTEM, temperature=0.85)
    return result


def maybe_enrich_name(culture, city_name="", role=""):
    if not ai_worldgen_enabled():
        return None
    prompt = f"""Generate one character name for culture {culture}, city {city_name}, role {role}.
Return JSON: {{ "given_name": string, "surname": string optional }}"""
    result = llm_json(prompt, validate_name_spec, system=_SYSTEM, temperature=0.95)
    if not result:
        return None
    if result.get("surname"):
        return f"{result['given_name']} {result['surname']}"
    return result["given_name"]


def _apply_npc_profile(npc, profile):
    if not profile:
        return
    if profile.get("persona"):
        npc["persona"] = profile["persona"]
    if profile.get("background"):
        npc["background"] = profile["background"]
    lock = profile.get("appearance_lock")
    if lock:
        npc.setdefault("physique", {})["appearance_lock"] = lock
    if profile.get("name"):
        npc["name"] = profile["name"]


def _enrich_npc_batch(batch, *, city_name, area_lookup):
    if not batch:
        return
    lines = []
    for npc in batch:
        area = area_lookup(npc.get("area", ""), "unknown district")
        lines.append(
            f"- id={npc.get('id')}: role={npc.get('role')}, age={npc.get('age')}, "
            f"gender={npc.get('gender')}, area={area}, name={npc.get('name')}"
        )
    prompt = f"""For each NPC below, write a distinct character profile for a gritty fantasy city RPG.
City: {city_name}
NPCs:
{chr(10).join(lines)}

Return JSON array (same order, one object per NPC). Each object:
{{
  "persona": {{ "speech_style", "voice_quirk", "core_value", "mood", "example_lines": [2], "avoids_topics": [1-2] }},
  "background": {{ "summary", "childhood", "formative_event", "current_situation", "belief", "secret", "mannerism", "hope" }},
  "appearance_lock": "one vivid sentence: face, hair, eyes, mark — for narrator consistency"
}}
Do NOT change roles or ages. Make each voice distinct."""
    raw = call_llm_json(prompt, system=_SYSTEM, temperature=0.88, max_tokens=4096)
    if not isinstance(raw, list):
        return
    for npc, item in zip(batch, raw):
        ok, cleaned, errors = validate_npc_profile(item)
        if ok:
            _apply_npc_profile(npc, cleaned)
        else:
            log.debug("AI worldgen: skipped NPC %s: %s", npc.get("id"), errors)


def enrich_npc_population(npcs, areas, city_name=""):
    if not ai_worldgen_enabled() or not npcs:
        return

    def lookup(area_id, default=""):
        area = (areas or {}).get(area_id) if isinstance(areas, dict) else None
        if isinstance(area, dict):
            return area.get("name", default)
        return default

    alive = [n for n in npcs.values() if n.get("status") == "alive"]
    batch_sz = npc_batch_size()
    total = len(alive)
    for i in range(0, total, batch_sz):
        chunk = alive[i:i + batch_sz]
        log.info("AI worldgen: enriching NPCs %d-%d / %d", i + 1, min(i + batch_sz, total), total)
        _enrich_npc_batch(chunk, city_name=city_name, area_lookup=lookup)


def _apply_institution_arc(inst, enriched, arc):
    arc["spec"] = enriched
    arc["title"] = enriched["title"]
    arc["theme"] = enriched.get("theme")
    arc["stages"] = list(enriched["stages"])
    arc["current"] = enriched["stages"][0]
    inst["arc"] = arc


def _apply_ai_secrets(npc, secret_specs):
    npc["secrets"] = [
        {
            "id": str(uuid.uuid4())[:8],
            "text": s["text"],
            "severity": s.get("severity", "major"),
            "exposed": False,
            "exposed_to_player": False,
            "blackmail_used": False,
        }
        for s in secret_specs
    ]


def enrich_world_narrative(world, locations, areas, institutions, npcs, factions):
    """Main hook from game/setup after procedural generation."""
    if not ai_worldgen_enabled():
        return

    cities = (locations or {}).get("cities") or world.get("cities") or []
    if isinstance(cities, dict):
        city_name = next(iter(cities.values()), {}).get("name", "the city")
    elif cities:
        first = cities[0]
        city_name = first.get("name", "the city") if isinstance(first, dict) else str(first)
    else:
        city_name = "the city"

    if world.get("history"):
        city_list = list(cities.values()) if isinstance(cities, dict) else cities
        world["history"] = maybe_enrich_world_history(world["history"], city_list)

    for inst in (institutions or {}).values():
        arc = inst.get("arc") or {}
        arc_spec = arc.get("spec") or {}
        if not isinstance(arc_spec, dict) or not arc_spec.get("stages"):
            continue
        enriched = maybe_enrich_institution_arc(
            arc_spec,
            inst_type=inst.get("type", ""),
            inst_name=inst.get("name", ""),
            city_name=city_name,
        )
        if enriched is not arc_spec:
            _apply_institution_arc(inst, enriched, arc)

    enrich_npc_population(npcs, areas, city_name=city_name)

    for npc in (npcs or {}).values():
        if npc.get("status") != "alive":
            continue
        obj_text = maybe_enrich_objective(npc)
        if obj_text:
            npc["personal_objective"] = {
                "text": obj_text,
                "progress": 0,
                "target": 100,
                "complete": False,
            }
        secret_specs = maybe_enrich_secrets(npc, count=1)
        if secret_specs:
            _apply_ai_secrets(npc, secret_specs)

    log.info("AI worldgen: narrative enrichment complete")
