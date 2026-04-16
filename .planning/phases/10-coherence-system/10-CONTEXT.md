# Phase 10: Coherence System - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

实现一致性检查和矛盾修复，保障"逻辑不断"的核心承诺。

核心交付物：
1. `app/coherence_checker.py` 模块——`validate_consistency(state)` 纯函数 + `generate_repair_narration(state, contradiction)` LLM 函数
2. `validate_consistency(tool_context)` 导演 Tool——触发一致性检查，返回检查结果
3. `add_fact(fact, category, tool_context)` 导演 Tool——手动添加已确立事实
4. `state["established_facts"]` 结构化事实清单——每条含 fact、category、actors、scene、importance
5. 角色一致性验证——`build_actor_context_from_memory()` 新增角色锚点提醒段落
6. 矛盾修复——检测到矛盾时生成修复性旁白（"其实..."、"之前未曾提及的是..."）
7. 每 5 场自动提醒一致性检查——导演 prompt §11 引导
8. 导演上下文【已确立事实】段落——升级 `_build_facts_section()` 为完整实现
9. `state["coherence_checks"]` 检查历史记录

**不包含：** 时间线追踪（Phase 11）、自适应检查频率（deferred）、LLM 自动提取事实（deferred）

</domain>

<decisions>
## Implementation Decisions

### 事实追踪数据结构
- **D-01:** 结构化对象列表——每条事实为 dict，与 Phase 7 `plot_threads` 模式对齐：
  ```python
  established_facts = [
      {
          "id": "fact_{scene}_{keyword}_{index}",  # 如 fact_5_起兵_1
          "fact": "朱棣已起兵",
          "category": "event",        # "event"|"identity"|"location"|"relationship"|"rule"
          "actors": ["朱棣"],
          "scene": 5,
          "importance": "high",       # "high"|"medium"|"low"
          "added_at": "2026-04-13T10:00:00",
      },
      ...
  ]
  ```
- **D-02:** 5 种事实类别常量 `FACT_CATEGORIES`：
  - `event` — 已发生事件（"朱棣已起兵"）
  - `identity` — 身份确认（"苏念是间谍"）
  - `location` — 地点确认（"故事发生在明朝"）
  - `relationship` — 关系确认（"林风是朱棣的旧部"）
  - `rule` — 世界规则（"魔法在满月时最强"）
- **D-03:** `importance` 三级权重：
  - `high` — 核心事实，矛盾必须修复（角色生死、重大事件）
  - `medium` — 重要事实，矛盾应修复（地点、关系变化）
  - `low` — 次要事实，矛盾可容忍（情绪描述、细节差异）
- **D-04:** 事实 ID 生成策略：`fact_{scene}_{keyword}_{index}`，keyword 从 fact 文本中提取前 2-4 字中文关键词，index 为同场景同关键词的序号。与 `thread_{scene}_{keyword}_{index}` 和 `conflict_{scene}_{type}_{index}` 模式对齐
- **D-05:** `_build_facts_section()` 展示格式——从结构化对象提取纯文本：
  ```
  【已确立事实】
  [核心] 朱棣已起兵（第5场确立，涉及：朱棣）
  [关系] 林风是朱棣的旧部（第3场确立，涉及：林风、朱棣）
  [地点] 故事发生在明朝（第1场确立）
  ```
  - 仅展示 `importance` 为 high/medium 的事实，low 级别不展示（避免信息过载）
  - 高亮标记：`[核心]` = high，`[关系]`/`[地点]`/`[身份]`/`[事件]`/`[规则]` = medium + category 中文名

### 事实创建方式
- **D-06:** 导演手动为主——新增 `add_fact(fact, category, importance, tool_context)` Tool 函数，与 Phase 7 `create_thread` 模式一致
- **D-07:** 不使用 LLM 自动提取——事实判断需要创意决策（什么算"确立事实"），误提取比漏提取更有害（错误事实导致假阳性矛盾检测）。与 Phase 7 D-16"不使用自动检测创建新线索"逻辑一致
- **D-08:** 导演 prompt §11 引导——每场 write_scene 后考虑是否需要 add_fact 记录关键事实，尤其是：
  - 角色生死或重大状态变化
  - 地点切换
  - 新关系建立或破裂
  - 世界规则确立
