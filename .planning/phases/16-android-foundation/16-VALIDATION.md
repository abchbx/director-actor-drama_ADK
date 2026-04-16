---
phase: 16
slug: android-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | JUnit 5 + Mockito + Kotlin Coroutines Test |
| **Config file** | android/app/build.gradle.kts (testImplementation dependencies) |
| **Quick run command** | `cd android && ./gradlew :app:testDebugUnitTest --tests "*.DramaApplicationTest"` |
| **Full suite command** | `cd android && ./gradlew :app:testDebugUnitTest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd android && ./gradlew :app:compileDebugKotlin` (compile check)
- **After every plan wave:** Run `cd android && ./gradlew :app:testDebugUnitTest` (full test suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | APP-14 | — | Hilt DI initializes without error | compile | `./gradlew :app:compileDebugKotlin` | ⬜ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | APP-13 | — | Navigation routes defined and navigable | compile | `./gradlew :app:compileDebugKotlin` | ⬜ W0 | ⬜ pending |
| 16-02-01 | 02 | 2 | APP-01, APP-13 | T-16-01, T-16-02 | Token encrypted in EncryptedSharedPreferences | unit | `./gradlew :app:testDebugUnitTest --tests "*.ServerPreferencesTest"` | ⬜ W0 | ⬜ pending |
| 16-02-02 | 02 | 2 | APP-01 | T-16-01 | ConnectionGuideDialog handles bypass/token modes | unit | `./gradlew :app:testDebugUnitTest --tests "*.ConnectionViewModelTest"` | ⬜ W0 | ⬜ pending |
| 16-03-01 | 03 | 3 | APP-16 | — | Dynamic Color enabled on API 31+ | unit | `./gradlew :app:testDebugUnitTest --tests "*.ThemeTest"` | ⬜ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `android/app/src/test/java/com/drama/app/DramaApplicationTest.kt` — Hilt initialization test
- [ ] `android/app/src/test/java/com/drama/app/data/local/ServerPreferencesTest.kt` — DataStore + encrypted token test
- [ ] `android/app/src/test/java/com/drama/app/ui/screens/connection/ConnectionViewModelTest.kt` — Connection flow test
- [ ] `android/app/src/test/java/com/drama/app/ui/theme/ThemeTest.kt` — Theme validation test
- [ ] JUnit 5 + Mockito + Coroutines Test dependencies in build.gradle.kts
- [ ] `android/app/src/test/java/com/drama/app/HiltTestRunner.kt` — Hilt test runner (integration tests)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dynamic Color renders on Android 12+ device | APP-16 | Requires physical device with wallpaper colors | Install on Pixel/Emulator with API 31+, verify colors match wallpaper |
| Dark mode default appearance | APP-16 | Visual inspection needed | Install app, verify dark theme renders by default |
| Bottom navigation bar 3 tabs visible | APP-13 | UI rendering requires device | Install app, verify 3 tab icons visible |
| ConnectionGuideDialog full-screen on first launch | APP-01 | First-launch behavior requires fresh install | Clear app data, launch, verify dialog appears |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
