# Codebase Concerns

**Analysis Date:** 2026-04-11

## Tech Debt

**STORM Research Produces Placeholder Findings (MEDIUM):**
- Issue: `storm_research_perspective()` in `app/tools.py` (line 965-972) generates static template strings as "findings" instead of actually using LLM reasoning. The findings dict contains generic phrases like `f"从{perspective}的视角中浮现的角色原型"` — these are not real research outputs.
- Files: `app/tools.py` lines 942-1011
- Impact: The entire STORM Research phase (Phase 2) produces no useful content. The outline synthesis in Phase 3 then operates on meaningless placeholder data, making the multi-phase pipeline effectively decorative for phases 1-3.
- Fix approach: Replace hardcoded findings with actual LLM calls, or remove the research phase tool and let the LLM agent produce research content naturally through conversation.

**StormRouter Fallback to First Sub-Agent (MEDIUM):**
- Issue: In `StormRouter._run_async_impl()`, if `self._sub_agents_map.get(...)` returns `None` (agent not found by name), the fallback is `self._sub_agents[0]` — which is always `_storm_discoverer`. This means any routing failure silently routes to the wrong agent.
- Files: `app/agent.py` lines 419-420
- Impact: If sub-agent names ever mismatch (e.g., after refactor), user commands are silently misrouted to the discoverer instead of the correct phase agent.
- Fix approach: Replace with explicit error/logging: if agent is None, log a warning and yield an error event instead of falling back silently.

