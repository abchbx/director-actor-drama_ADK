# Technology Stack

**Analysis Date:** 2026-04-25

## Languages

**Primary:**
- Kotlin — All application code (UI, logic, data, DI)

**Secondary:**
- XML — Android resources (manifest, layouts, themes, icons)
- Groovy/KTS — Gradle build scripts (`build.gradle.kts`, `settings.gradle.kts`)
- TOML — Version catalog (`gradle/libs.versions.toml`)
- Python — Backend (`event_mapper.py`, ADK Runner)

## Runtime

**Environment:**
- Android SDK (minSdk/targetSdk defined in `app/build.gradle.kts`)
- JVM (JDK 17 based on Kotlin configuration)

**Package Manager:**
- Gradle with Kotlin DSL
- Lockfile: Not present (version catalog `gradle/libs.versions.toml` serves as version pinning)

## Frameworks

**Core:**
- Jetpack Compose — Declarative UI framework (BOM-managed versions)
- Material3 — Design system (`androidx.compose.material3`)
- Hilt — Dependency injection (`dagger.hilt`)
- Navigation Compose — Type-safe routing (`androidx.navigation.compose`)
- Kotlin Serialization — JSON serialization (`kotlinx.serialization`)
- Kotlin Coroutines + Flow — Asynchronous programming

**Networking:**
- Retrofit — REST API client
- OkHttp — HTTP client + WebSocket support
- kotlinx.serialization.json — JSON parsing (not Gson/Moshi)

**Local Storage:**
- DataStore (Preferences) — Key-value persistence for saves and preferences
- EncryptedSharedPreferences — Secure credential storage

**Testing:**
- Not detected — No test dependencies or test files found in the codebase

**Build/Dev:**
- KSP (Kotlin Symbol Processing) — Hilt annotation processing
- Gradle Version Catalog — Centralized dependency version management

## Key Dependencies

**Critical:**
- `androidx.compose.material3` — All UI components use Material3 theming
- `dagger.hilt` — All ViewModels and repositories are Hilt-injected
- `kotlinx.serialization` — All DTOs and `SceneBubble` use `@Serializable`
- `okhttp3` — WebSocket connection (`WebSocketManager`) and HTTP client
- `retrofit2` — REST API calls (`DramaApiService`)
- `androidx.datastore` — Local save/load system

**Infrastructure:**
- `androidx.navigation.compose` — Screen navigation with type-safe routes
- `androidx.lifecycle` — ViewModel + `StateFlow` + `collectAsStateWithLifecycle()`
- `androidx.compose.foundation` — LazyColumn, animations, gestures

## Configuration

**Environment:**
- Server connection configured via `ServerPreferences` DataStore (IP, port, token, baseUrl)
- Auth token stored in `SecureStorage` (EncryptedSharedPreferences)
- `.env` files not used on Android side

**Build:**
- `app/build.gradle.kts` — Module-level build configuration
- `build.gradle.kts` — Root build configuration
- `gradle/libs.versions.toml` — Version catalog (all dependency versions)
- `gradle.properties` — Gradle properties
- `settings.gradle.kts` — Module inclusion

## Platform Requirements

**Development:**
- Android Studio (Iguana or later)
- JDK 17
- Android SDK with Compose tooling
- Physical device or emulator for testing

**Production:**
- Android API level matching minSdk (check `app/build.gradle.kts`)
- Network connectivity to server (REST + WebSocket)
- Server running at configured IP:port

---

*Stack analysis: 2026-04-25*
