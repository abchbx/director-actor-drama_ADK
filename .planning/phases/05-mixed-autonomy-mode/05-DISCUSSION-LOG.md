# Phase 5: Mixed Autonomy Mode - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 05-mixed-autonomy-mode
**Areas discussed:** 自动推进模式, 用户引导与干预, 终幕与结束机制, 场景后选项呈现, /storm定位, 自动中干预, /auto参数, 状态持久化, 番外篇模式, 导演Prompt重构

---

## 自动推进模式（/auto [N]）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. Prompt 驱动循环 | LLM 在 prompt 中被告知连续执行 N 场 | |
| B. 代码层循环 | Python while loop 调度 N 轮 | |
| C. 混合模式 | Prompt 驱动 + 代码级计数器 remaining_auto_scenes | ✓ |

**User's choice:** 混合模式（Claude's Discretion）
**Notes:** 尊重 ADK turn-based 模型，同时有代码级防护防止失控

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 任意输入中断 | 用户输入任何非空消息即中断，视为 /action | ✓ |
| B. /stop 显式中断 | 必须输入 /stop 才中断 | |
| C. 每场暂停点 | 每场后短暂暂停等待中断 | |

**User's choice:** 任意输入中断（Claude's Discretion）
**Notes:** 用户体验最自然，中断后视为 /action 事件注入

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 场景间短暂间隔 | 每场后插入提示行 | ✓ |
| B. 无间隔连续输出 | 只用分隔线 | |
| C. 每 K 场汇报 | 每 3 场输出摘要 | |

**User's choice:** 场景间短暂间隔（Claude's Discretion）

---

## 用户引导与干预（/steer）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. steer=方向/action=事件 | steer 给方向导演自由发挥，action 给事件必须执行 | ✓ |
| B. steer=轻量/action=强制 | steer 考虑但不保证执行 | |
| C. 合并为一个命令 | 自动判断权重 | |

**User's choice:** steer=方向/action=事件（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 注入 next_scene() 返回值 | 附加 steer_direction 字段 | |
| B. 注入 build_director_context() | 新增【用户引导】段落 | ✓ |
| C. 两者结合 | next_scene + director_context 双重注入 | |

**User's choice:** 注入 build_director_context()（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 仅下一场 | 自动清除 | ✓ |
| B. 持续 N 场 | 用户指定场数 | |
| C. 持续至取消 | /steer off 或新 steer 替换 | |

**User's choice:** 仅下一场（Claude's Discretion）

---

## 终幕与结束机制（/end）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 旁白 + 导出合一 | 两步合一，用户体验最顺畅 | ✓ |
| B. 旁白 + 确认 + 导出 | 给用户反悔机会 | |
| C. 仅设置结束标记 | 用户需手动 /export | |

**User's choice:** 旁白+导出合一（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. LLM 自由生成 | 完全交给导演创造力 | |
| B. 模板 + LLM 填充 | 预置结构，LLM 填内容 | ✓ |
| C. 纯模板 | 固定格式 | |

**User's choice:** 模板 + LLM 填充（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 不可继续 | /end 是终态 | |
| B. 可继续（番外篇） | /end 后可 /next，标注番外 | ✓ |
| C. 自动保存后可 /load 继续 | 结束时存档 | |

**User's choice:** 可继续番外篇（Claude's Discretion）
**Notes:** 同时自动保存存档，方便回溯正式结局前状态

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 新增 end_drama() Tool | 独立函数，明确入口 | ✓ |
| B. 复用 set_drama_status + prompt | 不新增函数 | |

**User's choice:** 新增 end_drama() 独立函数（Claude's Discretion）

---

## 场景后选项呈现

|| Option | Description | Selected |
|--------|-------------|----------|
| A. Prompt 驱动 | LLM 自由发挥 | |
| B. Tool 函数生成 | 新增 generate_scene_options() | |
| C. Prompt 驱动 + 格式约束 | 结构化格式约束输出 | ✓ |

