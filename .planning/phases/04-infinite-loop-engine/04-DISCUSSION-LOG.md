# Phase 4: Infinite Loop Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 04-infinite-loop-engine
**Areas discussed:** Router 架构, 循环驱动, 场景衔接, Setup 过渡

---

## Router 架构

### Router 演化方向

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 保留 BaseAgent，2 子 Agent | 保留 BaseAgent 子类模式，只保留 setup_agent + improv_director | ✓ |
|| B: 保留 BaseAgent，1 子 Agent | 只保留 1 个合并后的 drama_agent，不再区分阶段 | |
|| C: 换用 ADK LoopAgent | 使用 ADK 的 LoopAgent 模式实现循环 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 改动最小，风险最低，保留路由灵活性

### Setup 阶段合并粒度

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 3→1 合并 | discover + research + outline 合并为单个 _setup_agent | ✓ |
|| B: 3→2 合并 | 合并 discover+research 为 explorer，保留 outliner 分开 | |

**User's choice:** A（由 Claude 决定）
**Notes:** Setup 是一次性流程，拆3个Agent是过度设计

### Fallback 策略

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 默认路由到 improv_director | 最安全的兜底 | ✓ |
|| B: 抛出明确错误 | 严格但可能中断用户体验 | |
|| C: 按消息内容推断 | 逻辑复杂，容易误判 | |

**User's choice:** A（由 Claude 决定）

### 路由判断依据

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 按 actors 存在性 | state["actors"] 非空 → improvise | ✓ |
|| B: 按 status 简化 | 只设 "setup" / "improvising" 两值 | |
|| C: 两者结合 | actors + status 双条件 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 简单可靠，actors 存在即意味着角色已创建可演出

---

## 循环驱动

### 循环驱动力

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: System Prompt 驱动 | _improv_director prompt 中写明调用序列，LLM 自主按序调用 | ✓ |
|| B: 代码级循环 | DramaRouter 中 while 循环，单次用户输入自动产生多场戏 | |
|| C: 混合 | Prompt 驱动核心，next_scene() 返回引导信息 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 符合 ADK turn-based 模型，无需改框架

### 循环终止条件

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 每场等待用户 | /next 继续、/action 注入、/end 结束 | ✓ |
|| B: 自动推进 N 场 | /auto 5 自动推进 5 场 | |
|| C: 永远自动 | 除非用户打断否则一直推进 | |

**User's choice:** A（由 Claude 决定）
**Notes:** Phase 5 实现混合推进模式，Phase 4 保持简单

### 场景后评估步骤

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: Prompt 提示但代码不强制 | prompt 中提示导演每场后回顾局势 | ✓ |
|| B: 代码中强制调用评估 | write_scene() 末尾自动调用评估函数 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 灵活预留 Phase 6 evaluate_tension() 接口

---

## 场景衔接

### 衔接信息来源

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 增强 build_director_context() | 增加上一场结局摘要段落 | ✓ |
|| B: 新增 scene_transition_hints() 工具 | 独立工具函数 | |
|| C: 在 next_scene() 返回值中嵌入 | 改动最小但返回值已较复杂 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 复用现有模块，不引入新概念

### 衔接信息粒度

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 精简三要素 | ①上一场结局(1-2句) ②角色情绪状态 ③未决事件/悬念 | ✓ |
|| B: 完整上一场摘要 | 约150-200字场景摘要 + 情绪 + 未决事件 | |
|| C: 仅依赖记忆系统 | 不做额外衔接 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 精炼不占 token 预算

### 衔接信息组织

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: next_scene() 返回衔接段落 | 工具调用是每场必经步骤，零遗漏 | |
|| B: 导演自行调用 get_director_context() | 依赖 LLM 自主获取 | |
|| C: 两者结合 | next_scene() 返回精简衔接 + 可选全局视野 | ✓ |

**User's choice:** C（由 Claude 决定）
**Notes:** next_scene() 返回衔接要点（必看），get_director_context() 返回全局摘要（可选）

---

## Setup→Improvise 过渡

### Setup 完成判定

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 演员创建完毕即完成 | state["actors"] 非空 | ✓ |
|| B: 用户显式确认 | 询问"是否开始演出？" | |
|| C: 大纲+演员双条件 | 大纲已合成 AND 演员已创建 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 与 D-04 路由逻辑天然一致

### /start 流程

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 一站式 Setup | _setup_agent 单轮完成全部 setup | ✓ |
|| B: 多轮 Setup | 保留逐步推进模式 | |
|| C: 可选快/慢模式 | /start --quick 一站式 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 体验流畅，合并后 Agent 有完整工具集可自主完成

### 首次引导

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: next_scene() 返回 is_first_scene 标记 | current_scene==0 时标注 | ✓ |
|| B: 依赖导演自行判断 | 通过 get_director_context() 看场景号 | |
|| C: Setup Agent 交接 | _setup_agent 写入 setup_summary | |

**User's choice:** A（由 Claude 决定）
**Notes:** 简单标记，导演可据此调整风格

### 旧状态兼容

|| Option | Description | Selected |
||--------|-------------|----------|
|| A: 加载时自动升级状态 | 有 actors→acting，无→setup | ✓ |
|| B: 新旧状态映射表 | 维护旧→新状态映射 | |
|| C: 忽略旧状态 | 彻底不再依赖 status 字段 | |

**User's choice:** A（由 Claude 决定）
**Notes:** 用户无感迁移，与路由逻辑一致

---

## Claude's Discretion

- _setup_agent 和 _improv_director 的 system prompt 具体措辞和长度
- _setup_agent 内部步骤的详细编排
- build_director_context() 增强段落的具体格式
- next_scene() 返回值中衔接信息的精确字段名
- 旧 STORM 工具的保留/废弃策略

## Deferred Ideas

- /auto N 自动推进 N 场 — Phase 5
- evaluate_tension() 张力评分 — Phase 6
- inject_conflict() 冲突注入 — Phase 6
- /storm 命令和 Dynamic STORM — Phase 8
- /steer <direction> 轻量引导 — Phase 5
- /end 终幕旁白 — Phase 5 (LOOP-04)
- 代码级 while 循环 — 违背 ADK 模型，不建议
