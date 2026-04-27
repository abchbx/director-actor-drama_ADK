# Phase 21: Events & Export Completion — Context

**Phase:** 21-events-export-completion
**Milestone:** v2.0 Gap Closure
**Depends on:** Phase 19 (WS Heartbeat Fix), Phase 20 (Command & API Wiring Fix)
**Requirements:** WS-02, APP-09

---

## Objective

补全 3 种缺失的 WS 事件类型处理（`status`/`actor_status`/`progress`），完成剧本导出功能（后端返回 content + Repository + ViewModel + Share Intent UI）。

---

## Gap Analysis

### 事实纠正

ROADMAP 原文声称"5种被忽略的 WS 事件类型"。经代码审查确认，`actor_created` 和 `cast_update` 已在 `handleWsEvent` 中处理（ViewModel 627-637 行）。**实际仅 3 种事件缺失。**

### 缺失事件

| 事件 | 后端触发源 | call 数据 | response 数据 | 建议处理 |
|------|-----------|-----------|--------------|---------|
| `status` | `start_drama` | `{tool, sender_type}` | 无专属（走 else） | 空分支 + Log.d |
| `actor_status` | `update_emotion` | — | `{actor_name, emotion, sender_type}` | 精确更新演员情绪 + preloadActorPanel 兜底 |
| `progress` | `export_drama` | — | `{message, export_path, sender_type}` | Snackbar 确认 |

### Export 缺口

| 层级 | 现状 | 目标 |
|------|------|------|
| 后端 | `/drama/export` 写文件返回路径 | 添加 `content` 字段返回 Markdown |
| Android API | `DramaApiService.exportDrama()` 已定义 | 已就绪，无需改动 |
| Android DTO | `ExportResponseDto(status, message, export_path)` | 添加 `content` 字段 |
| Android Repository | 无 `exportDrama()` 方法 | 添加接口 + 实现 |
| Android ViewModel | 无 export action/state | 添加 exportDrama() + isExporting |
| Android UI | overflow menu 仅"保存" | 添加"导出"项 + Share Intent |

---

## Design Decisions

| ID | Decision | Choice | Rationale |
|----|----------|--------|-----------|
| D-21-01 | 缺失事件数 | 3 (非5) | actor_created/cast_update 已处理 |
| D-21-02 | `status` 处理 | 空分支 + Log.d | scene_start 已覆盖 |
| D-21-03 | `actor_status` 处理 | 精确更新 + 兜底刷新 | 避免面板闪烁 |
| D-21-04 | `progress` 处理 | Snackbar 确认 | WS 冗余确认通道 |
| D-21-05 | Export 内容获取 | 后端返回 content | 最简方案 |
| D-21-06 | Export 分享方式 | Share Intent | 系统原生 |
| D-21-07 | Export UI 位置 | overflow menu | 低频操作 |

---

## Files to Modify

### Backend (3 files)

1. `app/api/models.py` — ExportResponse 添加 `content: str = ""`
2. `app/state_manager.py` — export_script() 返回 content
3. (routers 无需改动 — `ExportResponse(**result)` 自动映射)

### Android (6 files)

1. `ExportResponseDto.kt` — 添加 `val content: String = ""`
2. `DramaRepository.kt` — 添加 `exportDrama()` 接口
3. `DramaRepositoryImpl.kt` — 实现 `exportDrama()`
4. `DramaDetailViewModel.kt` — 3 事件 + export action + isExporting
5. `DramaDetailUiState` (同 ViewModel 文件) — 添加 isExporting
6. `DramaDetailScreen.kt` — overflow "导出" + Share Intent

**Total: 9 files**

---

## Success Criteria (Revised)

1. Android ViewModel 正确处理 `status`/`actor_status`/`progress` 3种缺失事件
2. 后端 ExportResponse 包含 `content` 字段，DramaRepository.exportDrama() 返回含 Markdown 内容的响应
3. DramaDetailViewModel 包含 export action + isExporting 状态管理
4. DramaDetailScreen overflow menu 包含"导出"按钮，触发 Android Share Intent 分享

---

## Key References

- Discussion: `.planning/phases/21-events-export-completion/21-DISCUSSION-LOG.md`
- Event mapper: `app/api/event_mapper.py` (TOOL_EVENT_MAP, _extract_call_data, _extract_response_data)
- Backend export: `app/state_manager.py:1488` (export_script), `app/tools.py:2258` (export_drama)
- Backend router: `app/api/routers/queries.py:208` (export_drama endpoint)
- Android ViewModel: `android/.../dramadetail/DramaDetailViewModel.kt:444` (handleWsEvent)
- Android DTOs: `android/.../dto/ExportResponseDto.kt`, `RequestDtos.kt`
- Android Screen: `android/.../dramadetail/DramaDetailScreen.kt:278` (overflow menu)
