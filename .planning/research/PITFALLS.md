# Pitfalls: Infinite Improvisation AI Narrative Systems

**Research Date:** 2026-04-11
**Project:** Director-Actor-Drama (无限畅写版)

---

## Context/Memory Pitfalls

### Pitfall 1: Context Window Exhaustion at 50+ Scenes

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Actor prompts grow linearly with scene count. At 50 scenes × 3-5 memories per scene = 150-250 memory entries per actor. Each entry ~50 tokens → 7,500-12,500 tokens just for memories, per actor call. |
| **Severity** | 🔴 CRITICAL — System becomes unusable at scale |
| **Warning Signs** | Actor responses become generic/repetitive; LLM truncates input; latency spikes; `actor_speak()` prompt exceeds model's context limit |
| **Root Cause in This Codebase** | `app/tools.py` lines 201-213: `memory_entries = [m["entry"] for m in actor_data.get("memory", [])]` — builds a flat string of ALL memories. No pagination, no compression, no tiering. The `memory` list in `state_manager.py::update_actor_memory()` (line 636) is pure append — no eviction. |
| **Prevention** | Implement 3-tier memory (ARCHITECTURE.md Phase 1). Working memory (3 scenes) + recent summary (12 scenes) + arc summary (everything else). Token budget per actor call: ~8000 tokens max. |
| **Phase** | Phase 1 (Memory Manager) |

### Pitfall 2: Summarization Losing Critical Details → Logical Contradictions

| Aspect | Detail |
|--------|--------|
| **Pitfall** | When scene data is compressed into summaries, critical plot details (who killed whom, secret alliances, physical injuries) get lost. Actor then contradicts established facts: a dead character references events after their death, or a character with a broken arm fights normally. |
| **Severity** | 🔴 CRITICAL — Breaks the core promise of "逻辑不断" |
| **Warning Signs** | Actor references events that didn't happen; character ignores established injuries/relationships; user complains about inconsistency |
| **Root Cause in This Codebase** | No mechanism exists for marking memories as critical. The `memory` list in `state_manager.py` treats all entries equally — `update_actor_memory()` at line 636 just appends. There's no `critical` flag, no importance scoring, no protected memory concept. |
| **Prevention** | (1) Add `critical_memories` list per actor — events marked as critical are NEVER compressed, always included in context. (2) Use importance-weighted summarization: extract sentences containing entity names, relationship terms, and state changes before compressing. (3) Post-compression validation: after generating a summary, verify it contains all entities from the original text (simple NER check). |
| **Phase** | Phase 1 (Memory Manager) — critical_memories mechanism |

### Pitfall 3: Actor "Forgetting" Its Own Backstory

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Actor's system prompt contains backstory, but the context window fills with scene data and pushes out the character's core traits. Actor starts speaking out of character or ignoring their established background. |
| **Severity** | 🟠 HIGH — Undermines character consistency |
| **Warning Signs** | Actor's dialogue style shifts; character acts against their stated personality; responses become generic |
| **Root Cause in This Codebase** | Actor's backstory is embedded in the generated Python file's system prompt (`app/actor_service.py::generate_actor_agent_code()` lines 100+). This is FIXED at creation time and never modified. However, the prompt sent via `actor_speak()` (lines 208-213) puts `[当前情境]` and `[你的记忆]` AFTER the system prompt — the LLM may weight recent context over system instructions. |
| **Prevention** | (1) Always include a character identity reminder at the TOP of the `actor_speak()` prompt: "你是{name}，{role}。{personality_one_liner}" — this is a simple prefix that anchors identity. (2) In `build_actor_context()`, add a "character anchor" section that repeats core traits regardless of memory tier. (3) Periodically validate actor responses against character sheet — if drift detected, inject a corrective prompt. |
| **Phase** | Phase 1 (Memory Manager) — build_actor_context design |

### Pitfall 4: State File Bloat from Infinite Scenes

