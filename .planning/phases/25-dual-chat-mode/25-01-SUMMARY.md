参考https://adk.dev/skills/文档，用nuwa-skill给director-actor-drama里的导演Agent蒸馏一个著名导演的角色，并且还需要适配到Android客户端里。# Phase 25-01 Summary: 双模式聊天切换

**Phase:** 25-dual-chat-mode
**Plan:** 01
**Status:** Complete
**Date:** 2026-04-29

---

## Objective

在Android剧本详情页实现显式的**双模式聊天切换**：
- **群聊模式（DIRECTOR）**：用户消息经过导演Agent处理，导演控制剧情走向
- **自由模式（FREE_CHAT）**：用户消息绕过导演，直接通过A2A协议发给演员服务

---

## Changes Made

### Backend (3 修改 + 1 新建)

| File | Change |
|------|--------|
| `app/api/models.py` | 新增 `FreeChatRequest` Pydantic 模型（`message, mention?, sender_name`） |
| `app/api/routers/commands.py` | 新增 `POST /drama/free_chat` 路由，绕过ADK Runner直接A2A调用演员 |
| `app/free_chat_service.py` | **新建** — `broadcast_free_chat()` 封装A2A直接调用，`@提及`或广播给在场演员 |

### Android (8 修改)

| File | Change |
|------|--------|
| `data/remote/dto/ChatRequestDto.kt` | 新增 `FreeChatRequestDto` |
| `data/remote/api/DramaApiService.kt` | 新增 `freeChatMessage()` Retrofit 接口 |
| `domain/repository/DramaRepository.kt` | 新增 `sendFreeChatMessage()` + `sendFreeChatMessageAsBubbles()` |
| `data/repository/DramaRepositoryImpl.kt` | 实现上述两个接口 |
| `DramaDetailUiState.kt` | 新增 `ChatMode` 枚举 + `chatMode` 字段 |
| `DramaDetailViewModel.kt` | 新增 `toggleChatMode()` + `sendFreeChatMessage()` |
| `components/ChatInputBar.kt` | 新增 `chatMode` 参数，模式感知：placeholder变化、隐藏快捷芯片 |
| `DramaDetailScreen.kt` | 新增 `ChatModeSwitcher` 顶部切换控件，传入模式到输入栏 |

---

## Key Design Points

1. **后端完全解耦**：`/drama/free_chat` 不经过 `run_command_and_collect`，直接调用 `broadcast_free_chat()` → A2A Client → 演员服务
2. **事件复用**：自由模式的演员回应复用现有 `dialogue` WS事件类型，前端零改动兼容
3. **并发调用**：无`@提及`时，使用 `asyncio.gather()` 并发调用所有在场演员的A2A服务
4. **模式仅内存状态**：`ChatMode` 保存在 `UiState` 中，不持久化，每次进入默认群聊模式
5. **发送行为分离**：`DramaDetailScreen` 根据 `chatMode` 选择调用 `sendChatMessage` 或 `sendFreeChatMessage`

---

## Verification Results

- Python 语法检查：`app/api/models.py`, `app/api/routers/commands.py`, `app/free_chat_service.py` — PASS
- Android Linter：0 errors in modified files — PASS
- 后端 `/drama/free_chat` 路由无重复定义 — PASS

---

## End-to-End Flow

```
用户点击"自由聊天"切换 → toggleChatMode() → chatMode = FREE_CHAT
用户输入文本点发送 → onSend(text, mention) → sendFreeChatMessage()
  → FreeChatRequestDto(message, mention, senderName)
  → POST /drama/free_chat
  → broadcast_free_chat() 并发A2A调用演员
  → 演员回应 → WS推送 dialogue 事件 → Android显示对话气泡
```

---

*上将军运筹帷幄，双模式城池已筑。群聊与自由，一键切换，千军万马听令而行。*
