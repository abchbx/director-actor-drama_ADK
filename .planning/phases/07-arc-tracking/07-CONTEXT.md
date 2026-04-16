# Phase 7: Arc Tracking - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

追踪角色弧线和故事弧线的完成度，确保弧线不被遗忘。

核心交付物：
1. `state["plot_threads"]` 结构化剧情线索列表——每条线索包含 id、description、status（active/dormant/resolved）、involved_actors、introduced_scene
2. `state["actors"][name]["arc_progress"]` 角色弧线追踪——arc_type（成长/堕落/转变）、arc_stage（铺垫/发展/高潮/收束）、progress（0-100）
3. dormant 自动检测——线索超过 8 场无更新时自动标记 dormant，导演上下文自动提醒
4. active_conflicts 的 resolve 机制——冲突可被标记为已解决，从 active 列表移到 resolved 历史
5. 导演 Tool 函数——create_thread、update_thread、resolve_thread、set_actor_arc、resolve_conflict
6. 演员上下文集成——演员看到涉及自己的活跃线索

**不包含：** Dynamic STORM 多视角发现（Phase 8）、渐进式 STORM（Phase 9）、一致性检查（Phase 10）、时间线追踪（Phase 11）
</domain>

<decisions>
## Implementation Decisions

### plot_threads 与 active_conflicts 的关系
- **D-01:** `plot_threads` 与 `active_conflicts` 独立共存。`active_conflicts` 归 conflict_engine 管（短生命周期、自动去重），`plot_threads` 归 arc_tracker 管（长生命周期、手动/自动变迁）
- **D-02:** 冲突可通过可选 `thread_id` 字段关联到线索（`active_conflicts` 中的条目可包含 `thread_id: str | None`），但不强制——部分冲突不绑定任何线索
- **D-03:** 两者在语义上不同：冲突是"当前的张力源"（short-lived，注入后活跃一段时间），线索是"正在展开的故事线"（long-lived，可跨越整个戏剧）

### 角色弧线追踪方式
- **D-04:** 在 `state["actors"][name]` 中新增独立 `arc_progress` 字段，与 `arc_summary`（记忆压缩产物）分离
- **D-05:** `arc_progress` 字段结构：
  ```python
  arc_progress = {
      "arc_type": "",        # "growth" | "fall" | "transformation" | "redemption" | ""
      "arc_stage": "",       # "setup" | "development" | "climax" | "resolution" | ""
      "progress": 0,         # 0-100 完成度
      "related_threads": [], # 关联的 plot_thread ID 列表
  }
  ```
- **D-06:** 预定义弧线类型常量 `ARC_TYPES = {"growth": "成长", "fall": "堕落", "transformation": "转变", "redemption": "救赎"}`
- **D-07:** 预定义弧线阶段常量 `ARC_STAGES = {"setup": "铺垫", "development": "发展", "climax": "高潮", "resolution": "收束"}`
- **D-08:** `arc_progress` 初始值为空（arc_type="", arc_stage="", progress=0, related_threads=[]）——不要求角色创建时确定弧线

### dormant 检测与导演提醒机制
- **D-09:** dormant 检测通过 `context_builder` 自动注入，不需要导演主动调用 Tool。与 Phase 6 的"导演主动调用 evaluate_tension()"模式不同——dormant 提醒是被动警示灯
- **D-10:** `build_director_context()` 新增 `_build_arc_tracking_section(state)` 段落，自动计算每条线索"距上次更新的场次数"，>8 场标记 dormant
- **D-11:** 导演上下文格式：
  ```
  【弧线追踪】
  活跃线索：2 条 | 休眠线索：1 条 | 已解决：3 条
  ⚠️ 休眠线索：[thread_3_爱情线] "苏念与朱棣的秘密关系" — 10 场未更新
  - [active] thread_1_复仇线: "林风对朱棣的复仇计划"（涉及：林风、朱棣）
  - [active] thread_2_成长线: "苏念从懦弱到勇敢的转变"（涉及：苏念）
  ```
- **D-12:** 注册优先级 `"arc_tracking": 5`（与 tension 同级，不可忽略）

### 活跃冲突上限与线索 resolving 状态
- **D-13:** 软约束——`inject_conflict()` 在活跃冲突达上限时返回提醒，建议导演先推进某条线索进入 resolving 状态，但不阻止注入。延续 Phase 6 D-05"导演建议模式"精神
- **D-14:** 修改 `inject_conflict()` 返回值：当 `active_conflicts >= MAX_ACTIVE_CONFLICTS` 时，除了现有提醒外，额外返回"建议先推进线索"的提示，并列出当前 active 的 plot_threads 供导演选择

