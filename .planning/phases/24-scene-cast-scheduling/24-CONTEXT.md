# Phase 24: 场景级演员调度 — Context

## Problem Statement

当前系统中，每场戏（Scene）创建后，**所有**演员都参与其中。导演无法控制"当前场景谁上场、谁待机"。这导致：

1. **后端**：`next_scene()` 返回所有演员列表，`actor_speak_batch()` 默认调用所有 AI 演员，无"上场/待机"区分
2. **导演缺乏调度能力**：无法像真实舞台导演那样为每场戏选角
3. **Android 客户端**：演员面板展示所有演员，无在场/待机视觉区分
4. **资源浪费**：所有演员每次都参与 A2A 调用，即使某些角色本场无关

## Current Architecture

### 后端 (Python)

- `state["actors"]`: Dict[str, dict] — 所有演员信息，无场景级别区分
- `next_scene()`: 推进场景，返回 `actors_available = list(state["actors"].keys())` — 全部演员
- `actor_speak_batch()`: 遍历传入的 `actors` 列表调用 A2A — 不检查是否"上场"
- `director_narrate()`: 旁白，返回建议发言演员列表，但不限制范围
- `create_actor()`: 创建演员时设置 A2A 服务，无"待机"状态

### Android 客户端 (Kotlin)

- `ActorInfo`: data class with `name/role/personality/emotions/isA2ARunning/...` — 无 `onStage` 字段
- `ActorDrawerContent`: 演员面板，所有演员平等展示，无在场/待机区分
- `DramaDetailUiState.actors: List<ActorInfo>` — 扁平列表
- WS 事件处理: `actor_status` 事件更新演员信息，无上下场事件

## Proposed Solution: scene_cast 机制

### 核心概念

引入 **scene_cast**（场景卡司）机制：
- 每场戏有自己的"上场演员"列表
- 不在 scene_cast 中的演员处于"待机"状态
- 导演可手动调整上场演员名单

### 后端变更

1. **State 新增字段**: `state["scene_cast"]` = List[str] — 当前场景上场演员名
2. **next_scene() 改造**: 接受可选的 `cast` 参数，默认 = 所有 AI 演员
3. **actor_speak_batch() 改造**: 只调用 `scene_cast` 中的演员
4. **新增 set_scene_cast() 工具**: 导演手动调整上场演员
5. **新增 cast_change WS 事件**: 上下场变更推送

### Android 客户端变更

1. **ActorInfo 扩展**: 新增 `onStage: Boolean` 字段
2. **演员面板改造**: 在场演员高亮，待机演员灰显
3. **导演选角交互**: 支持手动切换演员上下场
4. **cast_change 事件处理**: 实时更新演员状态

## Dependencies

- Phase 22 (群聊模式): ChatInputBar 的 @角色 选择器
- Phase 23 (Android 技术债务治理): VM 拆分 + WS 生命周期

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| scene_cast 为空导致无人发言 | HIGH | 默认值 = 所有 AI 演员，set_scene_cast 校验非空 |
| 向后兼容：旧存档无 scene_cast 字段 | MEDIUM | 迁移逻辑：缺失时默认 = 所有 AI 演员名 |
| A2A 服务仍运行但演员待机 | LOW | 待机演员 A2A 保持运行，仅不参与本场景对话 |
| Android UI 复杂度增加 | MEDIUM | 复用现有演员面板，增加状态区分 |

## Requirements Mapping

- **CAST-01**: 后端 scene_cast state 字段与迁移
- **CAST-02**: set_scene_cast 导演工具
- **CAST-03**: next_scene + actor_speak_batch 调度改造
- **CAST-04**: cast_change WS 事件
- **CAST-05**: Android ActorInfo.onStage + 演员面板 UI
- **CAST-06**: Android 导演手动选角交互
