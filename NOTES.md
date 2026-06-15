# AIStory — systems overview (v4)

## Run it
1. `pip install -r requirements.txt`
2. Narrator uses a LOCAL **Ollama** server. Install Ollama, then
   `ollama pull llama3` and keep `ollama serve` running on
   `localhost:11434`. (Model/URL are at the top of `simulation/narrator.py`;
   a larger local model follows the novelistic instructions far better.)
3. From the project root: `python src/main.py`

## Reset the world (start fresh)
`python reset_world.py`  then  `python src/main.py`

## What's modelled
- **People**: locked pronouns, full physical description, age, 25 correlated
  personality traits, a generated background (origin/wound/secret/mannerism),
  a persona (speech style, voice quirk, core value, mood, literacy),
  role-weighted skills that earn XP, combat stats, and owned items.
- **Families**: households share a surname; spouses/parents/children/siblings
  with seeded bonds (and the odd sibling rivalry).
- **Institutions**: academies, guilds, temples, garrisons — members recruited
  by AGE (students young, masters old) — each carrying a slow story arc that
  advances on its own and seeds rumours/memories.
- **Memory**: every NPC keeps episodic memories of what happened TO them and
  NEAR them — player attacks, kindnesses, witnessed violence, and grief when
  kin die. Memories have salience that decays; the narrator uses each present
  person's strongest memories so the past shapes how they treat you.
- **Combat / monsters**: stat-based, shared by player/NPCs/monsters; a
  bestiary spawns in the wilds.
- **Relationships**: 8 dimensions (trust, respect, fear, affection, attraction,
  resentment, rivalry, obligation), familiarity-gated SLOW BURN — earned, never
  sudden.
- **Time & travel**: world time in hours; an area graph (city districts +
  wilderness). Long journeys burn hours and run many background ticks, so the
  world moves on while you travel.

## Code vs. model
All state — identity, pronouns, ages, families, institutions, memory, combat,
relationships, time — is enforced in CODE and tested. Prose quality (length,
tone, strictly showing-not-telling, weaving in memory) is guided by the prompt
and depends on your local model.
