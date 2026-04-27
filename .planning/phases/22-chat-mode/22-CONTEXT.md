# Phase 22: 群聊模式改造 — Context

**Phase:** 22-chat-mode
**Milestone:** v3.0 群聊模式
**Depends on:** Phase 17, Phase 18
**Requirements:** CHAT-01~CHAT-08

---

## Objective

将 Android 剧本详情页从导演指令模式打磨为群聊模式。Phase 17-18 已提前实现了 6/8 核心需求，本 Phase 补全剩余缺口：清理斜杠命令体系、添加快捷芯片、后端 ChatRequest 携带发送者信息、删除旧组件。

---

## Gap Analysis

### 已实现需求（6/8，验证通过即可）

| 需求 | 实现位置 | 说明 |
|------|---------|------|
| CHAT-01: 用户消息右对齐 | `SceneBubble.UserMessage` + `SceneBubbleList` | 右对齐气泡 + 蓝色背景 |
| CHAT-03: @提及选择器 | `ChatInputBar` — `MentionChip` + `@` 解析 | 输入 @角色名 触发提及 |
| CHAT-04: @→/speak, 不@→/action | `POST /drama/chat` + `sendChatMessage()` | 后端路由 + ViewModel 双路径 |
| CHAT-06: 后端 /drama/chat | `commands.py` — `ChatRequest(message, mention?)` | mention→/speak, else→/action |
| CHAT-07: 角色插话 | `actor_chime_in` 工具 + WS 事件 + `ActorInteraction` 气泡 | Director 触发 + WS 推送 |
| CHAT-08: UserMessage 气泡 | `SceneBubble.UserMessage` + `DetectActorInteractionUseCase` | 右对齐 + 互动检测 |

### 待补全需求（2/8 + 2 打磨项）

| 缺口 | 需求 | 当前问题 | 改造方案 |
|------|------|----------|----------|
| 斜杠命令未清理 | CHAT-02 | `ChatInputBar` 有 12 个斜杠命令下拉 | 删除 6 个有聊天等价物的命令，保留功能性命令 |
| 快捷芯片缺失 | CHAT-05 | 无 /next /end 快捷入口 | 添加芯片行（与 MentionChip 同级） |
| ChatRequest 无发送者 | — | A2A Actor 不知道"谁"在说话 | 添加 `sender_name` 字段 |
| 旧组件残留 | — | `CommandInputBar.kt` 不被使用 | 删除 |

---

## Design Decisions

| ID | Decision | Choice | Rationale |
|----|----------|--------|-----------|
| D-22-01 | 斜杠命令保留策略 | 保留功能性命令 | save/load 等无聊天等价物，高级用户需要 |
| D-22-02 | 快捷芯片位置 | 输入框下方芯片行 | 醒目但不占输入空间 |
| D-22-03 | ChatRequest sender | 添加 `sender_name: str = "导演"` | A2A prompt 更自然 |
| D-22-04 | CommandInputBar | 删除 | 死代码 |
| D-22-05 | actor_chime_in 主动化 | 保持现状 | A2A 无状态架构 |
| D-22-06 | Plan 数量 | 1 Plan | 改造量小，7 文件 |

---

## Files to Modify

### Android (4 修改 + 1 删除)

1. `ChatInputBar.kt` — 删除 6 个斜杠命令，添加快捷芯片
2. `ChatRequestDto.kt` — 添加 `sender_name: String = "导演"`
3. `DramaRepositoryImpl.kt` — `sendChatMessageAsBubbles` 传入 sender_name
4. `DramaDetailViewModel.kt` — sendCommand 清理（次要）
5. `CommandInputBar.kt` — **删除**

### Backend (2 修改)

1. `app/api/models.py` — `ChatRequest` 添加 `sender_name: str = "导演"`
2. `app/api/routers/commands.py` — `/drama/chat` 路由注入 sender_name

**Total: 7 files**

---

## Success Criteria (Revised)

1. ChatInputBar 斜杠命令下拉仅展示功能性命令（/next, /end, /save, /load, /list, /delete）
2. 输入框下方有 /next 和 /end 快捷芯片按钮
3. 后端 ChatRequest 包含 `sender_name`，`/drama/chat` 路由注入发送者信息到命令
4. ChatRequestDto 包含 `sender_name` 字段
5. CommandInputBar.kt 已删除
6. 用户消息右对齐气泡、@提及选择器、/drama/chat 路由正常工作（回归验证）

---

## Key References

- Discussion: `.planning/phases/22-chat-mode/22-DISCUSSION-LOG.md`
- ChatInputBar: `android/.../dramadetail/components/ChatInputBar.kt` (SLASH_COMMANDS, MentionChip)
- CommandInputBar: `android/.../dramadetail/components/CommandInputBar.kt` (to delete)
- ChatRequestDto: `android/.../dto/ChatRequestDto.kt`
- DramaRepositoryImpl: `android/.../repository/DramaRepositoryImpl.kt` (sendChatMessageAsBubbles)
- Backend ChatRequest: `app/api/models.py`
- Backend /drama/chat: `app/api/routers/commands.py`
- SceneBubble: `android/.../domain/model/SceneBubble.kt` (UserMessage, ActorInteraction)
- ViewModel: `android/.../dramadetail/DramaDetailViewModel.kt` (sendChatMessage, handleWsEvent)
