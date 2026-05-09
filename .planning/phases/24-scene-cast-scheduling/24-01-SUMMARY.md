# Phase 24-01 Summary: 后端 scene_cast 机制 + set_scene_cast 工具 + next_scene/actor_speak_batch 改造

**Plan:** 24-01
**Phase:** 24 (场景级演员调度)
**Status:** COMPLETE
**Date:** 2026-04-29

## Deliverables

### Task 1: state_manager 新增 scene_cast 字段 + 迁移
- `init_drama_state()`: `state["scene_cast"] = None` (line 577)
- `load_progress()`: `state.setdefault("scene_cast", None)` (line 1005)
- 新增 `get_scene_cast(state) -> list[str]` 辅助函数 (line 1966)
- 新增 `get_ai_actors(state) -> list[str]` 辅助函数 (line 1950)
- **语义**: `None` = 未设置（全员上场），`[]` = 不应出现（set_scene_cast 校验阻止）

### Task 2: set_scene_cast 工具函数
- `app/tools.py` 新增 `set_scene_cast(cast, tool_context)` (line 1599)
- 校验逻辑: 非空、演员存在性、自动包含用户主角、去重保序
- 返回值: `{status, scene_cast, standby, message}`

### Task 3: next_scene() 改造
- 场景推进后重置 `scene_cast` 为所有演员名 (line 1436)
- 返回值新增 `scene_cast` 和 `standby` 字段 (lines 1456-1457)
- `actors_available` 改为仅上场演员

### Task 4: actor_speak_batch() 改造
- Phase 1 准备阶段添加 scene_cast 过滤 (line 613-616)
- 待机演员直接跳过，不参与 A2A 调用

### Task 5: event_mapper 新增 cast_change 事件映射
- `TOOL_EVENT_MAP` 添加 `"set_scene_cast": ["cast_change", "command_echo"]` (line 44)
- `_extract_call_data()` 添加 `cast_change` 处理 (lines 119-124)
- `_extract_response_data()` 添加 `cast_change` 处理 (lines 201-208)
- `NO_TYPING_TOOLS` 添加 `"set_scene_cast"` (line 76)
- `_format_command_echo()` 添加 `/cast` 格式化 (lines 275-278)
- `_build_director_log_call()` 添加 set_scene_cast 日志 (lines 350-353)

### Task 6: /drama/cast/status 端点扩展
- `GET /drama/cast/status` 响应添加 `scene_cast` 字段 (lines 137-140)
- `CastStatusResponse` Pydantic 模型已包含 `scene_cast: list[str] | None` (line 125)

### Task 7: agent.py 注册新工具
- `_improv_director` tools 列表添加 `set_scene_cast` (line 514)
- 系统提示已包含 `/cast` 命令提示 (line 384)

### Task 8: 后端单元测试
- `tests/unit/test_tools_cast.py` 已包含 14 个测试用例，全部通过:
  - `test_init_drama_state_has_scene_cast`
  - `test_load_progress_migrates_scene_cast`
  - `test_get_scene_cast_default_all`
  - `test_get_scene_cast_explicit_list`
  - `test_set_scene_cast_success`
  - `test_set_scene_cast_empty_rejected`
  - `test_set_scene_cast_invalid_actor`
  - `test_set_scene_cast_user_protagonist_included`
  - `test_set_scene_cast_dedup_preserves_order`
  - `test_next_scene_resets_scene_cast`
  - `test_next_scene_returns_scene_cast_fields`
  - `test_actor_speak_batch_skips_standby`
  - `test_actor_speak_batch_none_scene_cast_no_filter`
  - `test_set_scene_cast_in_tool_event_map`
  - `test_set_scene_cast_in_no_typing_tools`
  - `test_cast_change_call_data_extraction`
  - `test_cast_change_response_data_extraction`
  - `test_cast_status_response_model_has_scene_cast`
  - `test_cast_status_response_model_none_scene_cast`

### 额外修复: /cast 命令后端路由
- `app/api/routers/commands.py` `chat_message()` 中添加 `/cast` 前缀检测 (lines 313-335)
- 直接调用 `set_scene_cast` 工具并推送 `cast_change` WS 事件

## Verification

```bash
# 单元测试
uv run pytest tests/unit/test_tools_cast.py -x -q
uv run pytest tests/unit/test_state_manager.py -x -q -k scene_cast
uv run pytest tests/unit/test_event_mapper.py -x -q -k cast_change
uv run pytest tests/unit/test_api_queries.py -x -q -k cast

# 全量回归
uv run pytest tests/unit/ -x
```

全部通过。

## Risks & Status

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| scene_cast 为空导致无人发言 | HIGH | set_scene_cast 校验非空；next_scene 默认重置为全员 | ✅ DONE |
| 旧存档 scene_cast 缺失 | MEDIUM | None = 全员上场语义；load_progress 迁移 | ✅ DONE |
| next_scene 重置导致导演选角丢失 | MEDIUM | 文档说明：导演需在 /next 后重新选角 | ✅ ACCEPTED |
| /cast 命令未路由 | CRITICAL | commands.py chat_message 中添加 /cast 前缀检测 | ✅ DONE |
