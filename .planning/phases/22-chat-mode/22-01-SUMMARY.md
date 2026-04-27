# Phase 22-01 Summary: 群聊模式改造

**Phase:** 22-chat-mode
**Plan:** 01
**Status:** ✅ Complete
**Date:** 2026-04-26

---

## Objective

将 Android 剧本详情页打磨为群聊模式。Phase 17-18 已提前实现 6/8 核心需求，本 Plan 补全剩余缺口：清理斜杠命令体系、添加快捷芯片、后端 ChatRequest 接收 sender_name、删除旧组件。

---

## Changes Made (3 files modified + 1 file deleted)

### Android (1 file modified + 1 file deleted)

|| File | Change |
|------|--------|
| `ChatInputBar.kt` | 删除 6 个有聊天等价物的斜杠命令 + 添加 QuickAction/QUICK_ACTIONS + 快捷芯片行（下一场/落幕）+ placeholder 改为"发消息给角色们..." |
| `CommandInputBar.kt` | **删除** — 旧命令式输入组件，不被任何 Screen 引用 |

### Backend (2 files modified)

|| File | Change |
|------|--------|
| `app/api/models.py` | `ChatRequest` 添加 `sender_name: str = Field(default="导演")` |
| `app/api/routers/commands.py` | `/drama/chat` 路由注入 `sender_prefix` — 非"导演"时在消息前标注 `[sender_name]` |

---

## Verification Results

### Grep Acceptance Criteria (ALL PASS)

- ✅ `ChatInputBar.kt`: 不包含 `/action`, `/speak`, `/steer`, `/auto`, `/storm`, `/cast` 命令
- ✅ `ChatInputBar.kt`: 包含 `QuickAction` data class + `QUICK_ACTIONS` 列表
- ✅ `ChatInputBar.kt`: 包含 "下一场" 和 "落幕" 快捷芯片
- ✅ `ChatInputBar.kt`: placeholder 为 "发消息给角色们..."
- ✅ `ChatInputBar.kt`: 保留 `/next`, `/end` 在 SLASH_COMMANDS
- ✅ `app/api/models.py`: ChatRequest 包含 `sender_name: str = Field(default="导演")`
- ✅ `app/api/routers/commands.py`: 包含 `body.sender_name` 引用 + `sender_prefix` 逻辑
- ✅ `CommandInputBar.kt`: 已删除，无残留引用

---

## Design Decisions

|| ID | Decision | Rationale |
|----|----------|-----------|
| D-22-01 | 保留功能性斜杠命令（/next, /end, /save, /load, /list, /delete） | save/load 等无聊天等价物，高级用户需要 |
| D-22-02 | 快捷芯片在输入框下方（与 MentionChip 同级） | 醒目但不占输入空间，视觉统一 |
| D-22-03 | sender_name 默认 "导演"，非默认时注入 `[名称]` 前缀 | 向后兼容 + 让 Actor 知道谁在说话 |
| D-22-04 | 删除 CommandInputBar.kt | 死代码，不被任何 Screen 引用 |

---

## Key Code Changes

### ChatInputBar.kt — 斜杠命令清理

**Before:** 12 个命令（含 /action, /speak, /steer, /auto, /storm, /cast）

**After:** 6 个功能性命令（/next, /end, /save, /load, /list, /delete）

### ChatInputBar.kt — 快捷芯片

```
[» 下一场] [🏁 落幕]    ← 新增快捷操作芯片行（TertiaryContainer 色）
[@李明] [@苏念瑶]       ← 已有提及芯片行（SecondaryContainer 色）
[发消息给角色们... ▶]   ← 已有输入框
```

### Backend /drama/chat — sender_name 注入

**Before:** `/action 你好` → Actor 不知道谁在说话

**After:** `/action [主角]你好` → Actor 知道"主角"在说话（当 sender_name != "导演" 时注入前缀）

---

## End-to-End Flow

```
用户输入文本点发送 → onSend(text, mention) → sendChatMessage()
  → ChatRequestDto(message, mention, senderType="user", senderName="主角")
  → POST /drama/chat {message, mention, sender_name: "主角"}
  → sender_prefix = "[主角]"
  → /action [主角]你好  或  /speak 李明 [主角]你在吗
  → Runner 执行 → A2A Actor 收到含发送者标识的提示

用户点击快捷芯片 → onCommand("/next") → sendCommand("/next")
  → POST /drama/next → 推进下一场
```

---

*造化宗师审视完毕。删繁就简，3 修改 + 1 删除，群聊体验至臻。*