| Aspect | Detail |
|--------|--------|
| **Pitfall** | `state.json` grows unboundedly. Each scene adds to `scenes[]`, each narration to `narration_log[]`, each memory to `actors[].memory`. At 100 scenes, state.json could be 500KB+ — slow to serialize, slow to load, may hit JSON parsing limits. |
| **Severity** | 🟡 MEDIUM — Degrades over time |
| **Warning Signs** | `/save` and `/load` become slow; state.json exceeds 1MB; `_save_state_to_file()` takes >100ms |
| **Root Cause in This Codebase** | `_set_state()` (line 890) serializes the ENTIRE state dict on every mutation. `scenes[]` stores full content (including dialogue text) for every scene. `narration_log[]` stores every narration ever. No archival mechanism. |
| **Prevention** | (1) Archive old scenes to separate files: `scenes/scene_001.json`, `scenes/scene_002.json`. Keep only the last 5 scenes in `state.json`. (2) Move `narration_log` to a separate append-only file. (3) Implement debounced saving (from CONCERNS.md) — batch writes. (4) Add a `/compact` command that archives old data and rebuilds state.json. |
| **Phase** | Phase 5 (Polish) — after core features are stable |

---

## Narrative Pitfalls

### Pitfall 5: Aimless Wandering — No Direction, Just Talking

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Without an overarching plot structure, scenes become "talking heads" — characters chat without conflict, nothing drives the story forward. The drama becomes a soap opera with no arc. |
| **Severity** | 🔴 CRITICAL — Violates core value "剧情始终有张力" |
| **Warning Signs** | 3+ consecutive scenes with no conflict escalation; characters discuss without tension; tension score stays below 20; user loses interest and stops interacting |
| **Root Cause in This Codebase** | The current `_storm_director` instruction (lines 174-351) has no mechanism for tension tracking. The Director just narrates and calls actors in sequence. There's no feedback loop — the Director doesn't evaluate whether the scene was "interesting" or "boring." `next_scene()` (line 459) just increments the counter. |
| **Prevention** | (1) `evaluate_tension()` tool returns a tension score after every scene. (2) Director's system prompt includes a rule: "If tension_score < 30, you MUST inject a conflict before the next scene." (3) Maintain a "story arc tracker" in state: `{current_act, act_goal, scenes_until_act_transition}` — gives the Director a structural target. (4) Dynamic STORM refreshes the Director's "creative palette" periodically. |
| **Phase** | Phase 2 (Conflict Engine) |

### Pitfall 6: Repetitive Conflict Injection — Same Twist Twice

| Aspect | Detail |
|--------|--------|
| **Pitfall** | The conflict engine injects the same type of twist repeatedly: another betrayal, another revelation, another accident. The drama becomes predictable in its unpredictability — the audience learns the pattern. |
| **Severity** | 🟠 HIGH — Makes the system feel mechanical |
| **Warning Signs** | User predicts the next twist; conflict types repeat within 5 scenes; `used_conflict_types` list shows clustering |
| **Root Cause in This Codebase** | No tracking mechanism exists for conflict history. The current `inject_conflict()` concept has no memory of what conflicts were already used. `state_manager.py` has no `conflict_engine` state section. |
| **Prevention** | (1) Track `used_conflict_types` in state — don't repeat the same type within 8 scenes. (2) Use a weighted conflict type selection: less-recently-used types get higher probability. (3) Generate conflicts from story-specific dynamics (actor relationships, unresolved threads) rather than from a generic type list. (4) The Director's prompt should encourage COMBINING conflict types ("a revelation that leads to a betrayal") rather than picking from a list. |
| **Phase** | Phase 2 (Conflict Engine) |

