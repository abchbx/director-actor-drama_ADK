# Phase 8: Dynamic STORM - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

实现周期性视角重新发现，基于新视角生成新冲突并扩展故事世界。

核心交付物：
1. `dynamic_storm(focus_area, tool_context)` 工具——从当前剧情中挖掘未探索角度，升级 Phase 5 的轻量 `trigger_storm()`
2. 每 N 场自动触发机制（默认 8 场）——通过 `evaluate_tension()` 的 `suggested_action` + 导演 prompt 引导实现
3. 新视角去重——生成前检查 `storm["perspectives"]`，prompt 列出已有视角 + 代码级关键词重叠过滤
4. 事实约束——新视角必须受已确立事实约束（作为扩展而非推翻），通过 prompt 注入当前剧情上下文实现
5. Dynamic STORM 结果合并入 `storm` 数据，Director 在同一轮次中使用新视角
6. 导演 prompt §10 Dynamic STORM 段落——触发条件、使用方式、约束规则
7. `state["dynamic_storm"]` 子对象——触发历史、发现记录、自动触发计数器

**不包含：** 渐进式 STORM 注入（Phase 9）、用户主动触发 `/storm` 的渐进融入（Phase 9）、一致性检查（Phase 10）、时间线追踪（Phase 11）

</domain>

<decisions>
## Implementation Decisions

### 视角发现方式
- **D-01:** LLM 自由生成 + 结构化 prompt——`dynamic_storm()` 将当前剧情状态组装成结构化 prompt，让 LLM 自由生成 1-2 个新视角。不使用硬编码模板（setup 阶段的 5 视角模板已完成了初始探索，Dynamic STORM 的价值在于运行时创意发现）
- **D-02:** prompt 注入的剧情上下文包括：
  1. 已有视角列表（`storm["perspectives"]` 的 name 字段）——明确告知 LLM 已探索过哪些角度
  2. 当前张力状态（`conflict_engine.tension_score`、`is_boring`、`consecutive_low_tension`）——提示 LLM 当前剧情是否缺乏张力
  3. 活跃冲突列表（`conflict_engine.active_conflicts`）——避免生成与已有冲突重叠的视角
  4. Dormant 线索（`plot_threads` 中 status="dormant" 的条目）——暗示被遗忘的故事线可能需要新角度重新激活
  5. 角色弧线进展（`actors[name].arc_progress` 中有进展的角色）——从角色发展角度发现新方向
- **D-03:** `dynamic_storm()` 的 LLM prompt 核心指令：
  - "基于当前剧情状态，发现 1-2 个尚未被探索的新视角或新角度"
  - "新视角应能引入新的冲突可能性或扩展故事世界的边界"
  - "不要重复已有视角（已列出），也不要与已有冲突直接重叠"
  - "新视角必须与已发生事件一致，是扩展而非推翻"
- **D-04:** 升级 `trigger_storm()` 为 `dynamic_storm()`——保留 `focus_area` 参数作为可选聚焦方向，新增 LLM 调用生成新视角。现有 `trigger_storm()` 的 prompt-only 模式废弃，替换为完整 Dynamic STORM 实现
- **D-05:** 新视角的结构与 setup 阶段的 perspectives 保持一致——每个新视角包含 `name`、`description`、`questions` 字段，可直接合并入 `storm["perspectives"]`
- **D-06:** 每次 Dynamic STORM 生成 1-2 个新视角（与 Phase 9 的渐进式注入对齐），不一次性大量生成

### 自动触发机制
- **D-07:** 导演 prompt 引导 + `evaluate_tension()` 建议触发——对齐 Phase 6 D-03"导演主动调用"模式，不使用代码级自动调用。尊重 ADK turn-based 模型
- **D-08:** `next_scene()` 递增 `dynamic_storm.scenes_since_last_storm` 计数器（在 next_scene 返回值中包含此字段）
- **D-09:** `evaluate_tension()` 返回值扩展——当 `scenes_since_last_storm >= STORM_INTERVAL`（默认 8）时，`suggested_action` 新增 "dynamic_storm" 选项，`suggested_storm_focus` 字段提供聚焦方向建议
- **D-10:** 导演 prompt §10 中明确触发条件：
  - 每 8 场（可配置）自动建议触发 Dynamic STORM
  - 张力连续 3+ 场低迷时强烈建议触发
  - 用户可通过 `/storm [焦点]` 手动触发
- **D-11:** `STORM_INTERVAL = 8`（可配置常量）——与 Phase 6 的 `DEDUP_WINDOW = 8` 和 Phase 7 的 `DORMANT_THRESHOLD = 8` 对齐，约覆盖 2-3 轮完整场景循环
- **D-12:** 不在 `next_scene()` 中代码级自动调用 `dynamic_storm()`——与 Phase 6 D-03 一致，由导演 LLM 决定何时触发，避免强制中断叙事节奏

