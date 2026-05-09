# Phase 24-02 Summary: Android ActorInfo 扩展 + cast_change WS 事件 + 演员面板 UI 改造

**Plan:** 24-02
**Phase:** 24 (场景级演员调度)
**Status:** COMPLETE
**Date:** 2026-04-29

## Deliverables

### Task 1: ActorInfo 新增 onStage 字段
- `ActorInfo.kt` 添加 `onStage: Boolean = true` (默认 true，向后兼容)

### Task 2: CastStatusResponseDto 扩展 scene_cast 字段
- `CastStatusResponseDto.kt` 添加 `scene_cast: List<String>? = null`
- `null` = 全员上场（向后兼容旧后端）

### Task 3: mergeCastWithStatus 填充 onStage
- `DramaRepositoryImpl.kt` `mergeCastWithStatus()` 新增 `sceneCast` 参数
- 根据 `scene_cast` 列表计算每个演员的 `onStage` 状态
- `getMergedCast()` 中将 `status.scene_cast` 传入 `mergeCastWithStatus`

### Task 4: DramaDetailViewModel 处理 cast_change 事件
- `handleWsEvent()` 添加 `"cast_change"` 分支
- 解析 `scene_cast` JSON 数组，增量更新演员 `onStage` 状态
- `scene_cast` 为 null 时，全员设为 `onStage = true`
- 不调用 `preloadActorPanel()`，避免全量刷新

### Task 5: 演员面板 UI 改造 — 在场/待机分组 + toggle
- `ActorDrawerContent.kt`:
  - 新增 `onToggleCast` 回调参数
  - 演员列表分为 "在场" 和 "待机" 两组
  - 组间用分割线 + 小标题分隔
  - 新增 `ActorListGrouped()` Composable 替代原来的 `ActorListWithStagger()`
- `ActorCard.kt`:
  - 新增 `onToggleCast` 回调参数
  - 右侧添加 `Switch` toggle 开关
  - `onStage = false` 时卡片 `alpha = 0.5f`

### Task 6: 选角交互 — toggle → REST API 调用
- `DramaRepository.kt` 接口添加 `setSceneCast(cast: List<String>)`
- `DramaRepositoryImpl.kt` 实现：通过 `chatMessage` 发送 `/cast 演员1,演员2` 命令
- `DramaDetailViewModel.kt` 添加 `toggleActorOnStage(actorName: String)`:
  - 切换演员上下场状态
  - 校验至少一人在场
  - 调用 `dramaRepository.setSceneCast()`
  - 失败时回滚并显示 Snackbar
- `DramaDetailScreen.kt` 中 `ActorDrawerContent` 传入 `onToggleCast = viewModel::toggleActorOnStage`

### Task 7: ChatInputBar @mention 芯片视觉区分
- `ChatInputBar.kt`:
  - `actors` 参数从 `List<String>` 改为 `List<ActorInfo>`
  - MentionChip 新增 `isOnStage` 参数
  - 在场演员: `secondaryContainer` 背景
  - 待机演员: `surfaceVariant` 背景 + 低透明度文字
- `DramaDetailScreen.kt` 中 `ChatInputBar` 传参改为 `actors = uiState.actors`

### 额外修复: /cast 命令后端路由
- `app/api/routers/commands.py` `chat_message()` 中添加 `/cast` 前缀检测
- 直接调用 `set_scene_cast` 工具并推送 `cast_change` WS 事件
- Android 端无需新增独立 API，复用现有 `chatMessage` 通道

## Verification

```bash
# Android 编译检查
./gradlew :app:compileDebugKotlin

# 手动验证清单
1. 创建戏剧 + 3+ 演员
2. 打开演员面板 → 观察所有演员"在场"状态
3. toggle 某演员 → 观察灰显 + WS cast_change 事件
4. 发送 /next → 观察场景推进后 scene_cast 重置
5. @待机演员 → 观察路由到 /speak
```

## Risks & Status

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| REST 调用失败导致 UI 与后端不一致 | MEDIUM | 乐观更新 + 失败回滚 + WS 事件最终一致 | ✅ DONE |
| 待机演员被 @mention 后 LLM 不知如何处理 | LOW | @mention 路由到 /speak，LLM 可通过 scene_cast 感知 | ✅ ACCEPTED |
| 演员面板分组后列表过长 | LOW | 待机组可折叠（未来优化） | ✅ ACCEPTED |
| toggle 快速点击导致重复 API 调用 | LOW | Switch 自带 debounce + isProcessing 锁 | ✅ ACCEPTED |
