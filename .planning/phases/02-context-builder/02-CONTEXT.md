# Phase 2: Context Builder - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

为每场戏组装精确的上下文，包含全局摘要 + 近期场景 + 当前工作记忆 + 导演指令，总 token 控制在预算内。核心交付：
1. `app/context_builder.py` 模块，实现 `build_director_context()` 和 `build_actor_context_from_memory()`
2. 将 `build_actor_context()` 从 `memory_manager.py` 迁移至 `context_builder.py`，并增强 token 预算控制
3. 导演上下文 ≤ 30000 tokens/次，演员上下文 ≤ 8000 tokens/次
4. 当上下文超出预算时，按优先级裁剪（全局摘要 > 近期场景 > 工作记忆细节）

</domain>

<decisions>
## Implementation Decisions

### 导演上下文内容
- **D-01:** Phase 2 即纳入所有当前可用信息：全局故事弧线（所有演员 arc_summary 合并）+ 近期场景标题/关键事件 + 当前场景编号/状态 + 演员情绪快照 + STORM 视角列表。后续 Phase 增量扩展：张力/冲突（Phase 6）、动态 STORM（Phase 8）、已确立事实（Phase 10）

### Token 预算控制
- **D-02:** Token 估算采用字符数近似（1 中文字 ≈ 1.5 token，1 英文词 ≈ 1 token），零外部依赖。裁剪策略采用逐层截断：超预算时从最低优先级层开始减少条目数——全局摘要不截 → 场景摘要减至最近 N 条 → 工作记忆减至最近 M 条

### 模块归属
- **D-03:** 新建 `app/context_builder.py`，将 `build_actor_context()` 从 `memory_manager.py` 迁移过去。职责划分：context_builder 负责所有上下文组装 + token 预算控制；memory_manager 只负责记忆 CRUD + 压缩。`tools.py` 的 import 从 `memory_manager` 改为 `context_builder`。`memory_manager.py` 中保留 `_merge_pending_compression()` 等内部函数，`build_actor_context()` 改为从 context_builder 导入重导出（兼容过渡期）

### 与后续 Phase 的边界
- **D-04:** 预留接口占位——`build_director_context()` 内部检查 state 中是否存在 `conflict_engine`、`dynamic_storm`、`established_facts` 等字段，存在则纳入，不存在则跳过。后续 Phase 添加新 state 字段后自动生效，无需修改 context_builder

### Claude's Discretion
- 字符数→token 的具体换算系数（可微调）
- 导演上下文各组件的格式和排版细节
- `build_actor_context_from_memory()` 与 `build_actor_context()` 的关系（是否为同一函数的别名或增强版）
- 逐层截断时每层减少的具体步长

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 上下文构建相关
- `.planning/ROADMAP.md` — Phase 2 成功标准：导演上下文 ≤ 30000 tokens，演员上下文 ≤ 8000 tokens，按优先级裁剪
- `.planning/REQUIREMENTS.md` — MEMORY-04 需求定义：上下文构建器
- `.planning/PROJECT.md` — 项目愿景和约束（Core Value: 无限畅写，逻辑不断）

### Phase 1 上下文（已锁定决策）
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构决策（D-01~D-13），关键记忆保护，异步压缩

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进：Context Builder 集成方案、token 预算分配表
- `.planning/research/PITFALLS.md` — 上下文耗尽、摘要失真等陷阱

### 现有代码（必须读取理解）
- `app/memory_manager.py` — `build_actor_context()` 当前实现（第 604-687 行），需迁移至 context_builder.py
- `app/tools.py` — `actor_speak()` 中调用 `build_actor_context()` 的位置（第 208 行），import 需更新
- `app/agent.py` — 导演 agent 的 instruction（第 175-352 行），需集成 `build_director_context()`
- `app/state_manager.py` — state 数据结构，了解 directors 上下文可用的 state 字段

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构，STORM 流水线数据流
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `memory_manager.py` 的 `build_actor_context()` — 已实现演员侧上下文组装（角色锚点→关键记忆→弧线→场景摘要→工作记忆→待压缩记忆），需迁移并增强 token 控制
- `memory_manager.py` 的 `_merge_pending_compression()` — 压缩结果合并逻辑，`build_actor_context()` 开头调用，迁移后仍需引用
- `memory_manager.py` 的 `_get_state()` / `_set_state()` — state 读写函数，context_builder 需要用于读取 state
- `tools.py` 的 `actor_speak()` — 已集成 `build_actor_context()`，迁移后需更新 import

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...}`
- State 路径：`tool_context.state["drama"]["actors"][name]`
- 中英双语 docstring（英文首行，中文细节）
- 演员上下文已有的优先级排序：角色锚点 → 关键记忆 → 弧线 → 场景摘要 → 工作记忆

### Integration Points
- `app/context_builder.py` — 新增模块，核心交付
- `app/memory_manager.py` — 迁出 `build_actor_context()`，保留 CRUD + 压缩职责
- `app/tools.py` — 更新 import（从 context_builder 导入 build_actor_context），导演工具集成 `build_director_context()`
- `app/agent.py` — 导演 agent instruction 中引导使用 `build_director_context()` 工具
- 后续 Phase 6/8/10 — 新增 state 字段（conflict_engine、dynamic_storm、established_facts）后自动生效

</code_context>

<specifics>
## Specific Ideas

- 导演上下文格式应与演员上下文风格统一，使用中文标签如【全局故事弧线】【近期场景】【演员状态快照】【STORM视角】
- Token 预算估算函数可独立为 `estimate_tokens(text: str) -> int`，方便复用和测试
- `build_director_context()` 应同时作为 Tool 函数注册（导演可主动调用获取上下文摘要），也可内部调用（自动注入导演 prompt）
- 逐层截断时应记录裁剪日志（如 "场景摘要从 10 条裁剪至 5 条"），方便调试

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-context-builder*
*Context gathered: 2026-04-11*
