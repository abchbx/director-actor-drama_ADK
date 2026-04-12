# Phase 4: Infinite Loop Engine - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

将线性 STORM 流水线替换为无限叙事循环引擎：场景→评估→注入→下一场，无预设终点。

核心交付物：
1. `StormRouter` 演化为 `DramaRouter`（2 子 Agent：setup + improvise）
2. improvise 阶段可无限循环，无硬编码终点
3. 每场戏 prompt 自动包含上一场关键信息（结局、情绪、未决事件）
4. `/start` 一站式 Setup 流程
5. 旧状态自动兼容迁移

**不包含：** 冲突引擎（Phase 6）、混合推进模式（Phase 5）、Dynamic STORM（Phase 8）
</domain>

<decisions>
## Implementation Decisions

### Router 架构
- **D-01:** 保留 `BaseAgent` 子类模式，重命名为 `DramaRouter`，只保留 2 个子 Agent（`_setup_agent` + `_improv_director`）
- **D-02:** 将 `_storm_discoverer` + `_storm_researcher` + `_storm_outliner` 合并为单个 `_setup_agent`，一个 system prompt 涵盖所有 setup 阶段，工具集合并
- **D-03:** Fallback 策略：路由找不到目标 Agent 时默认路由到 `_improv_director`（最安全的兜底）
- **D-04:** 路由判断依据：按 `state["actors"]` 是否非空判断——非空则 improvise，否则 setup。不再依赖 `drama.status` 细粒度状态

### 循环驱动
- **D-05:** 循环由 System Prompt 驱动——在 `_improv_director` 的 system prompt 中写明调用序列（next_scene → narrate → speak × N → write_scene），LLM 自主按序调用工具。每轮 `/next` 用户输入触发一轮完整场景
- **D-06:** 每场戏结束后等待用户输入——`/next` 继续、`/action` 注入、`/end` 结束。不自动推进多场
- **D-07:** 场景后评估步骤：在 prompt 中提示导演每场结束后回顾局势（调用 `get_director_context`），但代码层面不强制调用特定评估工具。为 Phase 6 `evaluate_tension()` 预留接口

### 场景衔接
- **D-08:** 衔接信息来源：增强现有 `build_director_context()` 函数，增加"上一场结局摘要"段落，从 `scenes[-1]` 中提取。不引入新工具
- **D-09:** 衔接信息粒度：精简三要素——①上一场结局（1-2句）②角色情绪状态 ③未决事件/悬念。不包含完整场景摘要以节省 token
- **D-10:** 衔接信息组织：两者结合——`next_scene()` 返回值中嵌入精简衔接段落（必看），导演可额外调用 `get_director_context()` 获取全局视野。信息不重复——`next_scene()` 返回衔接要点，`get_director_context()` 返回全局摘要

### Setup→Improvise 过渡
- **D-11:** Setup 完成判定：演员创建完毕即完成（`state["actors"]` 非空）。与 D-04 路由逻辑天然一致
- **D-12:** `/start` 流程：一站式 Setup——`_setup_agent` 在单轮对话中完成发现视角→合成大纲→引导用户确认→创建角色。用户只发一次 `/start <主题>`，Agent 自主推进到演员创建
- **D-13:** 首次引导：`next_scene()` 返回 `is_first_scene` 标记——当 `current_scene == 0` 时标注为 true，导演据此输出开场白和首场特殊引导
- **D-14:** 旧状态兼容：`load_drama()` 加载时自动升级旧状态——若有 actors 则统一改为 `"acting"`，否则改为 `"setup"`。用户无感迁移

### Claude's Discretion
- `_setup_agent` 和 `_improv_director` 的 system prompt 具体措辞和长度
- `_setup_agent` 内部步骤的详细编排（发现→研究→大纲的 prompt 逻辑）
- `build_director_context()` 增强段落的具体格式
- `next_scene()` 返回值中衔接信息的精确字段名
- 旧 STORM 工具（`storm_discover_perspectives`, `storm_ask_perspective_questions` 等）的保留/废弃策略

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture Design
- `.planning/research/ARCHITECTURE.md` — 完整的架构演进设计：从线性 STORM 到无限循环，Router 重构方案，循环驱动方式，组件设计
- `.planning/research/FEATURES.md` — 功能需求研究：无限叙事循环、上下文管理、用户干预、叙事连贯性
- `.planning/research/PITFALLS.md` — 已知陷阱和风险

