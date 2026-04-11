# CHANGELOG v1 — STORM Framework Migration

## 版本: v1.0.0-STORM

**日期**: 2026-04-10

**变更类型**: 架构重构 — 导演 Agent 采用 STORM 框架

---

## 概述

将导演-演员戏剧创作系统（Director-Actor Drama System）的导演 Agent 从单一单体 Agent 重构为基于 **STORM（Synthesis of Topic Outlines through Retrieval and Multi-perspective Question Asking）框架** 的多阶段智能体架构。

### 什么是 STORM？

STORM 是一种结构化的主题探索与内容生成框架，最初由斯坦福大学提出用于长篇文章写作。其核心思想是：

1. **多视角发现**（Discovery）：从多个不同视角提出探索性问题
2. **深度研究**（Research）：针对每个视角进行深入挖掘
3. **大纲合成**（Outline Synthesis）：将多视角研究结果融合为结构化大纲
4. **内容生成**（Content Generation）：基于大纲生成完整内容

### 为什么引入 STORM？

| 维度 | v0（原架构） | v1（STORM 架构） |
|------|-------------|-----------------|
| 创作方式 | 线性头脑风暴 | 多视角并行探索 → 辩证融合 |
| 大纲质量 | 单一视角，易偏颇 | 多视角碰撞，张力更强 |
| 角色深度 | 角色设计依赖导演直觉 | 每个角色承载多视角内涵 |
| 主题深度 | 表层+中层 | 表层+中层+深层（哲学维度） |
| 戏剧冲突 | 依赖线性推进 | 冲突来自视角间的矛盾与统一 |
| 可扩展性 | 单 Agent，指令膨胀 | 多 Agent 分阶段，职责清晰 |

---

## 架构变更

### v0 架构（原版）

```
root_agent (Agent)
  └── director —— 单一 Agent，集头脑风暴+剧本编写+旁白+导演于一身
       ├── tools: start_drama, create_actor, actor_speak, ...
       └── instruction: ~2000 token 的超长指令
```

### v1 架构（STORM）

```
root_agent (StormRouter — BaseAgent)
  ├── storm_discoverer (Agent) — STORM Phase 1: 多视角发现
  │    └── tools: start_drama, storm_discover_perspectives
  ├── storm_researcher (Agent) — STORM Phase 2: 深度研究
  │    └── tools: storm_ask_perspective_questions, storm_research_perspective
  ├── storm_outliner (Agent) — STORM Phase 3: 大纲合成
  │    └── tools: storm_synthesize_outline, create_actor
  └── storm_director (Agent) — STORM Phase 4: 场景执行
       └── tools: create_actor, actor_speak, director_narrate, write_scene, ...
```

**核心设计决策**：

- **`StormRouter`**（自定义 `BaseAgent`）：根据 `drama.status` 将用户消息路由到正确的 STORM 阶段 Agent
- **每个阶段 Agent 独立**：拥有自己的指令集和工具集，职责单一
- **通过共享 state 传递数据**：视角列表、研究结果、大纲均存储在 `drama.storm` 中
- **A2A 架构不变**：演员仍然是独立 A2A 服务，认知边界通过物理隔离保证

---

## 文件变更明细

### `app/agent.py` — **重写**

| 变更 | 描述 |
|------|------|
| 删除 | 单一 `root_agent = Agent(name="director", ...)` |
| 新增 | `_storm_discoverer` Agent — STORM Phase 1 |
| 新增 | `_storm_researcher` Agent — STORM Phase 2 |
| 新增 | `_storm_outliner` Agent — STORM Phase 3 |
| 新增 | `_storm_director` Agent — STORM Phase 4 |
| 新增 | `StormRouter(BaseAgent)` — 基于 state 的路由器 |
| 新增 | `root_agent = StormRouter(...)` — 新的根 Agent |
| 修改 | 新增导入: `BaseAgent`, `InvocationContext`, `Event`, `EventActions`, `AsyncGenerator` |
| 修改 | 新增导入: STORM 工具函数 |

### `app/tools.py` — **扩展**

| 变更 | 描述 |
|------|------|
| 修改 | 文件文档字符串增加 STORM 框架说明 |
| 修改 | 新增导入: `storm_add_perspective`, `storm_add_research_result`, `storm_get_perspectives`, `storm_get_research_results`, `storm_set_outline`, `storm_get_outline` |
| 新增 | `storm_discover_perspectives(theme, tool_context)` — 生成 5 个探索视角 |
| 新增 | `storm_ask_perspective_questions(perspective, theme, tool_context)` — 为特定视角生成深入问题 |
| 新增 | `storm_research_perspective(perspective, questions, tool_context)` — 深度研究视角 |
| 新增 | `storm_synthesize_outline(theme, tool_context)` — 合成多视角为戏剧大纲 |

