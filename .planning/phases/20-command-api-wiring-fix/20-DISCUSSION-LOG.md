# Phase 20: Command & API Wiring Fix — Discussion Log

**Phase:** 20-command-api-wiring-fix
**Mode:** Discuss (造化宗师·追求完美)
**Date:** 2026-04-26

---

## 审视：此 Phase 之本质

### Phase 目标
修复 isProcessing 永不重置导致命令输入栏永久禁用的 CRITICAL bug，补全 /steer /auto /storm 三个 REST 端点的 Android 接线。

### Gap Closure 范围
- **CRITICAL Gap 2**: isProcessing Never Resets → 输入栏永久禁用
- **HIGH Gap 3**: 4 API Endpoints Unwired → steer/auto/storm 命令误路由到 /action

---

## 剖析：问题之本源

### 问题 1: isProcessing/isTyping 永久锁定 — CRITICAL

**表象**: 命令输入栏永久禁用
**本质**: `ChatInputBar` 使用 `isLocked = isProcessing || isTyping`，任一为 true 即锁死

**根因链**:
1. `sendCommand()` 设置 `isProcessing = true` + `isTyping = true`
2. WS 连接路径：`isProcessing` 在 API 成功后立即重置 ✅，但 `isTyping` 依赖 WS 事件到达才重置
3. **如果 WS 事件丢失/延迟/超时** → `isTyping` 永远为 true → 输入栏永久禁用

**造化宗师之质问**:
- 此设计，可容忍否？**不可！** 任何网络波动都可能导致用户永久卡死
- 安全超时，是否必要？**必要！** 防御性编程是工匠精神之基
- 60秒超时，合理否？需审视 LLM 最长响应时间

**已知 WS 事件重置 isTyping 的路径**:
- narration (非空) → isTyping = false
- dialogue (非空) → isTyping = false
- error → isTyping = false
- scene_start → isTyping = false
- save_confirm / load_confirm → isTyping = false

**关键洞察**: 对 `/steer`、`/auto`、`/storm` 命令，后端返回的 WS 事件序列可能不同于 `/next` 和 `/action`。特别是 `/auto` 可能推进多场，事件流更长，更易超时。

### 问题 2: CommandType 缺失 STEER/AUTO/STORM — HIGH

**表象**: /steer /auto /storm 输入被路由到 /action
**本质**: 枚举不完整，导致命令类型降级为 FREE_TEXT

**接线链分析** (从底向上):
```
Backend endpoints  ✅  /drama/steer, /drama/auto, /drama/storm 已实现
Backend models     ✅  SteerRequest, AutoRequest, StormRequest 已定义
ApiService         ✅  steerDrama(), autoAdvance(), triggerStorm() 已声明
RequestDtos        ✅  SteerRequestDto, AutoRequestDto, StormRequestDto 已存在
Repository 接口    ❌  无 steerDrama/autoAdvanceDrama/stormDrama 方法
RepositoryImpl     ❌  无实现
CommandType 枚举   ❌  无 STEER/AUTO/STORM
ViewModel 路由     ❌  sendCommand() 无对应 when 分支
ChatInputBar       ❌  SLASH_COMMANDS 无 /steer /auto /storm
```

**造化宗师之洞察**: 这不是"4个端点未接线"，而是**3层接线缺失** — 枚举→路由→仓库。后端和 API 层早已就绪，差距全在中间层。

### 问题 3: ChatInputBar 缺少 /end 和 /speak — 额外发现

SLASH_COMMANDS 列表缺少 `/end` 和 `/speak`，这两个命令已有 CommandType 枚举值和正确的 ViewModel 路由，只是未暴露给用户发现。属于 UX 缺陷，非 CRITICAL 但应一并修复。

---

## 删减：范围精炼

### IN SCOPE (Phase 20 必须)
1. ✅ CommandType 添加 STEER/AUTO/STORM
2. ✅ DramaRepository + Impl 添加 3 个方法
3. ✅ ViewModel sendCommand() 添加 STEER/AUTO/STORM 路由
4. ✅ isTyping 安全超时机制（60s safety timeout）
5. ✅ ChatInputBar SLASH_COMMANDS 添加 /steer /auto /storm
6. ✅ 端到端验证：所有 7 种命令类型可执行

### IN SCOPE (顺手修复，零额外风险)
7. ✅ ChatInputBar SLASH_COMMANDS 添加 /end /speak（已有枚举+路由，仅缺发现入口）

### OUT OF SCOPE (留待后续)
- ❌ /start /quit /status /export 的 CommandType 枚举 — 这些命令有独立的 UI 入口，不适合命令输入栏
- ❌ isProcessing 的 CancellationException 处理 — runCatching 已包裹，onFailure 已处理
- ❌ 演员主动插话 (actor_chime_in) — Phase 22 群聊模式范畴
- ❌ Export 功能补全 — Phase 21 范畴

