# Phase 11: Timeline Tracking - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 11-timeline-tracking
**Areas discussed:** Time Representation, Time Advancement, Jump Detection, Context Presentation

---

## Time Representation

|| Option | Description | Selected |
|--------|-------------|----------|
| Descriptive only | current_time = "第三天黄昏", 纯字符串 | |
| Structured only | {day:3, period:"黄昏"}, 无描述性文本 | |
| **Hybrid** | **描述性字符串 + 结构化 time_periods 列表** | **✓** |

**User's choice:** Claude's Discretion (hybrid)
**Notes:** 描述性字符串用于 LLM/human 展示，结构化数据用于规则引擎判断。与 established_facts 的混合模式一致——既有 fact 文本，又有 category/importance 等结构化字段。

---

## Time Advancement Mechanism

|| Option | Description | Selected |
|--------|-------------|----------|
| Auto-advance per scene | advance_scene() 自动推进时间 | |
| LLM auto-infer | write_scene 后 LLM 推断时间变化 | |
| **Director manual declaration** | **advance_time() Tool 由导演显式调用** | **✓** |

**User's choice:** Claude's Discretion (manual declaration)
**Notes:** 与 Phase 10 D-07 "不使用 LLM 自动提取事实" 逻辑一致——时间判断需要创意决策，误推断比漏推断更有害。导演通过 advance_time() 显式控制，与 create_thread、add_fact 的手动模式对齐。

---

## Scene Jump Detection

|| Option | Description | Selected |
|--------|-------------|----------|
| Fixed day threshold | 固定天数阈值（如跨2天即警告） | |
| **Graduated severity** | **分3级：normal/minor/significant，基于 day gap** | **✓** |
| LLM-driven | LLM 判断跳跃是否合理 | |

**User's choice:** Claude's Discretion (graduated severity)
**Notes:** 纯规则引擎即可处理——同天正常、1-2天轻微、3+天显著。不需要 LLM 介入简单数值判断。与 Phase 10 的"启发式预筛选 + LLM 精查"不同，时间跳跃是确定性计算。

---

## Context Presentation

|| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (time only) | 仅当前时间一行 | |
| **Structured section** | **【时间线】完整段落含脉络、跳跃检测、统计** | **✓** |
| Full timeline dump | 所有 time_periods 详细展开 | |

**User's choice:** Claude's Discretion (structured section)
**Notes:** 导演需要脉络概览（不只是一行），但不能过载。_build_timeline_section() 格式参考 _build_facts_section()——统计行 + 提醒行 + 条目列表。演员上下文保持简洁（一行）。

---

## Claude's Discretion

- parse_time_description() 的实现方式
- _chinese_num_to_int() 的覆盖范围
- 上下文精确格式
- TIMELINE_JUMP_THRESHOLDS 精确值
- time_periods 保留上限
- 导演 prompt §12 具体措辞

## Deferred Ideas

- LLM 自适应时间推进
- 时间线可视化
- 用户自定义时间规则
- 时间线分支
- 时间压缩/扩展机制
- 闪回自动识别
- 时间线与天气/季节联动