### `app/state_manager.py` — **扩展**

| 变更 | 描述 |
|------|------|
| 新增 | `storm_add_perspective()` — 添加视角到 STORM 数据 |
| 新增 | `storm_get_perspectives()` — 获取所有视角 |
| 新增 | `storm_add_research_result()` — 添加研究结果 |
| 新增 | `storm_get_research_results()` — 获取所有研究结果 |
| 新增 | `storm_set_outline()` — 保存合成大纲 |
| 新增 | `storm_get_outline()` — 获取合成大纲 |
| 修改 | `save_progress()` — 新增 `storm` 字段序列化 |
| 修改 | `export_script()` — 新增 STORM 大纲章节导出 |

---

## 状态机变更

### v0 状态

```
brainstorming → acting → completed
                  ↕
                paused
```

### v1 状态（STORM）

```
storm_discovering → storm_researching → storm_outlining → acting → completed
                                                              ↕
                                                            paused
```

**新增状态**：

| 状态 | 路由目标 | 描述 |
|------|---------|------|
| `storm_discovering` | `_storm_discoverer` | 多视角发现阶段 |
| `storm_researching` | `_storm_researcher` | 深度研究阶段 |
| `storm_outlining` | `_storm_outliner` | 大纲合成阶段 |

**兼容性**：`brainstorming` 状态自动路由到 `_storm_discoverer`，保证向后兼容。

---

## STORM 数据结构

存储在 `drama.storm` 中：

```json
{
  "perspectives": [
    {
      "name": "主角视角",
      "description": "从主角的内心世界出发...",
      "questions": ["问题1", "问题2", "问题3"]
    }
  ],
  "research_results": [
    {
      "perspective": "主角视角",
      "questions": ["问题1", "问题2"],
      "findings": {
        "角色原型": "...",
        "冲突模式": "...",
        "情感曲线": "...",
        "意象符号": "...",
        "跨视角联系": "..."
      },
      "timestamp": "2026-04-10T..."
    }
  ],
  "outline": {
    "theme": "太空探险",
    "synthesis_strategy": "多视角辩证融合",
    "acts": [
      {
        "act_number": 1,
        "title": "起——多视角的碰撞",
        "description": "...",
        "key_conflict": "...",
        "emotional_arc": "好奇 → 紧张 → 震撼"
      }
    ],
    "core_tensions": ["..."],
    "thematic_layers": {
      "表层": "...",
      "中层": "...",
      "深层": "..."
    },
    "perspective_integration": {"...": "..."}
  }
}
```

---

## 默认视角列表

`storm_discover_perspectives` 工具默认生成以下 5 个视角：

1. **主角视角** — 从主角内心世界探索
2. **反派/对立面视角** — 从对立面立场探索
3. **旁观者/社会视角** — 从社会和旁观者角度探索
4. **伦理/哲学视角** — 从伦理和哲学高度探索
5. **时间/命运视角** — 从时间和命运维度探索

---

## 命令系统变更

| 命令 | v0 行为 | v1 行为 |
|------|---------|---------|
| `/start <主题>` | 直接头脑风暴 → 创建角色 | STORM 发现阶段 → 研究阶段 → 大纲合成 → 创建角色 |
| `/next` | 推进下一场景 | 根据当前阶段：发现→研究→大纲→下一场景 |
| 其他命令 | 不变 | 不变 |

**关键差异**：`/start` 和 `/next` 在 STORM 前三个阶段的行为发生了变化——`/next` 用于在 STORM 阶段间推进，进入 acting 阶段后恢复原有行为。

---

## 向后兼容性

1. **保存文件兼容**：v1 可以加载 v0 的保存文件（`storm` 字段默认为空）
2. **状态兼容**：`brainstorming` 状态路由到 `_storm_discoverer`
3. **A2A 架构不变**：演员 A2A 服务完全不受影响
4. **命令兼容**：所有 v0 命令在 v1 中继续可用

---

## 风险与已知限制

1. **StormRouter 复杂度**：自定义 `BaseAgent` 的路由逻辑需要覆盖所有状态场景
2. **视角研究轮次**：当前实现假设研究者 Agent 会对每个视角逐一调用工具，依赖 LLM 的自主决策
3. **大纲质量**：大纲合成的深度取决于研究发现的质量，需要足够的 LLM 推理能力
4. **状态一致性**：多 Agent 共享 state 需要注意并发写入（当前为单用户场景，风险较低）

---

## 下一步计划（v1.1）

- [ ] 评估 STORM 框架的实际创作质量
- [ ] 支持用户自定义视角
- [ ] 增加视角间的交叉验证（发现矛盾后自动深入）
- [ ] 支持大纲的迭代修订（用户反馈后重新合成）
- [ ] 增加 STORM 阶段的进度可视化
