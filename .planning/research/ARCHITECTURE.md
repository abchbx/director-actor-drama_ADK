# Architecture Evolution: From Linear STORM to Infinite Improvisation Loop

**Research Date:** 2026-04-11

## Current Architecture (From Codebase)

### StormRouter → 4 STORM Sub-Agents (Linear Pipeline)

The current system in `app/agent.py` implements a strict 4-phase linear pipeline:

```
StormRouter (BaseAgent)
  ├── _storm_discoverer  (status: "" | "brainstorming" | "storm_discovering")
  ├── _storm_researcher  (status: "storm_researching")
  ├── _storm_outliner    (status: "storm_outlining")
  └── _storm_director    (status: "acting" | everything else)
```

**Key constraints of the linear model:**
- `StormRouter._run_async_impl()` reads `ctx.session.state["drama"]["status"]` and routes to exactly one sub-agent per user turn
- Status transitions are one-directional: `"" → storm_discovering → storm_researching → storm_outlining → acting`
- Once in `"acting"`, the system stays in `_storm_director` forever — no re-entry to earlier phases
- STORM phases 1-3 produce **placeholder/template data** (lines 816-862, 965-972 in `app/tools.py`), making them effectively decorative
- The director agent's instruction (lines 174-351) is ~180 lines of rigid procedure: `/next` → `next_scene()` → `director_narrate()` → `actor_speak()` × N → `write_scene()` → output

### Actor A2A Services (Independent Processes)

Each actor is spawned as an independent uvicorn HTTP server:
- Code generated at runtime by `app/actor_service.py::generate_actor_agent_code()` → `app/actors/actor_<name>.py`
- Each actor has its own LLM session, system prompt, and memory
- Communication only via A2A protocol (HTTP + JSON-RPC)
- `actor_speak()` in `app/tools.py` (lines 168-274) builds a prompt with `[当前情境]` + `[你的记忆]` and sends it via `_call_a2a_sdk()`
- Actor memory is a flat list of strings stored in `state["actors"][name]["memory"]` — no compression, no prioritization

### Dual State Management

- **Primary:** `tool_context.state["drama"]` — dict in ADK session memory
- **Persistence:** `app/dramas/<theme>/state.json` — auto-saved on every `_set_state()` call
- **State structure:** `{theme, status, current_scene, scenes[], actors{}, narration_log[], storm{}}`
- **Write amplification:** Every tool call that mutates state triggers a full `json.dump()` to disk (6+ writes per scene)
- **No memory tiering:** Actor memories are stored as `[{entry: str, timestamp: str}]` — flat append-only list

---

## Proposed Architecture: Infinite Improvisation Loop

### Core Pattern: Scene → Evaluate → Inject → Next

Replace the linear STORM pipeline with a cyclic loop that can re-enter discovery/research phases dynamically:

```
                    ┌──────────────────────────────┐
                    │       InfiniteDramaLoop       │
                    │    (replaces StormRouter)     │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │    Phase: INIT (one-shot)     │
                    │  Discovery + Outline + Cast   │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
              ┌────►│   Phase: IMPROVISE (loop)     │────┐
              │     │                               │    │
              │     │  1. Director narrates scene   │    │
              │     │  2. Actors speak (A2A)        │    │
              │     │  3. Record scene              │    │
              │     │  4. Evaluate tension          │    │
              │     │  5. Inject conflict?          │    │
              │     │  6. Dynamic STORM trigger?    │────┤
              │     │  7. Await user or auto-next   │    │
              │     └───────────────────────────────┘    │
              │                                            │
              └────────────────────────────────────────────┘
```

### Where Does the Loop Live?

**Recommendation: In the Director agent itself, orchestrated by tools.**

Why NOT a new agent or new router:
- `StormRouter` is already a `BaseAgent` that yields events from sub-agents. Making it "loop" would require overriding the ADK event model — the Runner expects one response per user turn.
- A new "loop agent" would fight against ADK's turn-based model — ADK sends one user message, expects one agent response.

**The loop lives in the tool chain within a single Director turn:**

```
User: /next (or auto-trigger)
  │
  ▼
InfiniteDramaDirector agent
  │
  ├── 1. next_scene()           → advance scene counter
  ├── 2. director_narrate()     → scene narration
  ├── 3. actor_speak() × N      → A2A calls
  ├── 4. write_scene()          → record scene
  ├── 5. evaluate_tension()     → NEW: score tension, return assessment
  ├── 6. [if tension low] inject_conflict()  → NEW: generate + inject event
  ├── 7. [if N-scene trigger] dynamic_storm() → NEW: re-discover perspectives
  └── 8. Output formatted scene + tension report
```

