# Phase 1: Memory Foundation - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

构建 3 层记忆架构（工作记忆/场景摘要/全局摘要），替换现有扁平 `actor.memory` 列表，使系统能支撑 50+ 场戏而不溢出上下文窗口。包含：记忆分层、自动压缩、重要性权重摘要、关键记忆保护、旧格式迁移。

</domain>

<decisions>
## Implementation Decisions

### 记忆层划分
- **D-01:** 工作记忆容量 = 5 条（覆盖当前+2个近期场景的详情）
- **D-02:** 场景摘要容量 = 10 条（约覆盖 20-30 场的压缩信息）
- **D-03:** 全局摘要 = 结构化字段（主题/关键角色/未决冲突/已解决冲突）+ 自由文本概述，两者兼有
- **D-04:** 工作记忆超过 5 条时触发压缩（最旧条目压缩为场景摘要）
- **D-05:** 场景摘要超过 10 条时触发压缩（最旧摘要压缩入全局摘要）

### 重要性判定
- **D-06:** 6 类事件自动标记为关键记忆：
  1. 角色首次登场/关系确立
  2. 重大转折事件
  3. 情感高峰/低谷
  4. 未决事件/悬念
  5. 用户明确标记的事件（`/mark` 命令）
  6. 系统检测的其他高重要性事件
- **D-07:** 关键记忆独立存储于 `actor.critical_memories`，不占用工作记忆的 5 条槽位，压缩时不会被丢弃

### 压缩策略
- **D-08:** 使用 LLM 生成摘要（自然语言摘要，质量高）
- **D-09:** 异步后台压缩——场景结束后后台启动压缩，下次场景使用时读取结果，用户无感
- **D-10:** 全局摘要更新策略：每次场景摘要被压缩时，用 LLM 重写整个全局摘要（保持精炼一致）

### 迁移兼容
- **D-11:** 自动迁移——`load_progress()` 时检测旧格式 `actor.memory`（扁平列表），自动将全部条目倒入 `actor.working_memory`，用户无感
- **D-12:** 3 层记忆数据结构嵌套在 actor 对象内：
  ```
  actor.working_memory: [{"entry": "...", "importance": "normal|critical", "scene": N}]
  actor.scene_summaries: [{"summary": "...", "scenes_covered": "3-5", "key_events": [...]}]
  actor.arc_summary: {
    "structured": {"theme": "...", "key_characters": [...], "unresolved": [...], "resolved": [...]},
    "narrative": "一段自由文本故事弧线概述..."
  }
  actor.critical_memories: [{"entry": "...", "reason": "首次登场|转折|情感高峰|未决|用户标记|系统检测", "scene": N}]
  ```
- **D-13:** 旧版 `actor.memory` 字段保留为只读（不删除），新代码统一使用新字段

### Claude's Discretion
- LLM 调用使用的具体模型和 prompt 模板
- 异步压缩的具体实现方式（后台线程/协程/延迟任务）
- 场景摘要的格式细节
- `/mark` 命令的 CLI 交互设计

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 记忆管理相关
- `.planning/PROJECT.md` — 项目愿景和约束（Core Value: 无限畅写，逻辑不断）
- `.planning/REQUIREMENTS.md` — MEMORY-01/02/03 需求定义
- `.planning/research/STACK.md` — 零新依赖方案，3 层自定义记忆设计
- `.planning/research/ARCHITECTURE.md` — memory_manager.py 模块设计
- `.planning/research/PITFALLS.md` — 上下文耗尽、摘要失真等陷阱

### 现有代码（必须读取理解）
- `app/state_manager.py` — 当前状态管理，`update_actor_memory()`, `get_actor_info()`, `load_progress()`, `save_progress()` 等函数需修改
- `app/tools.py` — `actor_speak()` 中 `memory_str` 构建逻辑需替换为 `build_actor_context()`
- `app/actor_service.py` — 演员创建时记忆初始化
- `app/agent.py` — Agent 定义，了解工具如何被调用

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 现有双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（中文文档、ToolContext 模式、返回 dict 格式）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `state_manager.py` 的 `update_actor_memory()` — 可扩展为 `update_working_memory()`，保留函数签名风格
- `state_manager.py` 的 `load_progress()` / `save_progress()` — 自动迁移的插入点
- `tools.py` 的 `actor_speak()` — 已有 `memory_str` 构建，替换为 `build_actor_context()`
- `tools.py` 的 `load_drama()` — 已有演员重启逻辑，可在此触发记忆迁移

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...}`
- State 路径：`tool_context.state["drama"]["actors"][name]`
- 中英双语 docstring

### Integration Points
- `state_manager.py` — 新增 memory_manager 调用点
- `tools.py` actor_speak — 替换 memory_str 构建
- `tools.py` load_drama — 自动迁移入口
- 新模块 `app/memory_manager.py` — 核心新增

</code_context>

<specifics>
## Specific Ideas

- 全局摘要的结构化字段应包含：`theme`（故事主题）、`key_characters`（关键角色列表）、`unresolved`（未决冲突/悬念）、`resolved`（已解决冲突）
- 关键记忆的 reason 字段应支持中文值（与现有中文 UI 一致）
- `/mark` 命令应简洁，如 `/mark 这段很重要` 即可将最近一条记忆标记为关键

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-memory-foundation*
*Context gathered: 2026-04-11*
