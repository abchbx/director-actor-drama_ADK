# Phase 24: Scene Cast Scheduling — Codebase Findings

**Analysis Date:** 2026-04-29

## 1. Backend Python Code

### 1.1 `app/tools.py` — Key Functions

#### `next_scene()` (line 1295)
- **Signature:** `def next_scene(tool_context: ToolContext) -> dict`
- **Returns `actors_available`** as a flat list of `actor_names`:
  ```python
  actors_data = state.get("actors", {})
  actor_names = list(actors_data.keys())  # line 1418
  ```
  → Returns ALL actors including user protagonist. No scene-specific casting, no role/emotion metadata.
- **Return dict** (line 1426-1447):
  ```python
  {
      "status": "success",
      "current_scene": scene_num,
      "is_first_scene": bool,
      "transition": dict,        # last_ending, actor_emotions, unresolved, is_first_scene
      "transition_text": str,     # formatted paragraph for LLM
      "actors_available": list[str],  # ★ FLAT NAME LIST — no metadata
      "director_context": str,    # global context for LLM
      "auto_remaining": int,
      "steer_direction": str|None,
      "message": str,
  }
  ```
- **Anti-skip guard** (line 1327-1361): If `scene_num > 0` but no recorded scene data, returns current scene info without advancing.
- **10-second throttle** (line 1313-1322): Prevents consecutive `next_scene()` calls within 10 seconds.

#### `actor_speak_batch()` (line 569)
- **Signature:** `async def actor_speak_batch(actors: list[dict], tool_context: ToolContext) -> dict`
- **Input:** `actors` = list of `{"actor_name": str, "situation": str}`
- **Two-phase execution:**
  1. Phase 1 (sync, lines 600-709): Prep each actor — get info, resolve coreferences, build prompt, add working memory
  2. Phase 2 (async, lines 711-796): `asyncio.gather(*[_call_single(prep) for prep in prep_list])` — all A2A calls concurrent
- **Per-actor result** (line 779-793):
  ```python
  {
      "status": "success"|"error",
      "id": f"{actor_name}_{uuid_hex[:8]}",
      "actor_name": str,
      "role": str,
      "personality": str,
      "emotions": str,        # English label
      "emotions_cn": str,     # Chinese label
      "situation": str,
      "dialogue": str,         # raw A2A response
      "formatted_dialogue": str,
      "message": str,          # same as formatted_dialogue
      "sender_type": "actor",
      "sender_name": actor_name,
  }
  ```
- **Batch result** (line 817-826):
  ```python
  {
      "status": "success",
      "id": f"batch_{uuid_hex[:8]}",
      "message": formatted_output,   # multi-line formatted
      "results": list[dict],          # per-actor results
      "num_actors": int,
      "parallel_time_sec": float,
      "estimated_serial_sec": int,
      "speedup": str,                 # e.g. "3.2x"
  }
  ```
- **User protagonist skip:** If `is_user_protagonist` or `control_type == "User-Controlled"`, that actor is skipped (line 620-626).

#### `create_actor()` (line 245)
- **Signature:** `def create_actor(actor_name, role, personality, background, knowledge_scope, tool_context) -> dict`
- **Flow:**
  1. Check user protagonist collision (line 268-274)
  2. Get all existing actors info (line 278) for cross-actor awareness
  3. Call `create_actor_service()` — creates A2A agent .py + .json files, launches process (line 296-299)
  4. Call `register_actor()` — writes to `state["actors"]` (line 304)
- **Returns** (line 308-325):
  ```python
  {
      "status": "success",
      "message": str,
      "actor_name": str,
      "role": str,
      "port": int,
      "card_file": str,
  }
  ```

### 1.2 `app/state_manager.py` — State Structure

#### `state["actors"]` shape (initialized in `init_drama_state()`, line 578-609):
```python
state["actors"] = {
    "用户": {  # User protagonist — always present
        "role": "主角（Protagonist）",
        "personality": "由用户实时定义...",
        "background": "用户自己的故事...",
        "knowledge_scope": "用户所知范围...",
        "control_type": "User-Controlled",
        "memory": [],
        "working_memory": [],
        "scene_summaries": [],
        "arc_summary": {"structured": {...}, "narrative": ""},
        "critical_memories": [],
        "memorySummary": str,
        "emotions": "neutral",
        "arc_progress": {"arc_type": "", "arc_stage": "", "progress": 0, "related_threads": []},
        "is_user_protagonist": True,
        "created_at": iso_timestamp,
    },
    "角色名": {  # AI actors — same structure plus:
        # ... same fields as above ...
        "port": int,  # A2A service port (optional, line 1270-1271)
    }
}
```

