# Roadmap — Director-Actor-Drama 无限畅写版

## Milestones

- ✅ **v1.0 无限畅写版** — Phases 1-12 (shipped 2026-04-14)
- ✅ **v2.0 Android 移动端** — Phases 13-18 (shipped 2026-04-16)

## Phases

<details>
<summary>✅ v1.0 无限畅写版 (Phases 1-12) — SHIPPED 2026-04-14</summary>

- [x] Phase 1: Memory Foundation (3/3 plans)
- [x] Phase 2: Context Builder (2/2 plans)
- [x] Phase 3: Semantic Retrieval (2/2 plans)
- [x] Phase 4: Infinite Loop Engine (3/3 plans)
- [x] Phase 5: Mixed Autonomy Mode (3/3 plans)
- [x] Phase 6: Tension Scoring & Conflict Engine (2/2 plans)
- [x] Phase 7: Arc Tracking (2/2 plans)
- [x] Phase 8: Dynamic STORM (2/2 plans)
- [x] Phase 9: Progressive STORM (2/2 plans)
- [x] Phase 10: Coherence System (2/2 plans)
- [x] Phase 11: Timeline Tracking (2/2 plans)
- [x] Phase 12: Integration & Polish (4/4 plans)

</details>

---

## ✅ v2.0 Android 移动端 (Phases 13-18)

**Goal:** 为 director-actor-drama 添加 C/S 架构支持 — Python FastAPI 后端提供 REST + WebSocket API，Android (Kotlin/Jetpack Compose) 作为纯 UI 客户端

**Requirements:** 32 (API-01~05, WS-01~05, AUTH-01~04, STATE-01~03, APP-01~16)

### Phase 13: API Foundation

**Goal:** FastAPI 应用包裹现有 DramaRouter，14 个 REST 端点映射所有 CLI 命令，Pydantic v2 模型定义请求/响应契约，CORS + URL 版本前缀 + 全局状态迁移
**Requirements:** API-01, API-02, API-03, API-04, API-05, STATE-01, STATE-02, STATE-03
**Plans:** 4/4 plans complete
**Depends on:** —
**Success Criteria:**
1. `POST /api/v1/drama/start` 返回 drama_id + theme + status，不修改 12 个核心模块
2. 14 个 REST 端点均可独立调用并返回结构化 JSON（Pydantic 模型校验通过）
3. `_current_drama_folder` 全局变量完全迁移至 session-scoped context，CLI 兼容不破坏
4. Debounce flush-on-push：WebSocket 推送前强制写盘，内存与磁盘状态一致
5. API 同时仅支持一个活跃 drama session（单用户模式保持）

Plans:
- [x] 13-01-PLAN.md — FastAPI app skeleton + CORS + versioning + Pydantic models
- [x] 13-02-PLAN.md — REST endpoints (command-style: start/next/action/speak/steer/auto/end/storm)
- [x] 13-03-PLAN.md — REST endpoints (query-style: status/cast/save/load/list/export) + state migration
- [x] 13-04-PLAN.md — Debounce flush-on-push + single-session enforcement + integration tests

### Phase 14: WebSocket Layer

**Goal:** WebSocket 端点实时推送场景事件，EventBridge 观察 ADK Runner 事件流，100-event replay buffer 支持断线重连
**Requirements:** WS-01, WS-02, WS-03, WS-04, WS-05
**Plans:** 3/3 plans complete
**Depends on:** Phase 13
**Success Criteria:**
1. 客户端连接 `ws://host:8000/api/v1/ws` 后实时接收场景生成事件（旁白/对白/场景完成）
2. 18 种事件类型全部可推送，消息格式符合 Pydantic 模型定义
3. EventBridge 零侵入观察 ADK Runner 事件流，不修改 tool 代码
4. 客户端断线重连后获取最近 100 条事件补发，不丢失中间状态
5. 心跳机制（15s ping/pong）维持连接活跃，超时断连自动清理

Plans:
- [x] 14-01-PLAN.md — EventBridge callback hook + WS endpoint + WsEvent models + event_mapper + ConnectionManager
- [x] 14-02-PLAN.md — 18 event type emission wiring + event_callback in commands.py + flush-before-push
- [x] 14-03-PLAN.md — Replay buffer + heartbeat (15s/30s) + lifecycle management + reconnect handshake + connection limit

### Phase 15: Authentication

**Goal:** 简单 Token 认证覆盖 REST + WebSocket，局域网/单用户场景，FastAPI HTTPBearer 依赖注入
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Plans:** 2/2 plans complete
**Depends on:** Phase 13 (REST), Phase 14 (WebSocket)
**Success Criteria:**
1. 服务端首次启动生成 API Token（或从 .env 读取），无 Token 配置时认证禁用（dev 模式）
2. 所有 REST 端点要求 `Authorization: Bearer <token>` header，无效 token 返回 401
3. WebSocket 握手通过 `?token=xxx` query parameter 验证，无效 token 拒绝连接 (code 4001)
4. FastAPI HTTPBearer 依赖注入统一验证，无重复校验代码

