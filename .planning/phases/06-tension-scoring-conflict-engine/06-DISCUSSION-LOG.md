# Phase 6: Tension Scoring & Conflict Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 06-tension-scoring-conflict-engine
**Areas discussed:** Auto-resolved (Claude's discretion)

---

## 张力评分机制

|| Option | Description | Selected |
|--------|-------------|----------|
| 纯启发式规则 | 基于 4 信号加权计算（情感方差、未决冲突密度、对话重复度、距上次注入场次数），零 LLM 调用，延迟极低 | ✓ |
| LLM 辅助评分 | 每场调用 LLM 对剧情质量做评估，精度高但 token 开销大、延迟高 | |
| 混合模式 | 启发式为主 + LLM 抽样复核，复杂度适中 | |

**User's choice:** Claude's discretion → 纯启发式规则
**Notes:** ROADMAP 明确要求"无需 LLM 调用"，且 4 信号加权方案可解释性强、零延迟

---

## 冲突注入方式

|| Option | Description | Selected |
|--------|-------------|----------|
| 导演建议模式 | `inject_conflict()` 返回结构化建议，导演 LLM 自由发挥如何融入 | ✓ |
| 强制执行模式 | 代码级自动修改 prompt，强制注入冲突事件 | |
| 半自动模式 | 低张力时自动注入框架，高张力时导演手动触发 | |

**User's choice:** Claude's discretion → 导演建议模式
**Notes:** 保证创意灵活性，导演是最终决策者；避免代码级强制导致剧情生硬

---

## 冲突去重与节奏

|| Option | Description | Selected |
|--------|-------------|----------|
| 8 场窗口去重 + 渐进升级 | 同类型 8 场内不重复；连续低张力时 prompt 紧迫感递增 | ✓ |
| 固定间隔去重 | 每隔 N 场才允许同类型冲突，简单但不灵活 | |
| 随机去重 | 随机决定是否重复使用，增加不确定性 | |

**User's choice:** Claude's discretion → 8 场窗口去重 + 渐进升级
**Notes:** 8 场约覆盖 2-3 轮完整场景循环，避免短期重复；渐进升级通过 prompt 递增紧迫感而非代码强制

---

## 张力与现有系统的集成

|| Option | Description | Selected |
|--------|-------------|----------|
| Tool 函数 + Prompt 驱动 | 注册为 Tool 函数，导演 prompt 引导每场后调用 | ✓ |
| 代码级自动触发 | write_scene() 后代码自动调用 evaluate_tension() | |
| 用户手动触发 | 用户通过 /tension 命令主动查看 | |

**User's choice:** Claude's discretion → Tool 函数 + Prompt 驱动
**Notes:** 尊重 ADK turn-based 模型；与 Phase 4 D-07 一致（导演 prompt 预留了 evaluate_tension 调用位置）

---

## Claude's Discretion

All four areas were auto-resolved by Claude based on:
- ROADMAP 成功标准的明确要求（启发式规则、无需 LLM 调用）
- 前置 Phase 已锁定决策的约束（D-04 前向兼容、D-07 预留位置）
- 项目核心价值（无限畅写，逻辑不断——创意灵活性优先）
- 架构一致性（Tool 函数模式、Prompt 驱动模式）
