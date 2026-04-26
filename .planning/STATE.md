---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Android 移动端
current_phase: 19
status: executing
last_updated: "2026-04-26T03:57:53.264Z"
last_activity: 2026-04-26 -- Phase 23 planning complete
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 18
  completed_plans: 18
  percent: 100
---

# State

**Project:** Director-Actor-Drama 无限畅写版
**Milestone:** v2.0 Android 移动端 — Gap Closure
**Current Phase:** 19
**Status:** Ready to execute

## Current Position

Phase: 19 (ws-heartbeat-fix) — PENDING
Plan: 19-01 (not yet created)
Status: Ready to execute
Last activity: 2026-04-26 -- Phase 23 planning complete

## Progress

- [x] v1.0 milestone complete (12 phases, 29 plans, 517 tests)
- [x] v2.0 requirements defined (32 requirements)
- [x] v2.0 roadmap created (6 phases, ~18 plans)
- [x] Phase 13: API Foundation — 4/4 plans complete ✅
- [x] Phase 14: WebSocket Layer — 3/3 plans complete ✅
- [x] Phase 15: Authentication — 2/2 plans complete ✅
- [x] Phase 16: Android Foundation — 3/3 plans complete ✅
- [x] Phase 17: Android Interaction — 3/3 plans complete ✅
- [x] Phase 18: Android Features — 3/3 plans complete ✅
- [x] Phase 19: WS Heartbeat Fix — 1/1 plans complete ✅
- [ ] Phase 20: Command & API Wiring Fix — 0/1 plans (PENDING)
- [ ] Phase 21: Events & Export Completion — 0/1 plans (PENDING)

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

### v2.0 Decisions

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

## Key Risks (from PITFALLS.md)

| Risk | Phase | Mitigation |
|------|-------|------------|
| Event Loop 冲突 (P0) | 13 | FastAPI + ADK Runner 共享事件循环，避免嵌套 asyncio.run() |
| 全局状态迁移 (P0) | 13 | ~~_current_drama_folder → session-scoped context~~ DONE (13-03) |
| CLI 互斥 (P0) | 13 | ~~Lock file 或进程检测~~ DONE (13-04: lock file + stale PID detection) |
| 状态同步 (P1) | 13-14 | ~~WebSocket 推送前 flush-on-push~~ Hook ready (13-04); WebSocket wiring in 14 |
| WebSocket 长 LLM 调用 (P1) | 14 | 心跳 + 进度推送 + 请求去重 |
| Android 网络切换 (P2) | 17-18 | 自动重连 + 指数退避 + Foreground Service |

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)
**Core value:** 无限畅写，逻辑不断
**Current focus:** v2.0 milestone complete — ready for next milestone or archive
