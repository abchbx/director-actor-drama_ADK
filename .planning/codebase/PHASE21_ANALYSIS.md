# Phase 21 Analysis: Events & Export Completion

**Analysis Date:** 2026-04-26

---

## 1. DramaDetailViewModel.kt — handleWsEvent Current State

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`

### Pre-when Handling (lines 444-471)

Before the `when` block, two event types are handled with early returns:

1. **`"replay"`** — Silently ignored (line 445): `if (event.type == "replay") return`
2. **`"director_log"`** — Shows backend progress in typing indicator (lines 452-471):
   - Extracts `message` and `tool` from `event.data`
   - Updates `stormPhase` and `typingText`, sets `isTyping = true`

### when Block — ALL Currently Handled Event Types (lines 473-715)

| # | Event Type | Line | What It Does |
|---|-----------|------|-------------|
| 1 | `"narration"` | 475 | Creates Narration bubble (blank text = typing indicator only) |
| 2 | `"dialogue"` | 506 | Creates Dialogue bubble (blank text = typing indicator only) |
| 3 | `"end_narration"` | 557 | Creates Narration bubble (no blank-text guard) |
| 4 | `"scene_end"` | 573 | Creates SceneDivider bubble |
| 5 | `"tension_update"` | 580 | Updates `tensionScore` in UI state |
| 6 | `"typing"` | 585 | Sets `isTyping = true` with tool-based text + haptic feedback |
| 7 | `"error"` | 593 | Shows error bubble + snackbar, clears processing state |
| 8 | `"storm_discover"` | 601 | Updates `stormPhase = "发现新视角..."` |
| 9 | `"storm_research"` | 602 | Updates `stormPhase = "深入研究..."` |
| 10 | `"storm_outline"` | 603 | Updates `stormPhase` with outline summary |
| 11 | `"scene_start"` | 611 | Clears typing, calls `preloadActorPanel()` |
| 12 | `"command_echo"` | 620 | Updates `stormPhase = "执行: $command"` |
| 13 | `"actor_created"` | 627 | Clears `stormPhase`, calls `preloadActorPanel()` |
| 14 | `"cast_update"` | 634 | Calls `preloadActorPanel()` |
| 15 | `"actor_chime_in"` | 639 | Creates Dialogue bubble for chime-in (blank text = typing) |
| 16 | `"save_confirm"` | 677 | Shows snackbar with save message |
| 17 | `"load_confirm"` | 683 | Shows snackbar with load message |
| 18 | `"user_message"` | 692 | Dedup-safe user bubble creation |

### Missing Event Handlers (backend emits, Android does NOT handle):

| Event Type | Backend Source | Impact |
|-----------|---------------|--------|
| **`"status"`** | `start_drama` → `["scene_start", "status", "command_echo"]` | Emitted on drama start but silently dropped by Android |
| **`"actor_status"`** | `update_emotion` → `["actor_status"]` | Emitted on emotion update but silently dropped — actor panel may not refresh |
| **`"progress"`** | `export_drama` → `["progress", "command_echo"]` | Emitted on export but silently dropped — export has no feedback mechanism |

### Export-Related Code in ViewModel

**NONE.** There is no `exportDrama`, `exportAction`, or any export-related method/state in the ViewModel.

The only export reference in the dramadetail package is in `TypingIndicator.kt` line 53:
```kotlin
"save_drama", "load_drama", "export_drama" -> "正在处理存档..."
```
This is a mapping for the typing indicator text only — it doesn't implement export functionality.

---

## 2. DramaRepository.kt — No Export Method

**File:** `android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`

**All methods:**
1. `startDrama(theme)` → `Result<CommandResponseDto>`
2. `listDramas()` → `Result<List<Drama>>`
3. `deleteDrama(folder)` → `Result<String>`
4. `saveDrama(saveName)` → `Result<SaveLoadResponseDto>`
5. `loadDrama(saveName)` → `Result<SaveLoadResponseDto>`
6. `getDramaStatus()` → `Result<DramaStatusResponseDto>`
7. `nextScene()` → `Result<CommandResponseDto>`
8. `userAction(description)` → `Result<CommandResponseDto>`
9. `actorSpeak(actorName, situation)` → `Result<CommandResponseDto>`
10. `endDrama()` → `Result<CommandResponseDto>`
11. `getScenes()` → `Result<ScenesResponseDto>`
12. `getSceneDetail(sceneNumber)` → `Result<SceneDetailDto>`
13. `getCastStatus()` → `Result<CastStatusResponseDto>`
14. `getCast()` → `Result<CastResponseDto>`
15. `sendChatMessage(message, mention?)` → `Result<CommandResponseDto>`
16. `steerDrama(direction)` → `Result<CommandResponseDto>`
17. `autoAdvanceDrama(numScenes)` → `Result<CommandResponseDto>`
18. `stormDrama(focus?)` → `Result<CommandResponseDto>`
19. `sendChatMessageAsBubbles(message, mention?, senderName)` → `Result<List<SceneBubble>>`
20. `getSceneBubbles(sceneNumber, prefix, includeDivider)` → `Result<List<SceneBubble>>`
21. `getMergedCast()` → `Result<List<ActorInfo>>`

**No `exportDrama()` or `exportDramaContent()` method exists.**

---

## 3. DramaRepositoryImpl.kt — No Export Implementation

**File:** `android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`

Confirms: No export method. The class implements `DramaRepository` which has no export method.

---

## 4. DramaApiService.kt — Export Endpoint EXISTS

**File:** `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`

```kotlin
@POST("drama/export")
suspend fun exportDrama(@Body request: ExportRequestDto): ExportResponseDto
```

**The API endpoint is defined but not wired to the Repository layer.**

**Existing DTOs:**
- `ExportRequestDto(val format: String = "markdown")` — in `android/app/src/main/java/com/drama/app/data/remote/dto/RequestDtos.kt` line 30
- `ExportResponseDto(val status, val message, val export_path)` — in `android/app/src/main/java/com/drama/app/data/remote/dto/ExportResponseDto.kt`

---

## 5. DramaDetailScreen.kt — Overflow Menu (Save Only)

**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`

