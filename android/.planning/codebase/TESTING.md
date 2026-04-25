# Testing Patterns

**Analysis Date:** 2026-04-25

## Test Framework

**Runner:**
- Not configured — no test runner detected in the codebase
- No `jest.config.*`, `vitest.config.*`, or Android test configurations found
- `app/build.gradle.kts` does not include test dependencies beyond default Android test runner

**Assertion Library:**
- Not detected

**Run Commands:**
```bash
# No test commands available — no test infrastructure set up
```

## Test File Organization

**Location:**
- No test directories found (`src/test/`, `src/androidTest/` do not exist or are empty)
- No `*.test.kt` or `*Test.kt` files found

**Naming:**
- Not applicable

**Structure:**
```
# No test structure exists
```

## Test Structure

**Suite Organization:**
- No test suites exist

**Patterns:**
- No testing patterns established

## Mocking

**Framework:** None

**Patterns:**
- No mocking patterns established

## Fixtures and Factories

**Test Data:**
- No test fixtures or factories

**Location:**
- Not applicable

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
# Not available — no tests exist
```

## Test Types

**Unit Tests:**
- None

**Integration Tests:**
- None

**E2E Tests:**
- None

## Critical Areas Needing Tests

**ViewModel Logic (`DramaDetailViewModel.kt` — 1227 lines):**
- `handleWsEvent()` — Complex event routing with 15+ event types, each creating different bubble types
- `sendCommand()` — Command parsing and local save handling
- `sendChatMessage()` — Dual-path (WS vs REST) response handling
- Error deduplication via `addedErrorIds`
- `performInitSync()` — Race condition handling between skipLoad and state drift

**Use Case (`DetectActorInteractionUseCase.kt`):**
- Interaction type detection (REPLY, CHIME_IN, COUNTER, PROPOSE)
- Keyword-based semantic analysis for counter/propose detection
- Target actor inference from last bubble

**Repository (`DramaRepositoryImpl.kt`):**
- `getSceneBubbles()` — DTO → SceneBubble mapping with prefix and divider logic
- `sendChatMessageAsBubbles()` — CommandResponseDto → SceneBubble conversion
- `getMergedCast()` — Cast + CastStatus → ActorInfo merging

**WebSocket Manager (`WebSocketManager.kt` — 16KB):**
- Auto-reconnect with exponential backoff
- ConnectionState transitions
- Event parsing from JSON frames

## Recommended Testing Strategy

**Priority 1 — Unit Tests:**
- `DetectActorInteractionUseCase` — Pure logic, easy to test, high value
- `DramaDetailViewModel.handleWsEvent()` — Test each event type creates correct bubble
- `DramaRepositoryImpl.getSceneBubbles()` — Test DTO mapping correctness

**Priority 2 — Integration Tests:**
- WebSocket connection lifecycle (connect → receive events → disconnect → reconnect)
- REST API error handling and fallback

**Priority 3 — UI Tests:**
- Compose testing for `SceneBubbleList` rendering
- Input bar command handling
- Navigation flows

---

*Testing analysis: 2026-04-25*
