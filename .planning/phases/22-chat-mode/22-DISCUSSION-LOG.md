# Phase 22: 群聊模式改造 — Discussion Log

**Date:** 2026-04-26
**Status:** Discussion Complete → Ready for Planning

---

## 1. 重大发现：Phase 22 已完成 ~60%

ROADMAP 原文将 Phase 22 描述为"从导演指令模式改造为群聊模式"。经代码审查发现，Phase 17-18 已提前实现了大部分核心功能。

### 需求覆盖现状

| 需求 | 描述 | 实际状态 | 证据 |
|------|------|---------|------|
| CHAT-01 | 用户消息右对齐气泡 | ✅ 已实现 | `SceneBubble.UserMessage` + `SceneBubbleList` 右对齐渲染 |
| CHAT-02 | 删斜杠命令体系，@触发提及 | ❌ 未完成 | `ChatInputBar` 仍有 12 个斜杠命令下拉 |
| CHAT-03 | @提及选择器 | ✅ 已实现 | `ChatInputBar` — `MentionChip` + `@` 解析 |
| CHAT-04 | @→/speak, 不@→/action | ✅ 已实现 | `POST /drama/chat` + `sendChatMessage()` |
| CHAT-05 | 保留 /next /end 快捷按钮 | ❌ 未完成 | 当前有 12 个命令，无芯片按钮 |
| CHAT-06 | 后端 `/drama/chat` | ✅ 已实现 | `commands.py` — `ChatRequest(message, mention?)` |
| CHAT-07 | 角色主动发言 | ⚠️ 部分实现 | `actor_chime_in` 工具 + WS 事件已有，但由 Director 驱动非角色自触发 |
| CHAT-08 | SceneBubble UserMessage | ✅ 已实现 | `SceneBubble.UserMessage` + `DetectActorInteractionUseCase` |

**结论：** 6/8 已完成，2 需补全，1 需改善。

---

## 2. 待改造项详细分析

### 2.1 斜杠命令体系清理 (CHAT-02)

**当前状态：** `ChatInputBar.kt` 定义了 12 个 `SLASH_COMMANDS`，输入 `/` 弹出下拉菜单。

**改造方案：**
- 删除 `SLASH_COMMANDS` 列表中 `/action`, `/speak`, `/steer`, `/auto`, `/storm`, `/cast` 6 个命令
- 保留 `/next`, `/end`, `/save`, `/load`, `/list`, `/delete` — 这些是功能性命令，无聊天等价物
- 斜杠命令下拉菜单继续存在但只展示 6 个保留命令
- `/next` 和 `/end` 额外在输入框下方显示为快捷芯片（CHAT-05）

**理由：** 不完全删除斜杠命令能力——高级用户和 save/load 等功能仍需要。只移除有聊天等价物的命令。

### 2.2 快捷芯片按钮 (CHAT-05)

**当前状态：** 输入框上方仅有 `MentionChip` 行（@角色名），无快捷操作按钮。

**改造方案：**
- 在 `MentionChip` 行后面添加两个快捷芯片：`» 下一场`（/next）和 `🏁 落幕`（/end）
- 芯片样式与 `MentionChip` 一致，使用 `TertiaryContainer` 色区分
- 点击芯片直接调用 `onCommand("/next")` 或 `onCommand("/end")`

**理由：** /next 和 /end 是最高频操作，需要比输入框更醒目的入口。

### 2.3 后端 ChatRequest 缺少发送者信息

**当前状态：** `POST /drama/chat` 的 `ChatRequest(message, mention?)` 不携带用户身份信息。后端路由 `/action {message}` 时，Director Agent 不知道"谁"在说话——对 A2A Actor 来说，所有消息来自无名的"用户"。

**改造方案：**
- `ChatRequest` 添加 `sender_name: str = "导演"` 字段
- 后端路由逻辑：`/action [{sender_name}] {message}` — 在消息前标注发送者
- Android `ChatRequestDto` 添加 `sender_name: String = "导演"` 字段
- `DramaRepositoryImpl.sendChatMessageAsBubbles()` 传入 `protagonistName` 作为 `sender_name`

**理由：** 让 Actor 知道"导演"或"主角"在说话，A2A prompt 更自然。默认 "导演" 保持向后兼容。

