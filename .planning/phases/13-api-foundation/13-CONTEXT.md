# Phase 13: API Foundation - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

FastAPI 应用包裹现有 DramaRouter，14 个 REST 端点映射所有 CLI 命令，Pydantic v2 模型定义请求/响应契约，CORS + URL 版本前缀 + 全局状态迁移。不修改 12 个核心模块的内部逻辑。

</domain>

<decisions>
## Implementation Decisions

### Runner 集成策略
- **D-01:** 共享 Runner + 单 Session — 与 CLI 行为一致，单用户模式最简单，互斥天然保证
- **D-02:** 命令式端点同步等待完整结果 — Phase 13 只做 REST，设 120s 超时（与 A2A 调用一致），Phase 14 加 WebSocket 后自然升级为流式体验

### 端点设计细节
- **D-03:** 返回 final_response + 结构化 tool 结果 — 提取 scene_number, formatted_scene, actors_in_scene, narration 等关键字段，前端有丰富数据可渲染
- **D-04:** 混合错误码模式 — 端点级错误（无 drama、参数无效）HTTP 4xx，tool 内部业务错误 200 + status: error
- **D-05:** save/load 直接调 state_manager — 数据操作不需要 LLM，更快更可预测

### 会话与互斥管理
- **D-06:** `/start` 先自动保存旧 drama 再覆盖 — 安全优先，不丢数据，与 CLI "quit 时自动 save" 精神一致
- **D-07:** Lock file 互斥 — PID 写入 `app/.api.lock`，CLI 和 API 启动时互检，进程崩溃时可检测 stale lock
- **D-08:** Session 生命周期绑定 FastAPI 进程 — startup 事件创建 Runner + Session，shutdown 时清理 Actor 服务 + 删除 lock file

### 状态迁移方案
- **D-09:** 直接用 `state["drama"]["theme"]` — 已存在且冗余（CONCERNS.md 确认 "effectively dead code"），无需额外抽象
- **D-10:** 删除 `_current_drama_folder` 全局变量，强制要求 tool_context — `_get_current_theme(tool_context)` 必须传参，无参报错
- **D-11:** CLI 自然兼容 — 所有交互走 Runner，tool_context 自动注入，无需额外适配

### Claude's Discretion
- Pydantic 模型具体字段设计（请求/响应结构体）
- FastAPI 路由组织方式（单文件 vs 多文件 router）
- Lock file 的 stale 检测策略（PID 存活检查 + 超时）
- 命令式端点从 Runner 事件流中提取结构化结果的实现方式
- CORS 具体允许的 origin 列表

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 13 定义、成功标准、依赖关系
- `.planning/REQUIREMENTS.md` — API-01~05, STATE-01~03 需求定义
- `.planning/STATE.md` — v2.0 已决定的架构选型和风险表
- `.planning/PROJECT.md` — 项目愿景、约束、技术债

### 代码库分析
- `.planning/codebase/ARCHITECTURE.md` — 整体架构、数据流、StormRouter 路由逻辑
- `.planning/codebase/CONVENTIONS.md` — 命名、docstring、返回值格式约定
- `.planning/codebase/CONCERNS.md` — 技术债、已知 bug、安全顾虑（_current_drama_folder、全局状态等）
- `.planning/codebase/STRUCTURE.md` — 目录结构、模块依赖图、新代码放置指南
- `.planning/codebase/STACK.md` — 依赖版本、测试框架、环境配置
- `.planning/codebase/INTEGRATIONS.md` — A2A 协议、ADK 集成、状态持久化

### 核心源码
- `app/agent.py` §413-486 — DramaRouter 路由逻辑 + root_agent 定义
- `app/state_manager.py` §20-21 — `_current_drama_folder` 全局变量（待迁移）
- `app/state_manager.py` §471 — `_get_current_theme()` fallback 链
- `app/state_manager.py` §485-546 — `init_drama_state()` 全局变量赋值
- `app/state_manager.py` §765-766 — `load_progress()` 全局变量赋值
- `app/tools.py` — 所有 tool 函数签名和返回值格式
- `cli.py` — CLI 命令路由、Runner 调用模式、事件流处理

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DramaRouter` (`app/agent.py:413`): 现有路由器，API 端点复用其路由逻辑，无需修改
- `root_agent` (`app/agent.py:473`): 模块级单例，FastAPI 共享 Runner 直接引用
- `state_manager` 函数: `save_progress()`, `load_progress()`, `list_dramas()`, `export_script()`, `get_all_actors()` — 查询式端点可直接调用
- `_sanitize_name()`: 文件名安全化，API 层构造磁盘路径时复用
- `_set_state()` / `_get_state()`: 状态读写 + 自动持久化，API 层无需额外处理
- `Pydantic BaseModel` (`app/app_utils/typing.py`): 已有 Pydantic 使用先例

### Established Patterns
- Tool 函数签名: `(param1, param2, tool_context: ToolContext) -> dict` — API 不直接调 tool，但响应结构需对齐
- 返回值格式: `{"status": "success"|"error"|"info", "message": "...", ...领域字段}`
- 状态持久化: `_set_state()` 自动写磁盘，API 层无需手动 flush
- CLI 事件流处理: 逐 event 读取 function_call / function_response / final_response — API 需要类似逻辑提取结构化结果

### Integration Points
- `app/__init__.py`: 导出 ADK `app` 实例，FastAPI 可复用 `root_agent`
- `cli.py` 的 `Runner` + `InMemorySessionService` 模式: API 层复制此模式
- `stop_all_actor_services()`: FastAPI shutdown 时调用
- `app/actor_service.py`: Actor 进程生命周期管理，API shutdown 需要清理
- `_conversation_log` 全局变量: 与 `_current_drama_folder` 同类问题，Phase 12 已迁移至 `state["conversation_log"]`

</code_context>

<specifics>
## Specific Ideas

- 命令式端点（8个）走 ADK Runner，查询式端点（6个）直接读 state — STATE.md 已决定的 Hybrid 方案 C
- API 版本前缀 `/api/v1/` — REQUIREMENTS API-04
- CORS 允许 Android app origin — REQUIREMENTS API-05
- 一次只支持一个活跃 drama session — REQUIREMENTS STATE-03
- Debounce flush-on-push 留到 Plan 13-04（与 WebSocket 推送协同）— REQUIREMENTS STATE-02

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-api-foundation*
*Context gathered: 2026-04-15*
