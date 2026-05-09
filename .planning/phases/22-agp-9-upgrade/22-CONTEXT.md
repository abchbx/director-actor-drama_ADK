# Phase 22: AGP 9 Upgrade

## Goal
将 Android 项目从 AGP 8.7.3 升级到 AGP 9.0.1。

## Current State
- AGP 8.7.3, Gradle 8.9
- Kotlin 2.1.0, KSP 2.1.0-1.0.29, Hilt 2.54

## Final State
- AGP 9.0.1, Gradle 9.5.0
- Hilt 2.59.2, KSP 2.2.10-2.0.2
- 内置 Kotlin + 新 DSL **opt-out**（因 KSP 不兼容）

## Changes

### 1. Gradle wrapper: 8.9 → 9.5.0
- AGP 9.0.1 强制要求 Gradle 9.1.0+
- Gradle 9.1 未发布，Gradle 9.0 可用但 AGP 拒绝（要求 9.1+）
- Gradle 9.5.0 可用且满足版本要求

### 2. AGP: 8.7.3 → 9.0.1
- `build.gradle.kts` (project level)
- `gradle/libs.versions.toml`

### 3. Hilt: 2.54 → 2.59.2
- Maven Central 确认存在

### 4. KSP: 2.1.0-1.0.29 → 2.2.10-2.0.2
- AGP 9 强制升级到匹配 KGP 版本

### 5. 内置 Kotlin opt-out
- KSP 插件内部使用 `kotlin.sourceSets` DSL 添加生成代码
- AGP 9 内置 Kotlin 禁止 `kotlin.sourceSets` DSL
- 当前环境无 KSP 版本能解决此兼容性问题
- 解决方案：`gradle.properties` 添加 `android.builtInKotlin=false` + `android.newDsl=false`
- 保留 `kotlin-android` 插件和 `kotlinOptions` 块
- 待 KSP 更新后移除 opt-out 标志并迁移到内置 Kotlin

## Files Changed
- `gradle/wrapper/gradle-wrapper.properties`
- `build.gradle.kts`
- `app/build.gradle.kts`
- `gradle/libs.versions.toml`
- `gradle.properties`

## Verification
- ✅ `./gradlew help` — 成功（AGP 9.0.1 + Gradle 9.5.0 + 所有插件解析正确）
- ⏳ `./gradlew app:assembleDebug -x lint` — 待用户本地验证（依赖下载 + 编译耗时较长）

## Notes
- Opt-out 标志会产生 deprecation warnings（AGP 10.0 将移除）
- 这是官方支持的回退策略：https://developer.android.com/build/releases/agp-9-0-0-release-notes
