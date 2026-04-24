# Testing Patterns

**Analysis Date:** 2026-04-24

## Test Framework

**Runner:**
- None configured — no test dependencies found in `build.gradle.kts`
- `testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"` declared in defaultConfig but no test libraries included

**Assertion Library:**
- Not applicable

**Run Commands:**
```bash
# No test commands available — no tests exist
```

## Test File Organization

**Location:**
- Not applicable — no test source directories found
- Expected locations (not yet created):
  - `app/src/test/java/com/drama/app/` — Unit tests
  - `app/src/androidTest/java/com/drama/app/` — Instrumentation tests

**Naming:**
- Not established yet

**Structure:**
```
Not applicable — no test files exist
```

## Test Structure

**Suite Organization:**
- Not applicable

**Patterns:**
- Not applicable

## Mocking

**Framework:** None configured

**What to Mock:**
When tests are added, these should be mocked:
- `DramaRepository` — interface, easy to mock with Mockito/MockK
- `WebSocketManager` — singleton with complex lifecycle, mock or fake
- `ServerPreferences` — DataStore wrapper, use InMemoryDataStore for testing
- `AuthRepository` — interface, mock for connection flow tests
- `OkHttpClient` — use MockWebServer for API service tests

**What NOT to Mock:**
- Domain models (`SceneBubble`, `CommandType`, etc.) — pure data classes, use real instances
- DTOs — simple serializable data classes
- `DetectActorInteractionUseCase` — pure logic, test with real instances

## Fixtures and Factories

**Test Data:**
- Not applicable

**Location:**
- Not applicable

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
# Not available — no tests or coverage tools configured
```

## Test Types

**Unit Tests:**
- None exist
- Recommended areas for unit testing:
  - `DramaCreateViewModel` — script creation flow, polling logic, theme matching
  - `DramaDetailViewModel` — WS event handling, command routing, chat flow
  - `DramaRepositoryImpl` — DTO-to-domain mapping, bubble extraction
  - `DetectActorInteractionUseCase` — interaction detection rules
  - `CommandType.fromInput()` — command parsing
  - `ServerConfig.toApiBaseUrl()` / `toWsUrl()` — URL construction

**Integration Tests:**
- None exist
- Recommended areas:
  - API service calls with MockWebServer
  - WebSocket event flow with mock WebSocket server
  - Full creation flow: ViewModel → Repository → API

**E2E Tests:**
- Not used

## Common Patterns

**Async Testing:**
- Not established — when adding tests, use `Turbine` for Flow testing and `runTest` for coroutines

**Error Testing:**
- Not established — when adding tests, test `Result.failure` paths for network errors, timeouts, auth failures

## Recommended Testing Setup

When tests are added, include these dependencies in `app/build.gradle.kts`:

```kotlin
// Unit testing
testImplementation("junit:junit:4.13.2")
testImplementation("io.mockk:mockk:1.13.8")
testImplementation("com.google.truth:truth:1.4.2")
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
testImplementation("app.cash.turbine:turbine:1.1.0")

// Instrumented testing
androidTestImplementation("androidx.test.ext:junit:1.2.1")
androidTestImplementation("androidx.compose.ui:ui-test-junit4")
debugImplementation("androidx.compose.ui:ui-test-manifest")

// MockWebServer for API testing
testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
```

---

*Testing analysis: 2026-04-24*
