# Director-Actor-Drama — 无限畅写版

## What This Is

基于 Google ADK 的多智能体即兴戏剧系统，以 A2A 协议驱动演员间通信。导演 AI 协调多个独立运行的演员 Agent，让剧情无限延伸直至用户选择结束。用户可随时注入事件改变剧情走向，系统通过动态 STORM 机制自动注入新冲突与新视角，确保剧情始终有张力、有逻辑、有连贯性。

## Core Value

**无限畅写，逻辑不断** — 剧情可以无限延续，但每一场都必须与前文逻辑连贯、情感连贯、记忆连贯。这是比「写完一部剧」难十倍的问题。

## Requirements

### Validated

<!-- 从已有代码库推断的已实现能力 -->

- ✓ Director-Actor 多智能体架构 — 导演协调多个独立 A2A 演员服务
- ✓ A2A 协议通信 — 演员间通过 A2A SDK 进行消息传递，认知边界物理隔离
- ✓ STORM 框架基础 — 4 阶段流水线（Discovery → Research → Outline → Directing）
- ✓ 角色创建与管理 — 动态生成演员代码、启动 A2A 服务、分配端口
- ✓ 场景推进与旁白 — 导演旁白 + 演员对话 + 场景记录
- ✓ 状态持久化 — 双层存储（内存 ADK state + 文件系统 JSON），支持保存/加载
- ✓ 用户事件注入 — `/action` 命令允许用户注入事件
- ✓ 剧本导出 — Markdown 格式导出完整剧本和对话记录
- ✓ 3 层记忆架构 — 工作记忆/场景摘要/全局摘要，逐级压缩（Validated in Phase 1: Memory Foundation）
- ✓ 自动记忆压缩 — 异步 LLM 压缩，不阻塞主流程（Validated in Phase 1: Memory Foundation）
- ✓ 重要性权重摘要 — 关键记忆标记与保留，6 类关键事件检测（Validated in Phase 1: Memory Foundation）

### Active

<!-- 本次迭代要构建的核心能力 -->

- [ ] 无限畅写引擎 — 剧情不再受预设大纲约束，可以无限延续，每场戏自然衔接
- [ ] 混合推进模式 — AI 自主推进剧情 + 用户随时可注入事件/转向，两者无缝切换
- [ ] 动态 STORM 机制 — 每 N 场自动重新发现新视角、注入新冲突、扩展世界观
- [ ] 冲突引擎 — 自动检测剧情平淡时注入转折事件（新角色、意外、矛盾升级）
- [ ] 上下文窗口管理 — 控制每场戏传入 LLM 的上下文大小，防止质量退化

### Out of Scope

- [ ] 多用户协作 — 当前仅支持单用户交互
- [ ] 语音/视频输出 — 仅文本交互
- [ ] 自定义 LLM 模型选择 — 使用系统默认模型
- [ ] Web UI — 当前仅 CLI 交互

## Context

### 现有代码库状态

- **架构**: Director-Actor 多智能体，导演通过 StormRouter 路由到 4 个 STORM 子 Agent
- **通信**: A2A 协议（a2a-sdk 0.3.x），演员运行在独立 uvicorn 进程
- **状态**: `state_manager.py` 管理所有戏剧状态，双层持久化（内存 + JSON 文件）
- **工具**: `tools.py` 提供 18+ 工具函数，涵盖戏剧生命周期和 STORM 流程
- **LLM**: 通过 LiteLlm 接入，默认使用 OpenAI 兼容 API

### 核心技术挑战

1. **上下文窗口有限 vs 剧情无限** — 50 场戏后，将所有记忆塞入 prompt 不可行。需要智能的上下文压缩策略
2. **A2A 通信开销** — 每次演员对话都是一次 HTTP 调用，需要控制调用频率
3. **动态 STORM 触发时机** — 如何判断「当前剧情需要注入新冲突」而非机械地每 N 场触发
4. **记忆一致性** — 远期记忆压缩为摘要后，演员可能「遗忘」关键细节导致逻辑矛盾

### 已知问题

- `actor_speak` 中曾有 UnboundLocalError（已修复）
- 全局状态 `_current_drama_folder` 在多实例场景下可能冲突
- 演员端口管理使用递增分配，无回收机制
- 测试覆盖率极低（仅 1 个 dummy 测试 + 1 个集成测试骨架）

## Constraints

- **Tech Stack**: Python 3.10+, Google ADK >=1.15.0, a2a-sdk ~=0.3.22 — 已锁定
- **LLM 上下文窗口**: 约 200K tokens，超过此限制质量退化 — 决定记忆策略上限
- **A2A 进程隔离**: 每个演员是独立进程，通信必须通过 A2A 协议 — 无法共享内存
- **单用户模式**: 当前架构不支持多用户并发 — 不在此次范围

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 混合推进模式 | 用户需要自由度，纯 AI 推进会失控，纯用户驱动会中断沉浸感 | — Pending |
| 动态 STORM 替代静态 STORM | 静态大纲限制了剧情长度，动态视角发现让剧情可无限生长 | — Pending |
| 分层记忆而非全量记忆 | 上下文窗口有限，全量记忆 50 场后不可行 | — Pending |
| 保留 A2A 进程隔离 | 认知边界隔离是核心价值，不可为了性能牺牲 | — Pending |
| 保留文件系统持久化 | JSON 文件持久化简单可靠，不需要引入数据库 | — Pending |

---

*Last updated: 2026-04-11 after Phase 1 completion*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