### Pitfall 7: Dynamic STORM Creating Incoherent Plot Twists

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Mid-drama STORM re-discovery injects perspectives that contradict established plot. Example: STORM discovers "the villain was actually a hero" perspective, but the story has already established the villain's evil deeds in 10 scenes of detail. |
| **Severity** | 🟠 HIGH — Creates logical contradictions |
| **Warning Signs** | New STORM perspectives directly contradict established facts; Director's narration retcons previous events; actors confused by conflicting directives |
| **Root Cause in This Codebase** | The STORM system in `app/tools.py` (lines 800-1125) generates perspectives that are THEMATICALLY driven, not PLOT-CONSTRAINED. `storm_discover_perspectives()` (line 801) only takes `theme` as input — it doesn't see the current story state. Dynamic STORM would have the same problem if it only looks at the theme string. |
| **Prevention** | (1) `dynamic_storm()` MUST receive the current story state as input: established facts, character arcs, resolved conflicts. (2) New perspectives must be validated against existing plot before injection: "Does this perspective contradict established events?" (3) Frame new perspectives as EXTENSIONS ("what if there's another layer?") not CONTRADICTIONS ("what if everything was different?"). (4) Add a `established_facts` list in state — actor deaths, relationship changes, major events — that Dynamic STORM must respect. |
| **Phase** | Phase 3 (Dynamic STORM) |

### Pitfall 8: Tension Never Resolving — Constant Drama Fatigue

| Aspect | Detail |
|--------|--------|
| **Pitfall** | The conflict engine keeps injecting new conflicts without resolving old ones. The story becomes an exhausting escalator of drama — every scene raises stakes, nothing ever settles. The audience experiences "drama fatigue" and stops caring. |
| **Severity** | 🟠 HIGH — Makes the drama emotionally exhausting |
| **Warning Signs** | 5+ unresolved conflicts in `active_conflicts`; no conflict resolution in 8+ scenes; user stops engaging emotionally; actors all have extreme emotions |
| **Root Cause in This Codebase** | No conflict lifecycle management exists. Conflicts are injected but never tracked for resolution. The `inject_conflict()` concept doesn't have a counterpart `resolve_conflict()` or automatic conflict resolution detection. |
| **Prevention** | (1) Track `active_conflicts` with a `status` field: `{injected, escalating, resolving, resolved}`. (2) Cap active conflicts at 3-4 — before injecting a new one, require at least one to be in "resolving" state. (3) Add tension RELIEF scoring alongside tension INJECTION scoring. The Director should alternate between high-tension and low-tension scenes. (4) Implement a "conflict arc budget": inject → escalate → resolve within 5-8 scenes per conflict. (5) The Director's prompt should include: "Every conflict must have a resolution arc — do not start new conflicts if existing ones are unresolved." |
| **Phase** | Phase 2 (Conflict Engine) — active conflict tracking |

### Pitfall 9: The "Safe Middle" — Characters Avoid Conflict

| Aspect | Detail |
|--------|--------|
| **Pitfall** | LLM-generated characters tend toward politeness and conflict avoidance. When asked to "respond to the situation," actors often choose diplomacy, compromise, or de-escalation — even when their character profile says they should be aggressive or secretive. The drama defangs itself. |
| **Severity** | 🟡 MEDIUM — Makes drama boring without being obvious |
| **Warning Signs** | Actor dialogues contain many "也许" "不如" "我们能否" — hedging language; conflicts introduced by the engine get resolved by actors in the same scene; character emotions stay "neutral" or "calm" despite dramatic situations |
| **Root Cause in This Codebase** | The `actor_speak()` prompt (lines 208-213) says "保持角色一致性，不要跳出角色" but doesn't explicitly encourage dramatic responses. The actor's system prompt (generated in `actor_service.py`) contains personality traits but no instruction to seek conflict or resist easy resolution. |
| **Prevention** | (1) Add to the actor's system prompt: "你是一个戏剧角色。戏剧需要冲突。不要试图解决所有问题——有时你应该坚持立场、隐瞒真相、或做出冲动的决定。" (2) The `actor_speak()` situation prompt should include the current tension level and whether this scene calls for escalation: "【戏剧张力】本场需要升级冲突。不要轻易妥协。" (3) In `evaluate_tension()`, detect when actors consistently de-escalate: compare conflict injection descriptions with subsequent actor responses. If actors resolve 3+ injected conflicts immediately, flag as "conflict avoidance pattern." |
| **Phase** | Phase 2 (Conflict Engine) — prompt engineering |

---

## Architecture Pitfalls

