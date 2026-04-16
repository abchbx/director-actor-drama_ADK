---
phase: 16-android-foundation
plan: 02
subsystem: [networking, auth, ui]
tags: [retrofit, okhttp, datastore, hilt, websocket, compose]

# Dependency graph
requires:
  - phase: 16-android-foundation/01
    provides: "Android project skeleton with Hilt DI, Navigation Compose, and placeholder screens"
provides:
  - "Retrofit API services mapping 14 REST endpoints + /auth/verify"
  - "OkHttp AuthInterceptor for Bearer token injection"
  - "DataStore-based ServerPreferences for server config persistence"
  - "EncryptedSharedPreferences for secure token storage"
  - "WebSocketManager for real-time server events"
  - "ConnectionGuideDialog for first-launch server connection"
  - "ConnectionViewModel managing connection lifecycle"
  - "Settings page server connection section"
affects: [16-03, 17, 18]

# Tech tracking
tech-stack:
  added: [retrofit, okhttp, datastore-preferences, security-crypto, kotlin-serialization]
  patterns: [repository-pattern, clean-architecture-layers, hilt-di-modules, sealed-class-state]

key-files:
  created:
    - "android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/api/AuthApiService.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/AuthVerifyResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/CommandResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/DramaStatusResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/DramaListResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/CastResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/SaveLoadResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/ExportResponseDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/WsEventDto.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/dto/RequestDtos.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt"
    - "android/app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt"
    - "android/app/src/main/java/com/drama/app/data/local/ServerPreferences.kt"
    - "android/app/src/main/java/com/drama/app/domain/model/ServerConfig.kt"
    - "android/app/src/main/java/com/drama/app/domain/model/ConnectionStatus.kt"
    - "android/app/src/main/java/com/drama/app/domain/model/AuthMode.kt"
    - "android/app/src/main/java/com/drama/app/domain/repository/ServerRepository.kt"
    - "android/app/src/main/java/com/drama/app/domain/repository/AuthRepository.kt"
    - "android/app/src/main/java/com/drama/app/data/repository/ServerRepositoryImpl.kt"
    - "android/app/src/main/java/com/drama/app/data/repository/AuthRepositoryImpl.kt"
    - "android/app/src/main/java/com/drama/app/di/NetworkModule.kt"
    - "android/app/src/main/java/com/drama/app/di/DataStoreModule.kt"
    - "android/app/src/main/java/com/drama/app/ui/screens/connection/ConnectionGuideDialog.kt"
    - "android/app/src/main/java/com/drama/app/ui/screens/connection/ConnectionViewModel.kt"
  modified:
    - "android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsScreen.kt"
    - "android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsViewModel.kt"
    - "android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt"
    - "android/app/src/main/java/com/drama/app/MainActivity.kt"
    - "android/app/build.gradle.kts"

key-decisions:
  - "AuthRepositoryImpl uses temporary Retrofit for verify to support dynamic baseUrl"
  - "EncryptedSharedPreferences for token storage (security-crypto dependency added)"
  - "ConnectionGuideDialog as full-screen dialog, not separate route"
  - "ConnectionStatus as sealed class (Idle/Connecting/Connected/Error) for type-safe state"

patterns-established:
  - "Repository pattern: domain interfaces in domain/repository/, implementations in data/repository/"
  - "Clean Architecture layers: domain → data → ui, with Hilt binding"
  - "Sealed class for UI state: ConnectionStatus, AuthMode pattern"
  - "Hilt module organization: NetworkModule for networking, DataStoreModule for persistence"

requirements-completed: [APP-01, APP-13, APP-14]

# Metrics
duration: 30min
completed: 2026-04-16
---

# Phase 16: android-foundation Plan 02 Summary

**Retrofit API services (14 endpoints + auth) + OkHttp interceptor + DataStore persistence + WebSocket manager + connection guide UI with auto token detection**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2
- **Files modified:** 30

## Accomplishments
- Complete data layer: 10 DTO files, 2 API service interfaces, 2 repository implementations
- Network infrastructure: NetworkModule (Retrofit + OkHttp), DataStoreModule (DataStore + EncryptedPrefs)
- Connection UI: ConnectionGuideDialog with IP:port input, auto token detection (bypass/requireToken), error Snackbar
- Settings page updated with server connection section
- WebSocketManager wrapping OkHttp WebSocket with Flow<WsEventDto>
- AuthInterceptor injecting Bearer token via OkHttp interceptor chain

## Task Commits

1. **Task 1: Data layer — Retrofit API + DTOs + DataStore + Repositories + Hilt modules** - `8b1a820` (feat)
2. **Task 2: Server connection UI — guide dialog + settings section + ConnectionViewModel** - `a8c95fb` (feat)

**Chore:** `d5c1db2` - Add missing android .gitignore

## Files Created/Modified
- `android/app/src/main/java/com/drama/app/data/remote/api/DramaApiService.kt` - 14 REST endpoint Retrofit interface
- `android/app/src/main/java/com/drama/app/data/remote/api/AuthApiService.kt` - /auth/verify Retrofit interface
- `android/app/src/main/java/com/drama/app/data/remote/dto/*.kt` - 10 DTO files aligned with backend Pydantic models
- `android/app/src/main/java/com/drama/app/data/remote/ws/WebSocketManager.kt` - OkHttp WebSocket with Flow
- `android/app/src/main/java/com/drama/app/data/remote/interceptor/AuthInterceptor.kt` - Bearer token injection
- `android/app/src/main/java/com/drama/app/data/local/ServerPreferences.kt` - DataStore + EncryptedSharedPreferences
- `android/app/src/main/java/com/drama/app/di/NetworkModule.kt` - Hilt module for Retrofit/OkHttp
- `android/app/src/main/java/com/drama/app/di/DataStoreModule.kt` - Hilt module for DataStore/EncryptedPrefs
- `android/app/src/main/java/com/drama/app/ui/screens/connection/ConnectionGuideDialog.kt` - First-launch connection dialog
- `android/app/src/main/java/com/drama/app/ui/screens/connection/ConnectionViewModel.kt` - Connection state management
- `android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsScreen.kt` - Added server connection section
- `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt` - Updated for ConnectionGuide route
- `android/app/src/main/java/com/drama/app/MainActivity.kt` - Dynamic startDestination

## Decisions Made
- AuthRepositoryImpl uses temporary Retrofit for verify (dynamic baseUrl needed before full Retrofit setup)
- EncryptedSharedPreferences added via security-crypto for token storage security
- ConnectionGuideDialog implemented as full-screen dialog, not a separate navigation route

## Deviations from Plan

None - plan executed as specified.

## Issues Encountered
None

## Next Phase Readiness
- Data layer complete: all 14 API endpoints mapped, DTOs aligned with backend
- Connection flow ready: first-launch guide → connect → auto token detect → navigate to DramaList
- Wave 3 (16-03) can proceed: Theme system only needs MainActivity reference

---
*Phase: 16-android-foundation*
*Completed: 2026-04-16*