#### Key functions:
- `register_actor()` (line 1208): Adds to `state["actors"]`, max 10 AI actors (line 1234-1236)
- `get_actor_info(name)` (line 1336): Returns `{"status": "success", "actor": actors[name]}`
- `get_all_actors()` (line 1354): Returns summary dict with role/personality/background/emotions + counts
- `update_actor_emotion()` (line 1311): Sets `actors[name]["emotions"]`
- `_get_state(tool_context)` (line 1606): Reads from `tool_context.state["drama"]`
- `_set_state(state, tool_context, immediate_flush)` (line 1613): Writes back + optional file flush

### 1.3 `app/agent.py` — DramaRouter & Improv Director

#### `_improv_director` Agent (line 471-519):
- **Tools:** `actor_speak`, `actor_speak_batch`, `actor_chime_in`, `director_narrate`, `write_scene`, `next_scene`, `user_action`, `create_actor`, + many more
- **Instruction** (assembled dynamically via `_build_improv_instruction()`, line 436):
  - Core instruction: always included
  - MODE layer: added when auto-advance or /end
  - STRATEGY layer: added when scene_count > 3 or /storm
- **Mandatory flow** (line 344): `next_scene() → director_narrate() → actor_speak_batch() → actor_chime_in() → write_scene() → update_emotion()`

#### `DramaRouter` (line 525-607):
- Routes to `setup_agent` or `improv_director` based on:
  - `/start` → setup_agent
  - Utility commands or actors exist → improv_director
  - Fallback → improv_director
- Invocation dedup via `_active_invocations` set (line 540)

### 1.4 `app/api/routers/commands.py` — REST Endpoints

- `POST /drama/start` (line 102): Returns immediately, STORM runs in background
- `POST /drama/next` (line 158): Sends "/next" to Runner
- `POST /drama/chat` (line 297): Routes to `/speak` (if mention) or `/action` (if no mention)
- `POST /drama/action` (line 176): User action injection
- `POST /drama/speak` (line 199): Specific actor speak
- All endpoints use `run_command_and_collect()` with `event_callback` for WS push

### 1.5 `app/api/routers/queries.py` — Query Endpoints

- `GET /drama/cast` (line 117): Calls `get_all_actors()` directly — no Runner
- `GET /drama/cast/status` (line 128): A2A process status — `list_running_actors()`
- `GET /drama/status` (line 93): Full status including actors list

### 1.6 `app/api/event_mapper.py` — WS Event Mapping

#### Current 18+ event types:
| Event Type | Trigger Source | Phase |
|---|---|---|
| `scene_start` | `next_scene` call | call |
| `status` | `start_drama` call | call |
| `narration` | `director_narrate` response | response |
| `dialogue` | `actor_speak` / `actor_speak_batch` response | response |
| `actor_chime_in` | `actor_chime_in` response | response |
| `scene_end` | `write_scene` response | response |
| `actor_status` | `update_emotion` response | response |
| `actor_created` | `create_actor` call | call |
| `cast_update` | `create_actor` call | call |
| `storm_discover` | `storm_discover_perspectives` call | call |
| `storm_research` | `storm_research_perspective` call | call |
| `storm_outline` | `storm_synthesize_outline` response | response |
| `command_echo` | multiple tools call | call |
| `command_complete` | final_response text | final |
| `end_narration` | `end_drama` response / final_response | response/final |
| `save_confirm` | `save_drama` response | response |
| `load_confirm` | `load_drama` response | response |
| `progress` | `export_drama` response | response |
| `typing` | any tool call (except NO_TYPING_TOOLS) | call |
| `director_log` | DIRECTOR_LOG_TOOLS (both phases) | both |
| `tension_update` | `next_scene`/`write_scene` response | response |
| `error` | any response with status="error" | response |
| `user_action_echo` | (defined but not in TOOL_EVENT_MAP) | — |

#### `actor_speak_batch` special handling (line 507-526):
```python
# Expands batch results into individual dialogue events
if fn_name == "actor_speak_batch":
    batch_results = resp.get("results", [])
    for actor_result in batch_results:
        results.append({
            "type": "dialogue",
            "data": _extract_response_data("dialogue", actor_result),
        })
```
→ Each actor in the batch gets its own `dialogue` WS event.

#### `create_actor` event mapping (line 31):
```python
"create_actor": ["actor_created", "cast_update"]
```
→ Both `actor_created` and `cast_update` emitted on `create_actor` call phase.

### 1.7 `app/api/models.py` — WS Event Models

```python
class WsEvent(BaseModel):
    type: str          # Event type (one of 18+ business types)
    timestamp: str     # ISO format
    data: dict         # Event payload

class MessageSender(BaseModel):
    sender_type: str   # "director" | "actor" | "user"
    sender_name: str   # "旁白" | actor name | "用户"
```

### 1.8 `app/api/ws_manager.py` — Connection Manager