### plot_threads 的创建与更新时机
- **D-15:** 导演 Tool 为主——新增 3 个工具函数：
  1. `create_thread(description, involved_actors, tool_context)` — 导演主动创建线索
  2. `update_thread(thread_id, status, progress_note, tool_context)` — 导演主动更新线索进展
  3. `resolve_thread(thread_id, resolution, tool_context)` — 导演标记线索为 resolved
- **D-16:** 不使用自动检测创建新线索——线索提取需要创意决策，误提取比漏提取更有害
- **D-17:** dormant 自动检测在 context_builder 中实现（纯启发式，不依赖 Tool 调用）
- **D-18:** plot_threads 每条线索包含 `last_updated_scene` 字段——每次 `update_thread` 时更新，dormant 检测基于 `current_scene - last_updated_scene > DORMANT_THRESHOLD`
- **D-19:** `DORMANT_THRESHOLD = 8`（与 Phase 6 的 `DEDUP_WINDOW` 对齐）

### active_conflicts 的 resolve 机制
- **D-20:** `conflict_engine.py` 新增 `resolve_conflict(conflict_id, state)` 纯函数——将冲突从 `active_conflicts` 移到 `resolved_conflicts` 列表（保留历史，不删除）
- **D-21:** `tools.py` 新增 `resolve_conflict_tool(conflict_id, tool_context)` — 导演主动标记冲突已解决
- **D-22:** `conflict_engine` 状态新增 `resolved_conflicts: []` 字段——已解决冲突的归档列表
- **D-23:** 可选关联机制：当关联的 plot_thread（通过 `thread_id`）被标记 resolving/resolved 时，`resolve_thread()` 返回值中包含提示"关联冲突 {conflict_id} 是否也解决？"，但不自动执行——导演需另行调用 `resolve_conflict_tool()`
- **D-24:** 不实现冲突自动过期——冲突可能持续很久仍有张力，过早移除会丢失张力来源

### arc_progress 的更新触发
- **D-25:** 导演 Tool 手动更新——新增 `set_actor_arc(actor_name, arc_type, arc_stage, progress, tool_context)` 工具
- **D-26:** 导演 prompt §9 中引导：**当角色经历了关键转折后，使用 set_actor_arc 更新弧线状态**
- **D-27:** 不使用 LLM 自动推断弧线类型和进展——弧线类型判断需要创意决策，LLM 推断不稳定且增加调用开销
- **D-28:** 不要求角色创建时确定弧线——戏剧的乐趣在于角色不可预测的发展

### plot_threads 与演员上下文的集成
- **D-29:** 两层都注入——导演看全貌，演员只看涉及自己的
- **D-30:** 导演上下文：`_build_arc_tracking_section()` 显示全部线索（active/dormant/resolved），这是 D-10/D-11
- **D-31:** 演员上下文：`build_actor_context_from_memory()` 新增【你的剧情线索】段落
  - 从 `plot_threads` 中筛选 `involved_actors` 包含该演员的线索
  - 仅显示 `status == "active"` 的线索（dormant 不显示，避免干扰演员判断）
  - 格式简洁：`- [成长] 你正在经历从懦弱到勇敢的转变（进展：60%）`
  - 同时显示 `arc_progress` 信息
- **D-32:** 演员上下文中线索段落的优先级设为 5（与 arc_summary 同级），token 预算允许时显示

### 状态持久化
- **D-33:** 新增 `state["plot_threads"]` 顶层字段，结构：
  ```python
  plot_threads = [
      {
          "id": "thread_{scene}_{keyword}_{index}",  # 如 thread_3_复仇_1
          "description": "林风对朱棣的复仇计划",
          "status": "active",       # "active" | "dormant" | "resolving" | "resolved"
          "involved_actors": ["林风", "朱棣"],
          "introduced_scene": 3,
          "last_updated_scene": 5,
          "progress_notes": ["第3场：林风发现朱棣的秘密", "第5场：林风开始策划"],
      },
      ...
  ]
  ```
- **D-34:** `init_drama_state()` 初始化 `plot_threads: []`
- **D-35:** `load_progress()` 兼容旧存档——缺少 `plot_threads` 时自动初始化为 `[]`
- **D-36:** 演员级 `arc_progress` 初始化：`init_drama_state()` 中已有演员初始化逻辑，新增 `arc_progress` 默认值；`load_progress()` 中为旧演员数据 `setdefault("arc_progress", default_arc_progress)`
- **D-37:** `conflict_engine` 新增 `resolved_conflicts` 字段：`init_drama_state()` 和 `load_progress()` 中 `setdefault`