Plans:
- [x] 15-01-PLAN.md — Token generation + HTTPBearer dependency + REST auth enforcement
- [x] 15-02-PLAN.md — WebSocket token validation + auth bypass mode + integration tests

### Phase 16: Android Foundation

**Goal:** Android 项目搭建，MVVM + Hilt + Material Design 3 主题，服务器连接配置，导航骨架
**Requirements:** APP-01, APP-13, APP-14, APP-16
**Plans:** 3/3 plans complete
**Depends on:** — (可与 Phase 13-15 并行开发)
**Success Criteria:**
1. App 启动后显示服务器 IP:port 配置界面，连接成功后进入主界面
2. MVVM 架构清晰：Repository → ViewModel → Compose UI，Hilt 管理所有依赖
3. Material Design 3 主题生效，支持 Dynamic Color (Android 12+) 和暗色模式
4. Navigation Compose 骨架包含 drama-list / drama-create / drama-detail / settings 路由

Plans:
- [x] 16-01-PLAN.md — Project setup + Hilt + Gradle dependencies + Navigation skeleton
- [x] 16-02-PLAN.md — Server connection screen + Retrofit API service + Repository layer
- [x] 16-03-PLAN.md — Material Design 3 theming + dynamic colors + dark mode

### Phase 17: Android Interaction

**Goal:** 戏剧 CRUD 交互主界面，命令输入栏，场景历史浏览，保存/加载确认
**Requirements:** APP-02, APP-03, APP-04, APP-05, APP-06, APP-12
**Plans:** 3/3 plans executed ✅
**Depends on:** Phase 16, Phase 13, Phase 14
**Success Criteria:**
1. 创建戏剧屏幕接受主题输入，触发 STORM discovery，完成后跳转主屏幕
2. 戏剧列表屏幕显示所有已保存戏剧（卡片：主题/状态/场数/更新时间），支持加载/恢复/删除
3. 主戏剧屏幕实时显示当前场景，WebSocket 推送旁白/对白即时渲染
4. 命令输入栏支持 /next /action /speak /end 快捷按钮 + 自由文本输入
5. 场景历史可滚动浏览，时间线导航查看历史场景
6. 保存/加载操作返回确认反馈（snackbar 提示）

Plans:
- [x] 17-01-PLAN.md — DramaCreateScreen + DramaListScreen + DramaItemDto/Repository + 后端 DELETE /drama/{folder}
- [x] 17-02-PLAN.md — DramaDetailScreen + WS 事件驱动气泡渲染 + 命令输入栏 + Typing 指示器
- [x] 17-03-PLAN.md — 场景历史 BottomSheet + 后端 GET /drama/scenes + 保存/加载确认

### Phase 18: Android Features

**Goal:** 演员面板，戏剧状态概览，剧本导出，Typing 指示器，富文本渲染，WebSocket 自动重连
**Requirements:** APP-07, APP-08, APP-09, APP-10, APP-11, APP-15
**Plans:** 3/3 plans complete
**Depends on:** Phase 17
**Success Criteria:**
1. 演员面板显示角色列表（卡片：名字/身份/情绪/A2A 服务状态/记忆摘要）
2. 戏剧状态概览显示当前场景、张力评分、弧线进度、时间段
3. 剧本导出为 Markdown 文件，支持 Android Share Intent 分享
4. LLM 生成期间显示 typing 指示器（脉冲动画 + "导演正在构思..."）
5. 对白渲染富文本：角色名高亮 + 情绪标签 + 头像首字母圆形标识
6. WebSocket 断线自动重连（指数退避 1s→30s），网络切换后恢复连接

Plans:
- [x] 18-01-PLAN.md — Actor panel + drama status overview (APP-07, APP-08)
- [x] 18-02-PLAN.md — Typing indicator + rich scene display + export (APP-09, APP-10, APP-11)
- [x] 18-03-PLAN.md — WebSocket auto-reconnect + network resilience + end-to-end polish (APP-15)

---

## v2.0 Gap Closure (Phases 19-21)

**Goal:** 修复审计发现的6个需求差距、3个集成断裂、2个E2E流程中断

### Phase 19: WebSocket 心跳修复

