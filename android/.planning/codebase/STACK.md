# Technology Stack

**Analysis Date:** 2026-04-24

## Languages

**Primary:**
- Kotlin 2.1.0 - All application code (100%)

**Secondary:**
- None (pure Kotlin project)

## Runtime

**Environment:**
- Android SDK 35 (compileSdk), minSdk 26, targetSdk 35
- Java 17 (source/target compatibility)

**Package Manager:**
- Gradle 8.7.3 (via AGP)
- Version catalog: `gradle/libs.versions.toml`
- Lockfile: Not present (Gradle lockfile not enabled)

## Frameworks

**Core:**
- Jetpack Compose (BOM 2025.12.01) - Declarative UI framework
- Material3 - Design system
- Navigation Compose 2.8.9 - Type-safe navigation with `@Serializable` routes
- Hilt 2.54 - Dependency injection

**Networking:**
- Retrofit 2.12.0 - REST API client
- OkHttp 4.12.0 - HTTP client + WebSocket
- Kotlinx Serialization 1.8.1 - JSON serialization (compiler plugin + runtime)

**Data:**
- DataStore Preferences 1.1.7 - Key-value persistent storage
- Security Crypto 1.1.0-alpha06 - Encrypted SharedPreferences for token storage

**Lifecycle:**
- Lifecycle ViewModel Compose 2.8.7 - ViewModel integration with Compose
- Lifecycle Runtime Compose 2.8.7 - `collectAsStateWithLifecycle()`

**Build/Dev:**
- KSP 2.1.0-1.0.29 - Kotlin Symbol Processing (for Hilt)
- Compose Compiler Plugin 2.1.0 - Compose compiler (via kotlin-compose plugin)
- Kotlin Serialization Plugin 2.1.0 - `@Serializable` code generation

## Key Dependencies

**Critical:**
- `okhttp` 4.12.0 - HTTP client for REST and WebSocket; `WebSocketManager` depends on OkHttp's `WebSocket` API
- `retrofit` 2.12.0 - REST API client; all backend communication uses Retrofit service interfaces
- `kotlinx-serialization-json` 1.8.1 - JSON parsing for both REST responses and WebSocket messages
- `hilt-android` 2.54 - DI framework; all ViewModels, repositories, and managers are Hilt-injected

**Infrastructure:**
- `datastore-preferences` 1.1.7 - Server config persistence (IP, port, base URL)
- `security-crypto` 1.1.0-alpha06 - Encrypted token storage via `SecureStorage`
- `navigation-compose` 2.8.9 - Type-safe routing with `@Serializable` route objects

## Configuration

**Environment:**
- Server IP/port/base URL stored in DataStore (`drama_settings`)
- Auth token stored encrypted via `EncryptedSharedPreferences` (`drama_secure_prefs`)
- Default server: `http://127.0.0.1:8000/api/v1/` (placeholder for first launch)

**Build:**
- `app/build.gradle.kts` - App module config (SDK versions, compose, plugins)
- `gradle/libs.versions.toml` - Centralized version catalog
- `build.gradle.kts` - Root project config
- `settings.gradle.kts` - Module declarations (single `:app` module)
- `gradle.properties` - Gradle/JVM properties
- `proguard-rules.pro` - ProGuard rules (minify disabled in release)

## Platform Requirements

**Development:**
- Android Studio (Iguana or later)
- JDK 17
- Android SDK with API 35
- Kotlin 2.1.0 plugin

**Production:**
- Android 8.0 (API 26) minimum
- Internet permission required
- Deployed as APK (built via `build_apk.sh`)