### 新视角去重
- **D-13:** 两层去重策略：
  1. **Prompt 层**——在 LLM prompt 中列出所有已有视角的 `name` 和 `description`，明确要求"不要重复已有视角"
  2. **代码层**——轻量关键词重叠检查：提取新视角 `name` 中的中文关键词（2-4 字），与已有视角 `name` 的关键词对比，重叠度 > 60% 则标记为"可能与已有视角重叠"并在返回值中提示导演
- **D-14:** 关键词提取方式：中文分词取前 2-3 个实词（去除"视角"、"角度"等虚词）。不引入 NLP 库——使用简单的字符窗口滑动（2-4 字）+ 已有视角关键词集合匹配
- **D-15:** 去重检查不阻止视角生成——即使检测到重叠，仍然返回新视角但附加 `overlap_warning` 字段，由导演决定是否采纳。保持创意灵活性
- **D-16:** 新视角合并入 `storm["perspectives"]` 时标记 `source: "dynamic_storm"` 和 `discovered_scene: current_scene`，与 setup 阶段的视角区分

### 世界观扩展的边界
- **D-17:** 通过 prompt 注入剧情上下文约束——不依赖 Phase 10 的 `established_facts`（尚未实现），保持 Phase 独立性
- **D-18:** prompt 约束指令：
  - "新视角必须与已发生事件一致，是扩展而非推翻"
  - "已发生的事件不可改变，新视角应该揭示之前未探索的维度"
  - "新角色、新地点、新规则的引入必须与已有世界观兼容"
- **D-19:** 为 prompt 提供的剧情上下文包括：
  1. 近 3 场场景摘要（`scenes[-3:]` 的标题和关键事件）
  2. 活跃角色的基本信息（名字、身份、当前情绪）
  3. 当前的 story outline / 世界观设定（`storm["outline"]` 中已有的设定）
- **D-20:** 不在 Dynamic STORM 中实现严格的事实检查机制——Phase 10 的一致性系统会处理矛盾。Dynamic STORM 专注于创意发现，Phase 10 负责逻辑守门

### Dynamic STORM 与冲突注入的联动
- **D-21:** Dynamic STORM 发现新视角后，可建议基于新视角的冲突类型——返回值中包含 `suggested_conflict_types` 列表（从 CONFLICT_TEMPLATES 中选取与新视角最匹配的类型）
- **D-22:** 导演在 §10 prompt 中引导：**Dynamic STORM 发现新视角后，考虑调用 inject_conflict() 基于新视角注入冲突**——但不强制。保持"导演建议模式"精神
- **D-23:** 当 `evaluate_tension()` 的 `suggested_action` 同时包含 "inject_conflict" 和 "dynamic_storm" 时，优先建议 Dynamic STORM（先发现新角度，再基于新角度注入冲突，避免盲目注入）

### trigger_storm() 的升级路径
- **D-24:** 现有 `trigger_storm(focus_area, tool_context)` 升级为 `dynamic_storm(focus_area, tool_context)`——函数名变更，签名保持一致（`focus_area` 仍为可选参数）
- **D-25:** 向后兼容——`trigger_storm` 保留为别名函数，内部调用 `dynamic_storm()`，返回值格式不变（`status`、`message`、`focus_area`），但新增 `new_perspectives`、`suggested_conflict_types`、`overlap_warnings` 字段
- **D-26:** `dynamic_storm()` 返回值结构：
  ```python
  {
      "status": "success",
      "message": "🔍 Dynamic STORM 触发！发现 N 个新视角...",
      "focus_area": str,
      "new_perspectives": [{"name": ..., "description": ..., "questions": [...]}],
      "suggested_conflict_types": [str],  # 如 ["escalation", "dilemma"]
      "overlap_warnings": [str],  # 如 ["新视角'权力博弈'与已有视角'反派视角'可能重叠"]
      "scenes_since_last": int,
  }
  ```

### 状态持久化
- **D-27:** 新增 `state["dynamic_storm"]` 子对象，结构：
  ```python
  dynamic_storm = {
      "scenes_since_last_storm": 0,  # 距上次触发的场次数
      "trigger_history": [],          # 触发历史 [{scene, trigger_type, focus_area, perspectives_found}]
      "discovered_perspectives": [],  # Dynamic STORM 发现的所有新视角（合并入 storm.perspectives 的副本）
  }
  ```
