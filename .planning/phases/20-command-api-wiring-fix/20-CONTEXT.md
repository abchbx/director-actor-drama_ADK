# Phase 20: Command & API Wiring Fix — Context Analysis

**Analysis Date:** 2026-04-26
**Analyst:** Codebase Mapper

---

## 1. CRITICAL: `isProcessing` never resets in `sendCommand()` — permanently disabling command input bar

### Root Cause Analysis

**File:** `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`

**The bug is in `sendCommand()` method, lines 1142–1324.**

The flow:

1. **Line 1274–1279:** `isProcessing = true` is set immediately before the coroutine launches:
   ```kotlin
   _uiState.update { it.copy(
       isProcessing = true,
       isTyping = true,
       typingText = "思考中...",
       bubbles = it.bubbles + userBubble + listOfNotNull(plotGuidance),
   ) }
   ```

2. **Line 1281–1323:** Inside `viewModelScope.launch`, the API call is made. The reset logic has **two branches**:

3. **WS Connected branch (line 1295–1297):** `isProcessing = false` is correctly set:
   ```kotlin
   if (_uiState.value.isWsConnected) {
       _uiState.update { it.copy(isProcessing = false) }
   }
   ```
   But `isTyping` is **NOT** reset here! It stays `true`, waiting for WS events to eventually clear it.

4. **WS Disconnected branch (lines 1298–1316):** `isProcessing = false` is also correctly set in both sub-branches.

5. **Error branch (lines 1318–1322):** Both `isTyping` and `isProcessing` are correctly reset.

### The Real Problem

**The `isProcessing` reset itself appears correct in the happy path.** However, there is a subtle race condition / edge case:

- If the coroutine is cancelled before reaching line 1295 (e.g., ViewModel cleared, or any exception not caught by `Result`), `isProcessing` remains `true` forever.
- The `runCatching` wrapper in `DramaRepositoryImpl` converts exceptions to `Result.failure`, so `onFailure` at line 1318 should catch them. BUT if the coroutine itself is cancelled (CancellationException), `runCatching` catches it and wraps it, which is a known Kotlin coroutines anti-pattern — it swallows cancellation instead of propagating it, but the `onFailure` block should still fire.

**More likely scenario:** The WS event flow never sends a "scene_start" or equivalent "processing complete" event for certain command types, leaving `isTyping = true`. Since `ChatInputBar` uses `isLocked = isProcessing || isTyping` (line 77 of ChatInputBar.kt), even if `isProcessing` resets, `isTyping` being stuck also locks the input.

**Key observation:** For the WS connected path, `isProcessing` is reset at line 1297, but `isTyping` remains `true`. It only resets when specific WS events arrive:
- `"narration"` with non-blank text → line 471: `isTyping = false`
- `"dialogue"` with non-blank text → line 508: `isTyping = false`
- `"error"` → line 573: `isTyping = false`
- `"scene_start"` → line 589: `isTyping = false`
- `"save_confirm"` / `"load_confirm"` → line 654/660: `isTyping = false`

**If no WS event ever arrives** (e.g., command fails silently on backend, WS message is lost, or network hiccup), `isTyping` stays `true` forever, and the input bar remains permanently disabled.

### ChatInputBar Disabling Logic

**File:** `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`

- **Line 77:** `val isLocked = isProcessing || isTyping`
- **Line 78:** `val inputEnabled = !isLocked`
- **Line 164:** `enabled = inputEnabled` on `OutlinedTextField`
- **Lines 180–195:** When `isLocked`, shows a disabled Close icon instead of the Send button

This means **either** `isProcessing` **or** `isTyping` being stuck `true` will permanently lock the input bar.

### Fix Approach

1. **Add a safety timeout**: If `isTyping` stays `true` for more than N seconds without receiving a WS event, auto-reset both `isTyping` and `isProcessing`.
2. **Reset `isProcessing` immediately** in the WS connected path (already done at line 1297).
3. **Add `isProcessing = false`** in the `sendCommand()` WS connected branch as a belt-and-suspenders approach.
4. **Consider adding a "cancel" mechanism** in the UI that forcibly resets `isProcessing`/`isTyping`.

---

## 2. HIGH: Missing CommandType enum values for STEER/AUTO/STORM

### Current State

**File:** `app/src/main/java/com/drama/app/domain/model/CommandType.kt` (22 lines)

