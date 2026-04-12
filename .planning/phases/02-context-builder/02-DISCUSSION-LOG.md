# Phase 2: Context Builder - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 2-context-builder
**Areas discussed:** 导演上下文内容, Token预算控制, 模块归属, 与后续Phase的边界

---

## 导演上下文内容

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 即纳入所有当前可用信息 | 全局弧线+近期场景+情绪快照+STORM视角，后续Phase增量扩展 | ✓ |
| Phase 2 只做骨架 | 仅含场景编号和演员列表，其余留给后续 | |
| Claude决定 | — | |

**User's choice:** Phase 2 就纳入所有当前可用的信息，后续 Phase 再扩展
**Notes:** 导演当前完全依赖 LLM 自行拼凑上下文，立即提供完整上下文可显著提升导演决策质量

---

## Token预算控制

| Option | Description | Selected |
|--------|-------------|----------|
| 字符数近似 + 逐层截断 | 零依赖、足够准确、符合优先级规则 | ✓ |
| 字符数近似 + 混合裁剪 | 截断条目数 + 截断单条文本长度 | |
| tiktoken精确计数 + 逐层截断 | 精度高但引入新依赖 | |
| Claude决定 | — | |

**User's choice:** 字符数近似 + 逐层截断
**Notes:** 项目原则是零新依赖（见 Phase 1 RESEARCH.md），字符数近似与逐层截断完美契合

---

## 模块归属

| Option | Description | Selected |
|--------|-------------|----------|
| 新建 context_builder.py，迁移 build_actor_context() | context_builder 负责组装+预算控制，memory_manager 只负责 CRUD+压缩 | ✓ |
| 新建 context_builder.py，保留 build_actor_context() 在 memory_manager | context_builder 只放导演上下文，避免大范围迁移 | |
| 不新建模块，扩展 memory_manager.py | 最简单但不符合 ROADMAP | |
| Claude决定 | — | |

**User's choice:** 新建 `app/context_builder.py`，将 `build_actor_context()` 迁移过去
**Notes:** 职责清晰分离——memory_manager 管数据生命周期，context_builder 管上下文组装，符合 ROADMAP 原文要求

---

## 与后续Phase的边界

| Option | Description | Selected |
|--------|-------------|----------|
| 预留接口占位 | build_director_context() 检查字段存在性，存在则纳入，不存在则跳过 | ✓ |
| 硬编码当前可用字段 | 只组装当前 state 中确实存在的数据，后续需再改 | |
| Claude决定 | — | |

**User's choice:** 预留接口占位
**Notes:** 零耦合增量扩展模式——后续 Phase 只需往 state 中添加字段，context_builder 自动发现并纳入

---

## Claude's Discretion

- 字符数→token 的具体换算系数
- 导演上下文各组件的格式和排版细节
- `build_actor_context_from_memory()` 与 `build_actor_context()` 的关系
- 逐层截断时每层减少的具体步长

## Deferred Ideas

None — discussion stayed within phase scope
