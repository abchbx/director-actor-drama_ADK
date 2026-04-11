# Stack Research: Infinite Improvisation Multi-Agent Drama

**Research Date:** 2026-04-11

## Current Stack (from codebase map)

| Component | Current | Version | Notes |
|-----------|---------|---------|-------|
| Language | Python | 3.10–3.13 | Locked `>=3.10,<3.14` |
| Agent Framework | Google ADK | >=1.15.0,<2.0.0 | Core: `Agent`, `BaseAgent`, `Runner`, `LiteLlm`, `ToolContext` |
| Inter-Agent Protocol | a2a-sdk | ~=0.3.22 | A2A: `ClientFactory`, `Message`, `Task` |
| LLM Interface | LiteLlm | (via ADK) | OpenAI-compatible, default `openai/claude-sonnet-4-6` |
| ASGI Server | uvicorn | >=0.30.0 | One per actor process |
| State Persistence | JSON files | N/A | `app/dramas/<theme>/state.json` |
| Session Service | InMemorySessionService | (via ADK) | Director session only |
| Test Runner | pytest | >=8.3.4,<9.0.0 | With pytest-asyncio |
| Package Manager | uv | latest | With hatchling build system |
| Lint/Format | ruff | >=0.4.6,<1.0.0 | line-length: 88 |

## New Stack Needs

### 1. Memory/Context Management

**The Problem:** A drama that runs for 50+ scenes accumulates far more context than any LLM window can hold (~200K tokens). Each scene contains narration + N actor dialogues + emotional states + STORM perspectives. By scene 30, the full history exceeds 200K tokens. The current system stores everything in `state.json` and `_conversation_log` with no compression strategy.

**Options Evaluated:**

#### Option A: Custom Layered Memory (RECOMMENDED)

Build a 3-tier memory system using only the existing JSON file persistence + a small in-memory cache. No new database dependency.

- **Tier 1 — Working Memory (in-context):** Last 3–5 scenes in full detail, current actor states, active STORM perspectives. Fits within ~50K tokens. Stored in `tool_context.state["drama"]`.
- **Tier 2 — Recent Summary (compressed):** Scenes 6–20 summarized into a structured recap (~5K tokens). One summary per scene, each ~200–300 tokens. Stored as `summaries/<scene_number>.json`.
- **Tier 3 — Archive (semantic retrieval):** Scenes 21+ stored as individual scene files with embeddings for retrieval. Store in `scenes/<scene_number>.json` with a lightweight embedding index.

**Implementation approach:**
- After each scene completes, run a summarization LLM call to compress the scene into ~200 tokens of structured summary (key events, emotional shifts, plot threads, unresolved conflicts).
- At scene start, load Tier 1 + Tier 2 summaries + Tier 3 retrieved scenes (top-K relevant to current context).
- Use the existing `state.json` structure, adding a `memory_tiers` field.

**Why NOT use an external vector DB:**
- The project's Key Decision is "保留文件系统持久化 — JSON 文件持久化简单可靠，不需要引入数据库"
- For a single-user CLI drama system, ChromaDB/FAISS/Redis add operational complexity with no meaningful benefit
- Scene-level retrieval is bounded (even a 200-scene drama has at most ~200 retrieval candidates) — a simple JSON index with keyword matching suffices
- Embedding generation adds latency and API cost per scene; the LLM itself can judge relevance when given scene summaries

#### Option B: mem0 (REJECTED)

- Version: 0.0.26 (latest stable as of 2026-04)
- Pros: Self-improving memory layer, graph memory for entity relationships, ~90% token reduction claimed
- Cons: **Violates the "no database" constraint** — mem0 requires a vector store backend (ChromaDB/Qdrant/Postgres + pgvector); adds `mem0` + embedding model dependency; designed for user-level personalization, not narrative scene management; graph memory is over-engineered for our entity-tracking needs (we already track actors/emotions in state)
- Verdict: Over-engineered for a single-user narrative system. The memory pattern we need (scene → summary → retrieval) doesn't match mem0's user/session/agent memory model.

#### Option C: ChromaDB for Semantic Retrieval (REJECTED for now, possible future)