```kotlin
enum class CommandType(val prefix: String, val needsArgument: Boolean) {
    NEXT("/next", false),
    ACTION("/action", true),
    SPEAK("/speak", true),
    END("/end", false),
    CAST("/cast", false),
    SAVE("/save", true),
    LOAD("/load", true),
    LIST("/list", false),
    DELETE("/delete", true),
    FREE_TEXT("", false);
}
```

**Missing entries:**
- `STEER("/steer", true)` — steer drama in a direction
- `AUTO("/auto", true)` — auto-advance N scenes (argument: number, optional with default)
- `STORM("/storm", false)` — trigger STORM perspective discovery (focus argument optional)

### Impact

In `DramaDetailViewModel.sendCommand()` (lines 1142–1324):
- `CommandType.fromInput(text)` at line 1143 maps `/steer`, `/auto`, `/storm` inputs to `FREE_TEXT`
- `FREE_TEXT` falls through to `dramaRepository.userAction(text.trim())` at line 1292
- This means `/steer foo` gets sent as `/action /steer foo` instead of calling the `/steer` endpoint
- Similarly, `/auto 3` gets sent as `/action /auto 3` and `/storm` as `/action /storm`

The `when` block at lines 1146–1216 (local command handling) has no cases for STEER/AUTO/STORM.
The `when` block at lines 1282–1293 (API routing) has no cases for STEER/AUTO/STORM.
The `when` block at lines 1219–1235 (display text) has no cases for STEER/AUTO/STORM.
The `isActionCommand` check at line 1238 has no entries for STEER/AUTO/STORM.
The `isPlotChanging` check at lines 1253–1255 has no entries for STEER/AUTO/STORM.

### Also Missing in ChatInputBar Slash Commands

**File:** `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`

The `SLASH_COMMANDS` list (lines 41–53) does NOT include `/steer`, `/auto`, or `/storm`:
```kotlin
private val SLASH_COMMANDS = listOf(
    SlashCommand("/start", "<主题>", "开始一个新戏剧场景"),
    SlashCommand("/next", "", "推进到下一个情节"),
    SlashCommand("/action", "<描述>", "以主角身份执行动作"),
    SlashCommand("/cast", "", "查看当前演员阵容及状态"),
    SlashCommand("/save", "[名称]", "保存当前场景到本地"),
    SlashCommand("/load", "<名称>", "加载已保存的本地场景"),
    SlashCommand("/list", "", "列出所有本地存档"),
    SlashCommand("/delete", "<名称>", "删除指定的本地存档"),
    SlashCommand("/export", "", "导出当前场景"),
    SlashCommand("/status", "", "查看当前状态"),
    SlashCommand("/quit", "", "退出当前场景"),
)
```

Missing:
- `SlashCommand("/steer", "<方向>", "引导剧情走向指定方向")`
- `SlashCommand("/auto", "[场次]", "自动推进N场剧情")`
- `SlashCommand("/storm", "[焦点]", "触发STORM多视角发现")`

---

## 3. HIGH: DramaRepository missing methods: steerDrama(), autoAdvanceDrama(), stormDrama()

### Current State

**File:** `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt` (54 lines)

The interface has NO methods for steer/auto/storm. Current methods:
```kotlin
suspend fun startDrama(theme: String): Result<CommandResponseDto>
suspend fun listDramas(): Result<List<Drama>>
suspend fun deleteDrama(folder: String): Result<String>
suspend fun saveDrama(saveName: String = ""): Result<SaveLoadResponseDto>
suspend fun loadDrama(saveName: String): Result<SaveLoadResponseDto>
suspend fun getDramaStatus(): Result<DramaStatusResponseDto>
suspend fun nextScene(): Result<CommandResponseDto>
suspend fun userAction(description: String): Result<CommandResponseDto>
suspend fun actorSpeak(actorName: String, situation: String): Result<CommandResponseDto>
suspend fun endDrama(): Result<CommandResponseDto>
suspend fun getScenes(): Result<ScenesResponseDto>
suspend fun getSceneDetail(sceneNumber: Int): Result<SceneDetailDto>
suspend fun getCastStatus(): Result<CastStatusResponseDto>
suspend fun getCast(): Result<CastResponseDto>
suspend fun sendChatMessage(message: String, mention: String? = null): Result<CommandResponseDto>
suspend fun sendChatMessageAsBubbles(...): Result<List<SceneBubble>>
suspend fun getSceneBubbles(...): Result<List<SceneBubble>>
suspend fun getMergedCast(): Result<List<ActorInfo>>
```

