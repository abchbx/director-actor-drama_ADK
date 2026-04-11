# Features Research: Infinite Improvisation Multi-Agent Drama

**Research Date:** 2026-04-11

## Table Stakes (Must Have)

These features are non-negotiable for the system to function as an infinite improvisation drama engine. Without any one of these, the system degrades into either a finite drama or an incoherent mess.

### 1. Infinite Narrative Loop

**What:** The drama can continue scene → next scene → next scene indefinitely, with no predefined endpoint or scene count limit. The user decides when to stop.

**Current state:** The system has `/next` → `next_scene()` which increments `current_scene` counter. This is technically infinite (no upper bound), but in practice degrades after ~10–15 scenes because:
- All prior scene content stays in `state["scenes"]` — grows unbounded
- Director context window fills with old scenes
- No mechanism to "forget" old scenes while maintaining coherence

**What's needed:**
- Scene lifecycle: After a scene is summarized and compressed, remove its full content from active state
- Scene transition: Each `/next` must generate a scene that naturally follows the previous one, even when the previous scene is only available as a summary
- No planned ending: The Director's prompt must not assume a 3-act structure; instead, each scene should be treated as the middle of an ongoing story
- Exit mechanism: The user can `/quit` or `/action` an ending event at any time; the Director should be able to create a satisfying ending from any scene

**Validation criteria:**
- A drama can run 50+ scenes without context window overflow
- Scene 30's quality is comparable to scene 3's quality
- The Director can continue generating coherent scenes from summaries alone

### 2. Context/Memory Management

**What:** The system must not lose the plot, even after compressing old scenes. Characters remember what happened to them; the Director remembers the overall arc.

**Current state:** 
- `state["scenes"]` stores full scene content (grows unbounded)
- `state["actors"][name]["memory"]` stores timestamped entries (grows unbounded)
- `state["narration_log"]` stores all narration (grows unbounded)
- No compression, no summarization, no retrieval — everything is appended

**What's needed:**
- **3-tier memory** (detailed in STACK.md): Working (full detail, last 3–5 scenes) + Recent Summary (compressed, scenes 6–20) + Archive (tag-indexed, scenes 21+)
- **Actor memory compression:** Each actor's memory list should be summarized into key facts when it exceeds 20 entries
- **Director context assembly:** Before each scene, build a context payload that fits within the token budget (see STACK.md for budget table)
- **Memory consistency:** When a scene is compressed, ensure no critical information is lost (conflict states, emotional shifts, unresolved plot threads must be preserved in summaries)

**Validation criteria:**
- Context payload for scene 50 is the same size as for scene 5
- No critical plot points are "forgotten" after compression
- Actor responses reference past events correctly even when those events are only in summaries

### 3. User Intervention

**What:** The user can inject events at any time that alter the course of the drama, and the system must incorporate them seamlessly.

**Current state:** The `/action <description>` command exists and triggers `user_action()` → `add_system_message()`. The Director then narrates the event and actors respond. This works for simple injections.

**What's needed:**
- **Event types:** The system should recognize different types of user interventions:
  - **Character action:** "朱棣拔出了剑" — an existing character does something
  - **External event:** "突然地震了" — something happens in the world
  - **New character:** "一个神秘旅人出现了" — introduces a new character
  - **Time skip:** "三年后" — jumps forward in time
  - **Rewind:** "回到上一场之前" — undo/redo (STRETCH — complex with A2A state)
- **Seamless integration:** After a user action, the Director should:
  1. Acknowledge the event in narration
  2. Update affected actors' emotional states
  3. Create or modify plot threads as needed
  4. Resume normal scene flow from the new state
- **No breaking flow:** User intervention should feel like a natural plot twist, not a system interrupt

**Validation criteria:**
- User can inject an event at any scene number
- The drama continues coherently after injection
- Actors react to the injected event in character

### 4. Narrative Coherence

**What:** No contradictions across scenes. If a character is dead, they stay dead. If a promise was made, it's remembered. If it's raining in scene 10, it doesn't suddenly become sunny without explanation.

**Current state:** No coherence checking exists. The Director relies on the LLM's training to maintain consistency, which breaks down over long contexts.

