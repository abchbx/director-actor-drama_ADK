# Testing Patterns

**Analysis Date:** 2026-04-22

## Test Framework

**Runner:**
- Not detected — no test framework configured for the Android app
- No `junit`, `mockk`, `turbine`, or other test dependencies found in source

**Assertion Library:**
- None

**Run Commands:**
```bash
# No test commands available
./gradlew test           # Would run unit tests (none exist)
./gradlew connectedTest  # Would run instrumented tests (none exist)
```

## Test File Organization

**Location:**
- No test directories found under `android/app/src/test/` or `android/app/src/androidTest/`
- The directory `android/app/src/` only contains `main/`

**Naming:**
- Not applicable (no test files)

**Structure:**
- Not applicable

## Test Structure

**Suite Organization:**
- No tests exist to analyze

**Patterns:**
- Not applicable

## Mocking

**Framework:** None

**Patterns:**
- Not applicable

**What to Mock:**
- For future tests: `DramaRepository`, `WebSocketManager`, `ServerPreferences`, `DramaApiService`

**What NOT to Mock:**
- Domain models (pure data classes), DTOs, Route definitions

## Fixtures and Factories

**Test Data:**
- `app/dramas/南阳三子/state.json` exists in the Python backend as a sample drama fixture
- No Android-specific test fixtures

**Location:**
- Not applicable

## Coverage

**Requirements:** None enforced

**View Coverage:**
```bash
# No coverage tools configured
```

## Test Types

**Unit Tests:**
- None — 0% coverage for ViewModels, Repositories, UseCases

**Integration Tests:**
- None — no API integration tests, no database tests

**E2E Tests:**
- Not used

## Common Patterns

**Async Testing:**
- Not applicable (no tests)
- Recommended: Use `Turbine` for Flow testing, `runTest` for coroutine tests

**Error Testing:**
- Not applicable

## Recommendations for Adding Tests

**Priority 1 — ViewModel Unit Tests:**
```kotlin
// Example structure for DramaCreateViewModel
@OptIn(ExperimentalCoroutinesApi::class)
class DramaCreateViewModelTest {
    @get:Rule val mainDispatcherRule = MainDispatcherRule()
    
    private val dramaRepository = mockk<DramaRepository>()
    private val webSocketManager = mockk<WebSocketManager>()
    private val serverPreferences = mockk<ServerPreferences>()
    
    private lateinit var viewModel: DramaCreateViewModel
    
    @Before
    fun setup() {
        viewModel = DramaCreateViewModel(dramaRepository, webSocketManager, serverPreferences)
    }
    
    @Test
    fun `createDrama with blank theme does nothing`() = runTest {
        viewModel.createDrama("")
        assertEquals(DramaCreateUiState(), viewModel.uiState.value)
    }
    
    @Test
    fun `createDrama sets isCreating true`() = runTest {
        coEvery { serverPreferences.serverConfig } returns flowOf(ServerConfig("1.2.3.4", "8000", null, null))
        coEvery { webSocketManager.connect(any(), any(), any(), any()) } returns flowOf()
        coEvery { dramaRepository.startDrama(any()) } returns Result.success(CommandResponseDto())
        
        viewModel.createDrama("Test Theme")
        assertTrue(viewModel.uiState.value.isCreating)
    }
}
```

**Priority 2 — Repository Unit Tests:**
```kotlin
class DramaRepositoryImplTest {
    private val apiService = mockk<DramaApiService>()
    private val repository = DramaRepositoryImpl(apiService)
    
    @Test
    fun `startDrama calls api with correct request`() = runTest {
        coEvery { apiService.startDrama(any()) } returns CommandResponseDto()
        repository.startDrama("Test")
        coVerify { apiService.startDrama(StartDramaRequestDto("Test")) }
    }
}
```

**Priority 3 — Navigation Tests:**
- Test that `DramaNavHost` navigates correctly between routes
- Test that DramaCreate emits NavigateToDetail event on completion

---

*Testing analysis: 2026-04-22*