**Missing methods that need to be added:**
```kotlin
suspend fun steerDrama(direction: String): Result<CommandResponseDto>
suspend fun autoAdvanceDrama(numScenes: Int = 3): Result<CommandResponseDto>
suspend fun stormDrama(focus: String? = null): Result<CommandResponseDto>
```

### DramaRepositoryImpl also missing implementations

**File:** `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt` (284 lines)

No implementations for `steerDrama()`, `autoAdvanceDrama()`, or `stormDrama()`.

The implementations should follow the existing pattern, e.g.:
```kotlin
override suspend fun steerDrama(direction: String): Result<CommandResponseDto> =
    runCatching { dramaApiService.steerDrama(SteerRequestDto(direction)) }

override suspend fun autoAdvanceDrama(numScenes: Int): Result<CommandResponseDto> =
    runCatching { dramaApiService.autoAdvance(AutoRequestDto(numScenes)) }

override suspend fun stormDrama(focus: String?): Result<CommandResponseDto> =
    runCatching { dramaApiService.triggerStorm(StormRequestDto(focus)) }
```

---

## 4. HIGH: API endpoints /steer, /auto, /storm not wired from Android to backend

### Backend Side — ALREADY IMPLEMENTED ✅

**File:** `app/api/routers/commands.py`

All three endpoints exist and are fully functional:

| Endpoint | Line | Handler | Status |
|----------|------|---------|--------|
| `POST /drama/steer` | 210–226 | `steer_drama()` | ✅ Working |
| `POST /drama/auto` | 229–245 | `auto_advance()` | ✅ Working |
| `POST /drama/storm` | 266–284 | `trigger_storm()` | ✅ Working |

Backend request models all exist in `app/api/models.py`:
- `SteerRequest(direction: str)` — line 36–39
- `AutoRequest(num_scenes: int = 3, ge=1, le=10)` — line 42–45
- `StormRequest(focus: str | None = None)` — line 48–51

### Android API Service — ALREADY DEFINED ✅

**File:** `app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt`

The Retrofit interface already declares all three endpoints:

| Method | Line | Endpoint | Status |
|--------|------|----------|--------|
| `steerDrama()` | 20–21 | `POST drama/steer` | ✅ Defined |
| `autoAdvance()` | 23–24 | `POST drama/auto` | ✅ Defined |
| `triggerStorm()` | 26–27 | `POST drama/storm` | ✅ Defined |

Android DTOs also exist in `app/src/main/java/com/drama/app/data/remote/dto/RequestDtos.kt`:
- `SteerRequestDto(val direction: String)` — line 15
- `AutoRequestDto(val num_scenes: Int = 3)` — line 18
- `StormRequestDto(val focus: String? = null)` — line 21

### The Gap — Repository & ViewModel NOT WIRED ❌

The wiring chain is:
```
UI (ChatInputBar) → ViewModel (sendCommand) → Repository → ApiService → Backend
```

| Layer | steer | auto | storm |
|-------|-------|------|-------|
| ChatInputBar SLASH_COMMANDS | ❌ Missing | ❌ Missing | ❌ Missing |
| CommandType enum | ❌ Missing | ❌ Missing | ❌ Missing |
| DramaDetailViewModel.sendCommand() routing | ❌ Falls to FREE_TEXT | ❌ Falls to FREE_TEXT | ❌ Falls to FREE_TEXT |
| DramaRepository interface | ❌ No method | ❌ No method | ❌ No method |
| DramaRepositoryImpl | ❌ No impl | ❌ No impl | ❌ No impl |
| DramaApiService | ✅ Defined | ✅ Defined | ✅ Defined |
| Request DTOs | ✅ Exists | ✅ Exists | ✅ Exists |
| Backend endpoints | ✅ Working | ✅ Working | ✅ Working |

The **only gap** is the middle layers: CommandType → ViewModel → Repository → RepositoryImpl.
The API service and backend are already ready.

---

## 5. Summary of All Files to Modify

### Android Files (must modify)

| # | File | Changes Needed |
|---|------|---------------|
| 1 | `app/src/main/java/com/drama/app/domain/model/CommandType.kt` | Add `STEER`, `AUTO`, `STORM` enum entries |
| 2 | `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt` | Add `steerDrama()`, `autoAdvanceDrama()`, `stormDrama()` interface methods |
| 3 | `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt` | Implement the 3 new methods, delegating to `dramaApiService` |
| 4 | `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` | Add STEER/AUTO/STORM to `sendCommand()` when blocks; fix `isProcessing`/`isTyping` reset |
| 5 | `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt` | Add `/steer`, `/auto`, `/storm` to `SLASH_COMMANDS` list |