### Pitfall 10: A2A Call Overhead with Memory Retrieval (Latency)

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Each `actor_speak()` call now involves: (1) `build_actor_context()` — may need LLM call for arc compression, (2) A2A HTTP roundtrip — already 5-15 seconds for LLM inference, (3) `update_memory_tiers()` — may need LLM call for summary compression. A single scene with 3 actors could take 45-90 seconds — too slow for interactive use. |
| **Severity** | 🟠 HIGH — Makes the system feel sluggish |
| **Warning Signs** | Single scene takes >60 seconds; user gives up waiting; A2A timeouts increase |
| **Root Cause in This Codebase** | A2A calls are already slow (120-second timeout at line 327). Memory compression adds synchronous LLM calls. `actor_speak()` is called sequentially — actor B waits for actor A to finish. |
| **Prevention** | (1) **Pre-compress, don't compress on-demand:** Run `_compress_to_summary()` and `_merge_into_arc()` AFTER the scene is complete, not during `actor_speak()`. The `build_actor_context()` function only READS pre-computed summaries — no LLM calls. (2) **Parallel actor calls:** When multiple actors speak in the same scene, call `actor_speak()` concurrently using `asyncio.gather()`. BUT: actors may reference each other's dialogue, so only parallelize INDEPENDENT speakers (those not directly responding to each other). (3) **Cache actor context:** If `build_actor_context()` is called twice for the same actor in the same scene, return cached result. (4) **Lazy arc compression:** Only run `_merge_into_arc()` when `recent_summary` exceeds the limit — not every scene. |
| **Phase** | Phase 1 (Memory Manager) — pre-compression design |

### Pitfall 11: State Management Complexity Explosion

| Aspect | Detail |
|--------|--------|
| **Pitfall** | Adding conflict_engine, dynamic_storm, memory tiers, tension scores, and established_facts to state creates a deeply nested, hard-to-maintain data structure. Every new feature adds more fields, and `_set_state()` serializes the entire thing on every mutation. |
| **Severity** | 🟡 MEDIUM — Makes the codebase fragile |
| **Warning Signs** | State dict has 10+ top-level keys; `state.json` structure is undocumented; different features accidentally share state keys; state migration code grows complex |
| **Root Cause in This Codebase** | The current state is already a "god dict" — `tool_context.state["drama"]` holds everything. `_set_state()` at line 890 is a single entry point for all mutations. No schema, no validation, no separation of concerns. |
| **Prevention** | (1) Define a schema for each state section using TypedDict or Pydantic: `MemoryState`, `ConflictState`, `StormState`, `ActorState`. (2) Add a `validate_state()` function that runs after every `_set_state()` call — catches type errors and missing fields early. (3) Separate persistence concerns: `conflict_engine` state changes frequently, `arc_summary` changes rarely — different save schedules. (4) Document the state schema in a `STATE_SCHEMA.md` file that lives alongside the code. |
| **Phase** | Phase 5 (Polish) — after feature set is stable |

### Pitfall 12: Race Conditions in Parallel Actor Calls

| Aspect | Detail |
|--------|--------|
| **Pitfall** | If we parallelize `actor_speak()` calls (Pitfall 10 prevention), multiple concurrent calls read and write `tool_context.state["drama"]`. Actor A's `update_memory_tiers()` may overwrite Actor B's concurrent write. State corruption. |
| **Severity** | 🟠 HIGH — Can corrupt drama state |
| **Warning Signs** | Memory entries disappear; state.json has inconsistent data; actors seem to "forget" what just happened |
| **Root Cause in This Codebase** | `_set_state()` at line 890 does a full dict replacement: `tool_context.state["drama"] = state`. If two coroutines both read state, modify it, and write it back, the second write overwrites the first. The global `_conversation_log` (line 18) has the same problem — list append is not atomic. |
| **Prevention** | (1) **Don't parallelize actor calls in Phase 1.** Keep sequential execution. The latency cost is acceptable for now (3 actors × 15s = 45s per scene). (2) If parallelization is needed later, use `asyncio.Lock()` around `_set_state()` calls: acquire lock before reading state, release after writing. (3) Alternatively, collect all mutations from parallel calls and apply them atomically in a single write at the end of the scene. (4) Move `_conversation_log` into session state (from CONCERNS.md) to eliminate the global mutable list. |
| **Phase** | Phase 5 (Polish) — only if parallelization is pursued |

