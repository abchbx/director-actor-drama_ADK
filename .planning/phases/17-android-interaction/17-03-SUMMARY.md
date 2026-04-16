---
phase: 17-android-interaction
plan: 03
subsystem: ui, api
tags: [android, kotlin, compose, hilt, retrofit, websocket, mvvm, scene-history, save-load, bottom-sheet]

# Dependency graph
requires:
  - phase: 17-02
    provides: DramaDetailScreen, DramaDetailViewModel, SceneBubble, WebSocketManager
provides:
  - GET /drama/scenes backend endpoint for scene summary list
  - GET /drama/scenes/{scene_number} backend endpoint for scene detail
  - SceneHistorySheet ModalBottomSheet for scene history browsing
  - Save/load Snackbar confirmation feedback via SharedFlow events
  - Save Dialog with optional save name input
affects: [18-android-features]

# Tech tracking
tech-stack:
  added: []
  patterns: [ModalBottomSheet for scene history, AlertDialog for save input, WS save_confirm/load_confirm event handling, SharedFlow Snackbar confirmations]

key-files:
  created:
    - android/app/src/main/java/com/drama/app/data/remote/dto/SceneDto.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/components/SceneHistorySheet.kt
  modified:
    - app/state_manager.py
    - app/api/models.py
    - app/api/routers/queries.py
    - android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt
    - android/app/src/main/java/com/drama/app/domain/repository/DramaRepository.kt
    - android/app/src/main/java/com/drama/app/data/repository/DramaRepositoryImpl.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt

key-decisions:
  - "T-17-08 mitigation: scene_number path param validated 1-999 range in GET /drama/scenes/{n} endpoint"
  - "get_scene_summaries() handles both in-memory and archived (archived=True) scenes transparently"
  - "get_scene_detail() reads from state file then falls back to archived scene files on disk"
  - "History scene view replaces main bubbles content; returnToCurrentScene() reconnects WS for live content"

patterns-established:
  - "Backend scene listing pattern: iterate state.scenes list, load archived from disk on demand"
  - "History browsing pattern: loadScenes → showHistorySheet → viewHistoryScene → returnToCurrentScene"

requirements-completed: [APP-06, APP-12]

# Metrics
duration: 10min
completed: 2026-04-16
---

# Phase 17 Plan 03: Scene History + Save/Load Confirmation Summary

**Backend scene list API + SceneHistorySheet ModalBottomSheet + save/load Snackbar confirmation feedback**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-16T07:37:40Z
- **Completed:** 2026-04-16T07:47:40Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Backend GET /drama/scenes returns scene summaries (scene_number, title, description[:50])
- Backend GET /drama/scenes/{scene_number} returns full scene detail with narration, dialogue, raw data
- T-17-08 mitigation: scene_number validated 1-999 range
- SceneHistorySheet ModalBottomSheet with scrollable scene summary list
- History scene viewing replaces main content with back button (D-20)
- Save dialog with optional save name via overflow menu (D-23)
- WS save_confirm/load_confirm events trigger Snackbar confirmation (D-22)
- DramaDetailScreen fully integrated with all interaction features

## Task Commits

Each task was committed atomically:

1. **Task 1: 后端场景列表 API + Android 场景历史 BottomSheet + 保存/加载确认** - `99e8259` (feat)
2. **Task 2: DramaDetailScreen 整合历史面板 + 保存 Dialog + 导航更新** - `484a7ad` (feat)

## Files Created/Modified
- `app/state_manager.py` - Added get_scene_summaries() and get_scene_detail() functions
- `app/api/models.py` - Added SceneSummaryItem, ScenesResponse, SceneDetailResponse models
- `app/api/routers/queries.py` - Added GET /drama/scenes and GET /drama/scenes/{scene_number} endpoints
- `android/.../dto/SceneDto.kt` - New DTOs: SceneSummaryDto, ScenesResponseDto, SceneDetailDto
- `android/.../api/DramaApiService.kt` - Added getDramaScenes() and getDramaSceneDetail() Retrofit methods
- `android/.../repository/DramaRepository.kt` - Added getScenes() and getSceneDetail() interface methods
- `android/.../repository/DramaRepositoryImpl.kt` - Implemented getScenes() and getSceneDetail()
- `android/.../dramadetail/DramaDetailViewModel.kt` - Extended with history browsing, save dialog, WS confirm events
- `android/.../dramadetail/DramaDetailScreen.kt` - Integrated History button, overflow menu, back button, save dialog, SceneHistorySheet
- `android/.../components/SceneHistorySheet.kt` - New ModalBottomSheet component for scene history

## Decisions Made
- T-17-08 mitigation: scene_number path param validated with range check (1-999) in the endpoint
- get_scene_summaries() handles both in-memory scenes and archived scenes (archived=True) transparently by loading from disk when needed
- get_scene_detail() reads state from file first, then falls back to archived scene files on disk — necessary because we don't have tool_context in the detail endpoint
- History scene viewing replaces main bubbles content; returnToCurrentScene() reconnects WS to restore live content
- DramaDetailUiState extended with viewingHistoryScene, historyScenes, showHistorySheet, showSaveDialog fields

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Added scene_number range validation (T-17-08)**
- **Found during:** Task 1 (Backend GET /drama/scenes/{scene_number} implementation)
- **Issue:** Threat model T-17-08 assigned `mitigate` disposition — scene_number path param could be negative or excessively large
- **Fix:** Added range validation `1 <= scene_number <= 999` in the endpoint handler, returning 400 for invalid values
- **Files modified:** app/api/routers/queries.py
- **Verification:** grep confirms range check present
- **Committed in:** 99e8259 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 security)
**Impact on plan:** Essential security mitigation per threat model. No scope creep.

## Issues Encountered
None - all implementations followed plan specifications closely.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Scene history browsing fully functional, ready for Phase 18 enhancements (richer preview, scene comparison)
- Save/load confirmation Snackbar ready, Phase 18 can add undo functionality
- DramaDetailScreen is now complete with all Phase 17 interaction features
- Backend scene API ready for Phase 18 scene comparison/analytics features

## Self-Check: PASSED

All 10 created/modified files verified present. Both task commits (99e8259, 484a7ad) verified in git log.

---
*Phase: 17-android-interaction*
*Completed: 2026-04-16*
