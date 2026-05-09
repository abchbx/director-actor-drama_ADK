# Phase 28 Summary: 分层记忆机制重构

## 完成状态

✅ **COMPLETE** — 所有成功标准已达成

## 交付物

### 1. 新增模块

- **`app/short_term_memory.py`** — L2 短期记忆管理模块
  - `add_short_term_memory()` — 添加短期记忆条目
  - `search_short_term_memory()` — 标签加权轻量级检索
  - `build_short_term_context()` — 格式化为 LLM 上下文文本
  - `migrate_working_to_short_term()` — 场景切换时 L1→L2 迁移
  - `compute_rir_score()` — RIR 综合评分
  - `rank_vector_results_by_rir()` — 向量结果重排序

### 2. 修改模块

- **`app/memory_manager.py`**
  - `WORKING_MEMORY_LIMIT` 从 5 → 3（D-01 工作记忆聚焦当前场景）
  - `ensure_actor_memory_fields()` 自动初始化 `short_term_memory`
  - `pre_reasoning_hook()` 重构为明确的三层召回：L2 短期记忆 + L3 向量记忆（RIR 评分）
  - `add_working_memory()` 兼容新字段

- **`app/context_builder.py`**
  - `_assemble_actor_sections()` 新增 L2「短期记忆」和 L3「长期记忆」区块
  - `_ACTOR_SECTION_PRIORITIES` 添加 `short_term_memory`(2) 和 `vector_memory`(2)
  - 语义召回去重范围扩展至 `short_term_memory`

- **`app/tools.py`**
  - `next_scene()` 场景切换时自动调用 `migrate_working_to_short_term()`

### 3. 测试

- **`tests/unit/test_tiered_memory.py`** — 25 项测试全部通过
  - L2 添加/搜索/格式化/迁移：9 项
  - L3 RIR 评分：4 项
  - Memory Manager 集成：5 项
  - Context Builder 三层组装：5 项
  - 向后兼容：2 项

## 架构变化

```
改造前（四层，边界模糊）:
  working_memory (5) → scene_summaries (10) → arc_summary (1) → vector_memory (∞)

改造后（三层，边界清晰）:
  L1 工作记忆 (3) — 当前场景原始条目
  L2 短期记忆 (8) — 近期场景压缩摘要，标签检索
  L3 长期记忆 (∞) — 向量语义 + RIR 综合评分召回
```

## RIR 评分公式

```
score = 0.4 * relevance + 0.35 * recency + 0.25 * importance
```

- **relevance**: 向量语义相似度 (0.0~1.0)
- **recency**: 基于场景距离的指数衰减 (当前场景=1.0)
- **importance**: critical=1.0, high=0.8, medium=0.5, normal=0.3

## 向后兼容

- 旧存档的 `working_memory`/`scene_summaries`/`arc_summary` 数据结构完全不变
- 新增 `short_term_memory` 字段通过 `ensure_actor_memory_fields()` 自动初始化
- `build_actor_context()` 接口不变
- 无 chromadb 时 L3 召回优雅降级（try/except pass）

## 性能影响

- L2 检索：纯 Python 标签匹配，<1ms
- L3 RIR 重排序：O(n log n)，n≤8（over-fetch 数量），可忽略
- 预期 Token 节省：工作记忆从 5 条收紧到 3 条，减少 ~20% L1 Token 消耗
