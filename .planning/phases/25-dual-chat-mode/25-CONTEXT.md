# Phase 25: 双模式聊天切换 — Context

**Phase:** 25-dual-chat-mode
**Milestone:** v3.0 双模式聊天
**Depends on:** Phase 22, Phase 24
**Requirements:** DUAL-01~DUAL-08

---

## Objective

在Android剧本详情页实现显式的**双模式聊天切换**：
- **群聊模式（现有）**：用户消息经过导演Agent（ADK Runner）处理，导演控制剧情走向、场景推进
- **自由模式（新增）**：用户消息**绕过导演**，直接通过A2A协议发给演员服务，演员自由回应

两种模式通过顶部/输入区切换按钮显式切换，后端走完全不同的处理路径。

---

## Gap Analysis

### 已具备的基础

| 组件 | 状态 | 说明 |
|------|------|------|
| A2A Actor服务 | ✅ | 每个演员独立进程+端口，支持A2A协议接收消息 |
| WS事件体系 | ✅ | 18种事件类型，`dialogue`/`actor_chime_in`可直接复用 |
| Android群聊UI | ✅ | Phase 22已完成，消息气泡、@提及、快捷芯片 |
| REST+WS架构 | ✅ | FastAPI后端，Retrofit+OkHttp前端 |

### 待实现缺口

| 缺口 | 需求 | 改造方案 |
|------|------|----------|
| 后端无自由聊天路由 | DUAL-01 | 新增 `/drama/free_chat` POST端点 |
| 后端无A2A直接调用通道 | DUAL-02 | 新建 `free_chat_service.py`，A2A Client直接调用演员 |
| Android无模式状态 | DUAL-03 | `DramaDetailUiState` 新增 `ChatMode` 枚举 |
| Android无模式切换UI | DUAL-04 | `DramaDetailScreen` 顶部添加 Tab/Chip 切换 |
| Android输入栏未区分模式 | DUAL-05 | `ChatInputBar` 根据模式改变placeholder、芯片、发送行为 |
| Android无自由模式发送方法 | DUAL-06 | `ViewModel` + `Repository` 新增 `sendFreeChatMessage` |

---

## Design Decisions

| ID | Decision | Choice | Rationale |
|----|----------|--------|-----------|
| D-25-01 | 后端自由聊天实现 | 新建 `/drama/free_chat` + `free_chat_service.py` | 与现有 `/drama/chat`（导演模式）完全解耦，避免路由内部逻辑复杂度爆炸 |
| D-25-02 | A2A调用方式 | 后端作为A2A Client调用演员服务 | 复用演员代码中已验证的 `ClientFactory` + `AgentCard` + `send_message` 模式 |
| D-25-03 | 广播策略 | 无@提及时并发调用所有在场演员 | 真正的"群聊"体验；有@提及时只发目标演员 |
| D-25-04 | 事件复用 | 复用现有 `dialogue` WS事件类型推送 | 前端无需新增气泡类型，直接兼容 |
| D-25-05 | 模式持久化 | 仅内存状态，不持久化 | 切换成本低，每次进入默认群聊模式 |
| D-25-06 | 发送行为差异 | 群聊模式→`sendChatMessage`；自由模式→`sendFreeChatMessage` | ViewModel根据模式选择不同Repository方法 |
| D-25-07 | Plan数量 | 1 Plan | 改造量中等，9个文件，1个Plan可完成 |

---

## Files to Modify

### Backend (3 修改 + 1 新建)

1. `app/api/models.py` — 新增 `FreeChatRequest` 模型
2. `app/api/routers/commands.py` — 新增 `/drama/free_chat` 路由
3. `app/api/routers/commands.py` — import `FreeChatRequest` + 路由注册
4. `app/free_chat_service.py` — **新建** A2A直接调用封装

### Android (5 修改)

1. `data/remote/dto/ChatRequestDto.kt` — 新增 `FreeChatRequestDto`
2. `data/remote/api/DramaApiService.kt` — 新增 `freeChatMessage` 接口
3. `domain/repository/DramaRepository.kt` — 新增 `sendFreeChatMessage` 接口
4. `data/repository/DramaRepositoryImpl.kt` — 实现 `sendFreeChatMessage`
5. `ui/screens/dramadetail/DramaDetailUiState` — 新增 `ChatMode` + `chatMode` 字段
6. `ui/screens/dramadetail/DramaDetailViewModel.kt` — 模式切换 + 自由模式发送逻辑
7. `ui/screens/dramadetail/components/ChatInputBar.kt` — 模式感知动态UI
8. `ui/screens/dramadetail/DramaDetailScreen.kt` — 模式切换控件

**Total: 9个文件修改 + 1个新建**

---

## Success Criteria

1. Android聊天界面顶部/输入区有显眼的模式切换控件（"剧情推进" / "自由聊天"）
2. 剧情推进模式下，消息走导演Agent，支持场景推进、剧情控制
3. 自由模式下，消息直接通过A2A发给演员，演员自由回应，无导演干预
4. 自由模式支持 `@提及`，只发给指定演员；无提及时广播给所有在场演员
5. 两种模式的消息在同一个会话中混排显示
6. 模式切换时，输入框placeholder、快捷芯片、发送行为同步变化
7. 后端 `/drama/free_chat` 能正确返回演员回应，并通过WS推送 `dialogue` 事件

---

## Key References

- `app/actors/actor_*.py` — A2A Client调用参考（`call_actor`工具实现）
- `app/actor_service.py` — `_get_actor_port` / `get_actor_card` 获取演员地址
- `app/api/routers/commands.py` — 现有 `/drama/chat` 路由参考
- `android/.../DramaDetailViewModel.kt` — `sendChatMessage` / `sendCommand` 发送逻辑
- `android/.../ChatInputBar.kt` — 输入栏动态UI参考
