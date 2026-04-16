---
phase: 17-android-interaction
plan: 02
subsystem: ui
tags: [android, kotlin, compose, hilt, websocket, mvvm, scene-bubbles, command-input]

# Dependency graph
requires:
  - phase: 17-01
    provides: DramaRepository, DramaCreateScreen, DramaListScreen, WS infrastructure
provides:
  - DramaDetailScreen with real-time WS-driven scene bubbles + command bar
  - DramaDetailViewModel with WS event handling and command dispatch
  - SceneBubble domain model (Narration/Dialogue/SceneDivider)
  - CommandType enum with command parsing logic
  - 6 sub-components (NarrationBubble, DialogueBubble, SceneBubbleList, CommandInputBar, TypingIndicator, TensionIndicator)
affects: [17-03, 18-android-features]

# Tech tracking
tech-stack:
  added: []
  patterns: [WS event-driven StateFlow updates, SceneBubble sealed class for polymorphic list, CommandType parsing for command routing, SharedFlow for one-time events]

key-files:
  created:
    - android/app/src/main/java/com/drama/app/domain/model/SceneBubble.kt
    - android/app/src/main/java/com/drama/app/domain/model/CommandType.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/NarrationBubble.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/DialogueBubble.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneBubbleList.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/CommandInputBar.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/TypingIndicator.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/TensionIndicator.kt
  modified:
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt

key-decisions:
  - "narration event only marks typing=false; actual text rendered from end_narration event (per event_mapper.py analysis)"
  - "Replay messages (type=replay) silently ignored in handleWsEvent to prevent bubble duplication (Pitfall 6)"
  - "FREE_TEXT command type routes to userAction() — treating unstructured input as /action"

patterns-established:
  - "SceneBubble sealed class pattern for polymorphic LazyColumn items with stable keys"
  - "CommandType.fromInput() for command routing without regex"
  - "imePadding on bottom bar for soft keyboard accommodation"

requirements-completed: [APP-04, APP-05]

# Metrics
duration: 9min
completed: 2026-04-16
---

# Phase 17 Plan 02: DramaDetail Screen Summary

**Real-time scene bubble UI with WS event-driven updates, command input bar with /next /action /speak /end chips, and typing/tension indicators**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-16T07:22:14Z
- **Completed:** 2026-04-16T07:30:58Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- DramaDetailViewModel connects WebSocket, dispatches events to StateFlow, sends commands via DramaRepository
- SceneBubble sealed class enables type-safe polymorphic bubble rendering in LazyColumn
- 6 UI sub-components: NarrationBubble (grey left), DialogueBubble (primary right + avatar), SceneBubbleList (auto-scroll), CommandInputBar (4 chips + input), TypingIndicator (pulse), TensionIndicator (fire icon + score)
- DramaDetailScreen assembled with TopAppBar + scene area + bottom command bar

## Task Commits

Each task was committed atomically:

1. **Task 1: Domain models + DramaDetailViewModel** - `681d703` (feat)
2. **Task 2: DramaDetailScreen + 6 sub-components** - `0cde4b3` (feat)

## Files Created/Modified
- `android/.../model/SceneBubble.kt` - Sealed class for Narration/Dialogue/SceneDivider bubble types
- `android/.../model/CommandType.kt` - Enum with /next /action /speak /end and free text parsing
- `android/.../dramadetail/DramaDetailViewModel.kt` - Full rewrite with WS event handling + command dispatch
- `android/.../dramadetail/DramaDetailScreen.kt` - Full rewrite with Scaffold + TopAppBar + bubble list + command bar
- `android/.../components/NarrationBubble.kt` - Grey left-aligned narration bubble
- `android/.../components/DialogueBubble.kt` - Primary right-aligned dialogue bubble with actor avatar
- `android/.../components/SceneBubbleList.kt` - LazyColumn with auto-scroll and typing indicator
- `android/.../components/CommandInputBar.kt` - 4 SuggestionChips + OutlinedTextField + imePadding
- `android/.../components/TypingIndicator.kt` - Pulse animation + "导演正在构思..."
- `android/.../components/TensionIndicator.kt` - Fire icon + score with 3-tier color

## Decisions Made
- Narration event only sets `isTyping = false`; actual text is rendered from `end_narration` event data (consistent with event_mapper.py where narration function_call has no text, text comes from end_narration)
- Replay messages (type="replay") silently ignored in handleWsEvent to prevent bubble duplication (Pitfall 6)
- FREE_TEXT command type routes to `userAction()` — treating unstructured input as an action description
- `isProcessing` flag not cleared on command success — WS typing/content events control the state naturally

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all implementations followed plan specifications closely.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DramaDetailScreen ready for Plan 17-03 (scene history BottomSheet + save/load)
- WS event handling fully wired, ready for Phase 18 enhanced typing indicator and auto-reconnect

## Self-Check: PASSED

All 10 created/modified files verified present. Both task commits (681d703, 0cde4b3) verified in git log.

---
*Phase: 17-android-interaction*
*Completed: 2026-04-16*
