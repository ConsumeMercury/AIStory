# AIStory — System Architecture (Reviewer Reference)

**Purpose:** This is the canonical design document for code review, onboarding, and debugging. It describes how every major subsystem works, how data flows between them, and where to look in the codebase.

**Companion docs:**
- `NOTES.md` — operational quick reference (limits, run commands, NPC AI tables)
- `system/rules.md` — world/genre rules for content generation
- `tests/` — behavioral contracts (370+ pytest cases)

**Last aligned with codebase:** commit series through memory immersion + token optimizations (`memory_immersion.py`, `story_orchestrator.py`, unified `memory_record.py`).

---

## Table of contents

1. [Central design principle](#1-central-design-principle)
2. [Repository map](#2-repository-map)
3. [Entry points and runtime](#3-entry-points-and-runtime)
4. [Persistence and concurrency](#4-persistence-and-concurrency)
5. [The player turn (full pipeline)](#5-the-player-turn-full-pipeline)
6. [Action interpretation](#6-action-interpretation)
7. [Scene assembly](#7-scene-assembly)
8. [Story layer: stakes, arcs, orchestrator](#8-story-layer-stakes-arcs-orchestrator)
9. [Memory system (complete)](#9-memory-system-complete)
10. [Narrator and prompt assembly](#10-narrator-and-prompt-assembly)
11. [Validation, regen, and fact tags](#11-validation-regen-and-fact-tags)
12. [Background simulation](#12-background-simulation)
13. [Social systems: relationships, emotions, beliefs, reputation](#13-social-systems-relationships-emotions-beliefs-reputation)
14. [Events, importance, consequences, archive](#14-events-importance-consequences-archive)
15. [Observability and boundary tracing](#15-observability-and-boundary-tracing)
16. [Environment variables](#16-environment-variables)
17. [Reviewer checklist: trace one turn](#17-reviewer-checklist-trace-one-turn)

---

## 1. Central design principle

AIStory is **simulation-first, narration-second**.

| Layer | Language | Owns |
|-------|----------|------|
| **Simulation** | Python | Who is present, what happened mechanically, memory, relationships, stakes, cast, place |
| **Narration** | Gemini | Literary prose, voice, dialogue phrasing, atmosphere |
| **Validators** | Python | Contract between simulation truth and generated text |

**Invariant:** Cast, location, combat outcomes, and memory are decided in Python **before** Gemini runs. Validators + `regen_governor` constrain prose when the model drifts. Background sim mutates the same JSON stores between player turns.

If prose says an NPC remembers you but `relationships.json` and `npc_memories.json` show no history, that is a bug — not a design choice.

---

## 2. Repository map

```
AIStory/
├── src/main.py              CLI entry: bootstrap, game loop
├── api/server.py            FastAPI web UI backend
├── ui/                      Frontend (app.js, index.html)
├── game/
│   ├── bootstrap.py         Async world bootstrap for UI
│   ├── setup.py             ensure_world_data()
│   ├── state_context.py     state_lock()
│   └── undo.py              Undo snapshots
├── simulation/              Core game engine (most review time here)
│   ├── story_loop.py        ★ Player turn orchestration
│   ├── simulation_runner.py ★ Background world tick
│   ├── story_orchestrator.py  Beat planning (prepare/finalize)
│   ├── memory_record.py     ★ Unified memory write per beat
│   ├── memory_immersion.py  ★ Subjective memory, callbacks, gossip
│   ├── memory_index.py      Unified memory retrieval
│   ├── memory_context.py    Narrator MEMORY block assembly
│   ├── narrator.py          Prompt assembly + generate_scene
│   ├── narrator_blocks.py   Kind-aware section gating
│   ├── action_interpreter.py Regex action parsing
│   ├── action_classifier.py  Optional LLM classifier
│   ├── scene_state.py       Authoritative scene snapshot
│   ├── scene_cast.py        Focal NPC selection
│   ├── fact_gate.py         Post-prose validation gate
│   ├── regen_governor.py    Prose retry budget
│   ├── importance_router.py Universal importance scoring
│   ├── event_archiver.py    Hot log → archive batches
│   ├── sim_tiers.py         Hierarchical NPC sampling
│   └── … (see sections below)
├── generation/              One-time procedural world gen
├── storage.py               Atomic JSON load/save
├── tests/                   Pytest suite
├── ARCHITECTURE.md          ← You are here
└── NOTES.md                 Operational reference
```

---

## 3. Entry points and runtime

### CLI (`src/main.py`)
- `bootstrap_world()` if JSON missing
- Starts `simulation_runner.start()`
- Loop: `process_player_action(input)` from stdin

### Web UI (`api/server.py` + `ui/app.js`)
- `POST /api/action` → `process_player_action(text)`
- `POST /api/action/stream` → same with `on_prose_chunk` for token streaming
- `GET /api/state` → `simulation/ui_state.py:get_full_state()`
- Debug (requires `AISTORY_DEBUG=1`): `/api/debug/last-turn`, `/api/debug/boundary`

### Background sim (`simulation/simulation_runner.py`)
- Daemon thread `aistory-sim`, `TICK_INTERVAL = 30` seconds
- `_current_tick` incremented each tick; exposed via `get_current_tick()`
- **Paused during player turns:** `story_loop._exclusive_player_turn()` calls `simulation_runner.stop()` before the turn and `start()` after

---

## 4. Persistence and concurrency

### Storage (`storage.py`)
All simulation state is JSON on disk. Reads/writes use `load(path, default)` and `save(path, data)` with atomic replace (temp file + `os.replace`).

### Primary files

| Path | Contents |
|------|----------|
| `player/player.json` | Stats, journal, scene_cast, scene_stakes, goals, cases, boundary history, beat_memory_log, narrative_memories, causal_links, reputation |
| `world/world_state.json` | Clock, weather, `information_packets[]` |
| `world/areas.json` | Districts, storylines, tension, prosperity |
| `world/locations.json` | Cities |
| `world/institutions.json` | Orgs + institutional_memory |
| `world/factions.json` | Faction definitions |
| `characters/npcs.json` | NPC records: traits, emotions, beliefs, secrets, schedule |
| `characters/relationships.json` | Directed relationship graph |
| `characters/npc_memories.json` | Per-NPC episodic memory (valence, salience) |
| `characters/_mem_state.json` | Cursor for event→memory processing |
| `events/event_log.json` | Hot append-only event log |
| `events/event_archive.json` | Batched archives (low-importance events) |
| `rumors/rumors.json` | Active rumor pool |
| `system/config.json` | `max_npcs_per_tick`, feature flags |

**Runtime saves from playtests are not committed** — they mirror this layout locally.

### Concurrency
- `game/state_context.py:state_lock()` — reentrant lock around most mutations
- `simulation/locks.py:get_action_turn_lock()` — one player action at a time
- Sim thread and player turn never write concurrently (sim stopped during turns)

---

## 5. The player turn (full pipeline)

**Public API:** `simulation/story_loop.py:process_player_action(action, on_prose_chunk=None)`

**Core:** `_process_player_action_core()` — ~1600 lines; this is the spine reviewers should read first.

### Phase diagram

```
┌─────────────────────────────────────────────────────────────┐
│ _exclusive_player_turn() — stop sim, acquire action lock    │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ try_meta_command() → return if /stats, /help, /bonds, …     │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ state_lock: load JSON, push_undo_snapshot()                 │
│ log_event("player_action") — NO embedding here (deduped)      │
│ sync_all_pipelines(), nudge_stale_district_tension()          │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ assemble_scene_state() — bootstrap scene before interpret     │
│ resolve pending_target_clarification if any                   │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ interpret_action() — regex + optional LLM classifier          │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Kind mechanics: travel, approach, find, investigate, combat,  │
│ trade, wait, schedules, skill checks, faction/institution     │
│ apply_player_action_relationship() for non-attack targets     │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ prepare_beat() — story_orchestrator: stakes, beat_plan,       │
│ memory_query, scene_plan, sim_priorities, memory_callback     │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ _refresh_scene(persist=True); select_scene_cast()             │
│ → focus_npcs, crowd_note, focal_id                            │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ log_event("player_interaction"); record_beat_outcome()        │
│ emit_from_player_beat(); build_reputation_layers()            │
│ Build immersion (gated), hard_constraints, fact blocks      │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ _generate_scene_with_validation() → narrator.generate_scene   │
│ validate → regen_governor → optional retry                    │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ strip_narrator_facts(); append journal + boundary snapshot    │
│ finalize_beat(); trim_journal(); maybe_archive_events()       │
│ record_turn(); persist_boundary_trace()                       │
└─────────────────────────────────────────────────────────────┘
```

### Key functions by phase

| Phase | Module | Function |
|-------|--------|----------|
| Interpret | `action_interpreter.py` | `interpret_action()` |
| Classify | `action_classifier.py` | `apply_classifier_to_ctx()` |
| Plan | `story_orchestrator.py` | `prepare_beat()` |
| Cast | `scene_cast.py` | `select_scene_cast()` |
| Write memory | `memory_record.py` | `record_beat_outcome()` |
| Retrieve memory | `memory_index.py` | `retrieve_memories_for_beat()` |
| Generate | `narrator.py` | `generate_scene()` → `assemble_scene_prompt()` |
| Validate | `fact_gate.py` | `validate_turn_output()` |
| Regen | `regen_governor.py` | `apply_regen_governor()` |
| Finalize | `story_orchestrator.py` | `finalize_beat()` → `propagate_causal_pressure()` |

### Opening scene
`generate_opening_scene()` → if journal empty, runs `process_player_action("look around")`.

---

## 6. Action interpretation

Three layers; output is always validated against `action_vocab.VALID_ACTION_KINDS`.

### Layer 1 — Regex (`action_interpreter.py`)
- Ordered `_PATTERNS` → `kind` (first match)
- `_target_hint()` — name, role, pronoun, descriptor from present cast
- `extract_player_speech()` — quoted dialogue, wh-questions
- Produces `action_ctx` with: `kind`, `target_id`, `player_speech`, `memory_tag`, `story_directive`, stamina/skill hints

### Layer 2 — LLM classifier (`action_classifier.py`)
Env: `AISTORY_ACTION_CLASSIFIER` = `off` | `shadow` | `on`

| Function | Role |
|----------|------|
| `needs_llm_classifier()` | When regex alone is insufficient |
| `classify_action_llm()` | Gemini JSON: kind, target_id, player_speech |
| `validate_classifier_result()` | Reject invented cast IDs |
| `apply_classifier_to_ctx()` | Apply or log diff (`boundary_classifier`) |

**Fast-path skips** (`action_vocab.FAST_PATH_KINDS`): attack, travel, approach, wait, etc. when target resolved or (approach/travel) subplace resolved.

### Layer 3 — Vocabulary (`action_vocab.py`)
- `VALID_ACTION_KINDS` — authoritative set (~30 kinds)
- `SPEECH_KINDS`, `HIGH_STAKES_KINDS`
- `normalize_kind()` — classifier output gate

### Target ambiguity (`target_ambiguity.py`)
Multiple NPCs match → `pending_target_clarification` → clarification scene (no Gemini scene gen) until player picks.

---

## 7. Scene assembly

### SceneState (`scene_state.py`)
Immutable dataclass — single authoritative snapshot per beat:

```python
SceneState(
  tick, day, hour, time_of_day,
  area_id, subplace_id, place_label,
  area_present,    # all alive NPCs in district
  cast, cast_ids,  # social scene subset (≤ ~6)
  scene_focus, pending_events, constraints
)
```

Built by `assemble_scene_state()` → `resolve_scene_present()` → optional `persist_scene_cast()`.

### Scene population (`scene_population.py`)
- **Sticky cast** across continuation beats (same area/subplace)
- `should_reset_scene_cast()` on travel, relocation, subplace change
- `player.scene_cast` keyed by area + subplace

### Scene cast selection (`scene_cast.py`)
Returns `(focus_npcs, crowd_note, focal_id)` for narrator.

- Scores via `importance_router.score_npc()` + `beat_plan.priority_npc_ids`
- `_continuation_focal_npc()` keeps conversation partner for talk/ask_about/etc.
- **Approach/relocation:** clears prior cast; `left_behind_cast` populated (`scene_coherence.mark_scene_relocation`)

Narrator receives **one focal NPC** (+ optional crowd note). Simulation decides `focal_id`; model must not invent a different focus.

### Scene coherence (`scene_coherence.py`)
| Function | Role |
|----------|------|
| `sync_scene_focus()` | Focus NPC must be in cast |
| `resolve_target_and_absence()` | Target not present → `absent_npc` directive |
| `resolve_travel_destination()` | Travel text → area graph |
| `mark_scene_relocation()` | Subplace move: clear focus, left_behind |
| `build_conversation_ledger()` | Recent dialogue for continuity |
| `place_label()` | Human place string |

---

## 8. Story layer: stakes, arcs, orchestrator

### Story manager (`story_manager.py`)
- `sync_all_pipelines()` — align starting pipeline ↔ area storylines
- `get_primary_arc()` — merge investigation case, starting pipeline, area storyline
- **`record_turn_story_progress()`** — sets `player.scene_stakes` each meaningful beat:
  - `dramatic_question`, `gain`, `lose`, `purpose`
  - Bumps district tension; may advance arc stage
- `beat_obligation_directive()` — narrator obligation text
- `build_story_manager_block()` — ACTIVE STORY prompt section
- `npc_simulation_weights()` — background sim prioritization

### Story orchestrator (`story_orchestrator.py`)

**`prepare_beat()`** (pre-narration):
1. `record_turn_story_progress()`
2. `build_memory_query()` — arc + stakes + promises + focal name → retrieval query (≤400 chars)
3. `build_scene_plan()` — intent, must_surface, structure_hint, obligation
4. `pick_memory_callback()` — one salient past detail (`memory_immersion.py`)
5. `build_sim_priorities()` → persisted on player; drives rumor threshold + sim weights

Writes `action_ctx["beat_plan"]` and `action_ctx["story_orchestrator"]` metrics.

**`finalize_beat()`** (post-prose):
- `narrative_causality.propagate_causal_pressure()` — district tension, beliefs, delayed hooks
- Stores `player.last_beat_plan`

### Scene objectives (`scene_objectives.py`)
Translates stakes + beat_plan into SCENE OBJECTIVES block:
- Purpose, emotion, dramatic question, gain/lose
- `must_surface` bullets (arc beats, open promises)
- Memory callback line (one woven detail)

### Regen governor (`regen_governor.py`)
**Not story stakes** — prose retry budget:
- `VIOLATION_PRIORITY`: death/speaker/location > narrative issues
- `max_regen_attempts()` from `AISTORY_PROSE_RETRIES` (default 1)
- Exhausted → `player.delayed_directives`

---

## 9. Memory system (complete)

Memory is **multiple derived stores**, unified at **write** (`record_beat_outcome`) and **read** (`retrieve_memories_for_beat` + `build_memory_context`).

### 9.1 Store map

| Store | Location | Written by | Read by |
|-------|----------|------------|---------|
| Hot events | `events/event_log.json` | `log_event`, sim | retrieval, rumors, archiver |
| NPC episodic | `characters/npc_memories.json` | `record_player_action`, `process_memories`, gossip | `player_memories`, `memory_behavior`, reputation |
| Beat log | `player.beat_memory_log` | `_append_beat_memory_record` | retrieval, callbacks |
| Narrative layer | `player.narrative_memories` | `record_beat_narrative_memory` | memory_context, consolidation |
| Causal links | `player.causal_links` | `record_from_beat` | causality block, memory query |
| Journal | `player.journal` | post-turn append | journal blocks, retrieval |
| Embeddings | player vector cache | `ingest_event_vector` (once per interaction) | optional semantic rank |
| NPC object | `npc.emotions`, `beliefs`, `claimed_memories` | target on beat | focal blocks, sim |
| Rumors | `rumors/rumors.json` | rumor_engine, memory gossip | whispers, reputation |
| Info packets | `world.information_packets` | player beats, gossip propagation | social whispers |

### 9.2 Write path — `record_beat_outcome()` (`memory_record.py`)

Called from `story_loop.py` after `log_event("player_interaction")`.

```
record_beat_outcome()
  ├─ record_player_action()           → npc_memories.json (witnesses + target)
  ├─ score_event + ingest_event_vector (interaction event only — not player_action)
  ├─ record_beat_narrative_memory()   → narrative_memories (importance threshold)
  ├─ record_from_beat()               → causal_links
  ├─ _append_beat_memory_record()     → beat_memory_log (cap 120, importance-sorted)
  ├─ target NPC: emotions_from_beat, drift_from_beat, record_beat_memory, beliefs
  ├─ reinforce_target_relationship()    → extra relationship on high-stakes tags
  ├─ update_witness_beliefs()         → up to 2 witnesses
  ├─ maybe_append_gossip_rumor()        → rumors.json if salience high
  ├─ propagate_social_memory_gossip()   → information_packets via ally circle
  ├─ absorb_npc_memories_into_reputation() → reputation_profile
  └─ record_from_player_action()        → institution memory
```

Also sets `player.last_tick = tick` for decay scoring.

### 9.3 Per-NPC subjective memory (`npc_memory_engine.py`)

Each entry:
```python
{
  "tick", "day", "summary", "valence", "salience",
  "participants", "location", "source", "about_player"
}
```

**Target POV:** `"I remember when the outsider {action_snip}"` — not a shared world log.

**Witnesses:** diluted valence (×0.35), lower salience.

**Write decay:** `_decay_and_trim()` — salience × 0.984 per processing; drop below 6.0; cap 28/NPC.

**Behavior:** `memory_behavior(npc_id)` → narrator directive (hostile/guarded/warm/stranger) wired in `narrator._npc_line()`.

### 9.4 Salience-weighted retrieval (`memory_immersion.py`, `memory_index.py`)

```python
effective_salience = salience × (0.984 ^ ticks_elapsed) × (1 + |valence| × 0.35)
score_at_retrieval   = importance × recency_decay × emotional_boost
```

**Surface caps** (`surface_memory_limit`):
- Routine beats: **2** memories injected
- investigate / accuse / find / search: **3**

Merge in `retrieve_memories_for_beat()`:
1. Event/journal hits (`memory_retrieval.get_relevant_memories`)
2. Narrative memories (top by score)
3. Focal NPC subjective memories (when `focal_npc_id` set)
4. Beat log candidates (decay-scored)

Dedup by text prefix; sort by `score_at_retrieval`; return top N.

Query enrichment: `beat_plan.memory_query` from orchestrator (arc + stakes + promises).

Optional: `memory_embeddings.rank_by_embedding()` unless `AISTORY_SKIP_SEMANTIC_MEMORY=1`.

### 9.5 Memory context block (`memory_context.py`)

Assembled under token budget (`memory_budget.py`):

| Slot | Content | Eviction |
|------|---------|----------|
| `memory_callback` | One past detail to echo | **Pinned** |
| `focal_npc_memory` | 1–2 subjective POV lines | **Pinned** |
| `narrative_memory` | Story-meaning summaries | Medium |
| `social_whispers` | Arrived information_packets | Low |
| `recent_journal` | Last beats | Medium |
| `distant_history` | Compacted older context | Evictable |
| `retrieved_events` | World echoes | Evict first |

`build_memory_trace()` → `action_ctx["memory_trace"]` for boundary metrics.

### 9.6 Memory → consequences (not just prose)

| Mechanism | Module | Effect |
|-----------|--------|--------|
| Relationship nudge | `reinforce_target_relationship` | Extra trust/fear on attack/help/threat/etc. |
| Witness beliefs | `update_witness_beliefs` | Lighter propositions for bystanders |
| Reputation profile | `absorb_npc_memories_into_reputation` | NPC valence → violent/merciful/heroic axes |
| Narrator behavior | `memory_behavior` | Focal NPC manner from top memory |
| Sim action bias | `rumor_behavior.rumor_action_bias` | Weights from memory+rumor profile |
| Emotion bias | `npc_emotions.emotion_action_bias` | Transient emotions → sim |
| Gossip | `maybe_append_gossip_rumor`, `propagate_social_memory_gossip` | Rumors + packets spread through social graph |

**Realness test:** NPC prose tone, relationship dimensions, and reputation should align after repeated interaction.

### 9.7 Gossip propagation (three channels)

1. **Sim events → `rumor_engine.spread_rumors()`** — importance-gated distorted text
2. **Player beats → `information_packets.emit_from_player_beat()`** — attack/accuse/confess/blackmail/help
3. **Salient NPC memory → rumor + packet** (`memory_immersion`) — high salience + emotional weight; ally circle hears whispers

Arrived packets: `packets_as_rumor_whispers()` in memory block.

### 9.8 Journal retention (`journal_retention.py`)
Not naive `journal[-300:]`. `trim_journal()`:
- Cap 300 total; always keep last 40
- Older entries ranked by `score_journal_entry()`; keep highest-importance remainder

---

## 10. Narrator and prompt assembly

### Protocol (`narrator_protocol.py`)
`get_narrator()` → wrapper calling `narrator.generate_scene()`.

### `assemble_scene_prompt()` (`narrator.py`)
Builds ~30 sections → filtered by `narrator_blocks.join_sections()`.

**Profile:** `AISTORY_NARRATOR_BLOCKS` = `full` | `standard` | `minimal`

**Section order** (`narrator_blocks.SECTION_ORDER`):
```
arbitration → craft_core → narrative_thread → story_manager → scene_objectives →
story_graph → prose_structure → craft_kind → length → scene_mode → continuity →
narrative_continuity → causality → promises → culture → economy → world_pressure →
memory → conversation_ledger → known_places → place_lock → scene_facts → setting →
local_arc → scene_event → name_rule → protagonist → this_beat → extra_directive →
npc_context → focal_beliefs → focal_emotion → social_circle → institution_memory →
secret_pressure → avoid_repeat → reputation → entropy → guardrails → immersion →
hard_constraints → closing
```

**Kind-gated omissions** (`_STANDARD_OMIT` + rules in `should_include_block()`):
- `approach` — drops immersion, causality, reputation, focal beliefs, etc.
- `attack` — drops culture, economy, promises
- `structure_hint=continuation` without focal — drops story_manager, causality, promises

**Immersion block:** built in `story_loop._immersion_block()` only when `should_include_block("immersion")` is true (token optimization).

**Generation params:** `novel_craft.py` — temperature, frequency_penalty, max output tokens per kind.

**Directive arbitration:** `directive_validator` → `arbitrate_prompt()` when HARD CONSTRAINTS conflict with story directives.

### Token optimizations (safe)
- Duplicate embedding removed from turn-start `player_action` (single embed on interaction event)
- Classifier fast-path for approach/travel with resolved subplace
- Tighter memory retrieval caps (see §9.4)
- Block gating via `narrator_blocks` + structure_hint

---

## 11. Validation, regen, and fact tags

### Flow (`story_loop._generate_scene_with_validation()`)

```
generate_scene (attempt 0)
  → validate_turn_output()           [fact_gate.py]
       ├─ validate_scene_prose()     [prose_validator.py]
       ├─ parse/validate narrator_facts
       └─ run_prose_audit()          [prose_auditor.py]
  → validate_narrative_function()    [narrative_trace.py]
  → apply_regen_governor()
  → if retry: correction blocks → regenerate (no stream)
  → if exhausted: queue delayed_directives
  → build_output_boundary() + validator_chain trace
```

### Validator registry (`validator_chain.py`)

| Validator | Mode | Gates regen |
|-----------|------|-------------|
| prose_validator | hard | yes |
| narrator_facts | hard | yes |
| fact_gate | hard | yes |
| prose_auditor | shadow\|on | yes |
| narrative_trace | soft | yes |
| directive_validator | arbitrate | no |
| regen_governor | budget | no |

### Fact tags (`narrator_facts.py`)
Model emits structured tags: `[SPEAKING]`, `[DEATH]`, `[PLACE]`, `[SCHEDULE]`, etc. Validated against simulation; stripped from player-visible text via `strip_narrator_facts()`.

### Regen governor priorities
Death/speaker/location violations beat narrative softness. Max attempts: `AISTORY_PROSE_RETRIES` (default 1).

---

## 12. Background simulation

### Tick order (`simulation_runner._run_tick()`)

```
1.  simulate_npcs(tick)              — sim_tiers hierarchical sample
2.  maintain_monsters()
3.  apply_npc_consequences(tick)
4.  advance_districts(tick)
5.  process_leadership_succession()
6.  run_faction_tick(tick)
7.  update_relationships()           — ambient drift
8.  apply_memory_effects()           — trait nudges from events
9.  spread_rumors()
10. spread_rumor_beliefs()
11. advance_storylines(tick)
12. flush_events()
13. process_pending()                — consequence_queue
14. seed_legacy_rumors, maybe_goal_rumor
15. maybe_consolidate_player_memories()
16. advance_information_packets()
17. decay_all_npcs(), tick_secret_exposure, apply_pressure_to_world
18. rival_tick()
19. process_memories()               — event log → NPC episodic
```

Player turn calls `simulation_runner.stop()` before and `start()` after — no concurrent writes.

### Sim tiers (`sim_tiers.py`)
| Tier | Scope | Budget |
|------|-------|--------|
| 1 | Player district | ~55% |
| 2 | Same city | ~30% |
| 3 | Distant | ~15% + abstract regional pulse |

`build_sim_priorities()` (from orchestrator) boosts arc key NPCs and scene_focus.

### NPC actions (`npc_actions.py`)
`choose_action()` — weighted random from traits, role, schedule, memory bias, storyline, emotions, rumors, social circle, weather, co-location.

Config: `system/config.json` → `max_npcs_per_tick` (default ~10).

### Rumors (`rumor_engine.py`)
Recent events → distorted rumor text. Gated by `importance_router.score_event()` vs `rumor_spread_threshold(sim_priorities)`.

### Information packets (`information_packets.py`)
Physical news hops between neighboring areas each tick with credibility decay. Surfaced in narrator via memory social whispers.

---

## 13. Social systems: relationships, emotions, beliefs, reputation

### Relationships (`relationship_engine.py`)
`relationships[actor_id][toward_id]`:
```
trust, respect, fear, affection, attraction, resentment, rivalry, obligation,
familiarity, interactions
```

**Familiarity gates** bond movement: `gate = 0.15 + 0.85 × min(1, familiarity/60)`.

**Discrete:** `apply_player_action_relationship()` on player beats (non-attack).  
**Ambient:** `update_relationships()` each sim tick.

### Emotions (`npc_emotions.py`)
Transient `npc.emotions`: anger, fear, joy, grief, stress.
- `emotions_from_beat()` on target NPC
- `decay_all_npcs()` each sim tick
- `focal_emotion_block()` → narrator

### Beliefs (`belief_model.py`)
`npc.beliefs[]`: `{proposition, confidence, source, grounding, tick}`  
Grounding: witnessed > rumored > inferred.  
Updated from events, rumors, witness memories.

### Reputation
| Module | Scope |
|--------|-------|
| `player_reputation.build_reputation_profile()` | violent/merciful/honorable/greedy/suspicious/heroic |
| `reputation_layers.build_reputation_layers()` | local/faction/institution/world ambient text |
| `memory_immersion.absorb_npc_memories_into_reputation()` | NPC episodic → profile axes |

---

## 14. Events, importance, consequences, archive

### Event logger (`event_logger.py`)
- `log_event()` — buffered append with importance
- `flush_events()` — disk write; may trigger archive
- `all_events()` — read hot log + buffer for narrator retrieval

### Importance router (`importance_router.py`)
Central scoring: `score_event`, `score_rumor`, `score_npc`, `score_memory_record`, `score_journal_entry`, `rank_rumors`.

Used by: rumor_engine, memory retrieval, event_archiver, beat_memory_log sort, journal retention.

### Event archiver (`event_archiver.py`)
When hot log > `AISTORY_EVENT_HOT_CAP` (default 2500):
- Archive low-importance, non-rumor-linked events → `events/event_archive.json`
- Triggered from story_loop + flush path

### Consequence cascade (`consequence_cascade.py`)
- Fatal combat → district shock + `consequence_queue`
- High-importance causal links → delayed hooks

### Narrative causality (`narrative_causality.py`)
- `record_from_beat()` on memory write
- `propagate_causal_pressure()` in `finalize_beat()`
- `causality_narrator_block()` in prompts

---

## 15. Observability and boundary tracing

### Turn trace (`turn_trace.py`)
`record_turn()` — in-memory last turn. Ring buffer if `AISTORY_BOUNDARY_HISTORY` set.

### Boundary metrics (`boundary_metrics.py`)
| Function | Role |
|----------|------|
| `build_output_boundary()` | Facts, regen, auditor post-validation |
| `build_turn_boundary()` | Classifier + output + **memory_trace** |
| `tag_turn_issues()` | Issue shapes via bug_ledger |
| `persist_boundary_trace()` | Journal.boundary + player history |

### Per-turn observability payloads on `action_ctx`

| Key | Source |
|-----|--------|
| `beat_plan` | story_orchestrator |
| `story_orchestrator` | memory_query_len, must_surface_count |
| `memory_trace` | callback_preview, focal_preview |
| `narrator_blocks_included` | narrator_blocks.list_included_blocks |
| `prompt_profile` | est_tokens, top modules |
| `validator_chain` | per-validator issue counts |
| `boundary_classifier` | classifier diff |
| `narrative_trace` | stakes/arc validation |

### Debug API (`AISTORY_DEBUG=1`)
- `GET /api/debug/last-turn`
- `GET /api/debug/boundary`

---

## 16. Environment variables

| Variable | Subsystem | Values |
|----------|-----------|--------|
| `GEMINI_API_KEY` | All LLM calls | required |
| `AISTORY_ACTION_CLASSIFIER` | Action interpret | off / shadow / on |
| `AISTORY_NARRATOR_BLOCKS` | Prompt gating | full / standard / minimal |
| `AISTORY_PROSE_RETRIES` | Regen governor | int, default 1 |
| `AISTORY_NARRATIVE_REGEN` | Narrative trace regen | off / shadow / soft / on |
| `AISTORY_PROSE_AUDITOR` | Deferred auditor | shadow / on |
| `AISTORY_SKIP_SEMANTIC_MEMORY` | Embeddings | 1 to disable |
| `AISTORY_SKIP_MEMORY_BUDGET` | Memory trim | 1 to disable |
| `AISTORY_EVENT_HOT_CAP` | Event archiver | int, default 2500 |
| `AISTORY_DEBUG` | Debug API | 1 |
| `AISTORY_DEBUG_TOKENS` | Prompt profiler | 1 |
| `AISTORY_BOUNDARY_HISTORY` | Turn ring buffer | int |

---

## 17. Reviewer checklist: trace one turn

To verify a change does not break the simulation/narration contract:

1. **`api/server.py` or `src/main.py`** → entry
2. **`story_loop.process_player_action`**
3. **`action_interpreter.interpret_action`** — kind/target/speech
4. **`story_orchestrator.prepare_beat`** — beat_plan, memory_query
5. **`scene_cast.select_scene_cast`** — focal_id, cast
6. **`memory_record.record_beat_outcome`** — all memory side effects
7. **`memory_index.retrieve_memories_for_beat`** — read path
8. **`memory_context.build_memory_context`** — MEMORY block
9. **`narrator.assemble_scene_prompt`** + **`narrator_blocks.join_sections`**
10. **`fact_gate.validate_turn_output`** + **`regen_governor.apply_regen_governor`**
11. **`story_orchestrator.finalize_beat`** — causal propagation
12. **Journal entry** — boundary snapshot present

For background life: **`simulation_runner._run_tick`** → **`npc_actions.simulate_npcs`**.

For memory immersion specifically:
- Write: `memory_record.record_beat_outcome` → `npc_memory_engine.record_player_action`
- Read: `memory_immersion.pick_memory_callback` + `subjective_memory_lines`
- Trace: `action_ctx["memory_trace"]` in boundary output

For Tier 1 architecture (director + propagation + unified record):
- Canonical record: `memory_schema.build_memory_record` → `player.beat_memory_log`
- Director: `narrative_director.plan_director_beat` inside `prepare_beat`
- Consequences: `consequence_propagation.propagate` via `consequence_cascade`
- Trace: `action_ctx["director_plan"]`, `action_ctx["consequence_trace"]`

---

## 18. Tier 1 modules (implemented)

| Module | Role |
|--------|------|
| `memory_schema.py` | Canonical `MemoryRecord` on beat log with emotional/narrative/social/causal weights |
| `narrative_director.py` | Pacing, callback scheduling, dialogue intents before Gemini |
| `consequence_propagation.py` | Template-driven effect chains (district, institution, hooks, delayed queue) |

### Unified memory record
`build_memory_record()` writes to `beat_memory_log` with:
```python
{id, tick, kind, fact, participants, source, grounding,
 emotional_weight, narrative_weight, social_weight, causal_weight, ...}
```
Derived stores (npc_memories, narrative_memories, rumors) remain projections; retrieval uses `combined_retrieval_score()`.

### Narrative Director
`plan_director_beat()` sets:
- `pacing_mode`: breathe | orient | continuation | advance | complicate | revelation
- `dialogue_intents[]`: goal, stance, withhold (pre-Gemini)
- Schedules `memory_callback` sparingly (not every beat)
- Trims `must_surface` on breathe beats

### Consequence propagation
Templates: `fatal_kill_merchant`, `fatal_kill_authority`, `fatal_kill_generic`, `causal_ripple`

Merchant death chain example:
```
district shock → delayed trade_disruption → guild standing −12 →
area flags (trade_disrupted) → emergent_hook (trade_vacuum) → story_flag
```

`action_ctx["consequence_trace"]` records template + step results for boundary review.

---

## 19. Roadmap (future tiers)

| Tier | Focus | Status |
|------|-------|--------|
| **1** | Narrative Director, Scene Planner (dialogue intents), Consequence Propagation | **Partial — shipped v0** |
| **2** | Full unified memory (single index, projection-only derived stores), NPC Goal Planner, Long-Term Arc Tracker | Planned |
| **3** | Simulation LOD at scale, economic network, political layer | Planned |
| **4** | Dynamic theme engine, callback scheduler UI, emergent quest generator | Planned |

---

## System connection diagram

```
                    ┌──────────────┐
                    │  Player UI   │
                    │ CLI / Web    │
                    └──────┬───────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   story_loop.py        │
              │   (player turn spine)    │
              └─────────┬──────────────┘
                        │
     ┌──────────────────┼──────────────────┐
     ▼                  ▼                  ▼
┌─────────┐    ┌──────────────┐   ┌─────────────┐
│ interpret│    │ prepare_beat │   │ mechanics   │
│ + classify│   │ orchestrator │   │ combat/travel│
└────┬────┘    └──────┬───────┘   └──────┬──────┘
     │                │                   │
     └────────────────┼───────────────────┘
                      ▼
            ┌──────────────────┐
            │ record_beat_outcome │
            │ memory_record.py    │
            └─────────┬─────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
   npc_memories  beat_memory_log  beliefs/emotions
         │            │            │
         └────────────┼────────────┘
                      ▼
            ┌──────────────────┐
            │ retrieve + context│
            │ memory_index      │
            │ memory_context    │
            └─────────┬─────────┘
                      ▼
            ┌──────────────────┐
            │ narrator.py       │──────► Gemini
            │ assemble_prompt   │
            └─────────┬─────────┘
                      ▼
            ┌──────────────────┐
            │ validators + regen│
            └─────────┬─────────┘
                      ▼
            journal + finalize_beat

   Parallel (every 30s, paused during turns):
   simulation_runner → npc_actions, rumors, relationships,
                       information_packets, process_memories
```

---

*When updating subsystems, please keep this document in sync — especially §5 (turn pipeline), §9 (memory), §11 (validators), and §12 (sim tick order).*