### Pitfall 13: Actor A2A Service Crashes During Long Drama

| Aspect | Detail |
|--------|--------|
| **Pitfall** | During a 50+ scene drama, actor A2A services may crash (LLM API errors, memory issues, network problems). Current system has no recovery — the actor is permanently down until manually recreated. In infinite mode, this means the drama can't continue. |
| **Severity** | 🟠 HIGH — Blocks infinite drama sessions |
| **Warning Signs** | `actor_speak()` returns connection error; actor process poll() returns non-None; stderr output in actor subprocess |
| **Root Cause in This Codebase** | From CONCERNS.md: "No Graceful Recovery from Actor Process Crashes." Actor processes tracked in `_actor_processes` dict (line 26 of `actor_service.py`) — if process dies, the dict entry is stale. No health check, no auto-restart, no heartbeat. |
| **Prevention** | (1) Add a health check in `actor_speak()`: before building the prompt, verify the actor's process is alive via `process.poll()`. If dead, auto-restart using `create_actor_service()` with existing character data + memories. (2) Add a periodic health check background task that pings each actor's HTTP endpoint every 60 seconds. (3) On restart, restore actor's conversation history via `memory_entries` parameter in `create_actor_service()`. (4) Add PID file tracking so orphaned processes can be detected on main process restart. |
| **Phase** | Phase 5 (Polish) — but should be addressed early if infinite dramas are a goal |

---

## User Experience Pitfalls

### Pitfall 14: User Feels Powerless — AI Drives Everything

| Aspect | Detail |
|--------|--------|
| **Pitfall** | In "infinite mode," the AI auto-advances scenes, injects conflicts, and re-discovers perspectives. The user becomes a spectator rather than a participant. The drama feels like watching an AI talk to itself. |
| **Severity** | 🟠 HIGH — Undermines user engagement |
| **Warning Signs** | User only types `/next` repeatedly; user doesn't use `/action`; user stops mid-session; user says "I feel like I'm just watching" |
| **Root Cause in This Codebase** | The current system is already semi-automatic: `/next` triggers a full scene with narration + actors + recording. The user's only input is `/next` (advance) or `/action` (inject). There's no way to steer, pause, redirect, or veto. The Director's instruction (line 326) says "半自动模式" but the only "semi" part is waiting for `/next`. |
| **Prevention** | (1) **Offer choices, not just scenes:** After each scene, the Director should present 2-3 options: "接下来可以：A) 让朱棣发现密信 B) 道衍主动坦白 C) 你来决定（/action）" — giving the user agency even in auto mode. (2) **Conflict preview:** Before injecting a conflict, show the user: "剧情有点平淡，建议注入一个转折：{preview}。接受？/拒绝？/换一个？" (3) **User veto on STORM:** Dynamic STORM should present discovered perspectives to the user before incorporating them. (4) **Steering commands:** Add `/steer <direction>` as a lighter alternative to `/action` — nudges the story without forcing a specific event. (5) **Explicit mode toggle:** `/auto` (AI drives) vs `/manual` (user drives each scene) — let users choose their level of involvement. |
| **Phase** | Phase 4 (Router Refactor) — Director prompt redesign |

### Pitfall 15: User Feels Overwhelmed — Too Many Injection Options