The Director's system prompt drives the sequence. Tools provide the intelligence. This keeps the architecture within ADK's turn model while enabling infinite looping.

**Router simplification:** Replace `StormRouter` with a simpler `DramaRouter` that only distinguishes:
1. **Setup phase** (no actors yet) → routes to `_setup_agent` (merged discover+research+outline)
2. **Improvise phase** (actors exist) → routes to `_improv_director` (the loop driver)
3. **Utility commands** (`/save`, `/load`, etc.) → routes to whichever agent is active

---

## Component Design

### 1. Conflict Engine: Tool, Not Sub-Agent

**Design: A tool function `evaluate_tension()` + `inject_conflict()`**

Why a tool, not a sub-agent:
- Conflict detection is a **pure function** of current state (scenes, emotions, last N dialogues) — it doesn't need its own LLM session
- A sub-agent would require another routing decision, another context window, and more A2A overhead
- The Director agent already has the context — it just needs structured data to make decisions

**Implementation in `app/tools.py`:**

```python
def evaluate_tension(tool_context: ToolContext) -> dict:
    """Evaluate the current dramatic tension level.
    
    Analyzes recent scenes for:
    - Emotional variance (are emotions changing?)
    - Conflict density (how many active conflicts?)
    - Stagnation detection (are characters repeating?)
    - Arc progression (is the story moving?)
    
    Returns tension_score (0-100) and specific warnings.
    """
    state = _get_state(tool_context)
    scenes = state.get("scenes", [])
    actors = state.get("actors", {})
    
    # Compute from state data:
    # - emotion_delta: variance in actor emotions over last 3 scenes
    # - dialogue_novelty: trigram overlap between consecutive scenes  
    # - conflict_open_count: unresolved injected conflicts
    # - scene_since_last_event: how long since last conflict injection
    
    return {
        "tension_score": score,
        "is_boring": score < 30,
        "warnings": [...],
        "suggested_action": "inject" | "continue" | "storm",
    }

def inject_conflict(conflict_type: str, tool_context: ToolContext) -> dict:
    """Inject a dramatic conflict/event into the current scene.
    
    Args:
        conflict_type: One of "new_character", "revelation", 
                       "betrayal", "accident", "escalation"
    
    Returns a generated conflict description that the Director
    incorporates into the next narration.
    """
    # Generate conflict based on:
    # - Current actor relationships and tensions
    # - Unused perspective angles from STORM data
    # - Recent conflict history (avoid repetition)
    
    return {
        "conflict": generated_conflict,
        "affected_actors": [...],
        "tension_impact": +delta,
    }
```

**Conflict detection heuristics (no LLM needed):**
1. **Emotion stagnation:** If all actors' emotions haven't changed in 3+ scenes → tension drops
2. **Dialogue repetition:** Extract key noun phrases from last 2 scenes; high overlap → stagnation
3. **Time since injection:** If `current_scene - last_injection_scene > 5` → consider injection
4. **Unresolved threads count:** Track open conflict threads; if 0 → tension is low

**For more nuanced detection** (Phase 2 enhancement), use a lightweight LLM call within `evaluate_tension()` to judge narrative quality — but start with heuristics.

### 2. Dynamic STORM: Tool + State Extension

**Design: A tool `dynamic_storm()` that re-triggers perspective discovery**

Dynamic STORM is NOT a full re-run of the 4-phase pipeline. It's a **targeted re-discovery** that:
1. Reads the current story state (actors, recent scenes, current tensions)
2. Identifies **unexplored angles** — perspectives that weren't in the original discovery
3. Generates new conflict seeds and character dimensions
4. Merges them into the existing `storm` state data

**Implementation approach:**

```python
def dynamic_storm(focus_area: str, tool_context: ToolContext) -> dict:
    """Re-discover perspectives mid-drama (Dynamic STORM).
    
    Called every N scenes (configurable) or when tension evaluation
    suggests the story needs new directions.
    
    Args:
        focus_area: What to explore — "new_perspectives", 
                    "character_depth", "world_expansion"
    """
    state = _get_state(tool_context)
    storm_data = state.get("storm", {})
    existing_perspectives = [p["name"] for p in storm_data.get("perspectives", [])]
    recent_scenes = state.get("scenes", [-3:])  # last 3 scenes
    
    # Generate NEW perspectives that don't overlap with existing ones
    # This IS an LLM call — the agent's own reasoning generates them
    
    return {
        "new_perspectives": [...],
        "new_conflict_seeds": [...],
        "suggested_character_arcs": [...],
    }
```

