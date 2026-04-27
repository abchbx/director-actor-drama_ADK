# Technology Stack

**Analysis Date:** 2026-04-27

## Languages

**Primary:**
- Kotlin 2.1.0 - All app source code (Jetpack Compose UI, ViewModel, DI, networking)

**Secondary:**
- Kotlin Serialization - DTO definitions and JSON parsing
- Groovy/Kotlin DSL - Gradle build scripts (build.gradle.kts)

## Runtime

**Environment:**
- Android SDK 35 (compileSdk / targetSdk)
- Min SDK 26 (Android 8.0 Oreo)
- JVM Target: 17

**Package Manager:**
- Gradle (Kotlin DSL) with version catalog (`gradle/libs.versions.toml`)
- Lockfile: Not present (no gradle lockfile committed)

## Frameworks

**Core:**
- Jetpack Compose (BOM 2025.12.01) - Declarative UI framework
- Material 3 - Design system
- Hilt 2.54 - Dependency injection (Dagger wrapper)
- Navigation Compose 2.8.9 - Screen navigation

**Networking:**
- OkHttp 4.12.0 - HTTP client & WebSocket
- Retrofit 2.12.0 - REST API client
- OkHttp Logging Interceptor 4.12.0 - Debug HTTP logging
- Kotlin Serialization JSON 1.8.1 - JSON parsing

**Data Persistence:**
- DataStore Preferences 1.1.7 - Key-value storage (server config, settings)
- Security Crypto 1.1.0-alpha06 - Encrypted SharedPreferences for token storage

**Lifecycle:**
- Lifecycle ViewModel Compose 2.8.7
- Lifecycle Runtime Compose 2.8.7

**Testing:**
- JUnit 4.13.2 - Unit test runner
- Mockito Kotlin 5.4.0 - Mocking
- Kotlinx Coroutines Test 1.10.2 - Coroutine testing
- OkHttp MockWebServer 4.12.0 - HTTP test server

**Build/Dev:**
- KSP 2.1.0-1.0.29 - Annotation processing (Hilt, Serialization)
- AGP 8.7.3 - Android Gradle Plugin
- R8 - Code shrinking & obfuscation (release builds)

## Key Dependencies

**Critical:**
- `com.squareup.okhttp3:okhttp:4.12.0` - HTTP client, WebSocket, interceptors
- `com.squareup.retrofit2:retrofit:2.12.0` - REST API interface generation
- `com.squareup.retrofit2:converter-kotlinx-serialization:2.12.0` - JSON converter for Retrofit
- `org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1` - JSON serialization
- `com.google.dagger:hilt-android:2.54` - DI framework

**Infrastructure:**
- `androidx.datastore:datastore-preferences:1.1.7` - Server config persistence
- `androidx.security:security-crypto:1.1.0-alpha06` - Encrypted token storage
- `androidx.activity:activity-compose:1.9.3` - Compose Activity integration

## Configuration

**Environment:**
- Server URL is NOT hardcoded — dynamically configured at runtime via `ServerPreferences`
- Default fallback: `http://127.0.0.1:8000/api/v1/` (local emulator)
- Cloud URL mode: Supports `https://xxx.cloudstudio.club/` style base URLs
- Auth token stored in `EncryptedSharedPreferences` (AES256_GCM)

**Build:**
- `android/app/build.gradle.kts` - App module build config
- `android/build.gradle.kts` - Project-level build config
- `android/gradle/libs.versions.toml` - Version catalog
- `android/gradle.properties` - Gradle properties
- `android/app/proguard-rules.pro` - R8 keep rules for networking classes

**Build Variants:**
- **Debug**: No minification, permissive network security (`network_security_config_debug.xml`), HTTP logging enabled
- **Release**: R8 minification + resource shrinking, strict network security (`network_security_config.xml`), no HTTP logging

## Platform Requirements

**Development:**
- JDK 17
- Android SDK with compileSdk 35
- Android emulator or physical device for testing

**Production:**
- Android 8.0+ (API 26+)
- Network access (INTERNET permission)
- Release builds enforce HTTPS-only (no cleartext except localhost)

---

*Stack analysis: 2026-04-27*