| Aspect | Detail |
|--------|--------|
| **Pitfall** | The opposite of powerlessness: the system constantly asks the user to make decisions — "which conflict to inject?", "which perspective to explore?", "approve this STORM result?" — turning the experience into a decision tree rather than a drama. |
| **Severity** | 🟡 MEDIUM — Different users have different preferences |
| **Warning Signs** | User gives short/annoyed responses; user always picks the first option; user ignores prompts and just types `/next` |
| **Root Cause in This Codebase** | Not yet a problem — the current system doesn't ask the user anything during acting phase. But the proposed infinite loop adds many decision points (conflict approval, STORM review, steering choices). |
| **Prevention** | (1) **Default to auto, opt-in to manual:** The system should work well WITHOUT user intervention. Only ask when the AI genuinely can't decide. (2) **Silent operation with after-the-fact review:** Instead of "approve this conflict?", just inject it and let the user react. Add `/undo` to revert the last scene if they don't like it. (3) **Smart defaults for conflict types:** Use `evaluate_tension()` to automatically pick the best conflict type — don't ask the user to choose. (4) **Configurable verbosity:** Add a `/quiet` mode that suppresses all meta-commentary (tension scores, STORM reports) and only shows the drama. Add a `/verbose` mode that shows everything. |
| **Phase** | Phase 4 (Router Refactor) — UX design in Director prompt |

### Pitfall 16: "Uncanny Valley" of Near-Coherent But Subtly Wrong Plot

| Aspect | Detail |
|--------|--------|
| **Pitfall** | The story seems coherent on the surface but has subtle logical errors: a character references something they shouldn't know (cognitive boundary violation), a timeline inconsistency (it was night two scenes ago but now it's the same evening), or a character's emotional state doesn't match their recent experiences. These are WORSE than obvious errors because they undermine trust without being clearly identifiable. |
| **Severity** | 🟠 HIGH — Erodes user trust in the system |
| **Warning Signs** | User says "something feels off"; character knows information from another actor's private scene; time references are contradictory; emotional continuity breaks |
| **Root Cause in This Codebase** | (1) Cognitive boundaries ARE enforced by A2A isolation — actors can't directly access each other's state. BUT: the Director's narration (via `director_narrate()`) may leak information that creates implicit knowledge. If the Director narrates "朱棣看到道衍在密室中...", then the next `actor_speak()` for 道衍 might reference this — because the Director's narration was part of the "situation" sent to the actor. (2) No timeline tracking exists — `current_scene` is just an integer. There's no concept of "time of day" or "days elapsed." (3) Emotional state is a single string — no emotional history or continuity validation. |
| **Prevention** | (1) **Information flow audit:** The Director's narration prompt should be constructed per-actor — only include information that actor should know. Add a `knowledge_filter` step in `build_actor_context()`: strip details from the situation that the actor wouldn't have witnessed. (2) **Timeline tracking:** Add a `timeline` object to state: `{current_time: "第三天黄昏", days_elapsed: 3}`. Each scene advances time deterministically. Include current time in actor prompts. (3) **Emotional continuity check:** Before `actor_speak()`, compare the actor's current emotion with the last 3 emotions. If there's an unexplained jump (calm → furious without a trigger event), inject a bridging prompt: "你刚才还很平静，但[事件]让你突然愤怒。" (4) **Consistency validation tool:** A `validate_consistency()` tool that checks for common errors: timeline contradictions, knowledge boundary violations, emotional discontinuities. Run it every 5 scenes. |
| **Phase** | Phase 2 (Conflict Engine) — knowledge filtering; Phase 5 (Polish) — consistency validation |

### Pitfall 17: User Can't Recover from Bad Story Direction

| Aspect | Detail |
|--------|--------|
| **Pitfall** | The story goes in a direction the user doesn't want (e.g., a beloved character dies, the tone shifts from drama to comedy). The user has no way to undo, redirect, or recover. They're stuck with the consequences. |
| **Severity** | 🟡 MEDIUM — Frustrating but not system-breaking |
| **Warning Signs** | User types `/action` to try to undo something; user expresses frustration; user asks to "go back" |
| **Root Cause in This Codebase** | No undo mechanism exists. `save_progress()` creates snapshots, but there's no `/undo` or `/rewind` command. The closest is `/load` a previous save — but that requires the user to have manually saved before the unwanted event. |
| **Prevention** | (1) **Auto-save before conflict injection:** When `inject_conflict()` is called, automatically create a snapshot named `pre_conflict_scene_{N}`. (2) **Add `/undo` command:** Rewinds the last scene by popping the last entry from `scenes[]`, restoring actor emotions and memories to their pre-scene state. Requires storing a "pre-scene snapshot" before each scene. (3) **Add `/redirect <direction>` command:** A softer version of `/undo` — the Director acknowledges the unwanted direction and pivots. Example: "/redirect 不要让角色死亡" → Director narrates a near-death experience instead. (4) **"Safety net" for major events:** Before a character death or irreversible event, the Director should ask: "这个转折不可逆转。确认？" |
| **Phase** | Phase 4 (Router Refactor) — new commands |