**What's needed:**
- **Plot thread tracking:** A structured list of active/dormant/resolved plot threads (see STACK.md for data structure)
- **World state facts:** A growing list of established facts (location, weather, time of day, character status, possessions)
- **Coherence validation:** Every 5 scenes, run a check comparing new content against established facts
- **Contradiction resolution:** If a contradiction is detected, the Director should either:
  - Retcon the most recent scene (if the contradiction is minor)
  - Generate an explanation scene (if the contradiction is significant)
  - Alert the user for manual resolution (if the contradiction is fundamental)

**Validation criteria:**
- Running a drama for 30+ scenes should produce zero unresolved contradictions
- Established character deaths are never forgotten
- Location/time continuity is maintained

### 5. Dynamic Conflict Injection

**What:** When the plot starts to meander or become aimless, the system automatically injects new conflict to restore dramatic tension.

**Current state:** No conflict detection or injection exists. The Director follows the STORM outline linearly. Once the outline is exhausted (~10–15 scenes), the Director has no guidance and the drama becomes repetitive.

**What's needed:**
- **Tension scoring:** After each scene, compute a tension score (0–10) based on active conflicts, emotional intensity, plot thread staleness (see STACK.md for formula)
- **Injection trigger:** When tension drops below 3.0 for 3+ consecutive scenes, OR when the Director has been following the same emotional arc for 5+ scenes
- **Conflict catalog:** A set of conflict archetypes the Director can draw from (see STACK.md for catalog)
- **Natural integration:** Injected conflicts should emerge from the story's internal logic (a character's past, an unresolved thread, a world event), not from thin air
- **Tension curve:** Aim for a sawtooth pattern — tension rises to 7–8, partially resolves to 4–5, rises again to 8–9 with a new conflict. Avoid flatlining at any level.

**Validation criteria:**
- The tension score never stays below 3.0 for more than 3 consecutive scenes
- Injected conflicts feel organic, not arbitrary
- The user can override conflict injection with `/action`

---

## Differentiators

These features distinguish this system from a simple "chat with AI characters" experience. They are what make it an **infinite improvisation drama engine** rather than a roleplay chatbot.

### 6. Dynamic STORM (Re-discover Perspectives Every N Scenes)

**What:** The existing STORM framework (Discovery → Research → Outline → Directing) runs once at drama start. Dynamic STORM re-triggers the discovery and research phases periodically, injecting new perspectives that the original STORM didn't consider.

**How it works:**
1. **Trigger:** Every 10 scenes (configurable), OR when tension drops below threshold for 3+ scenes
2. **Mini-Discovery:** Generate 2–3 new perspectives based on current state:
   - "What has changed since the initial STORM?"
   - "What perspectives are under-represented?"
   - "What would a completely new viewer notice?"
3. **Mini-Research:** Explore each new perspective briefly (1 LLM call per perspective, not the full multi-call research)
4. **Outline Update:** Add new plot threads, conflicts, or character arcs to the existing outline
5. **Seamless Integration:** The Director incorporates the new outline elements into upcoming scenes

**Why it matters:** Static STORM creates a finite drama (the outline runs out). Dynamic STORM makes the drama genuinely infinite — new perspectives keep emerging, ensuring the story never runs out of ideas.

