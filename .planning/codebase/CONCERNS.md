# Codebase Concerns

**Analysis Date:** 2026-04-25

## Tech Debt

**Single-process state management:**
- Issue: InMemorySessionService is single-process only; state lost on server restart (partially mitigated by disk restore)
- Files: `app/api/app.py` (lifespan), `app/state_manager.py` (_restore_session_state)
- Impact: Hot-reload via uvicorn WatchFiles kills all state; concurrent users share one session
- Fix approach: Consider persistent session service (SQLite-backed) or external state store

**tools.py is 97KB / ~2700 lines:**
- Issue: Monolithic file containing 40+ tool functions, A2A call logic, crash recovery, shared client
- Files: `app/tools.py`
- Impact: Hard to navigate, slow to load, high cognitive overhead for modifications
- Fix approach: Split into domain modules (scene_tools.py, actor_tools.py, storm_tools.py, etc.)

**Dynamic code generation for actors:**
- Issue: `generate_actor_agent_code()` builds Python source code as f-strings, including API keys
- Files: `app/actor_service.py` (lines 48-168)
- Impact: No IDE support, hard to debug, API keys embedded in generated code files
- Fix approach: Template-based code generation or shared actor runtime with config injection

**No typed tool return models:**
- Issue: All tool functions return `dict` with no schema enforcement; keys documented in docstrings only
- Files: `app/tools.py` (all 40+ functions)
- Impact: Easy to introduce breaking changes to frontend event mapping; no compile-time safety
- Fix approach: Define Pydantic models for tool return types, especially for actor_speak, director_narrate, write_scene

## Known Bugs

**Duplicate WS events from dual-phase emission:**
- Symptoms: Backend emits both function_call and function_response events for same tool, causing duplicate "dialogue" events where first has empty text
- Files: `app/api/event_mapper.py` (map_runner_event), `android/.../DramaDetailViewModel.kt` (handleWsEvent)
- Trigger: Every tool call produces two events — call phase (text="") and response phase (text=full content)
- Workaround: Android checks `if (text.isBlank()) return` before creating bubbles

**State drift on hot-reload:**
- Symptoms: After uvicorn hot-reload, _restore_session_state may pick wrong drama if _active_theme marker is stale
- Files: `app/api/app.py` (_restore_session_state)
- Trigger: Code changes while drama is active → server restarts → state restored from disk
- Workaround: _active_theme marker file + mtime fallback

## Security Considerations

**API keys in generated actor code:**
- Risk: OPENAI_API_KEY embedded in dynamically generated Python files under `app/actors/`
- Files: `app/actor_service.py` (line 75: `os.environ["OPENAI_API_KEY"] = {repr(api_key)}`)
- Current mitigation: .gitignore excludes actors directory pattern... but actor files are committed
- Recommendations: Inject API keys via environment variables at runtime, not source code embedding

**No rate limiting:**
- Risk: Any client (with valid token) can flood the API with commands, overwhelming the LLM
- Files: `app/api/routers/commands.py`
- Current mitigation: asyncio.Lock serializes Runner access (prevents concurrent commands)
- Recommendations: Add rate limiting middleware per client IP

**CORS allows all origins:**
- Risk: `allow_origins=["*"]` in production
- Files: `app/api/app.py` (line 181)
- Current mitigation: None
- Recommendations: Restrict to actual client origins in production

## Performance Bottlenecks

**Actor A2A calls are sequential:**
- Problem: In a scene with N actors, director calls actor_speak() N times sequentially (each 5-30s)
- Files: `app/tools.py` (actor_speak), `app/agent.py` (improv_director instruction)
- Cause: LLM generates one tool call at a time, and each A2A call blocks
- Improvement path: Parallel actor_speak calls (would require changes to ADK agent instruction + tool design)

**tools.py import chain loads everything:**
- Problem: Importing `app.tools` loads 15+ modules (conflict_engine, arc_tracker, coherence_checker, etc.)
- Files: `app/tools.py` (lines 1-107)
- Cause: All imports at module top level
- Improvement path: Lazy imports for rarely-used modules

