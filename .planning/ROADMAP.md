# Roadmap — Director-Actor-Drama 无限畅写版

**Milestone:** v1
**Created:** 2026-04-11
**Granularity:** Fine (12 phases)
**Critical Path:** Memory → Loop → Tension → Dynamic STORM

## Phase Overview

```
Phase 1: Memory Foundation
    │
    ├──► Phase 2: Context Builder
    │         │
    │         └──► Phase 3: Semantic Retrieval
    │
    ├──► Phase 4: Infinite Loop Engine
    │         │
    │         └──► Phase 5: Mixed Autonomy Mode
    │
    └──────────────────────────────────────────► Phase 6: Tension Scoring & Conflict Engine
                                                       │
                                                       ├──► Phase 7: Arc Tracking
                                                       │
                                                       └──► Phase 8: Dynamic STORM
                                                                │
                                                                ├──► Phase 9: Progressive STORM
                                                                │
                                                                └──► Phase 10: Coherence System
                                                                         │
                                                                         └──► Phase 11: Timeline Tracking
                                                                                  │
                                                                                  └──► Phase 12: Integration & Polish
```

---

## Phase 1: Memory Foundation

**Goal:** 构建 3 层记忆架构，替换现有扁平记忆，使系统能支撑 50+ 场戏而不溢出上下文窗口。

**Requirements:**
- MEMORY-01: 3 层记忆架构
- MEMORY-02: 自动记忆压缩
- MEMORY-03: 重要性权重摘要

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Core memory_manager.py module (data structures, add/compress/build/migrate/detect)
- [x] 01-02-PLAN.md — Integration with state_manager.py & tools.py (actor_speak, mark_memory, load migration)
- [x] 01-03-PLAN.md — Async LLM compression & edge cases (pending merge, LiteLlm fallback, serialization)

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `app/memory_manager.py` 模块存在，实现 `add_working_memory()`、`build_actor_context()`、`check_and_compress()` 等函数
2. 运行 20+ 场戏后，每个演员的 `working_memory` ≤ 5 条、`scene_summaries` 逐步增长、`arc_summary` 在阈值触发后被填充
3. 旧版 `memory` 字段在 `load_progress()` 时自动迁移为 `working_memory`，不丢失数据
4. `critical_memories` 机制可用：标记为关键的记忆不会被压缩，始终保留在上下文中
5. `actor_speak()` 使用 `build_actor_context()` 替代原有扁平 `memory_str`，异步 LLM 压缩不阻塞主流程

**Depends on:** None（基础设施，一切依赖于此）

---

## Phase 2: Context Builder

**Goal:** 为每场戏组装精确的上下文，包含全局摘要 + 近期场景 + 当前工作记忆 + 导演指令，总 token 控制在预算内。

**Requirements:**
- MEMORY-04: 上下文构建器

**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — context_builder.py 核心模块（estimate_tokens + 逐层裁剪 + build_actor_context_from_memory + build_director_context）+ 单元测试
- [x] 02-02-PLAN.md — 迁移集成（memory_manager 重导出 + tools.py import 更新 + agent.py 导演工具注册 + 集成测试）

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `app/context_builder.py` 模块存在，实现 `build_director_context()` 和 `build_actor_context_from_memory()` 函数
2. 导演上下文包含：全局故事弧线 + 当前张力状态 + 近期场景标题 + 活跃冲突 + Dynamic STORM 视角
3. 演员上下文 token 预算 ≤ 8000 tokens/次，导演上下文 ≤ 30000 tokens/次
4. 当上下文超出预算时，按优先级裁剪（全局摘要 > 近期场景 > 工作记忆细节）

**Depends on:** Phase 1

---

## Phase 3: Semantic Retrieval

**Goal:** 实现基于标签/关键词/角色名/事件类型的记忆检索，让演员和导演能回忆特定过往。

**Requirements:**
- MEMORY-05: 语义检索

