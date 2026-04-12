# Phase 3: Semantic Retrieval - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 03-semantic-retrieval
**Areas discussed:** 标签生成策略, 检索范围与接口, 相关度算法, 调用时机与集成

---

## 标签生成策略

|| Option | Description | Selected |
||--------|-------------|----------|
|| 压缩时自动生成 + 回填 | 场景压缩时 LLM 输出标签，已有数据用回填工具补标签 | ✓ |
|| 仅压缩时自动生成 | 只对新压缩场景生成标签，已有数据不处理 | |
|| 事后批量生成 | 不修改压缩流程，单独用 LLM 对所有摘要生成标签 | |

**User's choice:** 自动决定 — 压缩时自动生成 + 回填
**Notes:** 已有场景摘要数量少，回填成本低；新场景自动标签是长期方案

---

## 检索范围与接口

|| Option | Description | Selected |
||--------|-------------|----------|
|| 统一接口搜三层 | retrieve_relevant_scenes 搜 scene_summaries + working_memory + critical_memories | ✓ |
|| 仅搜 scene_summaries | 只搜索有标签的场景摘要层 | |
|| 导演/演员分接口 | 两个不同接口分别处理 | |

**User's choice:** 自动决定 — 统一接口搜三层
**Notes:** 单一接口简洁，三层覆盖全面，演员/导演差异由调用方控制

---

## 相关度算法

|| Option | Description | Selected |
||--------|-------------|----------|
|| 加权标签匹配 | 角色名3.0/冲突2.0/情感1.5/地点1.0，纯Python计算<100ms | ✓ |
|| 纯标签交集计数 | 每个匹配标签计1分，简单但不够精确 | |
|| LLM rerank | 先粗筛再用LLM精排，精度高但可能超100ms | |

**User's choice:** 自动决定 — 加权标签匹配
**Notes:** 加权匹配比纯计数精确，比 LLM rerank 快，满足延迟要求

---

## 调用时机与集成

|| Option | Description | Selected |
||--------|-------------|----------|
|| 混合模式 | 导演手动Tool调用 + 演员context_builder自动注入 | ✓ |
|| 仅手动调用 | 导演和演员都通过Tool函数主动调用 | |
|| 仅自动注入 | context_builder自动为导演和演员注入相关回忆 | |

**User's choice:** 自动决定 — 混合模式
**Notes:** 导演需要主动控制回忆时机，演员需要自动获取相关上下文

---

## Claude's Discretion

- 标签前缀的具体分类列表
- LLM 压缩 prompt 中标签生成的具体措辞和格式
- 回填工具的批处理大小
- 关键词匹配的模糊程度
- 去重的具体阈值

## Deferred Ideas

- 向量数据库集成 — v2 范围
- 语义相似度模型 — 需要额外依赖
- 跨戏剧检索 — 远超当前范围
- 自然语言查询接口 — 后续增强
