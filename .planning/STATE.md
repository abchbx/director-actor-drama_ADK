---
gsd_state_version: 1.0
milestone: v2.5
milestone_name: Android 技术债务治理
current_phase: 23
status: complete
last_updated: "2026-04-26T16:00:00.000Z"
last_activity: 2026-04-26 -- Phase 23 complete (3/3 plans done)
progress:
  total_phases: 11
  completed_phases: 11
  total_plans: 26
  completed_plans: 26
  percent: 100
---

# State

**Project:** Director-Actor-Drama 无限畅写版
**Milestone:** v2.5 Android 技术债务治理
**Current Phase:** 23 (android-tech-debt) — COMPLETE
**Status:** All plans executed

## Current Position

Phase: 23 (android-tech-debt) — 3/3 plans complete ✅
Status: Phase 23 COMPLETE
Last activity: 2026-04-26 -- Phase 23-03 P2/P3 测试补全 complete

## Progress

- [x] v1.0 milestone complete (12 phases, 29 plans, 517 tests)
- [x] v2.0 requirements defined (32 requirements)
- [x] v2.0 roadmap created (6 phases, 18 plans)
- [x] Phase 13: API Foundation — 4/4 plans complete ✅
- [x] Phase 14: WebSocket Layer — 3/3 plans complete ✅
- [x] Phase 15: Authentication — 2/2 plans complete ✅
- [x] Phase 16: Android Foundation — 3/3 plans complete ✅
- [x] Phase 17: Android Interaction — 3/3 plans complete ✅
- [x] Phase 18: Android Features — 3/3 plans complete ✅
- [x] Phase 19: WS Heartbeat Fix — 1/1 plans complete ✅
- [x] Phase 20: Command & API Wiring Fix — ✅ (code verified, no formal PLAN/SUMMARY)
- [x] Phase 21: Events & Export Completion — 1/1 plans complete ✅
- [x] Phase 22: 群聊模式改造 — 1/1 plans complete ✅
- [x] Phase 23: Android 技术债务治理 — 3/3 plans complete ✅

## Decisions

### v1.0 Decisions (archived)

- 11-01: Hybrid time representation — descriptive current_time + structured time_periods list
- 11-06: Director manual advance_time() — no LLM auto-infer
- 11-11: Graduated jump detection severity — normal/minor/significant
- 11-16: Timeline validation integrated into validate_consistency()
- 12-01: 5-second debounce via threading.Timer
- 12-01: conversation_log migrated to state["conversation_log"]
- 12-01: Scene archival at 20-scene threshold
- 12-02: Error detection uses [ERROR:xxx] prefix markers
- 12-02: Shared AsyncClient uses lazy singleton
- 12-02: Passive crash detection
- 12-02: MAX_CRASH_COUNT=3
- [Phase 13]: 13-03: _current_drama_folder global removed entirely — ValueError replaces silent fallback
- [Phase 13]: 13-03: _require_active_drama helper centralizes 404 guard for query endpoints
- [Phase 13]: 13-03: Query endpoints call state_manager directly (D-05) without Runner
- [Phase 13]: Lock file at app/.api.lock uses PID for liveness detection; CLI and API mutually exclusive (D-07/STATE-03)
- [Phase 13]: flush-on-push hook: app.state.flush_state_sync reference for Phase 14 WebSocket (STATE-02)
- [Phase 14]: connect() returns bool for acceptance/rejection check
- [Phase 14]: heartbeat runs as asyncio.Task, cancelled on disconnect, 15s ping/30s timeout
- [Phase 15]: _validate_ws_token as plain function (not Depends) — WS endpoints don't support HTTP DI for auth
- [Phase 15]: WebSocketException(code=4001) raised before accept — ConnectionManager never polluted with unauthed connections
- [Phase 15]: _validate_ws_token is synchronous — token comparison is CPU-only, no I/O needed

### v2.0+ Decisions