### No Changes Needed

| File | Reason |
|------|--------|
| `DramaApiService.kt` | Already has `steerDrama()`, `autoAdvance()`, `triggerStorm()` |
| `RequestDtos.kt` | Already has `SteerRequestDto`, `AutoRequestDto`, `StormRequestDto` |
| Backend `commands.py` | Already has `/drama/steer`, `/drama/auto`, `/drama/storm` endpoints |
| Backend `models.py` | Already has `SteerRequest`, `AutoRequest`, `StormRequest` |

---

## 6. Detailed Fix Specification

### 6.1 CommandType.kt — Add 3 enum entries

**File:** `app/src/main/java/com/drama/app/domain/model/CommandType.kt`

Add before `FREE_TEXT`:
```kotlin
STEER("/steer", true),
AUTO("/auto", true),    // argument is optional but needsArgument=true for parsing
STORM("/storm", false), // focus argument is optional
```

### 6.2 DramaRepository.kt — Add 3 interface methods

**File:** `app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt`

Add after `endDrama()`:
```kotlin
suspend fun steerDrama(direction: String): Result<CommandResponseDto>
suspend fun autoAdvanceDrama(numScenes: Int = 3): Result<CommandResponseDto>
suspend fun stormDrama(focus: String? = null): Result<CommandResponseDto>
```

### 6.3 DramaRepositoryImpl.kt — Add 3 implementations

**File:** `app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt`

Add after `endDrama()` impl (after line 77):
```kotlin
override suspend fun steerDrama(direction: String): Result<CommandResponseDto> =
    runCatching { dramaApiService.steerDrama(SteerRequestDto(direction)) }

override suspend fun autoAdvanceDrama(numScenes: Int): Result<CommandResponseDto> =
    runCatching { dramaApiService.autoAdvance(AutoRequestDto(numScenes)) }

override suspend fun stormDrama(focus: String?): Result<CommandResponseDto> =
    runCatching { dramaApiService.triggerStorm(StormRequestDto(focus)) }
```

Add import: `import com.drama.app.data.remote.dto.SteerRequestDto` (others already imported)

### 6.4 DramaDetailViewModel.kt — Wire commands and fix isProcessing

**File:** `app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt`

#### 6.4a sendCommand() — Add STEER/AUTO/STORM to the local command handling when block (lines 1146–1216)

No local handling needed for these — they should fall through to the API routing section.

But add them to the `else` catch at line 1215:
```kotlin
CommandType.STEER, CommandType.AUTO, CommandType.STORM -> { /* 继续走原有逻辑 */ }
```

Actually, they can just stay in the existing `else` branch since they're not local commands.

#### 6.4b sendCommand() — Add display text for STEER/AUTO/STORM (lines 1219–1235)

Add to the `when` block:
```kotlin
CommandType.STEER -> {
    val dir = text.removePrefix("/steer").trim()
    if (dir.isBlank()) return
    "📌 方向：$dir"
}
CommandType.AUTO -> {
    val n = text.removePrefix("/auto").trim().ifBlank { "3" }
    "⏩ 自动推进 ${n} 场"
}
CommandType.STORM -> {
    val focus = text.removePrefix("/storm").trim()
    if (focus.isNotBlank()) "🌪️ 多视角探索：$focus" else "🌪️ 多视角探索"
}
```

Also add them to the SAVE/LOAD/LIST/DELETE/CAST branch:
```kotlin
CommandType.SAVE, CommandType.LOAD, CommandType.LIST, CommandType.DELETE, CommandType.CAST ->
    ""
```
→ Add `STEER, AUTO, STORM` to this branch? NO — these commands should display a user bubble.

#### 6.4c sendCommand() — Add to isActionCommand check (line 1238)

```kotlin
val isActionCommand = commandType in listOf(CommandType.ACTION, CommandType.NEXT, CommandType.STEER, CommandType.AUTO, CommandType.STORM)
```

#### 6.4d sendCommand() — Add to isPlotChanging check (lines 1253–1255)

```kotlin
val isPlotChanging = commandType in listOf(
    CommandType.NEXT, CommandType.ACTION, CommandType.SPEAK, CommandType.FREE_TEXT,
    CommandType.STEER, CommandType.AUTO, CommandType.STORM,
)
```

#### 6.4e sendCommand() — Add to API routing when block (lines 1282–1293)