**Global Mutable State Without Thread Safety (MEDIUM):**
- Issue: `_conversation_log` (list) and `_current_drama_folder` (string) in `app/state_manager.py` are module-level globals mutated with `global` keyword in multiple functions. No locking mechanism protects concurrent access.
- Files: `app/state_manager.py` lines 15, 18, 202, 232, 309, 332, 443
- Impact: If two tool invocations run concurrently (possible in ADK's async model), the conversation log could be corrupted — entries lost or duplicated due to list append race conditions.
- Fix approach: Use an asyncio.Lock or move conversation state into the session state dict (which is already per-session and managed by ADK).

**`_current_drama_folder` Global Is Set But Rarely Read (LOW):**
- Issue: The global `_current_drama_folder` is set in `init_drama_state()` and `load_progress()`, but the only reader is `_get_current_theme()` which first checks `tool_context` and only falls back to the global. Since `tool_context` is always available in tool calls, the global is effectively dead code.
- Files: `app/state_manager.py` lines 15, 314-318, 332, 350, 443-444
- Impact: Misleading code that suggests state can exist without tool_context, but it can't in practice.
- Fix approach: Remove `_current_drama_folder` global and make `tool_context` required in all callers.

## Known Bugs

**Operator Precedence Error in Error-Dialogue Detection (HIGH):**
- Issue: Line 246 in `app/tools.py` has `if actor_dialogue.startswith("[") and "失败" in actor_dialogue or "超时" in actor_dialogue:` — due to Python operator precedence, this evaluates as `(actor_dialogue.startswith("[") and "失败" in actor_dialogue) or ("超时" in actor_dialogue)`. Any dialogue containing "超时" is treated as an error, even if it doesn't start with `[`.
- Files: `app/tools.py` line 246
- Impact: Legitimate dialogue containing the Chinese word "超时" (timeout) is incorrectly formatted as a warning (⚠️ prefix), breaking the script output formatting.
- Trigger: Any actor response that naturally contains the string "超时" in its dialogue.
- Workaround: None. The formatting code path is misrouted.

**Inconsistent Error Detection Between Logging and Formatting (HIGH):**
- Issue: The dialogue logging gate at line 238 checks `not (actor_dialogue.startswith("[") and ("失败" in actor_dialogue or "超时" in actor_dialogue))` — this has the correct precedence (both conditions inside parentheses). But the formatting gate at line 246 has the broken precedence described above. This means: (1) A dialogue with just "超时" (no leading `[`) gets logged as normal dialogue but formatted as an error. (2) A dialogue with `[` prefix and "失败" is both correctly excluded from logging and correctly formatted as error.
- Files: `app/tools.py` lines 238, 246
- Impact: Inconsistent behavior between what's recorded in the conversation log and what's displayed to the user.

**Port Collision Risk with MD5 Hash (MEDIUM):**
- Issue: `_get_actor_port()` in `app/actor_service.py` uses MD5 hash modulo 100 to assign ports in range 9001-9100. With only 100 possible ports, the birthday paradox means ~50% collision probability at just 12 actors, and the system allows up to 10 actors.
- Files: `app/actor_service.py` lines 36-45
- Impact: Two actors with different names can be assigned the same port. When the second actor starts, the first actor's subprocess is NOT stopped (only the same-named actor is checked at line 277), so `subprocess.Popen` on an already-bound port will fail silently or cause the new actor to fail to start.
- Trigger: Creating two actors whose names hash to the same port. E.g., any names with MD5 values that differ by a multiple of 100.
- Workaround: The `time.sleep(2)` + `process.poll()` check catches startup failure, but the error message is uninformative.

## Security Considerations

**API Keys Embedded in Generated Actor Files (CRITICAL):**
- Risk: `generate_actor_agent_code()` in `app/actor_service.py` (lines 73-75, 158-159) writes `os.environ["OPENAI_API_KEY"] = {repr(api_key)}` directly into generated Python files in `app/actors/`. This means API keys are stored as plaintext in `.py` files on disk.
- Files: `app/actor_service.py` lines 73-75, 158-159; all files in `app/actors/actor_*.py`
- Current mitigation: `.env` is in `.gitignore`, but `app/actors/` is NOT in `.gitignore`. The generated actor files are not excluded from version control.
- Recommendations: (1) Add `app/actors/` to `.gitignore`. (2) Modify actor service code to read API keys from environment at runtime instead of baking them into generated source files. (3) Rotate any API keys that have been committed to git history. (4) Add `app/dramas/` and `app/.adk/` to `.gitignore` as well — they contain user data and session data.

**Sensitive Data in Saved State Files (HIGH):**
- Risk: `state.json` files in `app/dramas/` contain full actor details, conversation logs, and narrative content. These are persisted as plaintext JSON with no access controls.
- Files: `app/dramas/*/state.json`, `app/dramas/*/snapshot_*.json`
- Current mitigation: None. No encryption, no access control.
- Recommendations: If dramas contain sensitive user content, consider encrypting at rest or documenting that drama data is stored unencrypted locally.

**Actor Subprocesses Inherit Full Parent Environment (MEDIUM):**
- Risk: Actor processes launched via `subprocess.Popen` inherit the full parent environment, including any sensitive env vars beyond OPENAI_API_KEY/OPENAI_BASE_URL.
- Files: `app/actor_service.py` line 280-285
- Current mitigation: Only OPENAI_API_KEY and OPENAI_BASE_URL are explicitly set in the generated code.
- Recommendations: Use `env` parameter in `subprocess.Popen` to pass only required environment variables to actor processes.

**No Input Sanitization on Actor Prompts (LOW):**
- Risk: User input flows through `/action` → `user_action()` → `actor_speak()` → `_call_a2a_sdk()` without sanitization. Malicious user input could potentially inject instructions that alter actor behavior.
- Files: `app/tools.py` lines 168-274
- Current mitigation: Actor system prompts define cognitive boundaries, but prompt injection within the drama context is possible.
- Recommendations: This is an inherent LLM challenge; document that actors may respond to carefully crafted user inputs in unintended ways.

## Performance Bottlenecks

**Blocking `time.sleep(2)` After Every Actor Service Start (MEDIUM):**
- Problem: `create_actor_service()` calls `time.sleep(2)` synchronously after launching each actor subprocess. This blocks the entire event loop for 2 seconds per actor.
- Files: `app/actor_service.py` lines 289-290
- Cause: Using synchronous `time.sleep()` in what should be an async-friendly codebase.
- Improvement path: Replace with `await asyncio.sleep(2)` and make `create_actor_service` async, or implement a proper health-check polling loop that tests the HTTP endpoint instead of guessing startup time.

**State Written to Disk on Every Mutation (MEDIUM):**
- Problem: `_set_state()` in `app/state_manager.py` (lines 890-897) calls `_save_state_to_file()` on every state change. During a single scene, this means multiple disk writes: `advance_scene()` → write, `add_narration()` → write, `add_dialogue()` → write, `update_actor_memory()` → write, `update_actor_emotion()` → write, `update_script()` → write. A single `/next` command can trigger 6+ full state file writes.
- Files: `app/state_manager.py` lines 890-897
- Cause: Auto-save is coupled to state mutation with no batching or debouncing.
- Improvement path: Implement a dirty flag with a debounced save, or save only at explicit save points (`/save`, `/quit`).

**httpx Client Created Per A2A Call (LOW):**
- Problem: `_call_a2a_sdk()` creates a new `httpx.AsyncClient` for every actor speak call. Connection pooling is not reused.
- Files: `app/tools.py` lines 327-329
- Cause: No shared client instance.
- Improvement path: Create a module-level or session-level `httpx.AsyncClient` that persists across calls.

## Fragile Areas

**Actor Service Process Lifecycle (HIGH):**
- Files: `app/actor_service.py` lines 280-298
- Why fragile: (1) Actor processes are tracked only in the in-memory `_actor_processes` dict. If the main process restarts, all actor processes become orphans with no way to reconnect. (2) `atexit` in `cli.py` line 29 tries to stop actors, but `atexit` doesn't run on `SIGKILL` or crash. (3) The 2-second startup wait is a heuristic — slow machines or loaded systems may need more time.
- Safe modification: Add PID file tracking so orphaned processes can be detected and cleaned up on restart. Use `SIGTERM` handler in addition to `atexit`.
- Test coverage: No unit tests for actor process lifecycle, crash recovery, or cleanup.

**StormRouter Command Detection via String Search (MEDIUM):**
- Files: `app/agent.py` lines 395-402
- Why fragile: The router checks `any(cmd in user_message for cmd in director_commands)` by searching for substrings in the lowercased user message. This means a message like "I want to save the world" matches `/save`, and "let me cast a shadow" matches `/cast`. The routing is purely string-matching without command boundary detection.
- Safe modification: Use regex with word boundaries (e.g., `r'/save\b'`) or require commands to start with `/` at the beginning of a word.
- Test coverage: No tests for routing logic.

**Port Management Across Load/Save Cycles (MEDIUM):**
- Files: `app/actor_service.py` lines 311-346, `app/tools.py` lines 552-676
- Why fragile: The port is derived deterministically from the actor name hash, but `get_actor_remote_config()` has three different port resolution paths (card file URL, saved_port parameter, deterministic hash). On reload, if the card file doesn't exist yet (service hasn't started), the fallback chain may produce different ports than expected.
- Safe modification: Always use deterministic hash as the single source of truth, and make the card file URL reflect it.
- Test coverage: No tests for port resolution across different code paths.