**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — semantic_retriever.py 核心模块（加权标签匹配、三层搜索、去重排序、标签解析、回填工具）+ memory_manager.py 压缩 prompt 标签生成
- [ ] 03-02-PLAN.md — 集成层（tools.py 导演 Tool 注册 + context_builder.py 相关回忆段落 + agent.py instruction 更新）

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `retrieve_relevant_scenes(tags, current_scene, tool_context)` 函数可用，返回 top-K 相关场景摘要
2. 每个场景压缩时自动生成标签集（角色名、地点、情感关键词、冲突类型）
3. 检索结果按相关度排序，不依赖外部向量数据库
4. 检索延迟 < 100ms（纯 JSON 文件扫描）

**Depends on:** Phase 1, Phase 2

---

## Phase 4: Infinite Loop Engine

**Goal:** 将线性 STORM 流水线替换为无限叙事循环，场景→评估→注入→下一场，无预设终点。

**Requirements:**
- LOOP-01: 无限叙事循环
- LOOP-03: 场景自然衔接

**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — DramaRouter 重构（_setup_agent + _improv_director + 路由逻辑）
- [x] 04-02-PLAN.md — 场景衔接信息增强（_extract_scene_transition + build_director_context 衔接段落）
- [x] 04-03-PLAN.md — next_scene 返回值增强 + 旧状态迁移 + 单元测试

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `app/agent.py` 中 `StormRouter` 演化为 `DramaRouter`，仅区分 setup 阶段和 improvise 阶段
2. improvise 阶段可无限循环：场景推进 → 导演旁白 → 演员对话 → 记录场景 → 评估 → 下一场，无硬编码终点
3. 每场戏的 prompt 自动包含上一场的关键信息（结局、情绪、未决事件），逻辑自然延续
4. 合并 `_storm_discoverer` + `_storm_researcher` + `_storm_outliner` 为 `_setup_agent`
5. 移除 `_storm_director` 的单向状态锁定，`_improv_director` 可重新进入发现阶段

**Depends on:** Phase 1（记忆管理是循环引擎的基础）

---

## Phase 5: Mixed Autonomy Mode

**Goal:** 实现 AI 自主推进 + 用户随时干预的无缝切换，并提供明确的终止机制。

**Requirements:**
- LOOP-02: 混合推进模式
- LOOP-04: 用户终止机制

**Plans:** 3 plans

Plans:
- [x] 05-01-PLAN.md — Tool Functions: auto_advance, steer_drama, end_drama, trigger_storm + next_scene() counter decrement
- [x] 05-02-PLAN.md — Context Builder & State: steer/epilogue/auto-advance sections + state field init + load migration
- [x] 05-03-PLAN.md — Director Prompt Restructure + Router + CLI: 7-section prompt + routing + auto-interrupt + CLI updates

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. 用户可通过 `/action` 注入事件、`/steer <direction>` 轻量引导、`/storm` 手动触发视角发现，与 AI 自主推进无缝切换
2. `/end` 命令触发终幕旁白和完整剧本导出，戏剧优雅结束
3. AI 自主推进时，每场戏后向用户呈现 2-3 个选项引导参与，而非纯被动等待
4. 现有 `/next`、`/action`、`/save`、`/load` 命令向后兼容，行为不变

**Depends on:** Phase 4

---

## Phase 6: Tension Scoring & Conflict Engine

**Goal:** 实现张力评分和自动冲突注入，当剧情平淡时自动注入转折事件，防止"流水账"。

**Requirements:**
- CONFLICT-01: 张力评分
- CONFLICT-02: 低张力自动注入
- CONFLICT-03: 冲突模板库
- CONFLICT-04: 冲突去重

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `evaluate_tension(tool_context)` 工具可用，返回 `tension_score`（0-100）、`is_boring`、`suggested_action`
2. 张力评分基于启发式规则（情感方差、对话重复度、未决冲突数、距上次注入的场次数），无需 LLM 调用
3. 张力低于阈值时，`inject_conflict(conflict_type, tool_context)` 自动生成并注入冲突事件
4. 冲突模板库包含 7 种类型（新角色登场、秘密发现、矛盾升级、信任背叛、意外事件、外部威胁、抉择困境）
5. `used_conflict_types` 追踪近期已使用冲突类型，同一类型 8 场内不重复

**Plans:** 2/2 plans complete

