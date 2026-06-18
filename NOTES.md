# AIStory — Architecture & Systems Reference

> **For reviewers and onboarding:** see **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full system design — turn pipeline, memory stack, narrator gating, validation chain, background sim, and data flow diagrams. This file (`NOTES.md`) is a shorter operational companion (limits, run commands, NPC AI tables).

Dark-fantasy text RPG: **Python owns state**, **Gemini writes prose**. This document explains how the pieces fit together, what each system actually does today, and known limits.

---

## Run it

1. `pip install -r requirements.txt`
2. Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from [Google AI Studio](https://aistudio.google.com/apikey)
3. `python src/main.py` — play · `python reset_world.py` — wipe save · `python scripts/smoke_test.py` — offline checks

Optional env: `GEMINI_MODEL`, `GEMINI_MAX_OUTPUT_TOKENS`, `AISTORY_DEBUG_TOKENS=1`

---

## What the project accomplishes

| Layer | Role |
|-------|------|
| **Generation** | One-time procedural world: cities, districts, ~50 NPCs, institutions, storylines, monsters |
| **Background sim** | World advances every ~30s whether you act or not |
| **Player turns** | Input → intent → mechanics → memory → one narrated scene |
| **Narration** | Gemini turns structured context into literary second-person prose |

Design goal: **living novel**, not a game log. Python decides what happened; the model decides how it reads.

---

## High-level flow

```
bootstrap_world()  →  JSON state on disk
simulation_runner  →  background ticks (NPC AI, rumors, storylines, clock, …)
story_loop         →  player turn pipeline
narrator           →  prompt assembly → gemini_client → printed scene
```

**Persistence:** all state in JSON under `world/`, `characters/`, `player/`, `events/`, `rumors/`. Reads/writes go through `storage.py` (atomic saves, safe loads).

---

## Scalability & limits

These numbers are **current defaults**, not theoretical maximums.

| Resource | Limit | Where |
|----------|-------|--------|
| **Total NPCs** | **50** at world gen | `src/main.py` → `generate_population(count=50)` |
| **NPCs simulated per tick** | **10** (random sample of alive) | `system/config.json` → `max_npcs_per_tick` |
| **NPCs per district (named)** | **2 max** | `generation/population_tuning.py` → `MAX_NPCS_PER_AREA` |
| **Monsters (worldwide)** | **~40 cap**, dead pruned | `simulation/bestiary_engine.py` |
| **Memories per NPC** | **28 max**, salience decay | `simulation/npc_memory_engine.py` |
| **Memory forget threshold** | salience &lt; **6.0** dropped | same file, `FORGET_BELOW` |
| **Processed event IDs** | last **3000** tracked | `_mem_state.json` |
| **Rumors** | last **200** | `rumor_engine.py`, `storyline_engine.py` |
| **Player journal** | **300 cap** (importance-ranked trim) | `journal_retention.py` → `trim_journal()` |
| **Event log (hot)** | archived above **2500** | `event_archiver.py`, env `AISTORY_EVENT_HOT_CAP` |
| **Travel background ticks** | max **24** per trip | `travel_engine.py` |
| **Gemini output tokens** | **1200–4800** by action kind; retry at **2×** up to 8192 | `novel_craft.py`, `gemini_client.py` |

**Loaded-area simulation:** there is no full “simulate only where the player is” engine. Each tick randomly samples up to 10 alive NPCs globally. District placement affects **who you meet in scenes**, not who gets ticked.

**Token budgeting (narration):** prompt size is controlled by scene cast (one focal NPC), compressed memories, lighter immersion on dialogue follow-ups, and per-action `max_tokens`. Debug with `AISTORY_DEBUG_TOKENS=1`.

---

## NPC decision layer (`simulation/npc_actions.py`)

This is the heart of background life. Each sim tick, up to `max_npcs_per_tick` alive NPCs each pick **one action** and execute it.

### What an NPC carries into a decision

| Input | Stored on NPC | Effect |
|-------|---------------|--------|
| **Personality** | `traits` (0–100 axes: greed, kindness, courage, paranoia, …) | Weighted into every action |
| **Behavior profile** | `behavior_profile` (social, caution, work, risk, kindness) | Derived from traits at gen time |
| **Role** | `role` (merchant, guard, scholar, …) | `_ROLE_BIAS` adds big bonuses to fitting actions |
| **Long-term goals** | `goals[]` string list | Primary goal (+14 weight to matching action) |
| **Personal objective** | `personal_objective` (specific plot hook) | Narration + future goal bias |
| **Institution stance** | `institution_stance` | Internal politics bias via `institution_politics.py` |
| **Fears** | `fears[]` | Used in generation/persona; **not yet in choose_action weights** |
| **Schedule** | `schedule`, `schedule_label` | Hour-of-day district movement (`npc_schedule.py`) |
| **Player memory** | top episodic memory via `player_memories()` | Negative → hide/socialise down; positive → help/socialise up |
| **Rumor profile** | beliefs from memories + rumors | `rumor_behavior.py` → hide/fight/socialise/trade weights |
| **District storyline** | area `storyline` theme | `storyline_behavior.py` → role-specific action mults + area pull |
| **Weather** | read from `world_state.json` | Storm/snow/fog → hide up, trade/hunt/travel down |
| **Location** | `location` (city key), `area` (district id) | Travel moves between connected cities; social acts need co-located peers |

### Goal representation (NPC)

Goals are **plain strings**, assigned at generation from traits + background hope:

- `"accumulate wealth"`, `"gain power"`, `"help others"`, `"settle an old score"`, `"uncover a secret"`, or background-specific hope, or fallback `"get through the week"`.

`goal_engine.check_goal_progress()` runs after each NPC action:

- **accumulate wealth** → at 500 coin, goal becomes `"maintain wealth"`
- **gain power** → increments progress on `"plan"` actions
- **help others** → increments progress on `"help"` actions

Goals **bias** action weights; personal objectives (`generation/personal_objectives.py`) add specific hooks like “recover stolen ledger” or “avenge brother.”

### Action set & mechanics

Weighted random choice among:

| Action | Typical effect |
|--------|----------------|
| `trade` | NPC wealth +1–10; city wealth/stability up (via consequences_engine) |
| `fight` | brawl; small death chance; city crime up |
| `hunt` | combat vs random monster if any exist |
| `help` / `socialise` | relationship nudge with random co-located NPC |
| `hide` | self-preservation event |
| `plan` / `study` / `craft` | skill XP via `train_from_action`; logged |
| `travel` | move to random connected city |

After action: passive heal (+1 HP, +4 stamina), `last_action` stored, event logged.

### Cross-system inputs (each sim tick)

`choose_action()` now also applies:

- **Storyline pull** — smuggling/crime/heresy themes change weights and can override `area` (merchant avoids docks, guard investigates there)
- **Rumor belief → action** — murderer/hero/thief profiles from `npc_player_rumor_profile()`
- **Institution politics** — member stances (hardline, reform, …) nudge plan/fight/help
- **Player co-location** — `rumor_relationship_nudge()` when player shares a district

### Remaining NPC AI gaps

- **Fears** not yet in action weights
- **Personal objectives** bias narration more than daily AI yet
- **No needs/hunger/sleep** model beyond stamina heal

---

## Interconnected ecosystem (second-pass systems)

These modules close loops between storylines, rumors, factions, and the player.

| Module | Closes the loop |
|--------|-----------------|
| `storyline_behavior.py` | District plot → NPC movement + action weights + narrator texture |
| `rumor_behavior.py` | Belief about player → action weights + relationship nudges |
| `district_state.py` | Events drift district mood/prosperity/crime (`advance_districts` each tick) |
| `institution_politics.py` | Internal stances on guild/temple/garrison members |
| `institution_leadership.py` | Leader death → succession + priority shifts |
| `investigation_cases.py` | Multi-stage mysteries (evidence, suspects, witnesses); `case` command |
| `player_legacy.py` | Notable deeds → long-term rumors + narrator “your legacy” block |
| `faction_reputation.py` | Standing → invitations/ranks (`check_faction_invitations`) |
| `rival_engine.py` | Staged rival (unknown → nemesis) with escalating actions |
| `generation/personal_objectives.py` | Specific NPC plot hooks at world gen / patch |

**Player turn wiring (`story_loop.py`):** immersion blocks from storyline, district mood, politics, active case, and legacy; investigation actions advance cases; faction invites and legacy deeds land in journal.

**Background tick order additions (`simulation_runner.py`):** `advance_districts`, `process_leadership_succession`, `seed_legacy_rumors`.

---

## Relationship model (`simulation/relationship_engine.py`)

Directed graph: `relationships[actor_id][toward_id]` → dimensions **0–100**:

`trust`, `respect`, `fear`, `affection`, `attraction`, `resentment`, `rivalry`, `obligation`, plus **`familiarity`** and `interactions` count.

**Familiarity gates everything.** Strangers move slowly:

```
gate = 0.15 + 0.85 × min(1, familiarity / 60)
delta = per_point_effect × intensity × gate   (capped ±6 per event)
```

### Worked example (NPC → player)

Starting bond after a few meetings:

```
trust: 18   respect: 12   fear: 4   familiarity: 22
```

**You help them** (`kindness`, intensity 1.0):

- familiarity +2.5 → ~25
- gate ≈ 0.50
- trust +0.8 × 1.0 × 0.50 ≈ **+0.4** → trust **18.4**
- affection +0.6 × 0.50 ≈ **+0.3**

**You threaten them** (`threat`, intensity 1.25, failed skill check → intensity × 0.45):

- fear +1.2 × 0.5625 × gate ≈ **+0.5**
- trust −0.8 × … ≈ **−0.3**
- resentment +0.7 × … ≈ **+0.3**

**You attack** (`violence`, 1.5):

- fear +1.6 × 1.5 × gate (up to cap) → large fear/resentment jump, trust crash

Failed charm/intimidate/insult can **backfire** (NPC applies `insult` toward player at reduced intensity).

**Ambient drift** (`update_relationships`, every tick): tiny trust pull toward NPC kindness; fear/resentment/affection decay toward neutral; familiarity fades slowly.

Player-facing view: `bonds` meta-command.

---

## Economy

### Player ↔ NPC (turn-based, real transfers)

`economy_engine.py` on successful **trade** / **give**:

- **Trade success:** player buys random item from NPC inventory at ±15% of value, or haggles 3–12 coin if no item
- **Trade fail:** player loses 2–8 coin
- **Give success:** player loses inventory item (~55%) or 3–15 coin
- All logged to event log; inventories and wealth fields updated

### NPC ↔ world (background)

- NPC `trade` action: personal wealth +1–10 per tick when chosen
- `consequences_engine`: NPC trade raises **city wealth/stability**; fights raise **crime** and lower stability; help raises stability
- Faction `influence` can tick up on NPC `plan` actions

### What economy does **not** do yet

- No dynamic price lists or stock tables per merchant
- No “merchant runs out of goods” simulation
- No institution payroll or wage schedules
- Player theft affects relationships and events, not city GDP directly
- City `wealth` in `locations.json` is a macro stat, not item-level supply

---

## Player turn pipeline (`simulation/story_loop.py`)

See **ARCHITECTURE.md §5** for the full phased pipeline. Summary:

1. Meta-command? → `player_commands.py` (no LLM)
2. Log action → load state; **`prepare_beat()`** before cast (orchestrator)
3. `interpret_action()` → kind, target, speech; optional classifier
4. Travel / combat / trade / skill checks / relationships
5. `select_scene_cast()` → **one focal NPC** (or none for explore)
6. **`record_beat_outcome()`** — unified memory write (see ARCHITECTURE.md §9)
7. `_generate_scene_with_validation()` → Gemini + validators + regen
8. Journal append + **`trim_journal()`** + boundary trace + **`finalize_beat()`**

---

## Narration stack

| Module | Role |
|--------|------|
| `novel_craft.py` | Literary rules, beat types, token budgets |
| `narrator_variety.py` | Anti-repetition, continuity, scene modes |
| `immersion_context.py` | Rumors, world echoes, inner life |
| `narrator.py` | Assembles prompt from state |
| `gemini_client.py` | API call, fallbacks, truncation handling |

---

## AI failure recovery (`simulation/gemini_client.py`)

| Failure | Behavior |
|---------|----------|
| **Missing API key** | Blocked at game start with message |
| **Model 404** | Try fallbacks: `gemini-2.5-flash`, `gemini-3-flash-preview` |
| **Empty response** | `RuntimeError`, retried via next model |
| **Truncated output** | Detect via finish_reason / ending heuristics; **retry at 2× token cap** (max 8192); then error with hint to raise `GEMINI_MAX_OUTPUT_TOKENS` |
| **Other API errors** | Propagated (quota, auth, etc.) — **no silent degrade** |
| **Turn-level catch** | `game_loop` prints `[error message]`; **no emergency fallback prose** today |

There is **no** offline/template narration mode if Gemini is down. State changes still persist for mechanics-only paths (meta commands).

---

## Save compatibility (`simulation/world_patch.py`)

**Current approach:** opportunistic patch at game start — **no version tags or migration chain yet**.

`ensure_world_extensions()`:

- If districts lack `storyline` → run `attach_area_storylines()`
- If player lacks `goals` → build from motivation + background

**Full reset:** `reset_world.py` deletes listed JSON files; next boot regenerates.

**Gap vs ideal:** no `save_version` field, no deprecated-field handlers, no incremental migration log. Long saves rely on patch-on-load for the few fields implemented so far.

---

## Background tick order (`simulation_runner.py`, ~every 30s)

See **ARCHITECTURE.md §12** for full order. Summary:

1. `simulate_npcs` (tiered sampling) — NPC decision layer
2. `maintain_monsters`, `apply_npc_consequences`, `advance_districts`
3. `process_leadership_succession`, `run_faction_tick`
4. `update_relationships`, `apply_memory_effects`
5. `spread_rumors`, `spread_rumor_beliefs`, `advance_storylines`
6. `flush_events`, `process_pending` (consequence queue)
7. Legacy/goal rumors, memory consolidation
8. `advance_information_packets`
9. Emotion decay, secret exposure, world pressure, `rival_tick`
10. `process_memories` — event log → episodic memory

---

## Key files

| Path | Role |
|------|------|
| **`ARCHITECTURE.md`** | **Full system design for reviewers (start here)** |
| `src/main.py` | Bootstrap, character creation, game loop |
| `simulation/story_loop.py` | Player turn orchestration |
| `simulation/story_orchestrator.py` | Beat planning (prepare/finalize) |
| `simulation/memory_record.py` | Unified memory write per beat |
| `simulation/memory_immersion.py` | Subjective memory, callbacks, gossip |
| `simulation/npc_actions.py` | NPC decision layer |
| `simulation/narrator.py` | Prompt assembly |
| `simulation/narrator_blocks.py` | Kind-aware prompt gating |
| `simulation/gemini_client.py` | Gemini API |
| `simulation/relationship_engine.py` | Bond math |
| `simulation/npc_memory_engine.py` | Memory storage, decay, pruning |
| `simulation/importance_router.py` | Universal importance scoring |
| `simulation/event_archiver.py` | Hot log archival |
| `simulation/world_patch.py` | Save patching |
| `storage.py` | Atomic JSON I/O |

---

## Code vs model

**Enforced in code:** stats, combat, relationships, memory, economy transfers, time, travel, scene cast, skill checks, goals progress.

**Guided by prompt (model-dependent):** prose quality, showing-not-telling, obeying anti-repetition rules, dialogue craft.