---

## 打磨：实现决策

### D-20-01: isTyping 安全超时策略

**选择**: 60 秒安全超时 + 超时后显示错误气泡

**理由**:
- LLM 响应通常 10-30 秒，60 秒留有充分余量
- `/auto` 推进多场可能 30-60 秒，60 秒安全线合理
- 超时后重置 isTyping + isProcessing + 显示 "[超时] AI 响应超时，请重试"
- 不用更短的超时，避免误杀正常的长响应

**实现**:
```kotlin
// sendCommand() 中设置 isTyping = true 后启动 safety job
val safetyJob = viewModelScope.launch {
    delay(60_000)
    if (_uiState.value.isTyping || _uiState.value.isProcessing) {
        _uiState.update { it.copy(isTyping = false, isProcessing = false) }
        addErrorBubble("[超时] AI 响应超时，请重试")
    }
}
// 在 WS 事件处理中 isTyping = false 时取消 safetyJob
```

### D-20-02: CommandType.STEER needsArgument = true

**选择**: `STEER("/steer", true)` — 方向参数是必需的

**理由**: /steer 无方向无意义，必须有参数（如 "/steer 增加悬疑感"）

### D-20-03: CommandType.AUTO needsArgument = true

**选择**: `AUTO("/auto", true)` — 有默认值但仍标记 needsArgument

**理由**: 虽然默认 3 场，但 UX 上应引导用户输入数字。`needsArgument = true` 影响的是命令解析行为（是否提取参数），不影响默认值逻辑。

### D-20-04: CommandType.STORM needsArgument = false

**选择**: `STORM("/storm", false)` — focus 参数可选

**理由**: /storm 无参数时使用默认焦点，有参数时聚焦特定方向。needsArgument = false 允许无参数执行。

### D-20-05: ViewModel 中 STEER/AUTO/STORM 的 isActionCommand 和 isPlotChanging

**选择**: 全部纳入 isActionCommand 和 isPlotChanging

**理由**:
- 这三个命令都会改变剧情走向，属于 plot-changing
- 用户应该看到自己发送的命令气泡，属于 action command

### D-20-06: ChatInputBar /end 和 /speak 的添加

**选择**: 一并添加，最小改动

**理由**: CommandType 枚举和 ViewModel 路由已完整，仅缺 SLASH_COMMANDS 发现入口。零风险。

---

## 验证：成功标准对照

| # | ROADMAP 成功标准 | 实现方案 | 验证方式 |
|---|-----------------|---------|---------|
| 1 | DramaDetailViewModel.sendCommand() 成功路径重置 isProcessing = false | 已有 + 添加 60s safety timeout | 代码审查 + 手动测试 |
| 2 | CommandType 枚举添加 STEER/AUTO/STORM | 新增 3 个枚举值 | 编译验证 |
| 3 | DramaRepository 添加 steerDrama()/autoAdvanceDrama()/stormDrama() | 接口 + 实现 + 委托 ApiService | 编译验证 |
| 4 | 命令端到端流程：/next→/action→/steer→/auto→/storm→/speak→/end 全部可执行 | ViewModel when 分支路由 | 手动测试 |
| 5 | 成功发送命令后输入栏立即可用，无永久禁用 | isProcessing 重置 + isTyping safety timeout | 手动测试 |

---

## 实现文件清单

| # | 文件 | 改动类型 | 改动量 |
|---|------|---------|-------|
| 1 | `CommandType.kt` | 新增 3 枚举值 | ~3 行 |
| 2 | `DramaRepository.kt` | 新增 3 接口方法 | ~3 行 |
| 3 | `DramaRepositoryImpl.kt` | 新增 3 实现 + import | ~10 行 |
| 4 | `DramaDetailViewModel.kt` | sendCommand() 添加 when 分支 + safety timeout | ~40 行 |
| 5 | `ChatInputBar.kt` | SLASH_COMMANDS 添加 5 条目 | ~5 行 |

**总改动量**: ~61 行新增代码，0 个新文件，5 个文件修改

**不改的文件**: ApiService (已就绪)、RequestDtos (已就绪)、Backend (已就绪)

---

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| isTyping safety timeout 过短导致误杀正常响应 | LOW | 60 秒远超正常 LLM 响应时间 |
| STEER/AUTO/STORM 命令参数解析边界情况 | LOW | removePrefix + trim + toIntOrNull 处理所有边界 |
| sendCommand() when 分支遗漏 | LOW | 每个枚举值都有明确分支，编译期检查 |

---

*造化宗师审视完毕。此 Phase 之本质：3 层接线 + 1 个安全网。改动精准，无冗余。*

*讨论完成: 2026-04-26*