- **D-28:** `init_drama_state()` 初始化 `dynamic_storm` 子对象，所有字段设为默认值
- **D-29:** `load_progress()` 兼容旧存档——缺少 `dynamic_storm` 时自动初始化默认值
- **D-30:** `next_scene()` 递增 `dynamic_storm.scenes_since_last_storm`，`dynamic_storm()` 重置为 0
- **D-31:** `dynamic_storm()` 触发时记录 `trigger_history`：`{scene: current_scene, trigger_type: "auto"|"manual"|"tension_low", focus_area: str, perspectives_found: int}`

### 导演上下文集成
- **D-32:** `_build_dynamic_storm_section(state)` 升级——从当前空壳实现扩展为：
  - 显示距上次 STORM 的场次数
  - 当 `scenes_since_last_storm >= STORM_INTERVAL` 时显示"建议触发 Dynamic STORM"
  - 显示最近一次 STORM 发现的新视角摘要
- **D-33:** `dynamic_storm` 段落优先级保持 `3`（已有，可截断但尽量保留）

### 导演 Prompt 集成
- **D-34:** 导演 prompt 新增 §10 Dynamic STORM 段落：
  ```
  ## §10 Dynamic STORM（视角重新发现）
  - 每 8 场左右（或张力持续低迷时），调用 dynamic_storm() 重新发现新视角
  - evaluate_tension() 返回 suggested_action="dynamic_storm" 时，优先调用
  - 用户可通过 /storm [焦点] 手动触发
  - 新视角发现后，考虑基于新角度调用 inject_conflict() 注入冲突
  - 新视角必须与已发生事件一致，是扩展而非推翻
  ```

