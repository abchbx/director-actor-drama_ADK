# Phase 10: Coherence System - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 10-coherence-system
**Areas discussed:** 事实追踪方式, 一致性检查实现, 矛盾修复策略, 角色一致性验证

---

## 事实追踪数据结构

| Option | Description | Selected |
|--------|-------------|----------|
| A. 纯字符串 | `["朱棣已起兵"]` 最简单，与现有空壳兼容 | |
| B. 结构化对象 | `[{"fact": "...", "category": ..., "actors": [...]}]` 可检索可分类 | ✓ |
| C. 混合 | 存储结构化，展示纯文本 | |

**User's choice:** 全部由 Claude 决定
**Notes:** 选 B——与 plot_threads 模式对齐，矛盾检测可按 actors 交叉比对

## 事实创建方式

| Option | Description | Selected |
|--------|-------------|----------|
| A. 导演手动 | `add_fact()` Tool，精准无误提取 | ✓ |
| B. LLM 自动提取 | 每场 write_scene 后 LLM 提取 | |
| C. 混合 | 导演手动 + 每N场LLM补充 | |

**User's choice:** 全部由 Claude 决定
**Notes:** 选 A——与 Phase 7 create_thread 模式一致，误提取比漏提取更有害

## 一致性检查实现

| Option | Description | Selected |
|--------|-------------|----------|
| 纯启发式 | 无 LLM，文本匹配检测矛盾 | |
| LLM 驱动 | LLM 做语义判断，更精准 | |
| 启发式预筛选 + LLM | 两阶段，减少 LLM 输入量 | ✓ |

**User's choice:** 全部由 Claude 决定
**Notes:** 选两阶段——启发式筛选相关事实，LLM 做语义矛盾判断

## 矛盾修复策略

| Option | Description | Selected |
|--------|-------------|----------|
| 自动修复 | 检测到矛盾自动生成修复旁白 | |
| 导演建议 | 返回矛盾和建议，导演决定 | ✓ |
| 仅记录 | 只记录矛盾，不修复 | |

**User's choice:** 全部由 Claude 决定
**Notes:** 选导演建议——与全系统"导演建议模式"精神一致

## 角色一致性验证

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt 锚点 | 在演员上下文中注入性格+记忆+事实提醒 | ✓ |
| 代码级限制 | 拦截不一致输出 | |
| 事后审查 | 检查已输出内容的一致性 | |

**User's choice:** 全部由 Claude 决定
**Notes:** 选 Prompt 锚点——A2A 隔离架构下无法强制行为，prompt 引导最合适

## Claude's Discretion

- 所有四个领域的具体实现细节均由 Claude 自行决定
- 用户信任 Claude 的技术判断，要求快速推进

---

*Phase: 10-coherence-system*
*Discussion logged: 2026-04-13*