- C/S 架构: FastAPI (Python) + Kotlin/Jetpack Compose (Android)
- 通信协议: REST (命令) + WebSocket (推送)
- 认证: 简单 Token（局域网/单用户）
- 离线: 纯在线，不支持离线
- REST 命令走 ADK Runner，只读查询直接读 state（Approach C: Hybrid）
- EventBridge 零侵入观察 ADK Runner 事件流
- 100-event replay buffer 支持断线重连
- CLI 保持独立入口（不改为 API 客户端），但 API 和 CLI 互斥运行
- WebSocket 心跳 15s interval，30s 超时断连
- 13-01: CORS allow_origins=["*"] dev mode; production restricts in Phase 15+
- 13-01: ToolContextAdapter wraps session.state for state_manager compat
- 13-01: Endpoint stubs return structured Pydantic models (not bare dicts)
- 17-01: DELETE /drama/{folder} validates folder name with regex to prevent path traversal (T-17-01)
- 17-01: DramaCreateViewModel waits for WS scene_start event before navigating (D-04), not REST response
- 17-01: DramaRepository uses runCatching for all operations, no manual try-catch
- 17-02: narration event only marks typing=false; actual text rendered from end_narration event (per event_mapper.py)
- 17-02: Replay messages (type=replay) silently ignored in handleWsEvent to prevent bubble duplication (Pitfall 6)
- 17-02: FREE_TEXT command type routes to userAction() — treating unstructured input as /action
- 17-03: T-17-08 mitigation: scene_number path param validated 1-999 range in GET /drama/scenes/{n}
- 17-03: get_scene_summaries() handles both in-memory and archived scenes transparently
- 17-03: History scene view replaces main bubbles; returnToCurrentScene() reconnects WS
- 19-01: 客户端 JSON 解析替换字符串匹配 (parseToJsonElement + when)
- 19-01: OkHttp pingInterval=60s (TCP keepalive), 不与 15s 应用层心跳冲突
- 19-01: 服务端处理 {"type":"heartbeat"} 消息兼容旧客户端
- 20: isProcessing 在 WS connected/disconnected/error/timeout 四路径均重置 (D-20-01: 60s safety timeout)
- 20: CommandType 添加 STEER/AUTO/STORM，Repository 添加 steerDrama/autoAdvanceDrama/stormDrama
- 21-02: status 事件 → 空分支 (scene_start 已覆盖)
- 21-03: actor_status 事件 → 精确更新 + 兜底刷新
- 21-05: Export 内容获取 → 后端返回 content 字段
- 22-01: 保留功能性斜杠命令 (/next /end /save /load /list /delete)
- 22-03: sender_name 默认 "导演"，非默认时注入 [名称] 前缀
- 22-04: 删除 CommandInputBar.kt 死代码
- 23-01: VM 拆分策略：子组件组合 (@Inject constructor)，非独立 VM
- 23-02: 子组件通信：SharedFlow 事件上报
- 23-05: WS 作用域 @ActivityScoped + 独立 WebSocketModule
- 23-06: 多 VM 共享 WS：acquire/release AtomicInteger 引用计数
- 23-08: R8 isMinifyEnabled=true + shrinkResources=true
- 23-09: ProGuard 保守 keep (DTO/接口/密封类/Hilt/Compose/Coroutines)
- 23-10: ARCH-10 数据源策略 — WS 优先/REST 降级 (addFromRest)
- 23-14: UiState 子状态拆分 (Connection/Interaction/SaveLoad/ActorPanel)

## Key Risks

| Risk | Phase | Mitigation | Status |
|------|-------|------------|--------|
| Event Loop 冲突 (P0) | 13 | FastAPI + ADK Runner 共享事件循环 | ✅ DONE |
| 全局状态迁移 (P0) | 13 | _current_drama_folder → session-scoped | ✅ DONE (13-03) |
| CLI 互斥 (P0) | 13 | Lock file + stale PID detection | ✅ DONE (13-04) |
| 状态同步 (P1) | 13-14 | WebSocket 推送前 flush-on-push | ✅ DONE |
| WebSocket 长 LLM 调用 (P1) | 14 | 心跳 + 进度推送 + 请求去重 | ✅ DONE |
| Android 网络切换 (P2) | 17-18 | 自动重连 + 指数退避 | ✅ DONE |
| isProcessing 永不重置 (CRITICAL) | 20 | 四路径重置 + 60s safety timeout | ✅ DONE (code verified) |
| API 端点未接线 (HIGH) | 20 | STEER/AUTO/STORM + Repository | ✅ DONE (code verified) |
| WS 心跳 Pong 缺失 (CRITICAL) | 19 | JSON 解析 + 移除死代码 | ✅ DONE |
| BaseUrl 硬编码 (P1) | 23-02 | BaseUrlInterceptor 动态切换 | ✅ DONE |
| 明文 HTTP 安全 (P1) | 23-02 | network_security_config | ✅ DONE |
| 单元测试缺失 (P1) | 23-02 | BubbleMerger/CommandRouter/ConnectionOrchestrator 测试 | ✅ DONE |

## Phase 20 Verification Note

Phase 20 (Command & API Wiring Fix) has **no formal PLAN or SUMMARY** — only `20-CONTEXT.md` and `20-DISCUSSION-LOG.md`. However, codebase audit confirms all objectives met:

1. **isProcessing reset**: 4 paths reset `isProcessing = false` (WS connected L1147, REST fallback L1156/1160, error L1168, timeout L345). 60s safety timeout (D-20-01).
2. **CommandType STEER/AUTO/STORM**: Present in `CommandType.kt` L13-15
3. **Repository methods**: `steerDrama()`/`autoAdvanceDrama()`/`stormDrama()` in `DramaRepository.kt` L31-33, `DramaRepositoryImpl.kt` L84-97
4. **ViewModel wiring**: `when (commandType)` in `DramaDetailViewModel.kt` L1134-1139 routes correctly

Changes likely implemented during Phase 22/23 refactoring, never formally tracked under Phase 20.

## Phase 23-02 Gap Analysis → RESOLVED

All 23-02 deliverables from the original gap analysis have been implemented:

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| `BaseUrlInterceptor.kt` | ✅ Created | Dynamic BaseUrl interceptor |
| `ServerPreferences.kt` | ✅ Updated | +currentApiBaseUrl() +cachedApiBaseUrl |
| `network_security_config.xml` | ✅ Created | Release: cleartextTrafficPermitted=false |
| `network_security_config_debug.xml` | ✅ Created | Debug: cleartextTrafficPermitted=true |
| `usesCleartextTraffic=false` | ✅ Fixed | AndroidManifest.xml L14 |
| Unit test directory | ✅ Created | `app/src/test/.../orchestrator/` |
| `BubbleMergerTest.kt` | ✅ Created | 15 @Test (incl. addFromRest) |
| `CommandRouterTest.kt` | ✅ Created | 20 @Test |

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)
**Core value:** 无限畅写，逻辑不断
**Current focus:** v2.5 milestone complete — ready for v3.0 planning or archive