### Claude's Discretion
- `dynamic_storm()` 中 LLM prompt 的精确措辞和长度
- 关键词重叠检查的具体算法（字符窗口大小、虚词列表）
- `STORM_INTERVAL` 的精确值（默认 8，可调整）
- `_build_dynamic_storm_section()` 的精确格式和排版
- 导演 prompt §10 的具体措辞和长度
- `suggested_conflict_types` 的匹配逻辑（基于视角描述与冲突模板的关联度）
- `trigger_history` 的保留条数上限
- `discovered_perspectives` 与 `storm["perspectives"]` 的同步策略
- `trigger_storm` 别名函数的保留期限

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 8 需求定义
- `.planning/ROADMAP.md` — Phase 8 成功标准：dynamic_storm 工具可用、每 N 场自动触发、新视角去重、事实约束、结果合并入 storm 数据
- `.planning/REQUIREMENTS.md` — DSTORM-01（动态视角发现）、DSTORM-02（新冲突注入）、DSTORM-03（世界观扩展）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构，关键记忆保护
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分，token 预算控制，D-04 前向兼容预留（dynamic_storm 段落）
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — DramaRouter 架构，场景衔接
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 混合推进模式，storm 子对象结构（D-22），导演 prompt 7 段结构，trigger_storm 轻量实现
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 张力评分完整决策（D-01~D-19），evaluate_tension 工具签名，suggested_action 机制，导演建议模式
- `.planning/phases/07-arc-tracking/07-CONTEXT.md` — 弧线追踪完整决策（D-01~D-39），plot_threads 结构，dormant 检测，resolve_conflict 机制

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/tools.py` — 现有 `trigger_storm()` 函数（第764行），Phase 8 需升级为 `dynamic_storm()`；现有 `evaluate_tension()` 需扩展 suggested_action
- `app/tools.py` — 现有 `storm_discover_perspectives()` 函数（第1443行），理解 setup 阶段视角生成模式
- `app/agent.py` — `_improv_director` 的 tools 列表需替换 trigger_storm 为 dynamic_storm，prompt 需新增 §10
- `app/agent.py` — 导演 prompt §5 视角审视段落需更新为 Dynamic STORM 机制
- `app/context_builder.py` — `_build_dynamic_storm_section(state)` 空壳实现（第746行），Phase 8 需完整实现
- `app/context_builder.py` — `_DIRECTOR_SECTION_PRIORITIES` 已有 `"dynamic_storm": 3`
- `app/conflict_engine.py` — `calculate_tension()` 和 `generate_conflict_suggestion()` 函数，理解张力信号和冲突建议机制
- `app/state_manager.py` — `init_drama_state()` 需初始化 dynamic_storm，`load_progress()` 需兼容旧存档
- `app/state_manager.py` — `next_scene()` 需递增 scenes_since_last_storm 计数器

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools.py` 的 `trigger_storm()` — 已有 focus_area 参数和返回格式，升级基础
- `tools.py` 的 `storm_discover_perspectives()` — 已有视角生成和存储模式（storm_add_perspective），Dynamic STORM 的新视角可复用相同存储路径
- `context_builder.py` 的 `_build_dynamic_storm_section()` — 已有 D-04 前向兼容空壳，读取 `state["dynamic_storm"]` 的 `trigger_history`
- `conflict_engine.py` 的纯函数模式——`calculate_tension(state)` 只接收 `state: dict`，Phase 8 的 dynamic_storm 核心逻辑遵循相同模式
- `conflict_engine.py` 的 `update_conflict_engine_state()` — 状态更新集中式模式
- `state_manager.py` 的 `init_drama_state()` / `load_progress()` — 状态初始化和兼容模式
- `semantic_retriever.py` 的关键词匹配模式——可参考轻量关键词提取实现

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...额外字段}`
- State 路径：`tool_context.state["drama"]["dynamic_storm"]`
- 新模块模式：`app/dynamic_storm.py` — 与 `conflict_engine.py`、`arc_tracker.py` 同级
- 导演上下文段落格式：【中文标签】+ 内容
- 导演 prompt 段落：§编号 + 标题 + 规则描述
- 别名函数模式：旧函数名保留为别名，内部调用新函数
- ID 生成：`storm_{scene}_{keyword}_{index}`（与 thread_ / conflict_ 模式对齐）
- 常量命名：`UPPER_SNAKE_CASE`
- 测试模式：`_make_state(**overrides)` 构建测试用 state，测试纯函数

### Integration Points
- `app/dynamic_storm.py` — 新增模块，核心交付（视角发现、去重、建议生成）
- `app/tools.py` — 升级 `trigger_storm()` → `dynamic_storm()` + 别名保留；扩展 `evaluate_tension()` 返回值
- `app/agent.py` — `_improv_director` tools 列表注册 dynamic_storm + prompt §10 Dynamic STORM 段落 + §5 更新
- `app/context_builder.py` — `_build_dynamic_storm_section()` 完整实现
- `app/state_manager.py` — `init_drama_state()` 初始化 `dynamic_storm` + `load_progress()` 兼容 + `next_scene()` 递增计数器

</code_context>

<specifics>
## Specific Ideas

- `dynamic_storm()` 的 LLM prompt 应包含"已有视角列表"段落，格式：`已有视角：主角视角、反派/对立面视角、旁观者/社会视角、伦理/哲学视角、时间/命运视角`——LLM 看到已有视角名称后自然避开
- 关键词重叠检查：提取视角 name 中的 2-4 字中文词组，与已有视角 name 的词组集合做交集，交集占比 > 60% 则标记重叠。虚词列表：`["视角", "角度", "观点", "看法", "维度", "层面"]`
- `suggested_conflict_types` 的匹配逻辑：新视角 description 中出现的情感/行为关键词与 CONFLICT_TEMPLATES 的 prompt_hint 关键词做匹配。如新视角提到"隐藏的动机"→ 匹配 `secret_revealed`；新视角提到"两难选择"→ 匹配 `dilemma`
- `_build_dynamic_storm_section()` 格式：
  ```
  【Dynamic STORM】
  距上次视角发现：5 场 | 建议间隔：8 场
  最近发现：[第12场] "权力暗流"——从权力运作的隐秘机制审视剧情
  ⚡ 张力持续低迷——强烈建议调用 dynamic_storm() 发现新视角
  ```
- `trigger_history` 保留最近 10 条，与 `MAX_TENSION_HISTORY = 20` 对齐但减半（STORM 触发频率远低于张力评估）
- `dynamic_storm` 段落优先级 `3`（可截断但尽量保留）——当 token 预算紧张时，张力段落（5）和弧线追踪段落（5）优先
- `evaluate_tension()` 扩展：在 `generate_tension_result()` 中新增逻辑——当 `scenes_since_last_storm >= STORM_INTERVAL` 时，`suggested_action` 列表中追加 `"dynamic_storm"`，同时当 `consecutive_low_tension >= 3` 时也将 `"dynamic_storm"` 加入 suggested_action
- `/storm` 命令路径不变——CLI 已有 `/storm` 映射到 `trigger_storm`，升级后自动路由到 `dynamic_storm`

</specifics>

<deferred>
## Deferred Ideas

- LLM 自动评估视角质量——当前信任 LLM 生成质量，后续可考虑评分机制
- 自适应 STORM 间隔——根据剧情复杂度动态调整触发间隔（当前固定 8 场）
- 视角影响力追踪——追踪每个新视角被实际使用了多少场，评估 STORM 有效性
- 用户自定义 STORM 主题——指定下次 Dynamic STORM 的探索方向（v2 需求 DSTORM-06）
- 多轮 STORM 对话——用户对生成的新视角不满意时可要求重新生成
- 视角间的关联发现——发现不同视角之间的交叉点，生成复合视角
- Dynamic STORM 的可视化——展示视角发现时间线和影响力

</deferred>

---

*Phase: 08-dynamic-storm*
*Context gathered: 2026-04-13*