### 2.4 旧 CommandInputBar 组件残留

**当前状态：** `CommandInputBar.kt`（168行）是旧版命令式输入组件，不被任何 Screen 使用。

**改造方案：** 删除 `CommandInputBar.kt`

### 2.5 actor_chime_in "主动发言" (CHAT-07)

**当前状态：** `actor_chime_in()` 是一个工具函数，由 Director Agent 在每次对白后主动调用。Actor A2A 是无状态 HTTP 服务，没有定时器或事件循环，无法"主动发起"。

**改造方案：** 保持当前架构不变。Director Agent 在每次 `actor_speak` 后自动调用 `actor_chime_in()` 是正确设计。但改善 Director 的 system prompt，让插话更频繁更自然。

**理由：** A2A 架构决定了"主动"只能由 Director 触发。改变这一点需要引入 Actor 定时器/消息队列，属于架构级变更，超出 Phase 22 范围。

---

## 3. 文件修改范围

### Android (4 文件修改 + 1 文件删除)

| 文件 | 改动 |
|------|------|
| `ChatInputBar.kt` | 删除 6 个斜杠命令，添加快捷芯片行（/next, /end） |
| `DramaDetailViewModel.kt` | `sendCommand` 清理废弃命令路由（保持兼容但不推荐） |
| `ChatRequestDto.kt` | 添加 `sender_name: String = "导演"` |
| `DramaRepositoryImpl.kt` | `sendChatMessageAsBubbles` 传入 `sender_name` |
| `CommandInputBar.kt` | **删除** |

### 后端 (2 文件修改)

| 文件 | 改动 |
|------|------|
| `app/api/models.py` | `ChatRequest` 添加 `sender_name: str = "导演"` |
| `app/api/routers/commands.py` | `/drama/chat` 路由注入 sender_name 到命令 |

**总计：7 文件（4 修改 + 1 删除 Android，2 修改后端）**

---

## 4. 设计决策汇总

| # | 决策 | 选项 | 结论 | 理由 |
|---|------|------|------|------|
| D-22-01 | 斜杠命令保留策略 | 全删 / 保留全部 / 保留功能性 | **保留功能性命令**（/next, /end, /save, /load, /list, /delete） | save/load 等无聊天等价物，高级用户需要命令入口 |
| D-22-02 | 快捷芯片位置 | 输入框内 / 输入框下方 / 独立行 | **输入框下方芯片行**（与 MentionChip 同级） | 醒目但不占输入空间，与 @芯片视觉统一 |
| D-22-03 | ChatRequest sender | 不加 / 添加 | **添加 `sender_name: str = "导演"`** | 让 Actor 知道"谁"在说话，A2A prompt 更自然 |
| D-22-04 | CommandInputBar | 保留 / 删除 | **删除** | 死代码，不被任何 Screen 引用 |
| D-22-05 | actor_chime_in 主动化 | 改架构 / 保持现状 | **保持现状** | A2A 无状态架构，Director 触发是正确设计 |
| D-22-06 | Plan 数量 | 2 Plans / 1 Plan | **1 Plan** | 改造量小（7文件），1 Plan 即可覆盖 |

---

## 5. Success Criteria (修订)

基于代码审查事实，修订 ROADMAP 中的 Success Criteria：

1. ~~用户在输入框发消息，显示为右对齐用户气泡~~ → **已实现，验证通过即可**
2. ~~输入 @ 弹出角色选择器~~ → **已实现，验证通过即可**
3. ~~@角色 发送消息 → 路由到 /speak~~ → **已实现，验证通过即可**
4. ~~不 @ 发送消息 → 路由到 /action~~ → **已实现，验证通过即可**
5. `/next` `/end` 作为底部快捷芯片按钮可用（新增）
6. ~~角色可主动发言~~ → `actor_chime_in` WS 事件正确渲染为 `ActorInteraction` 气泡（已实现）
7. 斜杠命令下拉仅展示功能性命令（/next, /end, /save, /load, /list, /delete）
8. 后端 `ChatRequest` 包含 `sender_name`，`/drama/chat` 路由注入发送者信息
9. 旧 `CommandInputBar.kt` 已删除

---

*造化宗师审视完毕。删繁就简，7 文件收工，至臻之境。*