- **D-09:** `add_fact()` 函数签名：
  ```python
  def add_fact(fact: str, category: str = "event", importance: str = "medium", tool_context: ToolContext) -> dict:
  ```
  - `category` 默认 "event"（最常见）
  - `importance` 默认 "medium"
  - `actors` 从 fact 文本中启发式提取（与 Phase 8 关键词提取类似：匹配 `state["actors"]` 中的角色名）
  - `scene` 从 `state["current_scene"]` 自动获取
- **D-10:** 事实去重——添加前检查 fact 文本与已有事实的前 20 字重叠度，重叠 > 80% 则返回提醒，由导演决定是否仍然添加
- **D-11:** 事实数量上限——`MAX_FACTS = 50`，超出时建议导演清理低 importance 事实，但不强制。与 token 预算控制机制对齐

### 一致性检查实现
- **D-12:** LLM 驱动 + 启发式预筛选——两阶段策略：
  1. **启发式预筛选**（纯规则，无 LLM）：从 `established_facts` 中筛选出与当前场景可能相关的事实（按 actors 交集 + category 关联度），减少 LLM 输入量
  2. **LLM 一致性检查**：将筛选后的事实 + 最近 2 场场景内容送入 LLM，让 LLM 判断是否存在矛盾
- **D-13:** 不使用纯启发式规则做矛盾检测——矛盾判断需要语义理解（"朱棣在南京" vs "朱棣已北上" 是矛盾，"朱棣愤怒" vs "朱棣平静" 可能是时间差而非矛盾），启发式规则无法处理
- **D-14:** LLM 检查 prompt 核心指令：
  - "对比以下已确立事实与近期场景内容，判断是否存在逻辑矛盾"
  - "矛盾定义：与已确立事实直接冲突的陈述（同一时间同一地点不可能同时为真）"
  - "非矛盾：时间推移导致的变化、角色视角差异、新信息的补充"
  - "仅报告确信的矛盾，忽略模糊或可解释的差异"
- **D-15:** `validate_consistency(state)` 返回结构：
  ```python
  {
      "status": "success",
      "message": "✅ 一致性检查通过，未发现矛盾" 或 "⚠️ 发现 N 处潜在矛盾",
      "contradictions": [
          {
              "fact_id": "fact_5_起兵_1",
              "fact_text": "朱棣已起兵",
              "scene_text": "朱棣仍在犹豫是否出兵...",
              "severity": "high",  # 基于 fact 的 importance
              "repair_suggestion": "朱棣的犹豫可能是内心挣扎的体现..."
          },
          ...
      ],
      "facts_checked": 8,
      "scenes_analyzed": 2,
  }
  ```
- **D-16:** 预筛选规则——只检查满足以下条件的事实：
  1. `importance` 为 high 或 medium（low 级别跳过）
  2. 事实的 `actors` 与最近 2 场出现的角色有交集，或 category 为 "rule"（全局规则始终检查）
  3. 事实的 `scene` < `current_scene`（跳过本场景刚添加的事实）
- **D-17:** 检查频率——每 5 场导演 prompt 自动提醒调用 `validate_consistency()`（通过 `_build_facts_section()` 中的提醒行实现）。与 Phase 8 的 8 场 STORM 间隔区分，一致性检查更频繁因为它是质量保障

### 矛盾修复策略
- **D-18:** 三级矛盾严重度处理：
  1. **high severity**（核心事实矛盾）：必须修复——导演 prompt 中强制要求处理，生成修复性旁白
  2. **medium severity**（重要事实矛盾）：建议修复——导演 prompt 中提醒，导演可选择忽略
  3. **low severity**（次要事实矛盾，由 fact importance="low" 的矛盾降级为 low）：不修复——记录但不打断叙事
- **D-19:** 修复方式——生成修复性旁白（COHERENCE-04 要求），两种模式：
  1. **补充式**（"之前未曾提及的是..."）——用于信息缺失型矛盾，补充前文未明说但合理的信息
  2. **修正式**（"其实..."、"原来..."）——用于直接矛盾，用角色视角差异或新发现来"圆回"
- **D-20:** `generate_repair_narration(state, contradiction)` — LLM 调用生成修复旁白文本：
  - 输入：矛盾描述 + 相关事实 + 最近场景内容
  - 输出：1-2 句修复性旁白文本
  - prompt 指令："用自然的旁白语气修复矛盾，不要直接说'这是矛盾'，而是通过补充信息或视角转换让叙事自洽"
