# Phase 28: 分层记忆机制重构 — Mem0/Letta/ReMe 式三层记忆架构

## 目标

重构现有四层记忆架构（Tier1-4）为**三层清晰边界**的记忆系统：

| 层级 | 名称 | 对应原架构 | 职责 | 容量 | 召回方式 |
|------|------|-----------|------|------|----------|
| L1 | 工作记忆 (Working Memory) | Tier 1 (working_memory) | **当前场景**的原始记忆条目，直接注入 Prompt | 3-5 条 | 全量注入 |
| L2 | 短期记忆 (Short-term Memory) | Tier 2 (scene_summaries) 精炼 | **近期 N 场**的压缩摘要，供工作记忆之外补充 | 5-8 条 | 关键词+标签匹配 |
| L3 | 长期记忆 (Long-term Memory) | Tier 4 (vector_memory) 增强 | 生平设定、重大历史事件、角色锚点 | 不限 | 向量语义检索 + RIR 综合评分 |

## 设计决策

### D-01: 工作记忆严格聚焦当前场景
- `working_memory` 只保留**当前场景**产生的记忆条目
- 场景切换时，自动将上一场景的工作记忆压缩后移入短期记忆
- 容量从 5 条收紧到 3 条，确保只保留最相关的内容

### D-02: 短期记忆独立模块
- 新建 `app/short_term_memory.py` 专门管理 L2
- 短期记忆不是原始条目的堆砌，而是**每场一个摘要**
- 采用关键词+标签的轻量级检索（无需 LLM 实时参与）
- 容量 8 条，超过后触发向 L3 的异步迁移

### D-03: 长期记忆引入 RIR 综合评分
- R = Recency（时效性）：越新的记忆分数越高
- I = Importance（重要性）：critical > normal
- R = Relevance（相关性）：向量语义相似度
- 公式：`score = 0.4 * relevance + 0.35 * recency + 0.25 * importance`
- 召回时按 score 排序，只取 Top-K 注入上下文

### D-04: Token 预算重新分配
- Actor Context Token Budget: 8000（不变）
- L1（工作记忆）：优先保留，最高优先级，占 ~20%（~1600 tokens）
- L2（短期记忆）：次优先，占 ~25%（~2000 tokens）
- L3（长期记忆）：按需召回，占 ~20%（~1600 tokens）
- 角色锚点/情绪/关键记忆：固定开销，占 ~35%（~2800 tokens）

### D-05: 向后兼容
- 现有 `working_memory`、`scene_summaries`、`arc_summary`、`vector_memory` 数据结构不变
- 新增 `short_term_memory` 字段，旧存档自动迁移（通过 `ensure_actor_memory_fields`）
- `build_actor_context` 接口不变，内部实现改为三层组装

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 场景切换时工作记忆迁移遗漏 | P1 | 在 `next_scene()` 中显式调用迁移钩子 |
| L3 向量召回增加延迟 | P2 | RIR 评分在搜索后做，不额外调用 LLM |
| Token 预算重分配导致上下文过短 | P2 | 保留可配置的 budget 参数，默认不变 |
| 旧存档兼容性问题 | P1 | ensure_actor_memory_fields 自动初始化新字段 |

## 成功标准

1. `build_actor_context()` 输出明确包含【工作记忆】【短期记忆】【长期记忆】三个区块
2. 向量记忆召回支持按 RIR 综合评分排序
3. 工作记忆容量收紧为 3 条，场景切换时自动迁移
4. 回归测试全部通过（含旧测试不破坏）
5. Token 消耗相比改造前平均降低 15%+