---

## Summary Table

| # | Pitfall | Severity | Warning Signs | Prevention | Phase |
|---|---------|----------|---------------|------------|-------|
| 1 | Context window exhaustion | 🔴 CRITICAL | Actor responses generic, latency spikes | 3-tier memory with token budget | Phase 1 |
| 2 | Summarization loses critical details | 🔴 CRITICAL | Logical contradictions | Critical memories, importance-weighted summarization | Phase 1 |
| 3 | Actor forgets backstory | 🟠 HIGH | Out-of-character dialogue | Character anchor in prompt | Phase 1 |
| 4 | State file bloat | 🟡 MEDIUM | Slow save/load, large JSON | Scene archival, debounced saving | Phase 5 |
| 5 | Aimless wandering | 🔴 CRITICAL | No conflict for 3+ scenes | Tension scoring + forced injection | Phase 2 |
| 6 | Repetitive conflict injection | 🟠 HIGH | Same twist type repeated | Conflict type tracking + weighting | Phase 2 |
| 7 | Incoherent Dynamic STORM twists | 🟠 HIGH | Retcon/contradiction | Plot-constrained perspective generation | Phase 3 |
| 8 | Tension never resolves | 🟠 HIGH | 5+ unresolved conflicts | Active conflict lifecycle, arc budget | Phase 2 |
| 9 | Characters avoid conflict | 🟡 MEDIUM | Hedging language, quick resolution | Prompt engineering for dramatic tension | Phase 2 |
| 10 | A2A latency with memory | 🟠 HIGH | Scene takes >60s | Pre-compression, parallel calls | Phase 1 |
| 11 | State complexity explosion | 🟡 MEDIUM | Undocumented state structure | Schema definition, validation | Phase 5 |
| 12 | Race conditions in parallel calls | 🟠 HIGH | State corruption | asyncio.Lock, sequential writes | Phase 5 |
| 13 | Actor service crashes | 🟠 HIGH | Connection errors, dead processes | Health checks, auto-restart | Phase 5 |
| 14 | User feels powerless | 🟠 HIGH | Only /next, no engagement | Choice presentation, steering commands | Phase 4 |
| 15 | User feels overwhelmed | 🟡 MEDIUM | Ignoring prompts, always picking first | Smart defaults, quiet mode | Phase 4 |
| 16 | Uncanny valley plot errors | 🟠 HIGH | Subtle inconsistencies | Knowledge filtering, timeline tracking | Phase 2-5 |
| 17 | Can't recover from bad direction | 🟡 MEDIUM | Frustration, wanting to undo | /undo, auto-snapshots, /redirect | Phase 4 |

---

## Priority Matrix

**Must solve before infinite mode works at all:**
- Pitfall 1 (context exhaustion) → Phase 1
- Pitfall 5 (aimless wandering) → Phase 2
- Pitfall 2 (summarization accuracy) → Phase 1

**Must solve before infinite mode is pleasant:**
- Pitfall 3 (backstory forgetting) → Phase 1
- Pitfall 8 (tension never resolves) → Phase 2
- Pitfall 10 (latency) → Phase 1
- Pitfall 14 (user powerlessness) → Phase 4
- Pitfall 16 (uncanny valley) → Phase 2-5

**Can defer to polish phase:**
- Pitfall 4 (state bloat) → Phase 5
- Pitfall 9 (conflict avoidance) → Phase 2 (prompt)
- Pitfall 11 (state complexity) → Phase 5
- Pitfall 12 (race conditions) → Phase 5
- Pitfall 13 (actor crashes) → Phase 5
- Pitfall 15 (overwhelm) → Phase 4
- Pitfall 17 (bad direction recovery) → Phase 4

---

*Pitfalls research: 2026-04-11*