- **D-21:** 矛盾修复不自动执行——`validate_consistency()` 返回矛盾和建议，由导演决定是否修复及如何修复。与 Phase 6/7/8/9 的"导演建议模式"精神一致
- **D-22:** 导演修复矛盾的 Tool——`repair_contradiction(fact_id, repair_type, tool_context)`：
  - `repair_type`："supplement"（补充式）或 "correction"（修正式）
  - 执行后：更新 `established_facts` 中对应事实（追加 `repair_note` 字段），记录修复历史
  - 不删除或修改原始事实——保持审计轨迹

### 角色一致性验证
- **D-23:** Prompt 注入方式——在 `build_actor_context_from_memory()` 中新增【角色锚点】段落，提醒演员遵守性格定义和关键记忆。与 A2A 隔离架构兼容，不改变演员的独立性
- **D-24:** 角色锚点内容包含：
  1. **性格定义**：从 `actors[name].personality` 提取核心性格关键词
  2. **关键记忆**：从 `working_memory` 中 `is_critical=True` 的条目
  3. **已确立事实**：从 `established_facts` 中 `actors` 包含该演员的 high importance 事实
- **D-25:** 锚点段落格式：
  ```
  【角色锚点】（你必须遵守的约束）
  性格核心：果断、野心勃勃、多疑
  关键记忆：[第3场] 你发现了密信的内容
  已确立事实：你已起兵（第5场）
  ```
- **D-26:** 演员上下文中锚点段落优先级设为 `7`（与 anchor 同级，不可截断）——角色一致性是最重要的约束
- **D-27:** 不使用代码级行为限制——A2A 架构下演员是独立 Agent，无法强制其行为。通过 prompt 引导 + 事实提醒来间接保障一致性

### 导演上下文集成
- **D-28:** `_build_facts_section(state)` 升级——从现有空壳扩展为完整实现：
  - 展示 high/medium importance 事实
  - 每 5 场显示一致性检查提醒
  - 最近一次检查结果摘要
- **D-29:** `_DIRECTOR_SECTION_PRIORITIES` 中 `"facts"` 优先级保持 `5`（与 tension/arc_tracking 同级）
- **D-30:** 导演 prompt 新增 §11 一致性保障段落：
  ```
  ## §11 一致性保障
  - 每场 write_scene 后，考虑用 add_fact 记录关键事实（角色生死、地点切换、关系变化、世界规则）
  - 【已确立事实】段落显示提醒时，调用 validate_consistency() 检查一致性
  - 发现矛盾时，用修复性旁白（"其实..."、"之前未曾提及的是..."）自然圆回，不要报错中断
  - 高严重度矛盾必须修复，中严重度建议修复，低严重度可忽略
  ```

### 状态持久化
- **D-31:** 新增 `state["established_facts"]` 顶层字段——结构见 D-01
- **D-32:** 新增 `state["coherence_checks"]` 字段，结构：
  ```python
  coherence_checks = {
      "last_check_scene": 0,      # 上次检查的场景号
      "last_result": None,         # 上次检查结果摘要
      "check_history": [],         # 检查历史 [{scene, contradictions_found, facts_checked}]
      "total_contradictions": 0,   # 累计发现矛盾数
  }
  ```
- **D-33:** `init_drama_state()` 初始化 `established_facts: []` + `coherence_checks` 子对象（所有字段默认值）
- **D-34:** `load_progress()` 兼容旧存档——缺少 `established_facts` 时 `setdefault([])`，缺少 `coherence_checks` 时初始化默认值
- **D-35:** `COHERENCE_CHECK_INTERVAL = 5`（可配置常量）——与 Phase 8 `STORM_INTERVAL = 8` 对齐但更频繁

### 新增模块
- **D-36:** 新建 `app/coherence_checker.py` 模块——包含：
  - `validate_consistency_logic(state)` — 纯函数，启发式预筛选 + 返回待检查事实列表
  - `generate_repair_narration_prompt(contradiction, facts, recent_scenes)` — 生成 LLM 修复旁白的 prompt
  - `add_fact_logic(state, fact, category, importance)` — 纯函数，事实添加 + 去重检查
  - `repair_contradiction_logic(state, fact_id, repair_type, repair_note)` — 纯函数，更新事实修复记录
  - `FACT_CATEGORIES`、`COHERENCE_CHECK_INTERVAL`、`MAX_FACTS` 常量
  - 辅助函数：`_extract_actor_names(fact_text, known_actors)`、`_check_fact_overlap(new_fact, existing_facts)`、`_filter_relevant_facts(state)`
  - 与 `conflict_engine.py`、`arc_tracker.py`、`dynamic_storm.py` 同级

