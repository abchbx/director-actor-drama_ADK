# Phase 9: Progressive STORM - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 09-progressive-storm
**Areas discussed:** 渐进融入机制, 用户触发差异化, 融入节奏与 Prompt 策略

---

## 渐进融入机制

|| Option | Description | Selected |
||--------|-------------|----------|
|| A. 新视角"待融入"状态追踪 | 新视角先放 discovered_perspectives，标记 integration_status: "pending"，2-3 场后转为"已融入"并入 storm.perspectives | |
|| B. 纯 Prompt 引导，无状态追踪 | 不新增状态字段，仅通过导演 prompt 指令引导逐步融入 | |
|| C. 混合方案：轻量状态 + Prompt | 利用已有 discovered_scene 计算新鲜度（0-2 场🆕，3+ 场常规），Prompt 引导逐步融入 | ✓ |

**User's choice:** C. 混合方案（auto-selected）
**Notes:** 利用已有 discovered_scene 字段，不新增状态。🆕 标记在 _build_dynamic_storm_section() 中计算得出，3 场后自然消失。

---

## 用户主动触发的差异化

|| Option | Description | Selected |
||--------|-------------|----------|
|| A. 无差异化 | 手动触发与自动触发行为完全一致 | |
|| B. 手动触发更紧迫 | 手动触发时 Director 优先响应，返回信息更丰富 | ✓ |
|| C. 手动触发触发额外 LLM 调用 | 手动触发生成更详细的融入计划 | |

**User's choice:** B. 手动触发更紧迫（auto-selected）
**Notes:** 差异化体现在：不受间隔限制、prompt 标注"用户主动请求"、返回值新增 integration_hint 字段。trigger_type="manual" 已有，确保 dynamic_storm() 接受并传递此参数。

---

## 融入节奏与 Prompt 策略

|| Option | Description | Selected |
||--------|-------------|----------|
|| A. "建议逐步融入" | 与导演建议模式一致，prompt 用建议性语言 | ✓ |
|| B. "必须逐步融入" | 代码级限制 Director 发现场不能以新视角驱动核心冲突 | |
|| C. 三阶段硬编码 | 第1场只能旁白暗示，第2场角色感知，第3场才能驱动 | |

**User's choice:** A. "建议逐步融入"（auto-selected）
**Notes:** 与 Phase 6/8 导演建议模式精神一致。三阶段描述（旁白暗示→角色感知→成为驱动力）作为 prompt 引导，不强制执行。

---

## Claude's Discretion

- 🆕 标记的精确格式和排版
- integration_hint 的具体措辞和模板
- Director prompt §10 更新的具体措辞和长度
- 新鲜度计算中"0-2 场"的精确边界
- dynamic_storm() 签名变更的 trigger_type 默认值和验证

## Deferred Ideas

- 自适应 STORM 间隔
- 用户自定义 STORM 主题（v2 DSTORM-06）
- 视角影响力追踪
- 多轮 STORM 对话
- 渐进融入的硬性代码强制
- 视角融合提示
