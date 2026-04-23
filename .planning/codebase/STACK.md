# Technology Stack

**Analysis Date:** 2026-04-22

## Languages

**Primary:**
- Kotlin — All Android app code (UI, ViewModel, Data, Domain layers)

**Secondary:**
- Python — Backend server (`director_actor_drama/`, `app/`, `cli.py`)
- Kotlin DSL — Gradle build scripts (`build.gradle.kts`)

## Runtime

**Environment:**
- Android API (minSdk/targetSdk defined in build.gradle.kts)
- JVM (for Kotlin compilation)

**Package Manager:**
- Gradle with Kotlin DSL
- Lockfile: Gradle lockfile not present (uses version catalog or direct declarations)

## Frameworks

**Core:**
- Jetpack Compose — Declarative UI framework
- Material 3 (Material3) — Design system and component library
- Jetpack Navigation Compose — Type-safe navigation with `@Serializable` routes
- Hilt — Dependency injection (built on Dagger)
- Kotlin Coroutines + Flow — Asynchronous programming and reactive streams

**Networking:**
- Retrofit 2 — REST API client
- OkHttp — HTTP client + WebSocket support
- kotlinx.serialization — JSON serialization/deserialization

**Data:**
- DataStore (Preferences) — Key-value persistence for server config

**Testing:**
- Not detected — No test dependencies found in the Android app source

**Build/Dev:**
- KSP (Kotlin Symbol Processing) — Used by Hilt for code generation
- Gradle Wrapper — Build system

## Key Dependencies

**Critical:**
- `androidx.compose.ui` — Core Compose UI primitives
- `androidx.navigation.compose` — Navigation framework with type-safe routes
- `com.google.dagger:hilt-android` — DI framework
- `com.squareup.retrofit2:retrofit` — REST API communication
- `com.squareup.okhttp3:okhttp` — HTTP + WebSocket client
- `org.jetbrains.kotlinx:kotlinx-serialization-json` — JSON parsing

**Infrastructure:**
- `androidx.datastore:datastore-preferences` — Server config persistence
- `androidx.lifecycle:lifecycle-viewmodel-compose` — ViewModel integration with Compose
- `androidx.hilt:hilt-navigation-compose` — Hilt ViewModel injection in Compose

## Configuration

**Environment:**
- Server IP/port stored in DataStore (via `ServerPreferences`)
- Auth token stored in DataStore
- First launch detected by absence of server config → shows ConnectionGuide
- Base URL for API: `http://{ip}:{port}/api/v1/` (configurable)

**Build:**
- `android/app/build.gradle.kts` — App module build config
- `android/build.gradle.kts` — Project-level build config
- `android/settings.gradle.kts` — Module includes
- `android/gradle.properties` — Gradle properties

## Platform Requirements

**Development:**
- Android Studio (Iguana or later recommended)
- Android SDK with Compose support
- Kotlin 2.0+ (for type-safe navigation routes)
- KSP for Hilt annotation processing

**Production:**
- Android device/emulator (API level per minSdk)
- Backend server running (Python FastAPI) accessible via network
- Network connectivity required (no offline mode)

---

*Stack analysis: 2026-04-22*