### 新增模块
- **D-38:** 新建 `app/arc_tracker.py` 模块——包含 `create_thread_logic()`、`update_thread_logic()`、`resolve_thread_logic()`、`set_actor_arc_logic()`、`resolve_conflict_logic()` 纯函数，以及 `ARC_TYPES`、`ARC_STAGES`、`DORMANT_THRESHOLD` 常量。与 `conflict_engine.py` 同级，职责单一

### 导演 Prompt 集成
- **D-39:** 导演 prompt 新增 §9 弧线追踪段落：
  ```
  ## §9 弧线追踪与线索管理
  - 注意【弧线追踪】段落中的休眠线索——被遗忘的故事线需要重新激活或收束
  - 当角色经历关键转折时，使用 set_actor_arc 更新弧线类型和进展
  - 当发现新的故事线索时，使用 create_thread 创建追踪
  - 当线索有进展时，使用 update_thread 更新状态
  - 当线索自然结束时，使用 resolve_thread 标记为已解决
  - 活跃冲突达上限时，优先解决已有冲突或推进线索，而非继续注入
  ```

### Claude's Discretion
- plot_threads 的 `id` 生成策略（建议 thread_{scene}_{keyword}_{index}，具体 keyword 提取方式可自行决定）
- `_build_arc_tracking_section()` 的精确格式和排版
- 演员上下文中【你的剧情线索】段落的具体措辞
- `progress_notes` 的条目上限（建议 10 条，超出时丢弃最早的）
- `resolved_conflicts` 的保留上限（建议 20 条，与 MAX_TENSION_HISTORY 对齐）
- 导演 prompt §9 的具体措辞和长度
- `_DIRECTOR_SECTION_PRIORITIES` 和 `_ACTOR_SECTION_PRIORITIES` 中新增条目的精确优先级数值
- `set_actor_arc()` 是否允许部分更新（只更新 arc_type 而不更新 progress）
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 7 需求定义
- `.planning/ROADMAP.md` — Phase 7 成功标准：plot_threads 结构化列表、角色弧线追踪、dormant 自动标记、活跃冲突上限 3-4 + resolving 要求
- `.planning/REQUIREMENTS.md` — CONFLICT-05（弧线追踪）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构，arc_summary 是 Tier 3 压缩产物（会被 LLM 整体重写）
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分，token 预算控制，导演/演员上下文构建模式
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — DramaRouter 架构，场景衔接
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 混合推进模式，导演 prompt 7 段结构
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 冲突引擎完整决策（D-01~D-19），active_conflicts 结构，evaluate_tension / inject_conflict 工具签名

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/conflict_engine.py` — 冲突引擎核心，Phase 7 需扩展 resolve_conflict + resolved_conflicts 字段
- `app/context_builder.py` — 导演/演员上下文构建，Phase 7 需新增 _build_arc_tracking_section + 演员线索段落
- `app/state_manager.py` — init_drama_state / load_progress，Phase 7 需新增 plot_threads + arc_progress + resolved_conflicts 初始化
- `app/tools.py` — Tool 函数薄代理模式，Phase 7 需新增 5 个工具函数
- `app/agent.py` — _improv_director tools 列表 + prompt §9
- `app/memory_manager.py` — arc_summary 的生成和更新逻辑，Phase 7 需理解但不能修改（arc_progress 与之独立）

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）
- `.planning/codebase/STRUCTURE.md` — 模块依赖图，新代码添加位置

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `conflict_engine.py` 的纯函数模式——`calculate_tension(state)`、`generate_conflict_suggestion(state, conflict_type)` 等只接收 `state: dict`，不依赖 ToolContext。Phase 7 的 `arc_tracker.py` 遵循相同模式
- `conflict_engine.py` 的 `update_conflict_engine_state(state, tension_result, conflict_suggestion)` 状态更新模式——集中式状态更新，调用方持久化
- `context_builder.py` 的 `_build_tension_section()` / `_build_conflict_section()` — 段落构建模式，Phase 7 新增 `_build_arc_tracking_section()` 遵循相同签名和返回格式
- `context_builder.py` 的 `_DIRECTOR_SECTION_PRIORITIES` — 优先级注册机制
- `context_builder.py` 的 `build_actor_context_from_memory()` — 演员上下文构建，已有 arc_summary 段落（priority 3），Phase 7 新增线索段落
- `state_manager.py` 的 `init_drama_state()` / `load_progress()` — 状态初始化和兼容模式，已有 conflict_engine 字段初始化（Phase 6 D-16~D-18）
- `tools.py` 的 `evaluate_tension()` / `inject_conflict()` — Tool 函数薄代理模式，Phase 7 新增 5 个工具函数遵循相同签名
- `conflict_engine.py` 的 `CONFLICT_TEMPLATES` 常量模式——Phase 7 的 `ARC_TYPES` / `ARC_STAGES` 遵循相同模式

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...额外字段}`
- State 路径：`tool_context.state["drama"]["plot_threads"]`、`tool_context.state["drama"]["actors"][name]["arc_progress"]`
- 新模块模式：`app/arc_tracker.py` — 与 `conflict_engine.py`、`memory_manager.py` 同级
- 导演上下文段落格式：【中文标签】+ 内容
- 导演 prompt 段落：§编号 + 标题 + 规则描述
- ID 生成：`thread_{scene}_{keyword}_{index}`（与 `conflict_{scene}_{type}_{index}` 模式对齐）
- 常量命名：`UPPER_SNAKE_CASE`
- 测试模式：`_make_state(**overrides)` 构建测试用 state，测试纯函数

