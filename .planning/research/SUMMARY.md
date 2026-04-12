# Research Summary — Director-Actor-Drama 无限畅写版

**Date:** 2026-04-11

## Key Findings

### Stack
- **零新运行时依赖** — 所有方案基于现有 ADK/LiteLlm + JSON 文件构建，无需引入向量数据库
- **3 层自定义记忆**（工作记忆/场景摘要/全局摘要）优于 mem0/ChromaDB/FAISS（符合"无数据库"约束）
- **自定义叙事引擎** — 无现成 Python 叙事引擎，需自建 `narrative_engine.py`、`memory_manager.py`、`context_builder.py`、`coherence_checker.py`
- mem0/ChromaDB/Letta 可作为未来升级路径，但 v1 不引入

### Table Stakes (必备)
1. 无限叙事循环 — 场景→评估→注入→下一场，直至用户终止
2. 上下文/记忆管理 — 3 层记忆防止上下文窗口溢出
3. 用户随时干预 — 混合模式无缝切换
4. 叙事连贯性 — 一致性检查防止逻辑矛盾
5. 动态冲突注入 — 防止剧情"流水账"

### Watch Out For (关键陷阱)
1. **上下文耗尽** — 50+ 场后全量记忆不可行 → 分层压缩
2. **摘要丢失关键细节** → 重要性权重摘要
3. **无目的游荡** → 张力评分 + 弧线追踪
4. **重复冲突注入** → 冲突模板去重
5. **A2A 延迟叠加** → 异步并行调用

### Critical Path (关键路径)
**记忆管理 → 无限循环 → 张力评分 → 动态 STORM**

记忆管理是基础设施，必须先建；无限循环是核心引擎；张力评分是质量保障；动态 STORM 是增强层。

## Research Files

| File | Lines | Content |
|------|-------|---------|
| STACK.md | 296 | 技术栈建议，零新依赖方案 |
| FEATURES.md | 389 | 功能分级（必备/差异化/反功能）+ 依赖图 |
| ARCHITECTURE.md | 640 | 架构演进方案，5 阶段构建顺序 |
| PITFALLS.md | 260 | 17 个项目专属陷阱 + 预防策略 |