### Tool 函数
- **D-37:** `validate_consistency(tool_context)` — 导演主动触发一致性检查（含 LLM 调用）
- **D-38:** `add_fact(fact, category, importance, tool_context)` — 导演手动添加事实
- **D-39:** `repair_contradiction(fact_id, repair_type, tool_context)` — 导演标记矛盾已修复

### Claude's Discretion
- `validate_consistency()` 中 LLM prompt 的精确措辞和长度
- `generate_repair_narration_prompt()` 的精确措辞
- `_extract_actor_names()` 的实现方式（简单字符串匹配 vs 关键词提取）
- `_check_fact_overlap()` 的重叠度阈值和计算方式
- `_build_facts_section()` 的精确格式和排版
- 导演 prompt §11 的具体措辞和长度
- 角色锚点段落的精确格式
- `COHERENCE_CHECK_INTERVAL` 的精确值（默认 5，可调整）
- `MAX_FACTS` 的精确值（默认 50，可调整）
- `check_history` 的保留条数上限
- `validate_consistency()` LLM 调用的 model 选择（是否使用与主 Agent 不同的模型）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 10 需求定义
- `.planning/ROADMAP.md` — Phase 10 成功标准：coherence_checker.py 模块存在、established_facts 维护事实清单、角色一致性验证、矛盾修复、每5场自动检查
- `.planning/REQUIREMENTS.md` — COHERENCE-01（一致性检查）、COHERENCE-02（关键事实追踪）、COHERENCE-03（角色一致性）、COHERENCE-04（矛盾修复）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构，is_critical 标记，working_memory 结构
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分，token 预算控制，D-04 前向兼容预留（established_facts 字段存在则纳入）
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 混合推进模式，导演 prompt 段落结构
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 张力评分完整决策，导演建议模式，纯函数模式
- `.planning/phases/07-arc-tracking/07-CONTEXT.md` — plot_threads 结构，create_thread 手动模式，dormant 检测
- `.planning/phases/08-dynamic-storm/08-CONTEXT.md` — D-17/D-20（Dynamic STORM 不实现事实检查，Phase 10 处理），discovered_scene 字段
- `.planning/phases/09-progressive-storm/09-CONTEXT.md` — 渐进式 STORM，trigger_type 区分

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/context_builder.py` — `_build_facts_section(state)` 前向兼容空壳（第824行），Phase 10 需完整实现；`_DIRECTOR_SECTION_PRIORITIES` 已有 `"facts": 5`
- `app/context_builder.py` — `build_actor_context_from_memory()` 演员上下文构建，Phase 10 需新增角色锚点段落
- `app/tools.py` — 现有 Tool 函数模式，Phase 10 需新增 3 个工具函数
- `app/agent.py` — `_improv_director` 的 tools 列表需新增 3 个工具 + prompt 需新增 §11
- `app/state_manager.py` — `init_drama_state()` 需初始化 `established_facts` + `coherence_checks`；`load_progress()` 需兼容旧存档
- `app/conflict_engine.py` — 纯函数模式参考（calculate_tension, generate_conflict_suggestion）
- `app/arc_tracker.py` — 手动 Tool 创建模式参考（create_thread_logic, set_actor_arc_logic）
- `app/dynamic_storm.py` — LLM 调用 + 状态更新模式参考（discover_perspectives_prompt, update_dynamic_storm_state）

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `context_builder.py` 的 `_build_facts_section()` — 已有前向兼容空壳，读取 `state.get("established_facts")`，Phase 10 扩展为完整实现
- `context_builder.py` 的 `_DIRECTOR_SECTION_PRIORITIES` — 已有 `"facts": 5`
- `context_builder.py` 的 `build_actor_context_from_memory()` — 演员上下文构建，已有 anchor 和 arc_summary 段落
- `state_manager.py` 的 `init_drama_state()` / `load_progress()` — 状态初始化和兼容模式
- `conflict_engine.py` 的纯函数模式 — `calculate_tension(state)` 只接收 state dict
- `arc_tracker.py` 的手动 Tool 模式 — `create_thread_logic(state, ...)` 纯函数 + `create_thread(...)` Tool 薄代理
- `dynamic_storm.py` 的 LLM prompt 模式 — `discover_perspectives_prompt()` 返回 prompt 文本
- `tools.py` 的 `dynamic_storm()` — LLM 调用 + 状态更新 + 返回结构化 dict 的完整范例

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...额外字段}`
- State 路径：`tool_context.state["drama"]["established_facts"]`
- 新模块模式：`app/coherence_checker.py` — 与 `conflict_engine.py`、`arc_tracker.py` 同级
- 导演上下文段落格式：【中文标签】+ 内容
- 导演 prompt 段落：§编号 + 标题 + 规则描述
- ID 生成：`fact_{scene}_{keyword}_{index}`（与 `thread_`/`conflict_`/`storm_` 模式对齐）
- 常量命名：`UPPER_SNAKE_CASE`
- 测试模式：`_make_state(**overrides)` 构建测试用 state，测试纯函数
- 导演建议模式：Prompt 引导而非代码强制（Phase 6 D-03/D-05、Phase 8 D-07/D-12、Phase 9 D-10）

