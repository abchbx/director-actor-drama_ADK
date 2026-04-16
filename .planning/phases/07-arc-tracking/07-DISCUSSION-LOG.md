# Phase 7: Arc Tracking - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 07-arc-tracking
**Areas discussed:** plot_threads与active_conflicts关系, 角色弧线追踪方式, dormant检测与导演提醒, 活跃冲突上限与resolving状态, plot_threads创建与更新时机, active_conflicts的resolve机制, arc_progress更新触发, plot_threads与演员上下文集成

---

## plot_threads 与 active_conflicts 的关系

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 独立共存 | 不破坏 Phase 6 已有代码；职责清晰；最安全 | ✓ |
| B) 吞并 | plot_threads 吞并 active_conflicts，将冲突作为线索的一个子状态 | |
| C) 引用关联 | 两者独立，通过 thread_id 可选字段关联 | |

**User's choice:** 由 Claude 决断 → A) 独立共存
**Notes:** `active_conflicts` 被 5 处代码深度消费，改动代价高。两者语义和生命周期不同：冲突是短命张力源，线索是长命故事线。冲突可通过可选 `thread_id` 关联到线索，但不强制。

---

## 角色弧线追踪方式

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 扩展 arc_summary | 在现有 arc_summary 中新增 arc_type、arc_stage、progress 字段 | |
| B) 新建独立 arc_progress 字段 | 在 state["actors"][name] 中新增独立字段，与 arc_summary 分离 | ✓ |
| C) 弧线信息放在 plot_threads 中 | 角色弧线作为特殊的 plot_thread 统一管理 | |

**User's choice:** 由 Claude 决断 → B) 新建独立 arc_progress 字段
**Notes:** `arc_summary` 是 LLM 每次重写的压缩产物，往里面加结构化字段会被覆盖。弧线追踪需要增量更新，不是 LLM 压缩的语义。放在 plot_threads 不合适——角色弧线是角色级数据。

---

## dormant 检测与导演提醒机制

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 评分后自动检测 | evaluate_tension() 每场调用时顺便检测 dormant 线索 | |
| B) 独立 Tool 函数 | 新建 check_arc_status() 专用工具，导演定期调用 | |
| C) context_builder 自动注入 | 在 build_director_context() 中自动检测并注入提醒段落 | ✓ |

**User's choice:** 由 Claude 决断 → C) context_builder 自动注入
**Notes:** dormant 提醒是被动警示灯场景，不应要求导演主动调用 Tool。与 Phase 6 的 evaluate_tension（导演主动评估）模式不同——dormant 检测应自动出现。

---

## 活跃冲突上限与线索 resolving 状态

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 软约束 | inject_conflict() 返回提醒，建议先推进线索，但不阻止注入 | ✓ |
| B) 硬约束 | 活跃冲突达上限时 inject_conflict() 直接拒绝 | |
| C) 渐进约束 | 首次提醒、再次警告、第三次强制 | |

**User's choice:** 由 Claude 决断 → A) 软约束
**Notes:** 延续 Phase 6 D-05"导演建议模式"精神。硬约束会锁死创作灵活性，戏剧创作不应被代码锁死。

---

## plot_threads 的创建与更新时机

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 导演 Tool 函数 | 导演主动调用 create_thread / update_thread | |
| B) 自动检测 + 导演确认 | write_scene 后自动提取线索建议，导演确认 | |
| C) 纯手动 | 只提供 Tool，无自动检测 | |

**User's choice:** A+C 混合——导演 Tool 为主，dormant 自动检测
**Notes:** 线索提取需要创意决策，误提取比漏提取更有害。导演主动创建更可靠。dormant 检测是纯启发式，可在 context_builder 中自动完成。

---

## active_conflicts 的 resolve 机制

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 扩展 conflict_engine | 新增 resolve_conflict() 工具，冲突移到 resolved_conflicts | |
| B) 绑定到 plot_threads | 冲突 resolve 随线索 resolve 自动完成 | |
| C) 冲突自动过期 | 冲突引入后超过 N 场自动标记 stale | |

**User's choice:** A+B 混合——扩展 conflict_engine + 可选绑定 plot_threads
**Notes:** 独立冲突（不绑定线索）也需要能被 resolve。绑定到 plot_threads 的冲突应随线索自然消解，但不自动执行——导演需确认。

---

## arc_progress 的更新触发

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 创建角色时设定弧线类型 | create_actor() 增加 arc_type 参数 | |
| B) 剧情运行中自动推断 | 根据 arc_summary.narrative 自动推断弧线类型和进展 | |
| C) 导演 Tool 手动更新 | set_actor_arc() 工具，导演随时调整 | ✓ |

**User's choice:** 由 Claude 决断 → C) 导演 Tool 手动更新
**Notes:** 最灵活且无 LLM 开销。弧线类型判断是创意决策，LLM 推断不稳定。不要求角色创建时确定弧线——戏剧乐趣在于不可预测。

---

## plot_threads 与演员上下文的集成

|| Option | Description | Selected |
|--------|-------------|----------|
| A) 只在演员上下文注入 | build_actor_context_from_memory 中新增线索段落 | |
| B) 只在导演上下文显示 | 演员通过记忆系统自然获知线索进展 | |
| C) 两层都注入 | 导演看全貌，演员只看涉及自己的 | ✓ |

**User's choice:** 由 Claude 决断 → C) 两层都注入
**Notes:** 导演是全局协调者，必须看到全部线索。演员是独立 A2A 进程，无法主动查询 plot_threads，不注入会导致远期线索被压缩后遗忘。演员只看涉及自己的 active 线索，避免干扰。

---

## Claude's Discretion

- 8 个灰色地带中 4 个由用户指定"由你决定"，Claude 选择了推荐方案
- dormant 检测选择 context_builder 自动注入，与 Phase 6 的"导演主动调用 Tool"模式形成互补
- arc_progress 选择独立字段 + 导演手动更新，避免与 LLM 压缩的 arc_summary 冲突

## Deferred Ideas

- LLM 自动推断 arc_type 和 progress
- 自动检测新 plot_threads
- plot_threads 的语义检索
- 线索进展的自动评分
- 冲突-线索双向导航
- 弧线完成时的庆贺旁白
- 多角色联合弧线