- Version: 1.0.0+ (stable release available)
- Pros: Embedded mode (no server needed), Python-native, good for semantic search over scene archives
- Cons: Adds a heavy dependency (~200MB with ONNX); embedding model adds latency; the "no database" decision in PROJECT.md explicitly rules this out; file-based JSON with manual keyword matching covers our retrieval needs for up to ~500 scenes
- Verdict: Could be revisited if dramas regularly exceed 200+ scenes and keyword retrieval proves insufficient. Not needed for v1.

#### Option D: FAISS (REJECTED)

- Requires separate embedding model; adds C++ build dependency; no embedded Python-only mode; overkill for ~200 scene retrieval
- Verdict: Not suitable for a CLI-only, single-user system

### 2. Context Window Optimization

**The Problem:** Each scene invocation to the Director agent needs to fit within the LLM context window. The Director needs: system prompt + STORM outline + recent scenes + actor states + current scene instructions. This budget must be managed explicitly.

**Techniques Evaluated:**

#### Progressive Summarization (RECOMMENDED)

After each scene, generate 3 levels of summary:

- **Scene Digest** (~150 tokens): What happened, key dialogue quotes, emotional shifts
- **Plot Thread Update** (~100 tokens): Which ongoing plot threads advanced, which are dormant, any new threads
- **Conflict State** (~50 tokens): Current tension level, unresolved conflicts, power dynamics

These summaries replace the full scene text in context for all scenes beyond the working memory window.

**Implementation in `app/state_manager.py`:**
```python
def compress_scene(scene_number: int, tool_context=None) -> dict:
    """Compress a full scene into a structured summary."""
    # Call LLM to generate digest, plot threads, conflict state
    # Store summary in state["summaries"][scene_number]
    # Remove full scene content from active state (keep on disk)
```

**Token budget per scene invocation (200K window):**

| Component | Token Budget | Notes |
|-----------|-------------|-------|
| System prompt (Director instruction) | ~3,000 | Fixed, from `agent.py` |
| STORM outline | ~2,000 | Fixed, from `state["storm"]["outline"]` |
| Actor registry + emotions | ~1,500 | Fixed, grows with actor count |
| Working memory (last 3–5 scenes full) | ~15,000 | ~3K–5K per scene |
| Recent summaries (scenes 6–20) | ~5,000 | ~350 tokens per scene summary |
| Retrieved archive scenes (top-K) | ~3,000 | 2–3 relevant old scenes |
| Current scene generation | ~100,000 | Leave 50%+ for generation |
| **Total context** | **~129,500** | Well within 200K |

#### Hierarchical Memory (ADOPTED as the 3-tier model above)

The Director maintains a mental model at 3 granularities:
1. **Full detail** for recent scenes (immediate context)
2. **Structured summary** for mid-range scenes (continuity)
3. **Keyword-indexed archive** for distant scenes (retrieval on demand)

#### RAG for Scene Retrieval (SIMPLIFIED)

Full RAG with vector embeddings is overkill. Instead:

- Each scene gets a **tag set** when summarized: character names, location, emotional keywords, conflict types
- At scene start, the Director's tool can search tags to find relevant old scenes
- This is essentially RAG without the vector DB — tag matching replaces embedding similarity

```python
def retrieve_relevant_scenes(tags: list[str], current_scene: int, tool_context=None) -> dict:
    """Find scenes relevant to current context by tag matching."""
    # Load summaries from state["summaries"]
    # Match against provided tags (character names, themes, locations)
    # Return top-K matching summaries
```

### 3. Narrative/Event Engine