### Integration Points
- `app/coherence_checker.py` — 新增模块，核心交付
- `app/tools.py` — 新增 `validate_consistency`、`add_fact`、`repair_contradiction` 3 个 Tool 函数
- `app/agent.py` — `_improv_director` tools 列表注册 + prompt §11 一致性保障段落
- `app/context_builder.py` — `_build_facts_section()` 完整实现 + `build_actor_context_from_memory()` 角色锚点段落
- `app/state_manager.py` — `init_drama_state()` 初始化 + `load_progress()` 兼容

</code_context>

<specifics>
## Specific Ideas

- `_build_facts_section()` 完整格式：
  ```
  【已确立事实】
  事实总数：12 条 | 上次检查：第15场（无矛盾）
  💡 距上次检查已 5 场，建议调用 validate_consistency() 检查一致性
  [核心] 朱棣已起兵（第5场确立，涉及：朱棣）
  [关系] 林风是朱棣的旧部（第3场确立，涉及：林风、朱棣）
  [地点] 故事发生在明朝（第1场确立）
  ```
- 角色锚点段落格式：
  ```
  【角色锚点】（你必须遵守的约束）
  性格核心：果断、野心勃勃、多疑
  关键记忆：[第3场] 你发现了密信的内容
  已确立事实：你已起兵（第5场）
  ```
- `_extract_actor_names(fact_text, known_actors)` 实现：遍历 `known_actors`（从 `state["actors"].keys()` 获取），检查 fact_text 是否包含角色名。简单字符串包含匹配，不引入 NLP 库
- `_check_fact_overlap(new_fact, existing_facts)` 实现：取 new_fact 前 20 字，与每个 existing fact 的 fact 字段前 20 字比较，相同字符占比 > 80% 则标记重叠
- `validate_consistency()` LLM prompt 中提供的事实列表格式：编号 + fact 文本 + category + actors，便于 LLM 逐条对照
- `check_history` 保留最近 10 条，与 Phase 8 trigger_history 保留 10 条对齐
- `MAX_FACTS = 50`：50 条事实 × 约 30 字/条 = 1500 字 ≈ 750 tokens，在导演上下文中可控
- `COHERENCE_CHECK_INTERVAL = 5`：比 STORM_INTERVAL(8) 更频繁，因为一致性是"逻辑不断"的核心承诺
- 修复性旁白 prompt 示例：
  ```
  以下是一段戏剧中发现的逻辑矛盾，请生成1-2句自然的修复性旁白：
  矛盾：事实"朱棣已起兵"与场景描述"朱棣仍在犹豫是否出兵"冲突
  修复方式：补充式（之前未曾提及的信息）
  要求：用旁白语气，自然地化解矛盾，不要直接说"这是矛盾"
  ```

</specifics>

<deferred>
## Deferred Ideas

- LLM 自动提取事实——当前导演手动添加，后续可考虑每场 write_scene 后 LLM 自动建议事实
- 自适应检查频率——根据剧情复杂度动态调整检查间隔（当前固定 5 场）
- 事实影响力追踪——追踪每个事实被检查了多少次，评估事实库的有效性
- 事实过期机制——某些事实可能随时间不再相关（如"角色在A地"但已离开），自动降级 importance
- 角色行为一致性自动检测——当前通过 prompt 锚点引导，后续可考虑 LLM 对比角色言行与性格定义
- 矛盾严重度自动评分——当前基于 fact importance，后续可考虑 LLM 评估矛盾的叙事影响
- 跨场景时间线验证——Phase 11 的 Timeline Tracking 会处理时序矛盾
- 事实的可视化——展示事实网络和关系图
- 用户自定义一致性规则——允许用户定义特定的一致性约束

</deferred>

---

*Phase: 10-coherence-system*
*Context gathered: 2026-04-13*
