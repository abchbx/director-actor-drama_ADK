# Phase 8: Dynamic STORM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 08-dynamic-storm
**Areas discussed:** 视角发现方式, 自动触发机制, 新视角去重, 世界观扩展边界

---

## 视角发现方式

|| Option | Description | Selected |
|--------|-------------|----------|
| LLM 自由生成 + 结构化 prompt | 将当前剧情状态组装成 prompt，LLM 自由生成 1-2 个新视角 | ✓ |
| 基于数据信号的结构化分析 + 模板 | 分析张力曲线、冲突分布，从预定义模板中选择 | |
| 混合模式 | 结构化分析提供方向建议，LLM 基于方向自由发挥 | |

**User's choice:** 全部由 Claude 决定 → 选择 LLM 自由生成 + 结构化 prompt
**Notes:** 项目核心价值"无限畅写"需要创意驱动，与 trigger_storm() 升级路径自然，灵活度最高

---

## 自动触发机制

|| Option | Description | Selected |
|--------|-------------|----------|
| 导演 prompt 引导 + suggested_action | 对齐 Phase 6 D-03 模式，evaluate_tension() 返回建议，导演主动调用 | ✓ |
| 代码级自动调用 | next_scene() 后检查计数器，自动调用 dynamic_storm() | |
| 混合模式 | 代码级计数器检查 + prompt 引导确认 | |

**User's choice:** 全部由 Claude 决定 → 选择导演 prompt 引导 + suggested_action
**Notes:** 与 Phase 6 D-03 对齐，尊重 ADK turn-based 模型，避免强制中断叙事节奏

---

## 新视角去重

|| Option | Description | Selected |
|--------|-------------|----------|
| Prompt 引导 + 轻量关键词重叠检查 | prompt 列出已有视角 + 代码级关键词对比，重叠 > 60% 标记但不阻止 | ✓ |
| 仅 Prompt 引导 | prompt 列出已有视角，完全依赖 LLM 不重复 | |
| 语义相似度检查 | 引入 NLP 库计算视角描述的语义相似度 | |
| 精确字符串匹配 | 视角名称完全相同才视为重复 | |

**User's choice:** 全部由 Claude 决定 → 选择 Prompt 引导 + 轻量关键词重叠检查
**Notes:** 不引入 NLP 库，与项目风格一致，LLM prompt 层为主 + 代码层辅助验证

---

## 世界观扩展边界

|| Option | Description | Selected |
|--------|-------------|----------|
| Prompt 引导约束 | 用剧情上下文 prompt 约束 LLM，不依赖 Phase 10 的 established_facts | ✓ |
| established_facts 前置实现 | 先实现 Phase 10 的事实追踪，Dynamic STORM 读取事实约束 | |
| 严格代码级事实检查 | 新视角生成后代码级验证与已发生事件的一致性 | |

**User's choice:** 全部由 Claude 决定 → 选择 Prompt 引导约束
**Notes:** 保持 Phase 独立性，Phase 10 的 established_facts 尚未实现，Dynamic STORM 专注创意发现，Phase 10 负责逻辑守门

---

## Claude's Discretion

All four areas were delegated to Claude's discretion by the user.

## Deferred Ideas

- LLM 自动评估视角质量
- 自适应 STORM 间隔
- 视角影响力追踪
- 用户自定义 STORM 主题（v2 需求 DSTORM-06）
- 多轮 STORM 对话
- 视角间的关联发现
- Dynamic STORM 的可视化