### Existing Implementation
- `app/agent.py` — 当前 StormRouter + 4 子 Agent 实现，需重构
- `app/tools.py` — 现有工具函数（next_scene, director_narrate, actor_speak, write_scene 等），需增强
- `app/context_builder.py` — 导演/演员上下文构建器，需增强衔接信息
- `app/state_manager.py` — 状态管理，需适配新路由逻辑
- `app/memory_manager.py` — 3 层记忆架构（Phase 1 交付）
- `app/semantic_retriever.py` — 语义检索（Phase 3 交付）

### Prior Phase Context
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 记忆层决策（5条工作记忆/10条场景摘要/结构化+自由文本）
- `.planning/phases/02-context-builder/02-CONTEXT.md` — 上下文构建决策（8000/30000 token 预算）
- `.planning/phases/03-semantic-retrieval/03-CONTEXT.md` — 语义检索决策

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — 当前架构文档
- `.planning/codebase/CONCERNS.md` — 已知问题清单
- `.planning/codebase/CONVENTIONS.md` — 代码约定

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StormRouter._run_async_impl()` (agent.py:403-439): 路由逻辑骨架，可改造为 DramaRouter
- `build_director_context()` (context_builder.py): 导演上下文构建器，可增强衔接段落
- `build_actor_context()` (context_builder.py): 演员上下文构建器，已完整集成 3 层记忆
- `next_scene()` (tools.py:493-528): 场景推进工具，返回值可嵌入衔接信息
- STORM 工具集 (tools.py:924-1247): `storm_discover_perspectives`, `storm_synthesize_outline`, `create_actor` — 可被 `_setup_agent` 复用

### Established Patterns
- `BaseAgent` 子类 + `_run_async_impl()` + `yield event` — ADK Agent 标准模式
- `tool_context.state["drama"]` — 统一状态访问方式
- `_get_state()` / `_set_state()` — 状态读写封装
- `set_drama_status()` — 状态变更函数

### Integration Points
- `agent.py` — Router 重构主战场，所有子 Agent 定义和路由逻辑
- `tools.py` — `next_scene()` 增强返回值，`load_drama()` 兼容旧状态
- `context_builder.py` — `build_director_context()` 增加衔接段落
- `state_manager.py` — `load_progress()` 状态迁移逻辑

</code_context>

<specifics>
## Specific Ideas

- `_improv_director` 的 system prompt 应明确标注"你处于无限演出模式，无预设终点"
- `_setup_agent` 合并后的 prompt 应保留多视角发现的核心思想（STORM 价值），但不再拆成独立阶段
- 导演 prompt 中的场景衔接信息应以【上一场衔接】标记，与现有【舞台指示】【角色对话】格式统一
- `DramaRouter` 的路由判断应优先检查 utility commands（/save, /load 等），与当前逻辑一致
- `next_scene()` 返回的衔接信息应从 `scenes[-1]` 和演员情绪中提取，不依赖 LLM 调用

</specifics>

<deferred>
## Deferred Ideas

- `/auto N` 自动推进 N 场功能 — 属于 Phase 5: Mixed Autonomy Mode
- `evaluate_tension()` 张力评分工具 — 属于 Phase 6: Tension Scoring & Conflict Engine
- `inject_conflict()` 冲突注入工具 — 属于 Phase 6
- `/storm` 命令和 Dynamic STORM — 属于 Phase 8
- `/steer <direction>` 轻量引导 — 属于 Phase 5
- `/end` 终幕旁白和完整剧本导出 — 属于 Phase 5（LOOP-04）
- 代码级循环（while loop 自动多场）— 违背 ADK turn-based 模型，不建议实现

</deferred>

---

*Phase: 04-infinite-loop-engine*
*Context gathered: 2026-04-11*
