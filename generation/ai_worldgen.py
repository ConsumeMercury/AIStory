"""
Build-time narrative enrichment — optional LLM pass over procedural world data.
"""

import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from generation.llm_content import (
    ai_worldgen_enabled,
    ai_worldgen_history_enabled,
    ai_worldgen_institutions_enabled,
    institution_enrich_limit,
    llm_json,
    npc_batch_size,
    npc_enrich_limit,
    npc_batch_max_tokens,
    worldgen_parallel_workers,
    worldgen_retry_failed,
    worldgen_split_batches,
    unwrap_npc_batch_payload,
    validate_history_events,
    validate_npc_profile,
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
    if not ai_worldgen_enabled() or not ai_worldgen_history_enabled() or not events:
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
    if not ai_worldgen_enabled() or not ai_worldgen_institutions_enabled() or not spec:
        return spec
    prompt = f"""Create an institution arc for a fantasy city RPG.
Institution: {inst_name} ({inst_type}) in {city_name}
Return JSON object with exactly these keys:
{{ "title": string, "theme": string, "hook": string (one opening hook), "stages": [exactly 5 short beats] }}
The arc should fit guild/church/court politics, not epic fantasy."""
    enriched = llm_json(prompt, validate_storyline_spec, system=_SYSTEM, temperature=0.85)
    if enriched:
        log.info("AI worldgen: enriched institution arc %s", enriched.get("title", inst_name))
        return enriched
    return spec


def _npc_profile_enriched(npc):
    return bool((npc.get("physique") or {}).get("appearance_lock"))


def _apply_npc_batch_results(batch, raw):
    raw = unwrap_npc_batch_payload(raw)
    if not isinstance(raw, list):
        return False
    applied = 0
    for npc, item in zip(batch, raw):
        ok, cleaned, errors = validate_npc_profile(item)
        if ok:
            _apply_npc_profile(npc, cleaned)
            applied += 1
        else:
            log.debug("AI worldgen: skipped NPC %s: %s", npc.get("id"), errors)
    return applied > 0


def _retry_failed_npcs(batch, *, city_name, area_lookup):
    for npc in batch:
        if _npc_profile_enriched(npc):
            continue
        area = area_lookup(npc.get("area", ""), "unknown district")
        _enrich_npc_one(npc, city_name=city_name, area_name=area)


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
    obj_text = profile.get("personal_objective")
    if obj_text:
        npc["personal_objective"] = {
            "text": obj_text,
            "progress": 0,
            "target": 100,
            "complete": False,
        }


def _enrich_npc_one(npc, *, city_name, area_name):
    prompt = f"""Write one character profile for a gritty fantasy city RPG.
City: {city_name}, district: {area_name}
NPC: role={npc.get('role')}, age={npc.get('age')}, gender={npc.get('gender')}, name={npc.get('name')}
Return JSON object:
{{
  "persona": {{ "speech_style", "voice_quirk", "core_value", "mood", "example_lines": [2], "avoids_topics": [1-2] }},
  "background": {{ "summary", "childhood", "formative_event", "current_situation", "belief", "secret", "mannerism", "hope" }},
  "appearance_lock": "one vivid sentence: face, hair, eyes, mark",
  "personal_objective": "one short actionable sentence"
}}
Keep fields concise. Do NOT change role or age."""
    raw = call_llm_json(
        prompt, system=_SYSTEM, temperature=0.88, max_tokens=npc_batch_max_tokens(),
    )
    raw = unwrap_npc_batch_payload(raw)
    if not isinstance(raw, dict):
        return False
    ok, cleaned, errors = validate_npc_profile(raw)
    if ok:
        _apply_npc_profile(npc, cleaned)
        return True
    log.debug("AI worldgen: skipped NPC %s: %s", npc.get("id"), errors)
    return False


def _enrich_npc_batch(batch, *, city_name, area_lookup):
    if not batch:
        return
    if len(batch) == 1:
        area = area_lookup(batch[0].get("area", ""), "unknown district")
        _enrich_npc_one(batch[0], city_name=city_name, area_name=area)
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
  "appearance_lock": "one vivid sentence: face, hair, eyes, mark — for narrator consistency",
  "personal_objective": "one short actionable sentence"
}}
Keep each field short. Do NOT change roles or ages. Make each voice distinct."""
    raw = call_llm_json(prompt, system=_SYSTEM, temperature=0.88, max_tokens=npc_batch_max_tokens())
    if _apply_npc_batch_results(batch, raw):
        if worldgen_retry_failed():
            _retry_failed_npcs(batch, city_name=city_name, area_lookup=area_lookup)
        return
    if worldgen_split_batches() and len(batch) > 1:
        mid = len(batch) // 2
        log.info("AI worldgen: batch failed, splitting %d NPCs", len(batch))
        _enrich_npc_batch(batch[:mid], city_name=city_name, area_lookup=area_lookup)
        _enrich_npc_batch(batch[mid:], city_name=city_name, area_lookup=area_lookup)
        return
    if len(batch) == 1:
        area = area_lookup(batch[0].get("area", ""), "unknown district")
        _enrich_npc_one(batch[0], city_name=city_name, area_name=area)


def select_npcs_for_enrichment(npcs, institutions, limit):
    """
    Prioritize institution leaders/members, then fill to limit with other alive NPCs.
    limit 0 means enrich everyone alive.
    """
    alive = [n for n in npcs.values() if n.get("status") == "alive"]
    if limit <= 0 or len(alive) <= limit:
        return alive

    priority_ids = []
    seen = set()
    for inst in (institutions or {}).values():
        leader = inst.get("leader")
        if leader and leader not in seen:
            priority_ids.append(leader)
            seen.add(leader)
        for mid in list((inst.get("members") or {}).keys()):
            if mid not in seen:
                priority_ids.append(mid)
                seen.add(mid)
            if len(priority_ids) >= limit:
                break
        if len(priority_ids) >= limit:
            break

    for n in alive:
        if n.get("key_npc") and n["id"] not in seen:
            priority_ids.append(n["id"])
            seen.add(n["id"])
        if len(priority_ids) >= limit:
            break

    ordered = [npcs[nid] for nid in priority_ids if nid in npcs]
    rest = [n for n in alive if n["id"] not in seen]
    random.shuffle(rest)
    ordered.extend(rest)
    return ordered[:limit]


def enrich_npc_population(npcs, areas, city_name="", institutions=None):
    if not ai_worldgen_enabled() or not npcs:
        return

    def lookup(area_id, default=""):
        area = (areas or {}).get(area_id) if isinstance(areas, dict) else None
        if isinstance(area, dict):
            return area.get("name", default)
        return default

    limit = npc_enrich_limit()
    to_enrich = select_npcs_for_enrichment(npcs, institutions, limit)
    batch_sz = npc_batch_size()
    total = len(to_enrich)
    if total < len([n for n in npcs.values() if n.get("status") == "alive"]):
        log.info(
            "AI worldgen: enriching %d / %d NPCs (cap AISTORY_AI_WORLDGEN_NPC_LIMIT=%s)",
            total, len(npcs), limit,
        )

    batches = [to_enrich[i:i + batch_sz] for i in range(0, total, batch_sz)]
    workers = min(worldgen_parallel_workers(), len(batches)) if batches else 1

    if workers <= 1:
        for i, chunk in enumerate(batches):
            log.info(
                "AI worldgen: enriching NPCs %d-%d / %d",
                i * batch_sz + 1, min((i + 1) * batch_sz, total), total,
            )
            _enrich_npc_batch(chunk, city_name=city_name, area_lookup=lookup)
        return

    log.info("AI worldgen: enriching %d NPCs in %d parallel batches", total, len(batches))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_enrich_npc_batch, chunk, city_name=city_name, area_lookup=lookup): chunk
            for chunk in batches
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as err:
                log.warning("AI worldgen batch failed: %s", err)


def _apply_institution_arc(inst, enriched, arc):
    arc["spec"] = enriched
    arc["title"] = enriched["title"]
    arc["theme"] = enriched.get("theme")
    arc["stages"] = list(enriched["stages"])
    arc["current"] = enriched["stages"][0]
    inst["arc"] = arc


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

    if ai_worldgen_institutions_enabled():
        inst_list = sorted(
            (institutions or {}).values(),
            key=lambda i: len(i.get("members") or {}),
            reverse=True,
        )
        for inst in inst_list[:institution_enrich_limit()]:
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

    enrich_npc_population(npcs, areas, city_name=city_name, institutions=institutions)

    log.info("AI worldgen: narrative enrichment complete")