Add before the `FREE_TEXT` branch:
```kotlin
CommandType.STEER -> dramaRepository.steerDrama(text.removePrefix("/steer").trim())
CommandType.AUTO -> {
    val n = text.removePrefix("/auto").trim().toIntOrNull() ?: 3
    dramaRepository.autoAdvanceDrama(n)
}
CommandType.STORM -> dramaRepository.stormDrama(text.removePrefix("/storm").trim().ifBlank { null })
```

Also add STEER/AUTO/STORM to the "unreachable" branch:
```kotlin
CommandType.SAVE, CommandType.LOAD, CommandType.LIST, CommandType.DELETE, CommandType.CAST,
CommandType.STEER, CommandType.AUTO, CommandType.STORM ->
    Result.success(CommandResponseDto())  // 不会到达此处
```

Wait, STEER/AUTO/STORM WILL reach the API routing, so they should NOT be in the "unreachable" branch. Just leave the existing branch as-is and add the 3 new cases before `FREE_TEXT`.

#### 6.4f sendCommand() — Fix isProcessing reset

**Critical fix for the WS connected path.** At line 1295–1297:
```kotlin
if (_uiState.value.isWsConnected) {
    _uiState.update { it.copy(isProcessing = false) }
}
```

This only resets `isProcessing`, not `isTyping`. The `isTyping` relies on WS events arriving. But if no WS event arrives (timeout, lost message), `isTyping` stays true.

**Recommended fix:** Add a safety timeout coroutine that auto-resets `isTyping` and `isProcessing` after 60 seconds:

```kotlin
// After setting isProcessing = true and isTyping = true:
val safetyJob = viewModelScope.launch {
    delay(60_000)  // 60 seconds safety timeout
    if (_uiState.value.isTyping || _uiState.value.isProcessing) {
        _uiState.update { it.copy(isTyping = false, isProcessing = false) }
        addErrorBubble("[超时] AI 响应超时，请重试")
    }
}
// Cancel the safety job when WS events clear isTyping
// (in handleWsEvent's isTyping=false resets)
```

Alternative simpler fix: Add `isTyping = false` alongside `isProcessing = false` in the WS connected branch with a brief delay, so WS events have time to arrive:
```kotlin
if (_uiState.value.isWsConnected) {
    _uiState.update { it.copy(isProcessing = false) }
    // isTyping remains true, waiting for WS events
    // Safety: if no WS event resets isTyping within 60s, force reset
    viewModelScope.launch {
        delay(60_000)
        if (_uiState.value.isTyping) {
            _uiState.update { it.copy(isTyping = false) }
        }
    }
}
```

### 6.5 ChatInputBar.kt — Add slash commands

**File:** `app/src/main/java/com/drama/app/ui/screens/dramadetail/components/ChatInputBar.kt`

Add to `SLASH_COMMANDS` list (after `/next`):
```kotlin
SlashCommand("/steer", "<方向>", "引导剧情走向指定方向"),
SlashCommand("/auto", "[场次]", "自动推进N场剧情（默认3场）"),
SlashCommand("/storm", "[焦点]", "触发STORM多视角探索"),
```

---

## 7. Additional Observations

### 7.1 ChatInputBar also missing `/end` and `/speak` in SLASH_COMMANDS

The `SLASH_COMMANDS` list does not include `/end` or `/speak`, which are valid CommandType entries. This means users can't discover these commands through the slash menu. Consider adding:
```kotlin
SlashCommand("/end", "", "落幕，结束当前戏剧"),
SlashCommand("/speak", "<角色> <情境>", "让指定角色在情境中发言"),
```

### 7.2 `/start` is in SLASH_COMMANDS but not in CommandType

`ChatInputBar` lists `/start` as a slash command, but `CommandType` enum has no `START` entry. When a user types `/start foo`, it maps to `FREE_TEXT`, which calls `dramaRepository.userAction("/start foo")` instead of `dramaRepository.startDrama("foo")`. This is likely a bug, but may be intentional (start is usually handled from a different screen).

### 7.3 `/quit` and `/status` and `/export` are in SLASH_COMMANDS but not in CommandType

Same pattern — these will fall through to `FREE_TEXT` → `userAction()`, which may or may not be the intended behavior.

### 7.4 The `needsArgument` field is not used consistently

`CommandType.STORM` should have `needsArgument = false` since focus is optional, but `CommandType.AUTO` is tricky — the argument (number of scenes) is optional with a default. Set `needsArgument = true` to match the slash command UX where the user should provide a number.

---

*Analysis complete. All file paths use backticks for direct navigation.*