**WebSocket replay buffer unbounded memory:**
- Problem: replay_buffer stores up to 100 events with full data dicts in memory
- Files: `app/api/ws_manager.py` (line 27: `deque(maxlen=100)`)
- Cause: Design choice for late-joining clients
- Improvement path: Acceptable as-is; 100 events is reasonable

## Fragile Areas

**Event mapper ↔ ViewModel coupling:**
- Files: `app/api/event_mapper.py` ↔ `android/.../DramaDetailViewModel.kt` (handleWsEvent)
- Why fragile: Event type strings ("dialogue", "narration", "actor_chime_in") are hardcoded in both backend and frontend with no shared schema; adding/removing/renaming events requires coordinated changes
- Safe modification: Add new event types with backward-compatible defaults; never remove existing types
- Test coverage: No automated tests for event mapping correctness

**Tool return dict ↔ Repository extraction coupling:**
- Files: `app/tools.py` (return dicts) ↔ `android/.../DramaRepositoryImpl.kt` (extractBubblesFromCommandResponse)
- Why fragile: Android extracts `result["actor_name"]`, `result["text"]`, `result["emotion"]` from untyped dicts; key name changes break silently
- Safe modification: Never rename dict keys in tool returns; add new keys only
- Test coverage: None

**SceneBubble serialization ↔ local save system:**
- Files: `android/.../domain/model/SceneBubble.kt` ↔ `android/.../data/local/DramaSaveRepository.kt`
- Why fragile: SceneBubble uses kotlinx.serialization with @SerialName; changes to sealed class hierarchy break saved state deserialization
- Safe modification: Add new subtypes with default values; never remove or rename existing fields
- Test coverage: None for save/load roundtrip

## Scaling Limits

**Single-user session:**
- Current capacity: 1 concurrent user (single InMemorySessionService with hardcoded USER_ID/SESSION_ID)
- Limit: Hard limit — all requests share the same session
- Scaling path: Multi-session support requires session-per-user architecture

**WebSocket connections:**
- Current capacity: 10 concurrent WS connections (MAX_CONNECTIONS in ws_manager.py)
- Limit: Designed for single-user + testing
- Scaling path: Increase limit, add per-connection session isolation

**Actor service ports:**
- Current capacity: 100 unique ports (9001-9100, based on name hash)
- Limit: Port collision possible with many actors or cross-drama actor names
- Scaling path: Dynamic port allocation with port registry

## Dependencies at Risk

**google-adk (Agent Development Kit):**
- Risk: Pre-release / rapidly evolving; API may change
- Impact: Agent orchestration, A2A, Runner all depend on it
- Migration plan: Pin version in pyproject.toml; abstract ADK interfaces behind wrappers

**a2a-sdk:**
- Risk: Tightly coupled with ADK; version compatibility required
- Impact: All actor communication
- Migration plan: Pin compatible version with ADK

## Missing Critical Features

**No shared schema between backend and frontend:**
- Problem: No OpenAPI-generated Kotlin clients or shared protobuf; all DTOs manually maintained
- Blocks: Type-safe evolution of the API contract

**No Android tests:**
- Problem: Zero test coverage for Android client
- Blocks: Confident refactoring of ViewModel, Repository, or SceneBubble types

## Test Coverage Gaps

**Event mapping pipeline:**
- What's not tested: End-to-end flow from tool return → event_mapper → WS → Android parsing
- Files: `app/api/event_mapper.py`, `android/.../DramaDetailViewModel.kt`
- Risk: Event format changes break Android silently
- Priority: High

**SceneBubble deserialization:**
- What's not tested: WsEventDto.data → SceneBubble mapping (all type branches)
- Files: `android/.../DramaDetailViewModel.kt` (handleWsEvent)
- Risk: Malformed WS events crash the app
- Priority: High

**Local save/restore:**
- What's not tested: SceneBubble serialization roundtrip
- Files: `android/.../data/local/DramaSaveRepository.kt`
- Risk: Saved states become unloadable after schema changes
- Priority: Medium

---

*Concerns audit: 2026-04-25*