**Interaction with other features:**
- Depends on: Plot thread tracking (#4), Tension scoring (#5)
- Feeds into: Conflict injection (#5), Context management (#2)

### 7. Layered Memory (Recent Detailed, Old Summarized)

**What:** Not just the Director's context window — the entire system's approach to memory is layered. Actors also receive layered memory: recent scenes in detail, older scenes as summaries.

**Current actor memory model:**
- Each actor receives only what the Director sends them via A2A message
- Actor's own session accumulates full conversation history
- No compression on the actor side

**Enhanced actor memory model:**
- **Actor working memory:** Last 2–3 scenes of their own dialogue (in-context)
- **Actor summary memory:** Compressed recap of their older scenes (sent as part of the instruction)
- **Actor knowledge boundary:** Defined by `knowledge_scope` at creation (unchanged)
- **Actor emotional trajectory:** List of emotional states per scene (not just current emotion)

**Implementation:**
- Before sending an A2A message to an actor, the Director assembles a context packet:
  - Character definition (personality, background, knowledge_scope)
  - Recent dialogue (last 2–3 scenes)
  - Summary of relevant older scenes
  - Current scene instruction
- This is assembled by `context_builder.py` (new module)

### 8. Conflict Tension Scoring

**What:** A quantitative measure of dramatic tension that drives automated conflict injection and STORM re-triggering.

**Score components:**
- **Active conflict count** (weight: 1.5 each): Number of unresolved conflicts in `state["active_conflicts"]`
- **Average emotional intensity** (weight: 1.0): How far actors' emotions are from "neutral"
- **Dormant plot threads** (weight: 0.5 each): Threads not updated in 5+ scenes
- **Staleness factor** (weight: 0.3): Scenes since last major event
- **Decay factor:** Tension naturally decays by 0.5 per scene unless new events occur

**Score thresholds:**
| Score | State | Action |
|-------|-------|--------|
| 0–2 | Flatlined | URGENT: inject conflict within 1 scene |
| 2–4 | Low | Plan conflict injection in next 1–2 scenes |
| 4–6 | Moderate | Good range; no intervention needed |
| 6–8 | High | Climactic moment; may want to sustain or partially resolve |
| 8–10 | Peak | Must resolve or de-escalate within 2 scenes; sustained peak is exhausting |

**Visualization (future):** Display tension curve to user as part of `/status`.

### 9. Actor Emotion Evolution Tracking

**What:** Track not just an actor's current emotion, but their emotional trajectory across scenes. This enables:
- Plausible emotional transitions (no unexplained jumps)
- Emotional callbacks (a character revisits an old emotion)
- Director awareness of emotional stagnation

**Current state:** `state["actors"][name]["emotions"]` stores a single string (e.g., "neutral", "anxious")

**Enhanced model:**
```python
{
    "actors": {
        "朱棣": {
            "emotions": "焦躁而坚定",
            "emotion_trajectory": [
                {"scene": 1, "emotion": "自信", "trigger": "初登王位"},
                {"scene": 5, "emotion": "焦虑", "trigger": "削藩密信"},
                {"scene": 8, "emotion": "愤怒", "trigger": "被监视"},
                {"scene": 12, "emotion": "焦躁而坚定", "trigger": "道衍的建议"}
            ],
            "emotion_valence": 0.3,  # -1.0 (despair) to 1.0 (joy)
            "emotion_arousal": 0.7   # 0.0 (calm) to 1.0 (agitated)
        }
    }
}
```

**Valence-Arousal model:** Each emotion maps to a (valence, arousal) coordinate:
- Valence: positive/negative feeling direction
- Arousal: intensity/activation level

This allows the Director to:
- Detect emotional stagnation (trajectory stays in the same quadrant for 5+ scenes)
- Plan emotional arcs (move a character from low-arousal negative to high-arousal negative → climax)
- Validate transitions (valence shouldn't jump from -0.8 to +0.8 without a trigger)

### 10. Multi-Perspective Narrative Weaving

**What:** The same scene can be experienced differently by different actors. The Director can choose to show a scene from multiple character perspectives, not just a single omniscient viewpoint.

**Implementation:**
- After a scene's main narration, the Director can optionally request a **perspective retell** from a specific actor
- The actor's A2A agent generates their version of events, filtered through their `knowledge_scope` and `emotions`
- The Director weaves these perspectives together in the final scene output

**Example:**
- Scene 15: 朱棣 and 道衍 have a heated argument
- Default: Director narrates the argument from an omniscient perspective
- Perspective retell: The Director also asks 马皇后 (who was listening from behind a screen) to describe what she heard
- Weaving: The scene output includes all three perspectives, showing how each character perceived the same event differently

**Why it matters:** This is the core artistic innovation — the drama isn't just a single narrative, it's a tapestry of subjective experiences. It directly leverages the A2A cognitive isolation (each actor truly doesn't know what others are thinking).

---

## Anti-Features (Deliberately NOT Building)

These are explicitly out of scope. Documenting them prevents scope creep and helps prioritize.

### ❌ Multi-User Collaboration

**Why not:** The architecture is single-user CLI. A2A actors are per-session, not shared. Multi-user would require:
- Shared state management (conflict resolution)
- Real-time synchronization
- User identification and permission system
- Completely different CLI → Web architecture

**Cost:** Would triple the project scope. The single-user experience is already hard enough.

### ❌ Voice/Video Output

**Why not:** The system is text-only. Adding voice would require:
- TTS integration (additional API dependency)
- Audio playback infrastructure
- Timing/synchronization for dramatic delivery
- Video would require character animation (orders of magnitude more complex)

**Cost:** Massive infrastructure addition with no core value improvement. The text format IS the medium — it's a drama script, not a movie.

### ❌ Custom Model Selection UI

**Why not:** The system uses `LiteLlm` with env var configuration. Adding a model selection UI would require:
- Frontend for model configuration
- Model compatibility testing (different models have different context windows, instruction following)
- Prompt optimization per model
- Cost tracking per model

**Cost:** Significant frontend work + ongoing maintenance. The current env var approach (`MODEL_NAME`) is sufficient for power users. Non-power users benefit from a single well-tested model.

### ❌ Real-Time Streaming UI

**Why not:** The current system is request-response (type `/next`, get a scene). Streaming would require:
- SSE/WebSocket infrastructure
- Progressive rendering of scene output
- Actor A2A calls would need to be orchestrated as a stream
- UI that can handle partial updates gracefully

**Cost:** Significant architectural change. The CLI is naturally request-response. Streaming is a UX optimization, not a feature.

### ❌ Branching Narratives / Save Scumming

**Why not:** The system saves snapshots, but we're NOT building:
- A branching tree of narrative choices
- A "go back to scene N and make a different choice" mechanic
- A parallel timelines viewer

**Rationale:** The drama is improvisation, not a choose-your-own-adventure. The user's choices are final. Branching would require:
- Full state copy per branch
- Branch visualization
- Merge mechanics for converging branches

**The `/save` + `/load` snapshot system is sufficient** for the "what if I had done X differently?" use case.

---

## Feature Dependencies (Build Order)

The features form a dependency graph. Some features must be built before others.

### Dependency Graph

```
Layer 1 (Foundation — no dependencies):
├── #2 Context/Memory Management (3-tier memory, scene compression)
└── #4 Narrative Coherence (plot thread tracking, world state facts)

Layer 2 (Core Engine — depends on Layer 1):
├── #1 Infinite Narrative Loop (depends on #2: can't loop without memory management)
├── #5 Dynamic Conflict Injection (depends on #4: needs plot threads to know what's "flat")
└── #9 Actor Emotion Evolution Tracking (depends on #2: needs memory tiers for trajectory)

Layer 3 (Intelligence — depends on Layer 2):
├── #8 Conflict Tension Scoring (depends on #5: needs conflict model; depends on #9: needs emotions)
└── #3 User Intervention Enhancement (depends on #1: needs infinite loop; depends on #4: needs plot threads)

Layer 4 (Differentiation — depends on Layer 3):
├── #6 Dynamic STORM (depends on #8: uses tension as trigger; depends on #4: needs plot threads)
├── #7 Layered Actor Memory (depends on #2: needs memory tiers; depends on #9: needs emotion trajectory)
└── #10 Multi-Perspective Weaving (depends on #7: needs actor memory; depends on #1: needs infinite loop)
```

### Recommended Build Phases

**Phase 1: Memory Foundation (build #2 + #4 together)**
- `app/memory_manager.py` — 3-tier memory, scene compression, context assembly
- `app/narrative_engine.py` — plot thread tracking, world state facts, tension scoring
- Modify `app/state_manager.py` — add `plot_threads`, `active_conflicts`, `world_facts`, `summaries` fields
- Modify `app/agent.py` — Director prompt uses `memory_manager` to assemble context
- **Validation:** Run a 30-scene drama; verify summaries are generated correctly; verify plot threads are tracked

**Phase 2: Infinite Loop + Conflict Engine (build #1 + #5 + #9)**
- `app/narrative_engine.py` — add conflict injection, tension scoring formula, conflict archetype catalog
- Modify `app/agent.py` — Director checks tension after each scene; injects conflict when needed
- Extend `state_manager.py` — `emotion_trajectory` field, `emotion_valence`/`emotion_arousal`
- Modify `actor_service.py` — actors receive layered context packets
- **Validation:** Run a 50-scene drama; verify no context overflow; verify tension stays above 3.0; verify emotional transitions are plausible

**Phase 3: Dynamic STORM + Coherence (build #6 + coherence checks)**
- `app/coherence_checker.py` — contradiction detection, emotional continuity validation
- Modify `app/narrative_engine.py` — Mini-STORM trigger, perspective re-discovery
- Modify `app/agent.py` — Director prompt includes dynamic STORM results
- **Validation:** Run a 100-scene drama; verify STORM re-triggers at correct intervals; verify no contradictions

**Phase 4: User Experience + Differentiation (build #3 + #7 + #10)**
- Enhance `/action` command with event type detection
- Build `app/context_builder.py` — actor-specific context packets with layered memory
- Add perspective retell to Director's scene workflow
- **Validation:** User can inject events seamlessly; actor responses show layered memory; multi-perspective scenes are coherent

### Critical Path

```
#2 Memory → #1 Infinite Loop → #8 Tension Scoring → #6 Dynamic STORM
```

This is the critical path. Without memory management, the infinite loop is impossible. Without the infinite loop, tension scoring has nothing to score. Without tension scoring, Dynamic STORM has no trigger. Each step must work before the next can be built.

### Estimated Complexity

| Feature | New Modules | Modified Modules | Complexity | Risk |
|---------|------------|-----------------|------------|------|
| #2 Memory Management | 1 (`memory_manager.py`) | `state_manager.py`, `agent.py` | HIGH | HIGH — LLM summarization quality determines everything |
| #4 Narrative Coherence | 0 (in `narrative_engine.py`) | `state_manager.py` | MEDIUM | MEDIUM — plot thread tracking is straightforward; contradiction detection depends on LLM quality |
| #1 Infinite Loop | 0 (uses #2) | `agent.py`, `tools.py` | LOW | LOW — once memory management works, this is just removing the bounded mindset from prompts |
| #5 Conflict Injection | 0 (in `narrative_engine.py`) | `agent.py` | MEDIUM | MEDIUM — conflict archetype effectiveness must be tested |
| #9 Emotion Tracking | 0 | `state_manager.py`, `agent.py` | LOW | LOW — extending a single string to a list |
| #8 Tension Scoring | 0 (in `narrative_engine.py`) | `agent.py` | MEDIUM | MEDIUM — formula needs real-world tuning |
| #3 User Intervention | 0 | `tools.py`, `agent.py` | LOW | LOW — enhancing existing `/action` |
| #6 Dynamic STORM | 0 (in `narrative_engine.py`) | `agent.py` | HIGH | HIGH — re-triggering STORM mid-drama is untested; may produce incoherent results |
| #7 Layered Actor Memory | 1 (`context_builder.py`) | `actor_service.py`, `agent.py` | MEDIUM | MEDIUM — actor context packets must be well-scoped |
| #10 Multi-Perspective | 0 | `agent.py`, `tools.py` | MEDIUM | MEDIUM — perspective weaving quality depends on LLM |

### What Can Go Wrong

| Risk | Impact | Mitigation |
|------|--------|------------|
| Summarization loses critical details | HIGH — characters "forget" key events | Use structured summaries with mandatory fields (key_events, emotional_shifts, unresolved_conflicts) |
| Tension scoring formula is wrong | MEDIUM — conflicts injected at wrong times | Make formula configurable; start conservative (inject too early is better than too late) |
| Dynamic STORM produces incoherent new directions | HIGH — drama quality degrades | Limit Mini-STORM to adding 1–2 new perspectives, not replacing the outline; require Director validation |
| Actor emotion tracking is too granular | LOW — unnecessary complexity | Start with simple trajectory list; add valence/arousal only if needed |
| Conflict injection feels arbitrary | HIGH — breaks immersion | Always derive injections from existing plot threads or character backstories; never from thin air |

---

*Features research: 2026-04-11*
