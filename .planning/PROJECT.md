# Director-Actor-Drama — 无限畅写版

## What This Is

基于 Google ADK 的多智能体即兴戏剧系统，以 A2A 协议驱动演员间通信。导演 AI 协调多个独立运行的演员 Agent，让剧情无限延伸直至用户选择结束。用户可随时注入事件改变剧情走向，系统通过动态 STORM 机制自动注入新冲突与新视角，确保剧情始终有张力、有逻辑、有连贯性。v1.0 已交付，包含 12 个核心模块、517 个测试、9,560 行 Python 代码。

## Core Value

**无限畅写，逻辑不断** — 剧情可以无限延续，但每一场都必须与前文逻辑连贯、情感连贯、记忆连贯。

## Current State

**Shipped:** v1.0 — 2026-04-14
**Phases:** 12 phases, 29 plans, all complete
**Tests:** 577 passed (unit + integration + E2E)
**LOC:** ~9,560 lines Python (app/)
**Phase 13:** API Foundation complete — 2026-04-15 (14 REST endpoints, FastAPI, lock file, state migration)
**Phase 14:** WebSocket Layer complete — 2026-04-15 (18 event types, EventBridge, replay buffer, heartbeat)
**Phase 15:** Authentication complete — 2026-04-16 (Bearer token auth, dev mode bypass, WS token validation)

## Requirements

### Validated

- ✓ Director-Actor 多智能体架构 — 导演协调多个独立 A2A 演员服务
- ✓ A2A 协议通信 — 演员间通过 A2A SDK 消息传递，认知边界物理隔离
- ✓ 3 层记忆架构 — 工作记忆/场景摘要/全局摘要，逐级压缩 — v1.0
- ✓ 自动记忆压缩 — 异步 LLM 压缩，不阻塞主流程 — v1.0
- ✓ 重要性权重摘要 — 关键记忆标记与保留，6 类关键事件检测 — v1.0
- ✓ 上下文构建器 — 全局摘要 + 近期场景 + 工作记忆 + 导演指令，token 控制预算内 — v1.0
- ✓ 语义检索 — 标签/关键词/角色名/事件类型检索历史记忆 — v1.0
- ✓ 无限畅写引擎 — 剧情不再受预设大纲约束，每场戏自然衔接 — v1.0
- ✓ 混合推进模式 — AI 自主推进 + 用户随时注入事件/转向无缝切换 — v1.0
- ✓ 用户终止机制 — `/end` 命令触发终幕旁白和完整剧本导出 — v1.0
- ✓ 动态 STORM 机制 — 每 N 场自动重新发现新视角、注入新冲突、扩展世界观 — v1.0
- ✓ 渐进式 STORM — 每次仅注入 1-2 个新视角，避免过载 — v1.0
- ✓ 冲突引擎 — 张力评分 + 低张力自动注入 + 7 种冲突模板 + 冲突去重 — v1.0
- ✓ 弧线追踪 — 角色弧线和故事弧线完成度追踪，dormant 提醒 — v1.0
- ✓ 一致性检查 — validate_consistency() + established_facts + 矛盾修复 — v1.0
- ✓ 关键事实追踪 — 结构化事实清单，自动检查与矛盾修复 — v1.0
- ✓ 角色一致性 — actor_dna 锚点段落，行为符合性格和记忆 — v1.0
- ✓ 时间线追踪 — 描述性时间 + 结构化时间线 + 场景跳跃检测 — v1.0
- ✓ 状态持久化 — 双层存储 + debounce + 场景归档 — v1.0
- ✓ 演员崩溃恢复 — 被动检测 + 自动重启 + MAX_CRASH_COUNT=3 — v1.0
- ✓ CLI 优化 — Rich spinner + 场景摘要 + 中文错误提示 — v1.0

### Active