### Integration Points
- `app/arc_tracker.py` — 新增模块，核心交付
- `app/conflict_engine.py` — 新增 `resolve_conflict()` 纯函数 + `resolved_conflicts` 字段
- `app/tools.py` — 新增 `create_thread`、`update_thread`、`resolve_thread`、`set_actor_arc`、`resolve_conflict_tool` 5 个 Tool 函数
- `app/agent.py` — `_improv_director` tools 列表注册 + prompt §9 弧线追踪段落
- `app/context_builder.py` — 新增 `_build_arc_tracking_section()` + 演员上下文线索段落 + `_DIRECTOR_SECTION_PRIORITIES` / `_ACTOR_SECTION_PRIORITIES` 新增
- `app/state_manager.py` — `init_drama_state()` 初始化 `plot_threads: []` + 演员 `arc_progress` 默认值 + `conflict_engine.resolved_conflicts: []`；`load_progress()` 兼容

</code_context>

<specifics>
## Specific Ideas

- `plot_threads` 的 `id` 采用 `thread_{scene}_{keyword}_{index}` 格式，如 `thread_3_复仇_1`。keyword 从 description 中提取第一个关键词（中文 2-4 字），index 为同场景同关键词的序号
- dormant 检测的阈值 `DORMANT_THRESHOLD = 8`，与 Phase 6 的 `DEDUP_WINDOW = 8` 对齐——约覆盖 2-3 轮完整场景循环
- `_build_arc_tracking_section()` 中的休眠线索用 ⚠️ 标记，与 Phase 6 张力段落的格式风格一致
- 演员上下文中线索段落使用 `arc_type` 的中文名显示（如"成长"而非"growth"），与代码库中中文用户面向字符串的习惯一致
- `inject_conflict()` 的修改：在现有 `MAX_ACTIVE_CONFLICTS` 检查中，额外返回 `suggested_threads` 列表（当前 active 的 plot_threads），帮助导演选择推进哪条线索
- `resolve_conflict()` 移动冲突到 `resolved_conflicts` 而非删除——保留历史有助于后续 Dynamic STORM（Phase 8）分析冲突模式
- `progress_notes` 保留最近 10 条，超出时 FIFO 丢弃最早的——避免无限增长
- `resolved_conflicts` 保留最近 20 条，与 `MAX_TENSION_HISTORY` 对齐

</specifics>

<deferred>
## Deferred Ideas

- LLM 自动推断 arc_type 和 progress——当前手动更新足够，后续可考虑 LLM 辅助推断作为增强
- 自动检测新 plot_threads——当前导演手动创建，后续可考虑从场景内容中自动提取线索建议
- plot_threads 的语义检索——Phase 3 的 semantic_retriever 目前按标签检索场景，后续可扩展检索线索
- 线索进展的自动评分——根据 involved_actors 的记忆变化自动评估线索进展程度
- 冲突-线索双向导航——从线索页面查看关联冲突，从冲突页面跳转到关联线索
- 弧线完成时的庆贺旁白——角色弧线达到 100% 时自动生成庆贺性旁白
- 多角色联合弧线——多个角色的弧线相互影响时的追踪机制

</deferred>

---

*Phase: 07-arc-tracking*
*Context gathered: 2026-04-13*
