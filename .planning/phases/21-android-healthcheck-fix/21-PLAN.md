# Phase 21 Plan: Android Healthcheck Fix

## Goal
基于 r8-analyzer + edge-to-edge skills 体检结果，修复 ProGuard 过度 keep 规则和 Edge-to-Edge inset 处理问题。

## Task Breakdown

### Task 1: ProGuard 规则优化 (R8-01)
**File:** `android/app/proguard-rules.pro`

- 移除官方库自带 consumer keep rules 的冗余规则：
  - `kotlinx.serialization.**` (库自带)
  - `androidx.compose.**` (库自带)
  - `dagger.hilt.**` / `javax.inject.**` (库自带)
  - `com.drama.app.di.**` (Hilt 自动生成代码有自己的 keep 机制)
  - `com.drama.app.data.remote.interceptor.**` (Hilt 实例化，类名会被保留)
  - `kotlinx.coroutines.*` keepnames (Coroutines 1.7.0+ 自带)
- 保留：DTO 字段、API 接口、SceneBubble 密封类、Application、Hilt FragmentContextWrapper、OkHttp dontwarn

### Task 2: DramaListScreen edge-to-edge (E2E-01)
**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramalist/DramaListScreen.kt`

- 问题：`Scaffold { innerPadding -> Box(Modifier.padding(innerPadding)) { LazyColumn(...) } }`
- 修复：移除外层 `Box.padding(innerPadding)`，将 `innerPadding` 合并到 `LazyColumn.contentPadding`
- 效果：列表内容可在 system bars 后面滚动

### Task 3: DramaDetailScreen edge-to-edge (E2E-02)
**File:** `android/app/src/main/java/com/drama/app/ui/screens/dramadetail/DramaDetailScreen.kt`

- 问题：`navigationBars` inset 未被处理，键盘收起时底部内容与手势导航条可能重叠
- 修复：Column modifier 链添加 `.windowInsetsPadding(WindowInsets.navigationBars)`
- 新增 import: `androidx.compose.foundation.layout.windowInsetsPadding`

### Task 4: Theme.kt 清理 (E2E-03)
**File:** `android/app/src/main/java/com/drama/app/ui/theme/Theme.kt`

- 问题：`ComponentActivity.enableEdgeToEdge()` 已自动处理状态栏颜色与图标对比度，Theme.kt 中的 `SideEffect` + `WindowCompat` 逻辑冗余
- 修复：移除整个 `SideEffect` 块及未使用的 import（Activity, SideEffect, LocalContext, LocalView, WindowCompat, Build）

## Verification
- `./gradlew build` 通过
- ProGuard 规则数量从 ~58 行减少到 ~35 行
- Edge-to-edge 行为：列表在 system bars 后可滚动，键盘不遮挡输入

## Notes
- 未修改 SceneBubbleList.kt 内部代码（其 contentPadding 设计间距保持不变，由 DramaDetailScreen 外层 Column 统一处理 nav bar padding）
- 保留 `consumeWindowInsets(WindowInsets.statusBars)` 以避免子组件重复处理 status bar insets
