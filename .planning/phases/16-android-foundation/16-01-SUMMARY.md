---
phase: 16-android-foundation
plan: 01
subsystem: infra
tags: [android, kotlin, compose, hilt, navigation, gradle, mvvm]

# Dependency graph
requires:
  - phase: 13-api-foundation
    provides: REST API endpoints that Android Retrofit will consume
  - phase: 15-authentication
    provides: Token auth endpoint /auth/verify for connection detection
provides:
  - Complete Android Gradle project skeleton with Kotlin DSL
  - Hilt DI configuration (@HiltAndroidApp + @AndroidEntryPoint + @HiltViewModel)
  - Navigation Compose skeleton with 5 type-safe routes
  - Bottom navigation bar with 3 tabs
  - 4 placeholder screens with MVVM architecture
affects: [16-android-foundation, 17-android-interaction, 18-android-features]

# Tech tracking
tech-stack:
  added: [Kotlin 2.1.0, Compose BOM 2025.12.01, Hilt 2.54, Navigation Compose 2.8.9, Retrofit 2.12.0, OkHttp 4.12.0, DataStore Preferences 1.1.7, KSP 2.1.0-1.0.29, AGP 8.7.3, kotlinx-serialization-json 1.8.1]
  patterns: [MVVM + Hilt ViewModel + Repository, Type-safe Navigation routes, Version catalog (libs.versions.toml), Compose BOM unified versioning]

key-files:
  created:
    - android/build.gradle.kts
    - android/settings.gradle.kts
    - android/gradle.properties
    - android/gradle/libs.versions.toml
    - android/app/build.gradle.kts
    - android/app/src/main/AndroidManifest.xml
    - android/app/src/main/java/com/drama/app/DramaApplication.kt
    - android/app/src/main/java/com/drama/app/MainActivity.kt
    - android/app/src/main/java/com/drama/app/ui/navigation/Route.kt
    - android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt
    - android/app/src/main/java/com/drama/app/ui/components/AppBottomNavigationBar.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListScreen.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateScreen.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt
    - android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsViewModel.kt
    - android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsScreen.kt
    - android/.gitignore
  modified: []

key-decisions:
  - "Gradle wrapper JAR is a minimal stub — full wrapper requires Android SDK environment to generate via gradle wrapper command"
  - "Bottom bar visibility uses hasRoute() against bottomNavItems list — cleaner than route string matching"
  - "Adaptive icon drawables used for launcher (API 26+ compatible) instead of PNG mipmaps"
  - "DramaDetailScreen uses full-package hiltViewModel() call to avoid import ambiguity with navigation hiltViewModel"

patterns-established:
  - "MVVM pattern: each screen has @HiltViewModel + @Composable Screen function"
  - "Type-safe routes: @Serializable object/data class for each navigation destination"
  - "Bottom nav items as data class list: BottomNavItem(label, route, icon) enables hasRoute matching"
  - "Version catalog: all dependency versions in libs.versions.toml, referenced via libs.xxx in build files"

requirements-completed: [APP-13, APP-14]

# Metrics
duration: 8min
completed: 2026-04-16
---

# Phase 16 Plan 01: Android Project Skeleton Summary

**Android Gradle Kotlin DSL project with Hilt DI, Navigation Compose 5-route skeleton, 3-tab bottom bar, and 4 MVVM placeholder screens**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-16T04:07:02Z
- **Completed:** 2026-04-16T04:15:00Z
- **Tasks:** 2
- **Files modified:** 22

## Accomplishments
- Complete Android Gradle project with Kotlin DSL, version catalog, and all required plugins (AGP 8.7.3, Kotlin 2.1.0, Hilt 2.54, KSP, Serialization, Compose)
- Hilt dependency injection fully configured: @HiltAndroidApp Application, @AndroidEntryPoint Activity, 4 @HiltViewModel screens
- Navigation Compose skeleton with 5 type-safe @Serializable routes (ConnectionGuide, DramaList, DramaCreate, Settings, DramaDetail)
- Bottom navigation bar with 3 tabs (戏剧/创建/设置) using MD3 NavigationBar, automatically hidden on DramaDetail route
- 4 placeholder screens following MVVM pattern with MutableStateFlow UI state

## Task Commits

Each task was committed atomically:

1. **Task 1: Gradle project + Hilt configuration** - `750182c` (feat)
2. **Task 2: Navigation Compose skeleton + bottom nav + placeholder screens** - `936b462` (feat)