## Scaling Limits

**Maximum 10 Actors (LOW):**
- Current capacity: Hard-coded limit of 10 actors in `register_actor()` at `app/state_manager.py` line 598.
- Limit: With only 100 port slots (9001-9100), the effective limit is lower due to hash collisions.
- Scaling path: Increase port range (e.g., `ACTOR_BASE_PORT + port_hash % 1000` → range 9001-10000) and raise or remove the artificial 10-actor cap.

**InMemorySessionService Loses State on Process Restart (MEDIUM):**
- Current capacity: Session data is stored only in memory via `InMemorySessionService` in `cli.py` line 64.
- Limit: Any process restart (crash, intentional restart, deployment) loses the entire session state. Drama state is saved to disk, but the ADK session context is not.
- Scaling path: Use a persistent session service (ADK supports `DatabaseSessionService`) or ensure all critical state is in the disk-persisted `state.json` and can be fully reconstructed from it.

**Single-User Architecture (LOW):**
- Current capacity: CLI uses a single hardcoded `USER_ID` and `SESSION_ID` in `cli.py` lines 25-26. The global `_conversation_log` and `_current_drama_folder` in state_manager are shared across all requests.
- Limit: Cannot support multiple concurrent users or sessions.
- Scaling path: If multi-user support is needed, refactor globals into per-session objects and use unique user/session IDs.

## Dependencies at Risk

**a2a-sdk ~=0.3.22 (Pre-1.0, Unstable API) (HIGH):**
- Risk: The A2A SDK is pinned to `~=0.3.22` (allows 0.3.x updates only). Pre-1.0 packages can change APIs between minor versions. The code already handles version-specific behavior (streaming vs non-streaming, ClientEvent tuples vs Message objects) in `_call_a2a_sdk()`.
- Impact: Any `0.3.23+` update could break the A2A client code, breaking all actor communication.
- Migration plan: Pin exact version (`a2a-sdk==0.3.22`) until 1.0 release, or add integration tests that verify A2A communication after any dependency update.