- `ConnectionManager` (line 25): Manages WS pool, replay buffer (100 events), heartbeat (15s/30s)
- `create_broadcast_callback()` (line 132): Creates event_callback that maps Runner events → WS events
- **Content dedup** (line 149-156): Sliding window + committed set, prevents duplicate dialogue/narration pushes

---

## 2. Android Kotlin Code

### 2.1 `ActorInfo` data class

**File:** `android/app/src/main/java/com/drama/app/domain/model/ActorInfo.kt`
```kotlin
data class ActorInfo(
    val name: String,
    val role: String = "",
    val personality: String = "",
    val background: String = "",
    val emotions: String = "neutral",
    val memorySummary: String = "",
    val isA2ARunning: Boolean = false,
    val a2aPort: Int = 0,
    val thinkingProgress: Int = 0,
)
```
→ **No `is_user_protagonist` field** — user protagonist is NOT distinguishable from AI actors in ActorInfo.

### 2.2 `ActorDrawerContent` composable

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ActorDrawerContent.kt`
- **Props:** `actors: List<ActorInfo>`, `isActorLoading: Boolean`, `onDismiss: () -> Unit`
- Renders `ActorCard` for each actor in a `LazyColumn` with stagger animation
- Empty state text: "暂无演员，输入 /cast 加载"
- Loading state: skeleton screen with shimmer animation

### 2.3 `DramaDetailUiState`

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` (line 43-98)
```kotlin
data class DramaDetailUiState(
    // ... other fields ...
    val actors: List<ActorInfo> = emptyList(),       // line 84
    val showActorDrawer: Boolean = false,             // line 85
    val isActorLoading: Boolean = false,              // line 86
    // ...
)
```

### 2.4 WS Event Handling in ViewModel

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`

#### `handleWsEvent()` (line 509):
Main event dispatcher. Key actor-related handlers:

**`actor_created` (line 782-787):**
```kotlin
"actor_created" -> {
    val actorName = event.data["actor_name"]?.jsonPrimitive?.contentOrNull ?: ""
    _uiState.update { it.copy(stormPhase = null) }
    preloadActorPanel()  // re-fetches /drama/cast
}
```

**`cast_update` (line 789-792):**
```kotlin
"cast_update" -> {
    preloadActorPanel()  // re-fetches /drama/cast
}
```

**`scene_start` (line 767-770):**
```kotlin
"scene_start" -> {
    _uiState.update { it.copy(stormPhase = null, isTyping = false) }
    preloadActorPanel()
}
```

**`dialogue` (line 603-659):** Creates `SceneBubble.Dialogue` with actor_name/text/emotion. Dedup check against last bubble. Supports `ActorInteraction` detection via `DetectActorInteractionUseCase`.

#### `preloadActorPanel()` (line 1193-1200):
```kotlin
private fun preloadActorPanel() {
    viewModelScope.launch {
        dramaRepository.getMergedCast()
            .onSuccess { actors ->
                _uiState.update { it.copy(actors = actors) }
            }
    }
}
```
→ Calls `getMergedCast()` which merges `/drama/cast` + `/drama/cast/status`.

#### `loadActorPanel()` (line 1181-1191):
Same as `preloadActorPanel()` but also sets `isActorLoading = false`.

### 2.5 ChatInputBar — @ Mention Selector

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`

- **Props:** `actors: List<String>` (just names), `onSend: (String, String?) -> Unit`, `onCommand: (String) -> Unit`
- **Mention chips** (line 115-134): Horizontal scroll row of `@actor_name` chips. Clicking sets `inputText = "@$actor "`.
- **Mention parsing** (line 92-97):
  ```kotlin
  val mention = remember(inputText, actors) {
      if (inputText.startsWith("@") && actors.isNotEmpty()) {
          val namePart = inputText.substring(1).takeWhile { it != ' ' }
          actors.find { it == namePart }
      } else null
  }
  ```
- **Send logic** (line 238-247): If starts with `/` → `onCommand`, else → `onSend(text, mention)`
- **Slash commands** (line 41-48): `/next`, `/end`, `/save`, `/load`, `/list`, `/delete`
- **Quick actions** (line 65-68): "下一场" → `/next`, "落幕" → `/end`
- **Input locked** during `isProcessing || isTyping` (line 85-86)

