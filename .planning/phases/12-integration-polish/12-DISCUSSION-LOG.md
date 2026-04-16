# Phase 12: Integration & Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 12-integration-polish
**Areas discussed:** 端到端测试策略, 已知 Bug 修复, 性能优化, CLI 优化 & 演员健康检查

---

## 端到端测试策略

| Option | Description | Selected |
|--------|-------------|----------|
| Mock LLM | 预设响应模拟，确定性高、速度快 | |
| 真实 LLM | 调用真实 API，验证完整交互 | ✓ |
| 混合模式 | 核心 Mock，关键点真实 LLM | |

**User's choice:** 真实 LLM
**Notes:** 用户选择真刀真枪测试，不做假把式

| Option | Description | Selected |
|--------|-------------|----------|
| 逐场断言 | 每场写断言，全面但脆弱 | |
| 里程碑断言 | 关键节点验证状态，稳健 | ✓ |
| 全量快照 | 每场记录完整 state 比对 | |

**User's choice:** 里程碑断言
**Notes:** LLM 输出不可预测，逐场断言太脆弱

| Option | Description | Selected |
|--------|-------------|----------|
| 关键路径覆盖 | 最重要的跨模块交互 | ✓ |
| 全路径覆盖 | 每对模块交互都测试 | |

**User's choice:** 关键路径覆盖
**Notes:** 全路径 ROI 太低

---

## 已知 Bug 修复

| Option | Description | Selected |
|--------|-------------|----------|
| 全局状态根除 | 彻底解决，改动面大 | |
| 最小修复 | 只修 actor_speak，全局状态加注释 | |
| 渐进式修复 | 先修 actor_speak + conversation_log，current_drama_folder 延后 | ✓ |

**User's choice:** 渐进式修复
**Notes:** 由 Claude 决定，选择务实战法——影响最大的先修，风险低的延后

---

## 性能优化

| Option | Description | Selected |
|--------|-------------|----------|
| Debounce 2s | 更频繁写盘，崩溃丢更少 | |
| Debounce 5s | 平衡选择 | ✓ |
| Debounce 10s | 更少写盘，崩溃丢更多 | |

**User's choice:** Debounce 5s
**Notes:** 由 Claude 决定，5 秒是平衡点

| Option | Description | Selected |
|--------|-------------|----------|
| 归档阈值 10 场 | 更早归档 | |
| 归档阈值 20 场 | 平衡选择 | ✓ |
| 归档阈值 30 场 | 更晚归档 | |

**User's choice:** 归档阈值 20 场
**Notes:** 由 Claude 决定，20 场后 state 开始膨胀

| Option | Description | Selected |
|--------|-------------|----------|
| Director + Actor 共享 AsyncClient | 两端都共享 | |
| 仅 Director 共享 | Director 端共享，Actor 端不改 | ✓ |
| 不共享 | 保持现状 | |

**User's choice:** 仅 Director 共享
**Notes:** Actor 是独立进程，改动收益小

---

## CLI 优化 & 演员健康检查

| Option | Description | Selected |
|--------|-------------|----------|
| Spinner + 场景摘要 + 错误提示 | 三项全上 | ✓ |
| 仅 Spinner | 最小改善 | |
| 仅错误提示 | 最小改善 | |

**User's choice:** 三项全上
**Notes:** 由 Claude 决定

| Option | Description | Selected |
|--------|-------------|----------|
| 被动检测 | actor_speak 失败时检测 | ✓ |
| 主动心跳 | 定期 ping actor 端口 | |

**User's choice:** 被动检测
**Notes:** 由 Claude 决定，主动心跳过度设计

| Option | Description | Selected |
|--------|-------------|----------|
| 自动重启 | 检测崩溃后自动重建 | ✓ |
| 手动恢复 | 仅提示用户 | |

**User's choice:** 自动重启
**Notes:** 由 Claude 决定，3 次上限防无限重启

---

## Claude's Discretion

- `_conversation_log` 迁移的具体实现细节
- `archive_old_scenes()` 的归档文件格式
- Spinner 的具体实现库选择
- 场景摘要的精确格式
- `_restart_actor()` 的具体错误恢复流程
- 共享 AsyncClient 的连接池大小和 timeout 配置
- Debounce 实现方式（asyncio.Timer vs threading.Timer）
- `actor_speak()` 算符优先级 bug 的精确修复方式

## Deferred Ideas

- `_current_drama_folder` 全局变量迁移
- 主动心跳健康检查
- Mock LLM E2E 测试套件
- 自适应 debounce 间隔
- 场景归档压缩
- 并行 actor_speak
- Web UI / 多用户支持