**Trigger strategy (lives in Director's system prompt, not in code):**
- Every 8-10 scenes: automatic Dynamic STORM trigger
- When `evaluate_tension()` returns `suggested_action: "storm"`: immediate trigger
- When user uses `/storm` command: manual trigger

**Why NOT a sub-agent:** Dynamic STORM runs within the Director's turn. The Director calls `dynamic_storm()`, gets new perspectives, then uses them in the SAME turn to inform the next scene. No context-switch between agents.

**State extension:** Add to `storm` data:
```python
storm["dynamic_storm_history"] = [
    {"triggered_at_scene": 12, "new_perspectives": [...], "trigger_reason": "auto"}
]
storm["used_conflict_types"] = ["betrayal", "revelation"]  # track to avoid repetition
```

### 3. Layered Memory: New Module `app/memory_manager.py`

**Design: Separate module with 3-tier memory**

The current flat memory list (`actors[name]["memory"] = [{entry, timestamp}]`) will become unmanageable at 50+ scenes. Each actor accumulates ~3-5 memory entries per scene → 150-250 entries → exceeds context window.

**Three tiers:**

```
Tier 1: Working Memory (last 3 scenes, full detail)
  - Stored in: state["actors"][name]["working_memory"]  
  - Content: Full dialogue text, emotions, situations
  - Token budget: ~4000 tokens per actor
  
Tier 2: Recent Summary (scenes 4-15, compressed)  
  - Stored in: state["actors"][name]["recent_summary"]
  - Content: One-paragraph summary per scene, key events only
  - Token budget: ~2000 tokens per actor
  
Tier 3: Long-term Arc (scene 16+, highly compressed)
  - Stored in: state["actors"][name]["arc_summary"]
  - Content: Character arc summary, key relationships, critical events
  - Token budget: ~500 tokens per actor
```

**Implementation in `app/memory_manager.py`:**

```python
# New module: app/memory_manager.py

WORKING_MEMORY_SCENES = 3  # Last N scenes at full detail
RECENT_SUMMARY_SCENES = 12  # Scenes 4-15 compressed
# Everything beyond RECENT_SUMMARY_SCENES goes to arc

def update_memory_tiers(actor_name: str, scene_data: dict, tool_context):
    """Called after each scene. Shifts memory between tiers."""
    state = _get_state(tool_context)
    actor = state["actors"][actor_name]
    current_scene = state["current_scene"]
    
    # Add new scene to working memory
    working = actor.get("working_memory", [])
    working.append(scene_data)
    actor["working_memory"] = working
    
    # If working memory exceeds limit, compress oldest into recent_summary
    if len(working) > WORKING_MEMORY_SCENES:
        overflow = working[:-WORKING_MEMORY_SCENES]
        for entry in overflow:
            summary = _compress_to_summary(entry)  # LLM call or heuristic
            recent = actor.get("recent_summary", [])
            recent.append(summary)
            actor["recent_summary"] = recent
        
        actor["working_memory"] = working[-WORKING_MEMORY_SCENES:]
    
    # If recent_summary exceeds limit, compress into arc_summary
    recent = actor.get("recent_summary", [])
    if len(recent) > RECENT_SUMMARY_SCENES:
        overflow = recent[:-RECENT_SUMMARY_SCENES]
        arc = actor.get("arc_summary", "")
        arc = _merge_into_arc(arc, overflow)  # LLM call
        actor["arc_summary"] = arc
        actor["recent_summary"] = recent[-RECENT_SUMMARY_SCENES:]
    
    _set_state(state, tool_context)


def build_actor_context(actor_name: str, tool_context) -> str:
    """Build the context string for an actor_speak() call.
    
    Replaces the current flat memory_str construction
    in app/tools.py lines 201-213.
    """
    state = _get_state(tool_context)
    actor = state["actors"][actor_name]
    
    parts = []
    
    # Tier 3: Long-term arc (always included — it's small)
    arc = actor.get("arc_summary", "")
    if arc:
        parts.append(f"【你的故事弧线】\n{arc}")
    
    # Tier 2: Recent summary (compressed but informative)
    recent = actor.get("recent_summary", [])
    if recent:
        parts.append(f"【近期经历摘要】\n" + "\n".join(f"- {r}" for r in recent))
    
    # Tier 1: Working memory (full detail, last 3 scenes)
    working = actor.get("working_memory", [])
    if working:
        parts.append(f"【最近的经历（详细）】")
        for entry in working:
            parts.append(f"  第{entry['scene']}场: {entry['summary']}")
    
    return "\n\n".join(parts)
```

**Compression strategy:**

- **Working → Recent:** Use a deterministic summarizer (extract key sentences by position: first, last, and sentences with emotion words). This avoids an LLM call for every scene transition.
- **Recent → Arc:** This DOES need an LLM call — merging 12 scene summaries into a coherent arc requires reasoning. Trigger this lazily (only when `recent_summary` exceeds the limit), and cache the result.
- **Critical events preservation:** Mark certain memories as `"critical": True` (betrayals, revelations, deaths). These are NEVER compressed — always kept in working memory even if they fall outside the 3-scene window.

### 4. Context Builder: Integrated into `build_actor_context()`

The context builder is not a separate service — it's a function in `memory_manager.py` that assembles the right context for each actor call:

```python
def build_director_context(tool_context) -> str:
    """Build context for the Director agent itself.
    
    The Director needs:
    - Global story arc (all arc summaries merged)
    - Current tension score
    - Recent scene titles + key events
    - Active conflicts list
    - Dynamic STORM perspectives
    
    But NOT full dialogue text — that's in the actor context.
    """
    ...
```

**Token budget management:**

| Context Component | Token Budget | Source |
|---|---|---|
| Actor's arc summary | ~500 | `arc_summary` |
| Actor's recent summary | ~2000 | `recent_summary` |
| Actor's working memory | ~4000 | `working_memory` |
| Current situation prompt | ~500 | `actor_speak(situation)` |
| Actor system prompt | ~1000 | Generated actor code |
| **Total per actor call** | **~8000** | Well within 200K window |

---

## Data Flow for Single Turn in Infinite Mode

```
User input → DramaRouter
  │
  ├─ [/start] ──► Setup agent (Discovery + Outline + Cast, one-shot)
  │
  └─ [/next | /action | /storm | auto] ──► ImprovDirector
       │
       ├── 1. next_scene() or user_action()
       │      └── state["current_scene"] += 1
       │
       ├── 2. director_narrate()
       │      └── narration → add_narration() → narration_log[]
       │
       ├── 3. actor_speak() × N (sequential A2A calls)
       │      ├── build_actor_context(name, tool_context) ← memory_manager
       │      ├── _call_a2a_sdk(card, prompt, name, port)
       │      ├── update_memory_tiers(name, scene_data, tool_context) ← memory_manager
       │      └── add_dialogue(name, dialogue, tool_context)
       │
       ├── 4. write_scene()
       │      └── update_script() → scenes[]
       │
       ├── 5. evaluate_tension()  ← NEW
       │      └── returns {tension_score, is_boring, suggested_action}
       │
       ├── 6. [if suggested_action == "inject"]
       │      └── inject_conflict(type, tool_context) → narration + actor reactions
       │          └── director_narrate(conflict_event)
       │          └── actor_speak() × affected_actors
       │
       ├── 7. [if suggested_action == "storm" OR scene % N == 0]
       │      └── dynamic_storm(focus_area, tool_context)
       │          └── new perspectives → merged into storm data
       │
       └── 8. Output: formatted scene + tension report + next options
              └── Director decides: auto-advance or await user
```

---

## Changes to Existing Code

### `app/agent.py`: StormRouter → DramaRouter

**Before:**
```python
class StormRouter(BaseAgent):
    # Routes to 4 sub-agents based on status string
    # _storm_discoverer, _storm_researcher, _storm_outliner, _storm_director
```

**After:**
```python
class DramaRouter(BaseAgent):
    """Routes to setup or improvise phase.
    
    Setup: One-shot Discovery + Outline + Cast (merges old phases 1-3)
    Improvise: Infinite loop Director (replaces old phase 4)
    """
    async def _run_async_impl(self, ctx):
        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})
        
        if not actors:
            # No actors yet → setup phase
            agent = self._sub_agents_map.get("setup_agent")
        else:
            # Actors exist → improvise phase
            agent = self._sub_agents_map.get("improv_director")
        
        # Utility commands always go to improv_director
        if self._is_utility_command(ctx):
            agent = self._sub_agents_map.get("improv_director")
        
        async for event in agent.run_async(ctx):
            yield event
```

**Sub-agent changes:**
- Merge `_storm_discoverer` + `_storm_researcher` + `_storm_outliner` into `_setup_agent`
- Rename `_storm_director` → `_improv_director` with updated instruction incorporating loop logic
- Remove the broken `self._sub_agents[0]` fallback (from CONCERNS.md)

### `app/tools.py`: New Tools + Memory Integration

**New tools to add:**

1. `evaluate_tension(tool_context)` — heuristic tension scoring
2. `inject_conflict(conflict_type, tool_context)` — conflict generation
3. `dynamic_storm(focus_area, tool_context)` — mid-drama perspective re-discovery
4. `build_actor_context_from_memory(actor_name, tool_context)` — replaces inline memory_str

**Modify existing tools:**

1. `actor_speak()` (lines 201-213): Replace flat `memory_str` construction with `build_actor_context()` from `memory_manager`
2. `next_scene()`: Add tension evaluation step to the returned guidance message
3. `storm_research_perspective()` (lines 965-972): Replace placeholder findings with actual LLM-driven research (or remove and let the LLM agent handle research naturally)
4. Fix operator precedence bug at line 246

**Remove/deprecate:**
- `storm_discover_perspectives()` as a standalone tool — merge into setup flow
- `storm_ask_perspective_questions()` — LLM agent handles this naturally

### `app/state_manager.py`: Memory Tiers + Conflict State

**New state fields:**

```python
state["actors"][name]["working_memory"] = []   # Tier 1
state["actors"][name]["recent_summary"] = []   # Tier 2  
state["actors"][name]["arc_summary"] = ""       # Tier 3
state["actors"][name]["critical_memories"] = [] # Never compressed

state["conflict_engine"] = {
    "active_conflicts": [],
    "injection_history": [],      # [{scene, type, description}]
    "used_conflict_types": [],    # Track to avoid repetition
    "tension_scores": [],         # Historical scores
}

state["dynamic_storm"] = {
    "trigger_history": [],        # [{scene, focus_area, new_perspectives}]
    "storm_interval": 8,          # Scenes between auto-STORM triggers
}
```

**Migration concern:** Existing `memory` field (flat list) must be migrated to `working_memory` on first load. Add migration in `load_progress()`:

```python
# In load_progress(), after loading state:
for actor_name, actor_data in state.get("actors", {}).items():
    if "working_memory" not in actor_data:
        # Migrate old flat memory to working_memory
        old_memories = actor_data.pop("memory", [])
        actor_data["working_memory"] = [{"entry": m["entry"], "scene": 0} for m in old_memories]
        actor_data["recent_summary"] = []
        actor_data["arc_summary"] = ""
```

### New Module: `app/memory_manager.py`

Core functions:
- `update_memory_tiers(actor_name, scene_data, tool_context)` — called after each scene
- `build_actor_context(actor_name, tool_context)` — builds prompt for `actor_speak()`
- `build_director_context(tool_context)` — builds context for Director's own reasoning
- `_compress_to_summary(entry)` — deterministic scene→summary compression
- `_merge_into_arc(existing_arc, overflow_summaries)` — LLM-based arc compression
- `mark_critical_memory(actor_name, memory_id, tool_context)` — protect from compression

### New Module: `app/conflict_engine.py` (optional, can start in tools.py)

Core functions:
- `evaluate_tension_score(state)` — pure function, no LLM
- `generate_conflict(conflict_type, state)` — may use LLM for creative conflict generation
- `select_conflict_type(state)` — avoid repetition, match current story dynamics
- `track_conflict_resolution(state)` — detect when conflicts resolve naturally

---

## Build Order

### Phase 1: Foundation — Memory Manager (MUST be first)

**Why first:** Every other feature depends on memory being manageable. Without layered memory, the system can't run past 15-20 scenes without context overflow. This is the blocking dependency.

**Deliverables:**
1. Create `app/memory_manager.py` with 3-tier memory system
2. Migrate `actor_speak()` to use `build_actor_context()` instead of flat `memory_str`
3. Add `update_memory_tiers()` call after each scene in `actor_speak()` / `write_scene()` flow
4. Add migration logic in `state_manager.py::load_progress()` for existing `memory` → `working_memory`
5. Add `critical_memories` mechanism (protect key events from compression)

**Files changed:** `app/memory_manager.py` (new), `app/tools.py` (modify `actor_speak`), `app/state_manager.py` (add migration)

**Verification:** Run a drama to 20+ scenes and verify actor prompts stay within token budget. Check that `working_memory` has ≤3 entries, `recent_summary` grows correctly, `arc_summary` gets populated.

### Phase 2: Conflict Engine (depends on Phase 1)

**Why second:** Conflict injection needs layered memory to evaluate tension properly. Without memory tiers, the tension evaluator can't analyze scene history.

**Deliverables:**
1. Add `evaluate_tension()` tool to `app/tools.py` — heuristic scoring
2. Add `inject_conflict()` tool to `app/tools.py` — conflict generation
3. Add `conflict_engine` state fields to `init_drama_state()`
4. Update Director's system prompt to call `evaluate_tension()` after each scene
5. Add `conflict_engine.py` module (optional, can start inline in tools.py)

**Files changed:** `app/tools.py` (add tools), `app/state_manager.py` (add state fields), `app/agent.py` (update Director prompt)

**Verification:** Run a drama with deliberately "boring" scenes (repetitive actions). Verify tension score drops below threshold and conflict injection triggers.

### Phase 3: Dynamic STORM (depends on Phase 1, Phase 2)

**Why third:** Dynamic STORM is a "refresh" mechanism that creates new narrative directions. It depends on tension evaluation (Phase 2) to know WHEN to trigger, and on layered memory (Phase 1) to build context for new perspective discovery.

**Deliverables:**
1. Add `dynamic_storm()` tool to `app/tools.py`
2. Add `dynamic_storm` state fields
3. Update Director's system prompt with STORM trigger rules (every N scenes + tension-based)
4. Add `/storm` command support in DramaRouter
5. Implement perspective deduplication (new perspectives must differ from existing ones)

**Files changed:** `app/tools.py` (add tool), `app/state_manager.py` (add state fields), `app/agent.py` (update prompt + routing)

**Verification:** Run a drama past 10 scenes. Verify Dynamic STORM triggers at the configured interval. Check that new perspectives are genuinely different from initial ones.

### Phase 4: Router Refactor (depends on Phase 1-3)

**Why last:** The router is the orchestration layer. Refactoring it before the tools exist means building on speculation. After Phases 1-3, we know exactly what the Director needs.

**Deliverables:**
1. Replace `StormRouter` with `DramaRouter` in `app/agent.py`
2. Merge `_storm_discoverer` + `_storm_researcher` + `_storm_outliner` into `_setup_agent`
3. Rename `_storm_director` → `_improv_director` with infinite loop instructions
4. Remove broken fallback `self._sub_agents[0]`
5. Fix command detection to use regex word boundaries (from CONCERNS.md)

**Files changed:** `app/agent.py` (major refactor), `app/tools.py` (cleanup deprecated STORM tools)

**Verification:** Full end-to-end test: `/start` → setup → 20+ scenes with conflict injection + dynamic STORM → `/save` → `/load` → continue.

### Phase 5: Polish and Hardening (after Phase 4)

1. Fix existing bugs (operator precedence at line 246, conversation log not cleared)
2. Add actor process crash recovery (from CONCERNS.md)
3. Implement debounced state saving (from CONCERNS.md)
4. Add shared httpx.AsyncClient for A2A calls (from CONCERNS.md)
5. Port range expansion (from CONCERNS.md)
6. Write tests for all new modules

---

## Dependency Graph

```
Phase 1: Memory Manager
    │
    ├──► Phase 2: Conflict Engine
    │         │
    │         ├──► Phase 3: Dynamic STORM
    │         │         │
    │         │         └──► Phase 4: Router Refactor
    │         │                   │
    │         │                   └──► Phase 5: Polish
    │         │
    │         └──────────────────────► Phase 4: Router Refactor
    │
    └──────────────────────────────► Phase 3: Dynamic STORM
```

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5

Phase 1 is on the critical path for everything. Phase 2 and Phase 3 can be partially parallelized (Phase 3's core logic doesn't strictly need Phase 2's conflict injection — it needs the memory manager from Phase 1). However, Phase 3's trigger mechanism depends on tension evaluation from Phase 2.

**Estimated effort:**
- Phase 1: ~3-4 sessions (new module, migration, integration testing)
- Phase 2: ~2 sessions (scoring heuristics, conflict generation, prompt updates)
- Phase 3: ~2 sessions (perspective re-discovery, deduplication, trigger logic)
- Phase 4: ~2 sessions (router refactor, prompt rewrite, integration)
- Phase 5: ~3 sessions (bug fixes, recovery, tests)

---

*Architecture evolution research: 2026-04-11*
