# Phase 21: Android Healthcheck Fix

## Goal
基于 Android skills (r8-analyzer, edge-to-edge) 体检结果，修复 ProGuard 过度 keep 规则、Edge-to-Edge inset 处理问题，以及 Tink missing classes 导致的 R8 编译失败。

## Status
- ✅ Debug build 通过
- ⏳ Release build / R8 验证待用户确认

## Changes

### 1. ProGuard 规则优化 (`android/app/proguard-rules.pro`)
- **移除** 以下冗余规则（库自带 consumer keep rules）：
  - `androidx.compose.**`
  - `com.drama.app.di.**`
  - `com.drama.app.data.remote.interceptor.**`
  - `kotlinx.coroutines.*` keepnames
- **保留** 以下规则（运行时反射/代码生成必需）：
  - `kotlinx.serialization.**`（序列化内部反射）
  - `dagger.hilt.**` / `javax.inject.**`（Hilt 代码生成）
  - DTO 字段、API 接口、SceneBubble 密封类、Application
- **新增** Tink / security-crypto 的 `dontwarn`（修复预先存在的 R8 missing classes 错误）

### 2. DramaListScreen edge-to-edge (`DramaListScreen.kt`)
- 移除外层 `Box.padding(innerPadding)`
- `LazyColumn.contentPadding` 合并 `innerPadding.calculateTopPadding()` / `calculateBottomPadding()`
- 效果：列表内容现在可以在 system bars 后面滚动

### 3. DramaDetailScreen edge-to-edge (`DramaDetailScreen.kt`)
- Column modifier 链新增 `.windowInsetsPadding(WindowInsets.navigationBars)`
- 效果：键盘收起时底部内容（ChatInputBar）不再与手势导航条重叠

### 4. Theme.kt 清理 (`Theme.kt`)
- 移除冗余的 `SideEffect` + `WindowCompat` 逻辑（`enableEdgeToEdge()` 已自动处理）
- 清理未使用的 import

## Verification
```bash
# Debug 构建（已验证通过）
./gradlew app:assembleDebug -x lint

# Release 构建（待验证）
./gradlew app:assembleRelease -x lint
```