- [ ] FastAPI API Server — REST + WebSocket 双协议，为前端客户端提供统一接口
- [ ] WebSocket 实时推送 — 场景生成、旁白、演员对白实时推送到客户端
- ✓ 简单 Token 认证 — 局域网/单用户场景，Bearer token + dev mode bypass — Phase 15
- [ ] Android App (Kotlin + Jetpack Compose) — Material Design 3 风格的戏剧交互客户端
- [ ] 场景浏览与交互 — 查看场景历史、注入事件、推进剧情、角色对话
- [ ] 剧本管理 — 创建/保存/加载/导出剧本
- [ ] 演员状态面板 — 查看演员列表、A2A 服务状态、记忆摘要

### Out of Scope

- 多用户协作 — 当前架构为单用户设计，A2A 隔离不支持多用户会话共享
- 语音/视频输出 — 仅文本交互，多模态需要额外基础设施
- 自定义 LLM 模型选择 UI — 使用系统默认模型配置
- 向量数据库集成 — v1 使用 3 层 JSON 记忆，ChromaDB/FAISS 作为未来升级路径
- 离线模式 — 后端是唯一计算源（LLM + A2A），离线无意义
- iOS 客户端 — 本里程碑聚焦 Android
- 多用户认证系统 — 简单 Token 足够，不做 OAuth/注册系统
- 推送通知 — 场景推送通过 WebSocket 实时完成，无需 FCM

## Current Milestone: v2.0 Android 移动端

**Goal:** 为 director-actor-drama 添加 C/S 架构支持，Python 后端提供 API Server，Android App 作为纯 UI 客户端

**Target features:**
- FastAPI REST + WebSocket API Server
- Kotlin + Jetpack Compose Android App (Material Design 3)
- 混合通信：REST 发命令，WebSocket 接收场景实时推送
- 简单 Token 认证（局域网/单用户）
- 纯在线模式

## Context

### 代码库状态 (v1.0 shipped)

- **架构**: DramaRouter (setup + improvise 双阶段)，12 个核心模块
- **通信**: A2A 协议（a2a-sdk 0.3.x），演员独立 uvicorn 进程
- **状态**: `state_manager.py` + debounce + 场景归档
- **工具**: `tools.py` 30+ 工具函数
- **LLM**: LiteLlm + 共享 AsyncClient
- **测试**: 517 passed (unit + integration + E2E)

### 已知技术债

- `_current_drama_folder` 全局变量迁移未完成（D-07 TODO）
- E2E 测试需要真实 LLM API
- 演员端口管理使用递增分配，无回收机制

## Constraints

- **Tech Stack**: Python 3.10+, Google ADK >=1.15.0, a2a-sdk ~=0.3.22
- **LLM 上下文窗口**: 约 200K tokens
- **A2A 进程隔离**: 每个演员独立进程
- **单用户模式**: 不支持多用户并发

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 混合推进模式 | 用户需要自由度 | ✓ Good — 无缝切换已实现 |
| 动态 STORM 替代静态 STORM | 静态大纲限制剧情长度 | ✓ Good — 视角无限发现 |
| 分层记忆而非全量记忆 | 上下文窗口有限 | ✓ Good — 50+ 场戏稳定 |
| 保留 A2A 进程隔离 | 认知边界隔离是核心价值 | ✓ Good — 物理隔离无妥协 |
| 保留文件系统持久化 | JSON 简单可靠 | ✓ Good — 无需数据库 |
| Debounce 状态保存 | 频繁 IO 浪费资源 | ✓ Good — 5 秒防抖 |
| 共享 AsyncClient | 连接泄漏风险 | ✓ Good — 懒单例 + 自动重建 |
| 被动崩溃检测 | 主动轮询浪费资源 | ✓ Good — 连接错误触发重启 |
| C/S 架构 (FastAPI + Android) | Python 后端不可替代(google-adk, a2a-sdk)，移动端仅做 UI | — Pending |
| REST + WebSocket 混合通信 | REST 适合命令式操作，WebSocket 适合 LLM 长等待推送 | — Pending |
| 简单 Token 认证 | 单用户/局域网场景，无需 OAuth 复杂度 | — Pending |
| 纯在线模式 | 后端是唯一计算源，离线无意义 | — Pending |

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
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-04-14 after v2.0 milestone start*