Overflow menu (lines 278-293):
```kotlin
DropdownMenu(
    expanded = showOverflowMenu,
    onDismissRequest = { showOverflowMenu = false },
) {
    DropdownMenuItem(
        text = { Text("保存") },
        onClick = {
            viewModel.showSaveDialog()
            showOverflowMenu = false
        },
    )
}
```

**Only "保存" (Save) exists. No "导出" (Export) button.**

TopAppBar actions:
1. `TensionIndicator` — tension score display
2. `People` icon — actor drawer
3. `History` icon — scene history
4. `MoreVert` icon — overflow menu (save only)

---

## 6. Backend Event Types — 18 Business Events

**File:** `app/api/event_mapper.py`

The `TOOL_EVENT_MAP` defines the mapping from tool names to business event types. Collecting all unique event types across the entire mapper:

### Primary Events (from TOOL_EVENT_MAP):

| # | Event Type | Source Tool(s) | Call Data | Response Data |
|---|-----------|---------------|-----------|--------------|
| 1 | `scene_start` | start_drama, next_scene | tool, sender_type | — |
| 2 | `status` | start_drama | tool, sender_type | — |
| 3 | `narration` | director_narrate | tool, text, sender_type | text, sender_type |
| 4 | `dialogue` | actor_speak, actor_speak_batch | actor_name, tool, situation, sender_type | actor_name, text, emotion, sender_type |
| 5 | `actor_chime_in` | actor_chime_in | tool, trigger_context, speaking_actor, sender_type | chime_ins, chime_count, trigger_context, sender_type |
| 6 | `scene_end` | write_scene | — | scene_number, scene_title, sender_type |
| 7 | `actor_status` | update_emotion | — | actor_name, emotion, sender_type |
| 8 | `actor_created` | create_actor | actor_name, tool, sender_type | — |
| 9 | `cast_update` | create_actor | tool, sender_type | — |
| 10 | `storm_discover` | storm_discover_perspectives, dynamic_storm | — | — |
| 11 | `storm_research` | storm_research_perspective | — | — |
| 12 | `storm_outline` | storm_synthesize_outline | — | theme, message, num_acts, acts, core_tensions, new_status |
| 13 | `save_confirm` | save_drama | — | message, sender_type |
| 14 | `load_confirm` | load_drama | — | message, theme, sender_type |
| 15 | `progress` | export_drama | — | message, export_path, sender_type |
| 16 | `end_narration` | end_drama | — | text, sender_type |
| 17 | `command_echo` | multiple tools | tool, command, args, sender_type | — |
| 18 | `user_action_echo` | (internal, mapped from user_action in _extract_call_data but NOT in TOOL_EVENT_MAP) | text, sender_type | text, sender_type |

### Conditional Events (emitted outside TOOL_EVENT_MAP):

| # | Event Type | Trigger | Data |
|---|-----------|---------|------|
| 19 | `typing` | Every function_call arrival | tool |
| 20 | `director_log` | Function call/response for DIRECTOR_LOG_TOOLS | message, tool, phase, status, timestamp |
| 21 | `tension_update` | next_scene/write_scene response with tension_score | tension_score |
| 22 | `error` | Any function_response with status="error" | tool, message |
| 23 | `end_narration` | Final response text (non-tool, LLM direct text) | text |

### Android vs Backend Event Coverage:

