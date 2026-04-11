# Phase 1: Memory Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 01-memory-foundation
**Areas discussed:** 记忆层划分, 重要性判定, 压缩策略, 迁移兼容

---

## 记忆层划分

| Option | Description | Selected |
|--------|-------------|----------|
| A: 3 条工作记忆 | 极简，强制频繁压缩，省 token | |
| B: 5 条工作记忆 | 约覆盖当前+2个近期场景详情 | ✓ |
| C: 8 条工作记忆 | 宽松，更多上下文但更费 token | |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 5 条场景摘要 | 约覆盖 10-15 场 | |
| B: 10 条场景摘要 | 约覆盖 20-30 场 | ✓ |
| C: 15 条场景摘要 | 宽松但 token 累积 | |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 自由文本全局摘要 | 灵活自然 | |
| B: 结构化字段 | 精确但刻板 | |
| C: 两者兼有 | 结构化 + 自由文本 | ✓ |

**User's choice:** B B C — 5条工作记忆 / 10条场景摘要 / 结构化+自由文本全局摘要
**Notes:** 选择兼顾灵活性与精确性

---

## 重要性判定

| Option | Description | Selected |
|--------|-------------|----------|
| A-F: 全选6类关键事件 | 首次登场/转折/情感/未决/用户标记/系统检测 | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 始终保留工作记忆 | 最安全但占固定槽位 | |
| B: 独立关键记忆区 | 不占工作记忆槽位 | ✓ |
| C: 优先保留可压缩 | 有弹性但可能丢失 | |

**User's choice:** F B — 全类关键 + 独立存储区
**Notes:** 宁可多保留不可丢失关键信息

---

## 压缩策略

| Option | Description | Selected |
|--------|-------------|----------|
| A: LLM 生成摘要 | 质量高但增加延迟 | ✓ |
| B: 规则模板提取 | 快但可能丢细节 | |
| C: 混合 | 兼顾但复杂度翻倍 | |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 同步压缩 | 简单但用户等待 | |
| B: 异步后台压缩 | 用户无感 | ✓ |
| C: 批量压缩 | 减少 LLM 调用但延迟大 | |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 增量追加 | 全局摘要不断增长 | |
| B: LLM 重写全局摘要 | 保持精炼一致 | ✓ |
| C: 固定长度截断 | 简单粗暴 | |

**User's choice:** A B B — LLM摘要 + 异步压缩 + 重写全局摘要

---

## 迁移兼容

| Option | Description | Selected |
|--------|-------------|----------|
| A: 自动迁移 | load_progress() 时自动，用户无感 | ✓ |
| B: 手动 /migrate | 用户控制但需额外操作 | |
| C: 不迁移 | 旧记忆不可检索 | |

| Option | Description | Selected |
|--------|-------------|----------|
| A: 嵌套在 actor 内 | working_memory/scene_summaries/arc_summary/critical_memories | ✓ |
| B: 独立顶级 memory 对象 | 与 actors 分离 | |
| C: 独立模块管理 | state 中只存 ID | |

**User's choice:** A A — 自动迁移 + 嵌套在 actor 对象内

---

## Claude's Discretion

- LLM 调用使用的具体模型和 prompt 模板
- 异步压缩的具体实现方式
- 场景摘要的格式细节
- `/mark` 命令的 CLI 交互设计

## Deferred Ideas

None