Plans:
- [x] 06-01-PLAN.md — conflict_engine.py 核心模块（calculate_tension + CONFLICT_TEMPLATES + 冲突选择/去重/渐进升级）+ TDD 单元测试
- [x] 06-02-PLAN.md — 集成层（tools.py 薄代理 + state_manager.py 初始化/兼容 + agent.py §8 prompt + context_builder.py 张力/冲突段落）+ TDD 测试

**Depends on:** Phase 1, Phase 4（需要记忆和循环引擎基础）

---

## Phase 7: Arc Tracking

**Goal:** 追踪角色弧线和故事弧线的完成度，确保弧线不被遗忘。

**Requirements:**
- CONFLICT-05: 弧线追踪

**Plans:** 2 plans

Plans:
- [ ] 07-01-PLAN.md — Core arc_tracker.py module + conflict_engine resolve extension + state initialization
- [ ] 07-02-PLAN.md — Integration layer (tools + context_builder + agent.py §9 + inject_conflict enhancement)

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `state["plot_threads"]` 维护结构化的剧情线索列表，每条线索包含 `id`、`description`、`status`（active/dormant/resolved）、`involved_actors`、`introduced_scene`
2. 每个演员的角色弧线（成长/堕落/转变）在 `state["actors"][name]["arc_progress"]` 中追踪
3. 线索超过 8 场无更新时自动标记为 `dormant`，导演收到提醒
4. 活跃冲突数上限为 3-4，注入新冲突前建议推进已有线索
5. 冲突可通过 resolve_conflict_tool 从 active 移到 resolved_conflicts

**Depends on:** Phase 6

---

## Phase 8: Dynamic STORM

**Goal:** 实现周期性视角重新发现，基于新视角生成新冲突并扩展故事世界。

**Requirements:**
- DSTORM-01: 动态视角发现
- DSTORM-02: 新冲突注入
- DSTORM-03: 世界观扩展

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `dynamic_storm(focus_area, tool_context)` 工具可用，从当前剧情中挖掘未探索角度
2. 每 N 场（可配置，默认 8 场）自动触发 Dynamic STORM，或当 `evaluate_tension()` 建议时触发
3. 新视角与已有视角去重：生成前检查 `storm["perspectives"]`，避免视角重叠
4. 新视角必须受已确立事实约束（不与已发生事件矛盾），作为扩展而非推翻
5. Dynamic STORM 结果合并入 `storm` 数据，Director 在同一轮次中使用新视角

**Depends on:** Phase 6（张力评分触发 STORM）、Phase 4（循环引擎承载 STORM）

---

## Phase 9: Progressive STORM

**Goal:** 实现渐进式 STORM 注入和用户主动触发，避免一次性过载。

**Requirements:**
- DSTORM-04: 用户触发的 STORM
- DSTORM-05: 渐进式 STORM

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `/storm` 命令可用，用户可主动请求新视角发现，不受 N 场间隔限制
2. 每次 Dynamic STORM 仅注入 1-2 个新视角，避免一次性过载导致剧情失焦
3. 渐进式注入后，Director 在 2-3 场内逐步融入新视角，而非当场强行使用
4. `state["dynamic_storm"]["trigger_history"]` 记录每次触发原因（auto/manual/tension_low）

**Depends on:** Phase 8

---

## Phase 10: Coherence System

**Goal:** 实现一致性检查和矛盾修复，保障"逻辑不断"的核心承诺。

**Requirements:**
- COHERENCE-01: 一致性检查
- COHERENCE-02: 关键事实追踪
- COHERENCE-03: 角色一致性
- COHERENCE-04: 矛盾修复

**Plans:** 1/2 plans complete

Plans:
- [x] 10-01-PLAN.md — coherence_checker.py 纯函数核心 + state_manager 初始化/兼容 + TDD 测试
- [ ] 10-02-PLAN.md — 集成层（3 个 Tool 函数 + context_builder 升级 + agent.py §11 + tools 注册）