**The Problem:** The current system advances scenes linearly (`/next` → `next_scene()` → scene number++). There's no mechanism for:
- Detecting when the plot is "flat" (no tension)
- Injecting unexpected events at dramatic moments
- Ensuring narrative coherence across long runs
- Managing the dramatic arc (Freitag's pyramid: exposition → rising action → climax → falling action → resolution)

**No Off-the-Shelf Solution:** There is no Python library that provides a "narrative engine" for turn-based dramatic generation. Ink and Twine are authoring tools for branching narratives, not engines for AI-generated content. AI Dungeon's approach is a monolithic GPT call with context — no structured conflict management.

**RECOMMENDED: Build a custom Narrative Engine as a new module `app/narrative_engine.py`**

#### Conflict/Tension Injection Patterns

**Pattern 1: Tension Score Tracking**

After each scene, compute a tension score (0–10) based on:
- Number of active conflicts (from `state["conflicts"]`)
- Emotional intensity of actors (from `state["actors"][name]["emotions"]`)
- Unresolved plot threads (from `state["plot_threads"]`)
- Time since last major event (scenes since last conflict escalation)

```python
def compute_tension_score(state: dict) -> float:
    """Compute current dramatic tension (0.0–10.0)."""
    conflicts = len(state.get("active_conflicts", []))
    avg_emotion_intensity = _avg_emotion(state.get("actors", {}))
    dormant_threads = _count_dormant_threads(state)
    stale_factor = state.get("current_scene", 0) - state.get("last_climax_scene", 0)
    return min(10.0, conflicts * 1.5 + avg_emotion_intensity + dormant_threads * 0.5 + stale_factor * 0.3)
```

**When tension drops below 3.0 for 3+ consecutive scenes → inject conflict.**

**Pattern 2: Conflict Injection Catalog**

Pre-define conflict archetypes that the Director can draw from:

| Archetype | Description | Example |
|-----------|-------------|---------|
| New character | A stranger arrives | An old rival appears at the door |
| Secret revealed | Hidden information surfaces | A letter is found exposing a lie |
| Forced choice | Character must choose between two values | Save the village OR save the loved one |
| Power shift | Someone gains or loses power | The king falls ill, succession crisis |
| Betrayal | Trusted ally acts against interest | The advisor has been working for the enemy |
| External threat | Outside force disrupts the world | War breaks out, plague arrives |
| Time pressure | Deadline imposed | The treaty expires at dawn |

Each injection is a structured event that the Director incorporates via `user_action`-like mechanism.

**Pattern 3: Dynamic STORM Re-trigger**

The existing STORM framework (Discovery → Research → Outline → Directing) currently runs once at the start. For infinite drama:

- Every N scenes (default: 10), or when tension drops below threshold, trigger a **Mini-STORM** cycle:
  1. **Re-discover** perspectives based on current state (what's changed since initial STORM?)
  2. **Identify gaps** — what plot threads are unresolved? What characters are under-utilized?
  3. **Inject new conflict** — add a new perspective/conflict that the current drama doesn't cover
  4. **Update outline** — revise the STORM outline to incorporate new directions

This is distinct from the initial STORM: it starts from the current state, not from the theme.

#### Narrative Coherence Patterns

**Pattern 1: Plot Thread Tracking**

Maintain a structured list of plot threads in state:

```python
{
    "plot_threads": [
        {
            "id": "thr_1",
            "description": "朱棣的夺位野心",
            "status": "active",  # active | dormant | resolved
            "involved_actors": ["朱棣", "道衍"],
            "introduced_scene": 3,
            "last_updated_scene": 15,
            "resolution_conditions": "朱棣做出最终抉择"
        }
    ]
}
```

**Pattern 2: Contradiction Detection (LLM-assisted)**

Every 5 scenes, run a coherence check:
- Feed the Director a prompt with all plot thread summaries
- Ask: "Are there any contradictions with established facts?"
- If contradictions found, flag them and generate a correction scene

**Pattern 3: Emotional Continuity**

Actor emotions are already tracked in `state["actors"][name]["emotions"]`. Extend to:
- Track emotion **trajectory** (not just current state) — e.g., `["calm", "worried", "anxious", "angry"]`
- Before generating a new scene, validate that the emotional transition is plausible given the last 2 scenes
- If an actor's emotion jumps implausibly (e.g., "joyful" → "furious" with no trigger), the Director should add an intervening event

### 4. Token Budgeting for Multi-Agent Calls

**The Problem:** Each scene involves:
1. Director narration call (~2K output tokens)
2. N actor speak calls (~500 tokens each, N = 2–5 actors)
3. Scene summarization call (~300 output tokens)
4. Optional: tension scoring, coherence check

**Total per scene: ~5K–8K tokens in LLM calls.** For 100 scenes = ~500K–800K tokens.

**Budget Strategy:**

| Call Type | Max Output Tokens | Rationale |
|-----------|-------------------|-----------|
| Director narration | 2,000 | Scene description + atmosphere |
| Actor dialogue (per actor) | 500 | One speech + action per scene |
| Scene summarization | 300 | Structured summary (digest + threads + conflicts) |
| Tension scoring | 100 | Numeric score + brief rationale |
| Coherence check (every 5 scenes) | 500 | List contradictions found |
| Mini-STORM (every 10 scenes) | 3,000 | New perspectives + revised outline |

**Actor context window management:**
- Each actor is an independent A2A agent with its own session
- Actor context = system prompt (character definition) + recent dialogue (last 3 scenes of their lines) + director instruction for current scene
- Actor memory is managed separately from Director memory — actors only receive their own dialogue history, not the full scene text
- This is already enforced by A2A isolation; we just need to ensure the Director sends appropriately scoped instructions

## Recommendations Table

| Component | Library/Approach | Version | Confidence | Rationale |
|-----------|-----------------|---------|------------|-----------|
| **Layered Memory** | Custom 3-tier (Working + Summary + Archive) | N/A (build) | HIGH | Matches "no database" constraint; sufficient for single-user CLI; 200-scene bound makes vector DB unnecessary |
| **Scene Summarization** | LLM call per scene via LiteLlm | via ADK | HIGH | Already have LLM access; no new dependency; ~300 tokens per summary is cheap |
| **Semantic Retrieval** | Tag-based matching on JSON summaries | N/A (build) | HIGH | Simple, no new deps, sufficient for bounded corpus; upgrade to ChromaDB later if needed |
| **Context Budget** | Explicit token budgets per call type | N/A (build) | HIGH | Deterministic, testable; prevents quality degradation from context overflow |
| **Tension Scoring** | Custom formula (conflicts + emotions + staleness) | N/A (build) | MEDIUM | No off-the-shelf solution; formula can be tuned; must validate with real dramas |
| **Conflict Injection** | Conflict archetype catalog + Director prompt | N/A (build) | MEDIUM | Inspired by Ink/interactive fiction patterns; no Python library for this; must test archetype effectiveness |
| **Dynamic STORM** | Re-trigger STORM cycle every N scenes | N/A (build) | MEDIUM | Extends existing STORM architecture; untested for infinite drama; may need trigger timing tuning |
| **Plot Thread Tracking** | Structured state in `plot_threads` | N/A (build) | HIGH | Simple data structure; existing state_manager pattern; critical for coherence |
| **Coherence Checking** | LLM-assisted every 5 scenes | via LiteLlm | MEDIUM | Adds ~1 call per 5 scenes; catches contradictions early; LLM may miss subtle contradictions |
| **Emotion Tracking** | Extend existing `emotions` field to trajectory list | N/A (build) | HIGH | Already have single emotion state; trajectory is a natural extension |
| **mem0** | NOT RECOMMENDED | 0.0.26 | — | Violates no-DB constraint; wrong abstraction (user personalization vs. scene management) |
| **ChromaDB** | DEFERRED (revisit for v2) | 1.0.0+ | — | Could upgrade tag-matching to semantic search if dramas exceed 500+ scenes |
| **FAISS** | NOT RECOMMENDED | N/A | — | C++ build dependency; overkill; no embedded Python mode |
| **Redis** | NOT RECOMMENDED | N/A | — | Adds infra dependency; single-user CLI doesn't need distributed cache |
| **Ink/Twine** | NOT APPLICABLE | N/A | — | Authoring tools for human-written branching narratives; not engines for AI generation |

## New Dependencies Required

**Zero new runtime dependencies.** All recommended approaches are built on:
- Existing `google-adk` + `LiteLlm` for LLM calls
- Existing `state_manager.py` patterns for state persistence
- Existing JSON file storage for all data
- New Python modules in `app/` for narrative engine logic

**Optional future dependency (v2):**
- `chromadb>=1.0.0` — only if semantic retrieval proves necessary for 500+ scene dramas

## Implementation Modules

New modules to create:

| Module | Purpose | Dependencies |
|--------|---------|--------------|
| `app/memory_manager.py` | 3-tier memory: compress scenes, load context, retrieve relevant | Existing state_manager, LiteLlm |
| `app/narrative_engine.py` | Tension scoring, conflict injection, plot thread tracking | Existing state_manager |
| `app/coherence_checker.py` | Contradiction detection, emotional continuity validation | LiteLlm |
| `app/context_builder.py` | Assemble context for Director/Actor calls within token budget | memory_manager, state_manager |

---

*Stack research: 2026-04-11*