**Handled by Android (18 in when + 2 pre-when):**
- Pre-when: `replay`, `director_log`
- When: `narration`, `dialogue`, `end_narration`, `scene_end`, `tension_update`, `typing`, `error`, `storm_discover`, `storm_research`, `storm_outline`, `scene_start`, `command_echo`, `actor_created`, `cast_update`, `actor_chime_in`, `save_confirm`, `load_confirm`, `user_message`

**NOT handled by Android (3 gaps):**
- **`status`** — Backend emits on start_drama, Android ignores
- **`actor_status`** — Backend emits on update_emotion, Android ignores
- **`progress`** — Backend emits on export_drama, Android ignores

**Note:** `user_action_echo` is defined in `_extract_call_data` but is NOT in `TOOL_EVENT_MAP` — it appears to be an unused/legacy event type. The `user_message` event type IS handled by Android but is NOT in TOOL_EVENT_MAP either — it may be emitted elsewhere in the backend.

---

## 7. WebSocketManager.kt — WS Event Flow

**File:** `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt`

### How Android Handles Incoming WS Events:

1. **Connection:** `WebSocketManager.connect()` → creates OkHttp WebSocket to `ws://{host}:{port}/api/v1/ws`
2. **Message reception:** `onMessage()` callback receives raw text
3. **Parsing:** Deserializes JSON → checks `type` field
4. **Special handling:**
   - `"ping"` → replies `{"type":"pong"}` (server heartbeat, line 172-176)
   - `"pong"` → ignored (line 177-180)
   - `"replay"` → deserializes as `ReplayMessageDto`, emits each nested event individually (line 181-188)
5. **Normal events:** Deserializes as `WsEventDto`, emits to `MutableSharedFlow<WsEventDto>` (line 192-193)
6. **Consumer:** ViewModel collects `webSocketManager.events` SharedFlow → calls `handleWsEvent()`

### Key Characteristics:
- Events are **generic** — single `WsEventDto(type: String, timestamp: String, data: Map<String, JsonElement>)` for all event types
- No type-specific DTO classes needed — all event data is in the `data` map
- Reconnect: exponential backoff (2s → 30s max, 10 retries) → permanent failure → REST fallback
- Network callback: auto-reconnects on network availability
- Connection state: sealed class `ConnectionState` (Disconnected, Connecting, Connected, Reconnecting)

---

## 8. WsEvent Models (Android)

**File:** `android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt`

```kotlin
@Serializable
data class WsEventDto(
    val type: String,
    val timestamp: String,
    val data: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class ReplayMessageDto(
    val type: String = "replay",
    val events: List<WsEventDto> = emptyList(),
)

@Serializable
data class HeartbeatMessageDto(
    val type: String = "ping",
)
```

**Design:** Single generic DTO for all event types. No per-event-type DTO classes. Event-specific data is accessed via `event.data["key"]?.jsonPrimitive?.contentOrNull` pattern in the ViewModel.

---

## Gap Summary for Phase 21

### What's Already Done:
- ✅ Backend: `export_drama` tool fully implemented (`app/tools.py` line 2258)
- ✅ Backend: `POST /drama/export` endpoint exists (`app/api/routers/queries.py` line 208)
- ✅ Backend: `export_script()` generates full Markdown (`app/state_manager.py` line 1488)
- ✅ Backend: `export_conversations()` generates conversation log (`app/state_manager.py` line 412)
- ✅ Backend: Event mapper maps `export_drama` → `["progress", "command_echo"]` (`app/api/event_mapper.py` line 35)
- ✅ Backend: `_extract_response_data("progress")` returns message + export_path (`app/api/event_mapper.py` line 167-168)
- ✅ Backend: `_format_command_echo("export_drama")` returns "/export" (`app/api/event_mapper.py` line 225-226)
- ✅ Android: `DramaApiService.exportDrama()` endpoint defined (line 57-58)
- ✅ Android: `ExportRequestDto` and `ExportResponseDto` exist
- ✅ Android: TypingIndicator knows "export_drama" tool name

### What Needs to Be Built:
1. **DramaRepository.kt** — Add `exportDrama(format: String)` method to interface
2. **DramaRepositoryImpl.kt** — Implement `exportDrama()` calling `dramaApiService.exportDrama()`
3. **DramaDetailViewModel.kt** — Add:
   - `exportDrama()` action method
   - Export state fields (isExporting, exportResult)
   - `"progress"` event handler in `handleWsEvent()` when block
   - `"status"` event handler (optional, for drama start status)
   - `"actor_status"` event handler (optional, for emotion updates)
4. **DramaDetailScreen.kt** — Add "导出" (Export) item to overflow DropdownMenu
5. **Export dialog/result** — UI for showing export result (snackbar or dialog with path)

---

*Phase 21 analysis: 2026-04-26*