**Success Criteria:**
1. `app/coherence_checker.py` 模块存在，实现 `validate_consistency(tool_context)` 函数
2. `state["established_facts"]` 维护已确立事实清单（谁是谁、在哪、发生了什么），新场景生成前自动检查
3. 角色一致性验证：演员行为符合性格定义和累积记忆，`build_actor_context()` 包含角色锚点提醒
4. 矛盾修复：检测到逻辑矛盾时生成修复性旁白（"其实..."、"之前未曾提及的是..."），而非报错中断
5. 每 5 场自动运行一致性检查，检测结果记录在 `state["coherence_checks"]`

**Depends on:** Phase 8（Dynamic STORM 可能引入矛盾，需一致性保障）

---

## Phase 11: Timeline Tracking

**Goal:** 维护剧情时间线，防止时序矛盾和场景跳跃。

**Requirements:**
- COHERENCE-05: 时间线追踪

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. `state["timeline"]` 包含 `current_time`（描述性时间，如"第三天黄昏"）和 `days_elapsed`
2. 每场戏推进时间确定性更新，时间信息包含在演员和导演的 prompt 中
3. 场景跳跃检测：如果两场戏时间跨度超过合理范围，Director 收到警告
4. 时间线与已确立事实交叉验证：事件时序与时间线一致

**Depends on:** Phase 10（时间线是一致性系统的一部分）

---

## Phase 12: Integration & Polish

**Goal:** 端到端集成测试、CLI 优化、性能调优、文档完善，确保系统可交付。

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — Core dynamic_storm.py module + TDD tests
- [x] 08-02-PLAN.md — Integration layer (tools + state + context_builder + agent)

**UAT:** 08-UAT.md — 15/15 passed, 0 issues

**Success Criteria:**
1. 端到端测试：`/start` → setup → 30+ 场戏（含冲突注入 + Dynamic STORM）→ `/save` → `/load` → 继续 → `/end`，全流程无错误
2. 修复已知 bug：`actor_speak()` 算符优先级（line 246）、conversation_log 全局状态、`_sub_agents[0]` fallback
3. 性能优化：debounced state saving、场景归档（旧场景从 state.json 移至独立文件）、共享 httpx.AsyncClient
4. CLI 命令完整可用：`/next`、`/action`、`/steer`、`/storm`、`/end`、`/save`、`/load`、`/export`
5. 演员进程健康检查和崩溃恢复机制可用
6. 测试覆盖：每个新模块至少有单元测试，核心流程有集成测试

**Depends on:** Phase 11

---

## Dependency Matrix

| Phase | Depends On | Enables |
|-------|-----------|---------|
| 1: Memory Foundation | — | 2, 3, 4, 6 |
| 2: Context Builder | 1 | 3 |
| 3: Semantic Retrieval | 1, 2 | 10 |
| 4: Infinite Loop Engine | 1 | 5, 6, 8 |
| 5: Mixed Autonomy Mode | 4 | 9, 12 |
| 6: Tension & Conflict | 1, 4 | 7, 8 |
| 7: Arc Tracking | 6 | 8 |
| 8: Dynamic STORM | 6, 4 | 9, 10 |
| 9: Progressive STORM | 8 | 12 |
| 10: Coherence System | 8 | 11 |
| 11: Timeline Tracking | 10 | 12 |
| 12: Integration & Polish | 11 | — |

## Requirement Traceability

| REQ-ID | Phase |
|--------|-------|
| MEMORY-01 | 1 |
| MEMORY-02 | 1 |
| MEMORY-03 | 1 |
| MEMORY-04 | 2 |
| MEMORY-05 | 3 |
| LOOP-01 | 4 |
| LOOP-02 | 5 |
| LOOP-03 | 4 |
| LOOP-04 | 5 |
| CONFLICT-01 | 6 |
| CONFLICT-02 | 6 |
| CONFLICT-03 | 6 |
| CONFLICT-04 | 6 |
| CONFLICT-05 | 7 |
| DSTORM-01 | 8 |
| DSTORM-02 | 8 |
| DSTORM-03 | 8 |
| DSTORM-04 | 9 |
| DSTORM-05 | 9 |
| COHERENCE-01 | 10 |
| COHERENCE-02 | 10 |
| COHERENCE-03 | 10 |
| COHERENCE-04 | 10 |
| COHERENCE-05 | 11 |

---

*Roadmap created: 2026-04-11*