### 2.6 DramaDetailScreen — How actors flow to UI

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`
- `ChatInputBar(actors = uiState.actors.map { it.name }, ...)` (line 399)
- `ActorDrawerContent(actors = uiState.actors, ...)` (line 211)

### 2.7 `DramaRepositoryImpl.getMergedCast()` (line 154-168)

Merges `/drama/cast` (role/personality/background/emotions) with `/drama/cast/status` (A2A running/port/thinking_steps).

**`mergeCastWithStatus()`** (line 358-396):
```kotlin
// Parses raw JSON from /drama/cast response
for ((name, actorElement) in cast.actors) {
    val actorObj = (actorElement as? JsonObject)?.jsonObject ?: continue
    val role = actorObj["role"]?.jsonPrimitive?.contentOrNull ?: ""
    val personality = actorObj["personality"]?.jsonPrimitive?.contentOrNull ?: ""
    val background = actorObj["background"]?.jsonPrimitive?.contentOrNull ?: ""
    val emotions = actorObj["emotions"]?.jsonPrimitive?.contentOrNull ?: "neutral"
    val memorySummary = buildMemorySummary(actorObj)
    // ... merge with A2A status ...
    mergedActors.add(ActorInfo(name=name, role=role, ...))
}
```

### 2.8 WsEventDto

**File:** `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt`
```kotlin
data class WsEventDto(
    val type: String,
    val timestamp: String,
    val data: Map<String, JsonElement> = emptyMap(),
)
```

---

## 3. Key Data Structures Summary

### 3.1 `state["actors"]` (Python backend)

A `dict[str, dict]` where:
- Key = actor name (e.g. "云铮", "用户")
- Value = actor data dict with fields:
  - `role: str` — character role
  - `personality: str` — personality traits
  - `background: str` — backstory
  - `knowledge_scope: str` — what they know
  - `control_type: str` — "User-Controlled" or "AI-Controlled"
  - `is_user_protagonist: bool` — True for user (line 606)
  - `emotions: str` — current emotion (English, e.g. "neutral", "angry")
  - `memory: list` — deprecated, kept for backward compat
  - `working_memory: list` — Tier 1 working memory
  - `scene_summaries: list` — Tier 2 scene summaries
  - `arc_summary: dict` — Tier 3 arc summary
  - `critical_memories: list` — standalone critical memories
  - `memorySummary: str` — Tier 4 summary
  - `arc_progress: dict` — arc_type, arc_stage, progress, related_threads
  - `port: int` — A2A service port (AI actors only)
  - `created_at: str` — ISO timestamp

### 3.2 How `next_scene()` returns `actors_available`

Currently returns **only `list(actors_data.keys())`** — a flat list of actor name strings.
No per-actor metadata (role, emotion, casting status, scene relevance).

### 3.3 How `actor_speak_batch()` currently works

1. **Input:** `actors: list[dict]` where each dict has `actor_name` and `situation`
2. **The LLM (improv_director)** decides which actors to include and what `situation` text each gets
3. **Phase 1:** Prep each actor independently — memory, coreferences, prompt
4. **Phase 2:** `asyncio.gather` all A2A calls concurrently
5. **Result:** Per-actor dialogue + formatted multi-line output
6. **WS events:** Batch results are expanded into individual `dialogue` events per actor

### 3.4 WS Event Flow for a Scene

```
User sends /next
  → POST /drama/next → Runner → next_scene() call
    → WS: typing, scene_start, command_echo
  → Runner → director_narrate() call
    → WS: typing
  → Runner → director_narrate() response
    → WS: narration (with text)
  → Runner → actor_speak_batch() call
    → WS: typing, director_log("💬⚡ 批量对话: A、B、C")
  → Runner → actor_speak_batch() response
    → WS: dialogue (per actor, expanded from batch)
    → WS: director_log("⚡ 批量对话完成: 3人并行...")
  → Runner → actor_chime_in() call/response (optional)
  → Runner → write_scene() call
    → WS: scene_end, tension_update
  → Runner final_response
    → WS: command_complete
```

---

## 4. Gaps & Opportunities for Phase 24

### 4.1 No Scene-Specific Cast Information
`next_scene()` returns ALL actors in `actors_available`, with no indication of:
- Which actors are **on-stage** vs. off-stage for this scene
- Which actors the director should prioritize
- Actor emotions or status relevant to the scene

### 4.2 No `is_user_protagonist` in Android `ActorInfo`
The Android data class lacks `is_user_protagonist` or `control_type` fields.
`mergeCastWithStatus()` doesn't extract these from the `/drama/cast` response.
→ User protagonist appears identically to AI actors in the actor panel and @mention chips.

### 4.3 No `scene_cast` WS Event
There is no dedicated WS event for scene casting. The LLM decides cast internally
and the Android client only learns about actors through:
- `actor_created` / `cast_update` events (new actors)
- `dialogue` events (who's speaking)
- `preloadActorPanel()` on `scene_start`

### 4.4 No On-Stage/Off-Stage Visual Distinction
`ActorDrawerContent` renders all actors identically — no visual cue for who's currently on-stage.

### 4.5 ChatInputBar @Mention Has No Cast Awareness
The `actors: List<String>` passed to `ChatInputBar` is just names.
No way to indicate "this actor is on-stage" vs. "off-stage but available".

---

*Phase 24 codebase analysis: 2026-04-29*