**User's choice:** Prompt 驱动 + 格式约束（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 剧情方向选择 | "A. 政变 / B. 隐忍" | |
| B. 混合型 | 剧情方向 + 操作指引 | ✓ |
| C. 纯操作型 | "继续/注入/结束" | |

**User's choice:** 混合型（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 仅自动模式 | 手动模式不需要 | |
| B. 所有模式 | 降低参与门槛 | ✓ |
| C. 默认开启可关闭 | /options off | |

**User's choice:** 所有模式（Claude's Discretion）

---

## /storm 轻量版定位

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 完整 Dynamic STORM | Phase 5 就实现完整版 | |
| B. 轻量 STORM 占位 | 命令入口 + 简单审视 prompt | ✓ |
| C. 延迟到 Phase 8 | Phase 5 不做 /storm | |

**User's choice:** 轻量 STORM 占位（Claude's Discretion）
**Notes:** 满足 ROADMAP 成功标准"用户可通过 /storm 手动触发视角发现"，但内部逻辑是轻量版

---

## 自动推进中用户干预

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 中断 + 视为 action | 输入 = 中断 + 事件注入 | ✓ |
| B. 中断 + 纯引导 | 只中断不自动注入 | |
| C. 智能判断 | 根据内容语义判断 action/steer | |

**User's choice:** 中断 + 视为 action（Claude's Discretion）

---

## /auto 参数与边界

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 默认 3 场 | 安全起步 | ✓ |
| B. 默认 5 场 | 更长自主空间 | |
| C. 无限（到中断） | /auto 无上限 | |

**User's choice:** 默认 3 场（Claude's Discretion）

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 无上限 | 用户自由决定 | |
| B. 硬上限 20 场 | 超过拒绝 | |
| C. 软上限 10 场 + 警告 | 超过提示确认 | ✓ |

**User's choice:** 软上限 10 场 + 警告（Claude's Discretion）

---

## 状态持久化设计

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 散布在 drama 顶层 | 简单直接 | |
| B. 分组到子对象 | 结构清晰 | |
| C. 混合 | 高频放顶层，关联的分组 | ✓ |

**User's choice:** 混合（Claude's Discretion）
**Notes:** remaining_auto_scenes/steer_direction 放顶层，storm 分组

---

## 番外篇模式

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 无变化 | 导演不知道已结束 | |
| B. 轻量标记 | director_context 附加番外篇提示 | ✓ |
| C. 完全不同 prompt | 独立番外 prompt 模板 | |

**User's choice:** 轻量标记（Claude's Discretion）

---

## 导演 Prompt 重构

|| Option | Description | Selected |
|--------|-------------|----------|
| A. 增量修改 | 追加新段落 | |
| B. 重构重写 | 统一编排结构 | ✓ |
| C. 分层 prompt | 核心不变，动态部分 Tool 注入 | |

**User's choice:** 重构重写（Claude's Discretion）
**Notes:** 当前 prompt 已 160+ 行且 Phase 4 写的过渡性内容自相矛盾，统一编排更清晰

---

## Claude's Discretion

- _improv_director 重构后 prompt 的具体措辞和长度
- auto_advance() 计数器递减的精确触发时机
- steer_drama() 返回的确认信息格式
- end_drama() 终幕旁白模板的具体文本结构
- trigger_storm() 轻量版审视的具体 prompt 内容
- 场景后选项的精确格式
- 选项中剧情方向 vs 操作指引的比例
- 自动推进中断后的过渡提示
- 软上限警告的具体措辞

## Deferred Ideas

- /auto 无限模式（无上限直到用户中断）— 后续增强
- 完整 Dynamic STORM — Phase 8
- 渐进式 STORM — Phase 9
- /steer <direction> N 持续 N 场语法 — 后续增强
- 场景后选项的 Tool 函数生成方式 — 后续若质量不稳定可改为 Tool 函数
- /stop 显式中断命令 — 后续增强
- 代码级循环（Python while loop）— 违背 ADK 模型
- 多用户并发干预 — Out of Scope