## Files Created/Modified
- `android/build.gradle.kts` - Project-level Gradle config with all plugin declarations
- `android/settings.gradle.kts` - Plugin management and dependency resolution
- `android/gradle.properties` - JVM args, AndroidX, R8 settings
- `android/gradle/libs.versions.toml` - Version catalog with all dependency versions
- `android/gradle/wrapper/gradle-wrapper.properties` - Gradle 8.9 distribution URL
- `android/gradlew` / `android/gradlew.bat` - Gradle wrapper scripts
- `android/app/build.gradle.kts` - App-level config with minSdk=26, targetSdk=35, all dependencies
- `android/app/proguard-rules.pro` - Empty proguard rules (minifyEnabled=false)
- `android/app/src/main/AndroidManifest.xml` - INTERNET permission, usesCleartextTraffic, Hilt Application
- `android/app/src/main/java/com/drama/app/DramaApplication.kt` - @HiltAndroidApp Application class
- `android/app/src/main/java/com/drama/app/MainActivity.kt` - @AndroidEntryPoint Activity with Scaffold + nav + bottom bar
- `android/app/src/main/java/com/drama/app/ui/navigation/Route.kt` - 5 @Serializable route definitions
- `android/app/src/main/java/com/drama/app/ui/navigation/DramaNavHost.kt` - NavHost with all 5 composable routes
- `android/app/src/main/java/com/drama/app/ui/components/AppBottomNavigationBar.kt` - MD3 NavigationBar with 3 tabs
- `android/app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListViewModel.kt` - @HiltViewModel with StateFlow
- `android/app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListScreen.kt` - Placeholder with onDramaClick callback
- `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateViewModel.kt` - @HiltViewModel with StateFlow
- `android/app/src/main/java/com/drama/app/ui/screens/dramacreate/DramaCreateScreen.kt` - Placeholder screen
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailViewModel.kt` - @HiltViewModel with StateFlow
- `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt` - Placeholder with dramaId parameter
- `android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsViewModel.kt` - @HiltViewModel with StateFlow
- `android/app/src/main/java/com/drama/app/ui/screens/settings/SettingsScreen.kt` - Placeholder for settings + future server config
- `android/app/src/main/res/values/strings.xml` - App name string resource
- `android/app/src/main/res/values/themes.xml` - Material3 theme placeholder
- `android/app/src/main/res/drawable/ic_launcher_foreground.xml` - Adaptive icon foreground
- `android/app/src/main/res/drawable/ic_launcher_background.xml` - Adaptive icon background
- `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` - Adaptive icon definition
- `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` - Round adaptive icon
- `android/.gitignore` - Exclude .gradle, build, local.properties

## Decisions Made
- Used adaptive icon drawables (XML vector) instead of PNG mipmaps for launcher icons — lighter weight, resolution-independent, API 26+ compatible
- Bottom bar visibility controlled by `hasRoute()` check against `bottomNavItems` list rather than string route matching — type-safe and maintainable
- Gradle wrapper JAR is a minimal stub; real wrapper generation requires running `gradle wrapper` in an environment with Gradle installed
- DramaDetailScreen uses fully-qualified `androidx.hilt.navigation.compose.hiltViewModel()` to avoid import collision

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Android SDK not available in build environment, so `./gradlew assembleDebug` cannot be verified here — will be verified at integration time

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| DramaListViewModel.kt | `_uiState = MutableStateFlow("戏剧列表 - 占位")` | Phase 17 will wire real drama list data |
| DramaCreateViewModel.kt | `_uiState = MutableStateFlow("创建戏剧 - 占位")` | Phase 17 will implement drama creation form |
| DramaDetailViewModel.kt | `_uiState = MutableStateFlow("戏剧详情 - 占位")` | Phase 17 will fetch drama details via API |
| SettingsViewModel.kt | `_uiState = MutableStateFlow("设置 - 占位")` | Phase 16-02 will add server connection config |
| DramaNavHost.kt ConnectionGuide | Empty composable body | Phase 16-02 implements connection guide dialog |
| themes.xml | Material.Light.NoActionBar placeholder | Phase 16-03 will add proper MD3 theme |
| gradle-wrapper.jar | Minimal stub JAR | Requires Gradle installation to generate proper wrapper |

## Next Phase Readiness
- Android project skeleton complete, ready for Phase 16-02 (network layer, DataStore, server connection config)
- Phase 16-03 can add MD3 theme (DramaTheme composable) and replace the themes.xml placeholder
- Phase 17 can build on the MVVM + Navigation skeleton for real drama list, create, detail screens

---
*Phase: 16-android-foundation*
*Completed: 2026-04-16*