**Goal:** 修复 Android WebSocketManager 不响应服务端 ping 的 CRITICAL bug，连接每30s断连导致实时推送不可靠
**Requirements:** WS-05, APP-04, APP-15
**Gap Closure:** Closes CRITICAL Gap 1 (WS Heartbeat Pong Missing)
**Depends on:** Phase 14, Phase 18
**Plans:** 1 plan
**Success Criteria:**
1. Android WebSocketManager 收到 `{"type":"ping"}` 后立即发送 `{"type":"pong"}`
2. WS 连接持续稳定 >5 分钟无断连（无心跳超时）
3. 自动重连后 replay buffer 正确消费，无事件丢失
4. 心跳超时恢复后 DramaDetailScreen 实时渲染恢复正常

Plans:
- [x] 19-01-PLAN.md — 客户端JSON解析替换字符串匹配 + 移除自定义心跳死代码 + 服务端heartbeat处理 + 生命周期测试 ✅

### Phase 20: 命令与 API 接线修复

**Goal:** 修复 isProcessing 永不重置导致命令输入栏永久禁用的 CRITICAL bug，补全 /steer /auto /storm 三个 REST 端点的 Android 接线
**Requirements:** APP-05, API-02 (partial)
**Gap Closure:** Closes CRITICAL Gap 2 (isProcessing Never Resets) + HIGH Gap 3 (4 API Endpoints Unwired)
**Depends on:** Phase 17, Phase 18, Phase 19
**Plans:** 1/1 complete* (code verified, no formal PLAN/SUMMARY document)
**Success Criteria:**
1. DramaDetailViewModel.sendCommand() 成功路径重置 isProcessing = false ✅
2. CommandType 枚举添加 STEER/AUTO/STORM，路由到正确 API 端点 ✅
3. DramaRepository 添加 steerDrama()/autoAdvanceDrama()/stormDrama() 方法 ✅
4. 命令端到端流程：/next → /action → /steer → /auto → /storm → /speak → /end 全部可执行 ✅
5. 成功发送命令后输入栏立即可用，无永久禁用 ✅

*\* Phase 20 changes were implemented during Phase 22/23 refactoring but never formally tracked with PLAN/SUMMARY docs. Codebase audit on 2026-04-26 confirmed all success criteria met.*

### Phase 21: 事件处理与 Export 补全

**Goal:** 补全3种缺失的 WS 事件类型处理（status/actor_status/progress），完成剧本导出功能（后端返回 content + Repository + ViewModel + Share Intent UI）
**Requirements:** WS-02, APP-09
**Gap Closure:** Closes HIGH Gap (3 WS Event Types Unhandled) + APP-09 (Export Incomplete)
**Depends on:** Phase 19, Phase 20
**Plans:** 1/1 plan complete
**Success Criteria:**
1. Android ViewModel 正确处理 status/actor_status/progress 3种缺失事件（actor_created/cast_update 已在 Phase 18 处理）
2. 后端 ExportResponse 包含 content 字段，DramaRepository.exportDrama() 返回含 Markdown 内容的响应
3. DramaDetailViewModel 包含 exportDrama() action + isExporting 状态管理
4. DramaDetailScreen overflow menu 包含"导出"按钮，触发 Android Share Intent 分享

Plans:
- [x] 21-01-PLAN.md — 后端 ExportResponse 添加 content + Android 3 事件处理 + Export Repository/ViewModel/Screen 接线

---

## v2.5 技术债务治理 (Phase 23)

**Goal:** 治理Android客户端全面技术评估发现的17个问题，按P0→P1→P2/P3优先级推进

### Phase 23: Android 技术债务治理

**Goal:** 拆分巨型ViewModel、统一WS生命周期、启用代码混淆、修复安全隐患、补全测试覆盖
**Requirements:** ARCH-01~ARCH-17 (技术评估发现)
**Depends on:** Phase 19, Phase 20, Phase 21, Phase 22
**Success Criteria:**
1. DramaDetailViewModel拆分为5个子组件，单文件<400行
2. WebSocketManager连接生命周期由ConnectionLifecycleOwner统一管理，无VM间泄露
3. Release构建启用R8混淆，APK类名/方法名不可读
4. BaseUrlInterceptor替代runBlocking，切换服务器无需重启
5. 核心业务逻辑单元测试覆盖率>60%
6. usesCleartextTraffic=false + network_security_config仅放行本地开发
7. SingleSourceOfTruth统一REST/WS数据源，消除UI闪烁

Plans:
- [x] 23-01-PLAN.md — P0歼灭战：VM拆分 + WS生命周期统一 + R8混淆 ✅
- [x] 23-02-PLAN.md — P1阵地战：动态BaseUrl + 测试覆盖 + 安全加固 + 数据源统一 ✅
- [x] 23-03-PLAN.md — P2/P3扫荡战：测试补全 ✅

---

## v3.0 群聊模式 (Phase 22)

**Goal:** 将Android剧本详情页从导演指令模式改造为群聊模式：用户输入主题→创建角色→进入群聊界面→@角色对话→角色可主动发言

