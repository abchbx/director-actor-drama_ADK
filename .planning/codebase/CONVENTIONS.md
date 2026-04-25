# Coding Conventions

**Analysis Date:** 2026-04-25

## Naming Patterns

**Files:**
- Python: `snake_case.py` — `state_manager.py`, `conflict_engine.py`, `actor_service.py`
- Kotlin: `PascalCase.kt` — `SceneBubble.kt`, `DramaDetailViewModel.kt`, `WsEventDto.kt`
- Test files: `test_<module>.py` — `test_state_manager.py`

**Functions:**
- Python tools: `snake_case` with descriptive names — `director_narrate()`, `actor_speak()`, `next_scene()`
- Python helpers: Leading underscore for internal — `_extract_call_data()`, `_build_coref_annotations()`
- Kotlin: `camelCase` — `handleWsEvent()`, `sendCommand()`, `sendChatMessage()`

**Variables:**
- Python: `snake_case` — `current_scene`, `actor_data`, `tool_context`
- Kotlin: `camelCase` — `bubbleCounter`, `lastKnownScene`, `isTyping`
- Constants: `UPPER_SNAKE_CASE` — `DRAMAS_DIR`, `MAX_CRASH_COUNT`, `DEBOUNCE_SECONDS`

**Types:**
- Python: No type enforcement; function signatures use `dict` returns with documented keys
- Kotlin: Strict typing; sealed classes for state hierarchies, data classes for DTOs
- Pydantic models: `PascalCase` class names — `CommandResponse`, `ChatRequest`, `WsEvent`

## Code Style

**Formatting:**
- Python: No formal formatter detected (no .prettierrc, no black config)
- Kotlin: Standard Android Kotlin style

**Linting:**
- Python: ruff (`.ruff_cache/` exists)
- Kotlin: Android Studio default lint

## Import Organization

**Python Order:**
1. Standard library (`os`, `json`, `logging`, `asyncio`)
2. Third-party (`httpx`, `pydantic`, `fastapi`, `google.adk.*`)
3. Local application (`from .tools import ...`, `from .state_manager import ...`)

**Kotlin Order:**
1. Android framework (`android.*`)
2. Compose (`androidx.compose.*`, `androidx.lifecycle.*`)
3. Third-party (`dagger.hilt.*`, `kotlinx.serialization.*`, `okhttp3.*`)
4. Local application (`com.drama.app.domain.*`, `com.drama.app.data.*`)

**Path Aliases:**
- None detected in Python
- Kotlin: Standard package-based imports

## Error Handling

**Python Backend Patterns:**
- Tool functions NEVER raise — always return `{status: "error", message: "..."}` dicts
- API endpoints use HTTPException for infrastructure errors (404, 504)
- Actor A2A failures: Try/except with auto-restart logic in `_restart_actor()`
- State I/O: Atomic writes (tempfile + os.replace) to prevent corruption

```python
# Tool error pattern (from tools.py)
if actor_info["status"] != "success":
    return actor_info  # Returns error dict, never raises

# API error pattern (from commands.py)
def _require_active_drama(tool_context):
    if not tool_context.state.get("drama", {}).get("theme"):
        raise HTTPException(status_code=404, detail="No active drama session")
```

**Kotlin Android Patterns:**
- `Result<T>` for all repository calls — `.onSuccess {}` / `.onFailure {}`
- `SceneBubble.SystemError` for inline error display in chat
- `MutableSharedFlow<DramaDetailEvent>` for transient UI events (snackbars)

```kotlin
// Repository call pattern
dramaRepository.nextScene()
    .onSuccess { resp -> /* handle success */ }
    .onFailure { e -> addErrorBubble("[错误] ${e.message}") }
```

## Logging

**Framework:** Python `logging` module (backend), Android `Log` (client)

**Patterns:**
- Backend: `logger = logging.getLogger(__name__)` per module
- Backend lifecycle: `[DIRECTOR-LOG]` prefix with emoji indicators (🎬✅❌💥⚠️)
- Backend WS events: INFO level for every event processed
- Android: TAG constant per class: `private const val TAG = "DramaDetailViewModel"`

## Comments

**When to Comment:**
- Chinese comments are common — domain-specific terminology in Chinese (旁白, 对话, 导演)
- `★ 核心修复` / `⚠️` markers for important design decisions and fixes
- `D-XX` / `T-XX-XX` references to design ticket numbers throughout codebase
- Phase markers: `# Phase 7`, `# Phase 12: Letta-inspired memory enhancements`

**Docstrings:**
- All Python tool functions have comprehensive docstrings (Google style)
- All Kotlin public functions have KDoc
- Docstrings often include "Args:", "Returns:" sections

## Function Design

**Size:** Tool functions can be 50-150 lines (build context + call A2A + format result). Helper functions are shorter.

**Parameters:**
- Python tools: `(param1, param2, tool_context: ToolContext)` — `tool_context` always last
- API endpoints: `(body: RequestModel, request: Request, _auth: bool = Depends(require_auth), ...)`

**Return Values:**
- Python tools: `dict` with `status`, `message`, and domain-specific fields
- API endpoints: Pydantic response models
- Kotlin repository: `Result<T>` wrapping DTOs or domain models

## Module Design

**Exports:**
- Python: `__init__.py` exports public API — `from .agent import app`
- Kotlin: Interface/implementation split — `DramaRepository` (interface) / `DramaRepositoryImpl` (impl)

**Barrel Files:**
- `app/__init__.py` — single export (`app`)
- `app/api/__init__.py` — minimal (imports create_app)
- No Kotlin barrel files — direct imports per class

## Architecture Conventions

**Tool Function Pattern (Backend):**
Every tool function follows this structure:
1. Get state from `tool_context`
2. Validate inputs (return error dict if invalid)
3. Execute business logic
4. Update state via `_set_state()`
5. Return result dict with `status` and formatted output

**Event Mapping Pattern:**
- Each tool maps to 1+ business event types via `TOOL_EVENT_MAP`
- function_call = "typing" indicator + mapped event(s) with call data
- function_response = mapped event(s) with response data + conditional events (tension, error)

**Android ViewModel Pattern:**
- `MutableStateFlow<UiState>` for all UI state
- `MutableSharedFlow<Event>` for one-shot events (snackbars)
- WS events processed in `handleWsEvent()` with `when(event.type)` dispatch
- Commands processed in `sendCommand()` with `CommandType.fromInput()` routing

---

*Convention analysis: 2026-04-25*