**google-adk >=1.15.0,<2.0.0 (Evolving API) (MEDIUM):**
- Risk: The ADK is pinned to `>=1.15.0,<2.0.0`. The code uses several internal-looking APIs: `LiteLlm`, `RemoteA2aAgent`, `InvocationContext`, `to_a2a`, `App`. Some of these may not be stable public APIs.
- Impact: ADK minor version updates could change these APIs without warning.
- Migration plan: Pin to exact minor version for production use; test thoroughly before upgrading.

**Unused Dependencies (LOW):**
- Risk: `gcsfs>=2024.11.0`, `google-cloud-logging>=3.12.0`, and `opentelemetry-instrumentation-google-genai` are declared in `pyproject.toml` but no imports found in the codebase. These add unnecessary attack surface and install time.
- Impact: Bloated dependency tree; potential for supply chain attacks through unused packages.
- Migration plan: Audit and remove unused dependencies.

## Missing Critical Features

**No Graceful Recovery from Actor Process Crashes (HIGH):**
- Problem: If an actor A2A service crashes mid-session, there's no detection or auto-restart mechanism. The next `actor_speak()` call will get a connection error, which is surfaced as `[{actor_name}连接失败(端口:{port})]` — but the actor is permanently down until manually recreated.
- Files: `app/actor_service.py`, `app/tools.py` lines 219-229
- Blocks: Reliable long-running drama sessions

**No Conversation Log Cleanup on New Drama Start (MEDIUM):**
- Problem: `init_drama_state()` does not clear the global `_conversation_log`. Starting a new drama after a previous one will carry over conversation entries from the old drama.
- Files: `app/state_manager.py` lines 321-356
- Blocks: Clean drama isolation between sessions

**No STORM Phase Validation / Skip Prevention (LOW):**
- Problem: There's no validation that STORM phases are completed in order. A user could skip directly to "acting" status by calling `advance_scene()` without completing discovery/research/outline. The `StormRouter` just routes based on current status string, not on whether prior phases produced meaningful output.
- Files: `app/agent.py` lines 386-423
- Blocks: Quality assurance for the drama creation pipeline

**No Delete Drama Command (LOW):**
- Problem: There's no way to delete a saved drama. Over time, `app/dramas/` accumulates folders with no cleanup mechanism.
- Files: `app/state_manager.py`
- Blocks: Disk space management

## Test Coverage Gaps

**Core Business Logic - Zero Test Coverage (CRITICAL):**
- What's not tested: `app/tools.py` (all 15+ tool functions), `app/actor_service.py` (service lifecycle, port management), `app/state_manager.py` (state persistence, save/load, conversation logging), `app/agent.py` (StormRouter routing logic)
- Files: `app/tools.py`, `app/actor_service.py`, `app/state_manager.py`, `app/agent.py`
- Risk: Any refactoring or dependency update could introduce regressions undetected. The operator precedence bug at line 246 would have been caught by a simple unit test.
- Priority: HIGH — Start with `state_manager.py` (pure functions, easy to test), then `tools.py` (mock A2A calls), then `actor_service.py` (mock subprocess).

**Existing Tests Are Placeholders (HIGH):**
- What's not tested: `tests/unit/test_dummy.py` contains only `assert 1 == 1`. `tests/integration/test_agent.py` tests a generic "why is the sky blue" query, not any drama-specific functionality.
- Files: `tests/unit/test_dummy.py`, `tests/integration/test_agent.py`
- Risk: CI passes regardless of whether the application actually works.
- Priority: HIGH — Replace placeholder tests with meaningful ones.

**No Tests for A2A Communication (MEDIUM):**
- What's not tested: The entire `_call_a2a_sdk()` function, including streaming/non-streaming response handling, error recovery, and text extraction from different Part types.
- Files: `app/tools.py` lines 277-370
- Risk: A2A SDK updates silently break actor communication.
- Priority: MEDIUM — Requires mocking the A2A client or running a test actor service.

**No Tests for Error Handling Paths (MEDIUM):**
- What's not tested: Actor connection failures, timeout handling, port conflicts, missing actor card files, corrupted state.json, missing env vars.
- Files: `app/tools.py` lines 219-229, `app/actor_service.py` lines 292-298, `app/state_manager.py` line 485
- Risk: Error handling code is never exercised in CI, may contain bugs.
- Priority: MEDIUM

---

*Concerns audit: 2026-04-11*