### Phase 22: 群聊模式改造

**Goal:** 用户消息右对齐气泡 + @提及选择器 + 输入框聊天化 + 角色主动插话
**Requirements:** CHAT-01~CHAT-08
**Depends on:** Phase 17, Phase 18
**Success Criteria:**
1. 用户在输入框发消息，显示为右对齐用户气泡 ✅
2. 输入 @ 弹出角色选择器，选择后 @角色名 插入输入框 ✅
3. @角色 发送消息 → 路由到 /speak，角色回复显示为左对齐气泡 ✅
4. 不 @ 发送消息 → 路由到 /action（群消息） ✅
5. /next /end 保留为底部快捷芯片按钮 ✅
6. 角色可主动发言（WS 推送 actor_chime_in 事件） ✅
7. 斜杠命令下拉仅展示功能性命令 ✅
8. 后端 ChatRequest 包含 sender_name ✅

Plans:
- [x] 22-01-PLAN.md — ChatInputBar清理斜杠命令+快捷芯片 + 后端sender_name注入 + 删除旧CommandInputBar ✅

---

## Dependency Graph

```
Phase 13 (API Foundation) ─────┬─── Phase 14 (WebSocket Layer) ────┬─── Phase 15 (Auth)
|                                │                                    │
|                                └────────────────────────────────────┘
                                           │
                                           ▼
Phase 16 (Android Foundation) ──── Phase 17 (Android Interaction) ──── Phase 18 (Android Features)
     (parallel with 13-15)                                                             │
                                                         ┌─────────────────────────────┘
                                                         ▼
                                                Phase 19 (WS Heartbeat Fix)
                                                         │
                                                         ▼
                                                Phase 20 (Command & API Wiring Fix)
                                                         │
                                                         ▼
                                                Phase 21 (Events & Export Completion)
```

**Parallelization opportunities:**
- Phase 13 + Phase 16 can start simultaneously (backend vs Android project setup)
- Phase 14 + Phase 15 partially parallel (WS endpoint vs auth middleware)
- Phase 17 requires both Phase 16 (Android) + Phase 13/14 (backend API) to be complete
- Phase 19-21 are strictly sequential: heartbeat fix → command wiring → event/export completion

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Memory Foundation | v1.0 | 3/3 | Complete | 2026-04-11 |
| 2. Context Builder | v1.0 | 2/2 | Complete | 2026-04-11 |
| 3. Semantic Retrieval | v1.0 | 2/2 | Complete | 2026-04-11 |
| 4. Infinite Loop Engine | v1.0 | 3/3 | Complete | 2026-04-12 |
| 5. Mixed Autonomy Mode | v1.0 | 3/3 | Complete | 2026-04-12 |
| 6. Tension & Conflict | v1.0 | 2/2 | Complete | 2026-04-12 |
| 7. Arc Tracking | v1.0 | 2/2 | Complete | 2026-04-13 |
| 8. Dynamic STORM | v1.0 | 2/2 | Complete | 2026-04-13 |
| 9. Progressive STORM | v1.0 | 2/2 | Complete | 2026-04-13 |
| 10. Coherence System | v1.0 | 2/2 | Complete | 2026-04-13 |
| 11. Timeline Tracking | v1.0 | 2/2 | Complete | 2026-04-14 |
| 12. Integration & Polish | v1.0 | 4/4 | Complete | 2026-04-14 |
| 13. API Foundation | v2.0 | 4/4 | Complete    | 2026-04-15 |
| 14. WebSocket Layer | v2.0 | 3/3 | Complete   | 2026-04-15 |
| 15. Authentication | v2.0 | 2/2 | Complete    | 2026-04-16 |
| 16. Android Foundation | v2.0 | 3/3 | Complete    | 2026-04-16 |
| 17. Android Interaction | v2.0 | 3/3 | Complete    | 2026-04-16 |
| 18. Android Features | v2.0 | 3/3 | Complete    | 2026-04-16 |
| 19. WS Heartbeat Fix | v2.0-gap | 1/1 | Complete | 2026-04-25 |
| 20. Command & API Wiring Fix | v2.0-gap | 1/1 | Complete* | 2026-04-26 |
| 21. Events & Export Completion | v2.0-gap | 1/1 | Complete | 2026-04-26 |
| 22. 群聊模式改造 | v3.0 | 1/1 | Complete | 2026-04-26 |
| 23. Android技术债务治理 | v2.5 | 3/3 | Complete | 2026-04-26 |

---

*Roadmap reorganized: 2026-04-14 after v1.0 milestone completion*
*v2.0 phases added: 2026-04-14*
*v2.0 gap closure phases 19-21 added: 2026-04-16*
*v2.5 tech debt phase 23 added: 2026-04-25*
