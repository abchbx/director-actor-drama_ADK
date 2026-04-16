# Phase 11: Timeline Tracking - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

维护剧情时间线，防止时序矛盾和场景跳跃。

核心交付物：
1. `app/timeline_tracker.py` 模块——时间线追踪纯函数 + LLM 时间推断
2. `state["timeline"]` 结构化时间状态——包含 `current_time`、`days_elapsed`、`time_periods`、`events`
3. `advance_time(time_description, tool_context)` 导演 Tool——声明时间推进
4. `detect_timeline_jump(tool_context)` 导演 Tool——检测场景时间跳跃
5. 导演上下文【时间线】段落——`_build_timeline_section(state)` 完整实现
6. `build_actor_context_from_memory()` 新增时间信息段落
7. 与 `established_facts` 交叉验证——事件时序与时间线一致性
8. 导演 prompt §12 时间线管理段落
9. `write_scene()` 自动记录场景时间戳

**不包含：** 自适应时间推进（deferred）、时间线可视化（deferred）、用户自定义时间规则（deferred）

</domain>

<decisions>
## Implementation Decisions

### 时间表示方式
- **D-01:** 混合模式——`current_time` 保留描述性字符串（如"第三天黄昏"），同时维护结构化 `time_periods` 列表用于规则引擎判断。两套表示互为补充：
  - 描述性字符串 → LLM 和人类可读，用于 prompt 展示
  - 结构化 `time_periods` → 规则引擎可计算，用于跳跃检测和交叉验证
- **D-02:** `time_periods` 结构定义——有序列表，每个时间段为 dict：
  ```python
  time_periods = [
      {
          "label": "第一天清晨",          # 描述性标签
          "day": 1,                       # 天数（整数，用于计算跨度）
          "period": "清晨",               # 时段（清晨/上午/中午/下午/黄昏/夜晚/深夜）
          "scene_range": [1, 3],          # 覆盖的场景范围
      },
      {
          "label": "第三天黄昏",
          "day": 3,
          "period": "黄昏",
          "scene_range": [4, 4],
      },
  ]
  ```
- **D-03:** 时段枚举常量 `TIME_PERIODS`：
  ```python
  TIME_PERIODS = ["清晨", "上午", "中午", "下午", "黄昏", "夜晚", "深夜"]
  ```
  用于规则引擎比较时序——`TIME_PERIODS.index(period_a) < TIME_PERIODS.index(period_b)` 判断先后。
- **D-04:** `days_elapsed` 为整数，从 1 开始。`current_time` 为描述性字符串，由导演通过 `advance_time()` 设置或 LLM 推断。初始值为"第一天"。
- **D-05:** 时间线不强制线性推进——允许倒叙（回忆、闪回），但必须明确标记。`time_periods` 中的条目可包含 `"flashback": True` 标记。

### 时间推进机制
- **D-06:** 导演手动声明为主——新增 `advance_time(time_description, day, period, tool_context)` Tool 函数。导演在 `director_narrate()` 或 `write_scene()` 时声明本场时间设定。
- **D-07:** `advance_time()` 函数签名：
  ```python
  def advance_time(
      time_description: str,     # 如"第三天黄昏"——完整描述性时间
      day: int | None = None,    # 天数（可选，LLM 可从描述推断）
      period: str | None = None, # 时段（可选，需在 TIME_PERIODS 中）
      tool_context: ToolContext = ...,
  ) -> dict:
  ```
  - 当 `day` 和 `period` 都提供时，直接更新 `state["timeline"]`
  - 当缺少 `day` 或 `period` 时，尝试从 `time_description` 中解析（中文数字转换 + 时段关键词匹配）
  - 解析失败时仍更新 `current_time` 字符串，但 `days_elapsed` 和 `period` 保持旧值，并返回提醒
- **D-08:** 每场 `write_scene()` 自动记录场景时间戳——在 scene dict 中新增 `"time_label"` 字段，值为调用时的 `state["timeline"]["current_time"]`。这是被动记录，不改变时间状态。
- **D-09:** 不使用 LLM 自动推断时间推进——与 Phase 10 D-07"不使用 LLM 自动提取事实"逻辑一致：时间判断需要创意决策（本场跨多长时间？是否闪回？），误推断比漏推断更有害。导演通过 `advance_time()` 显式控制。
- **D-10:** `advance_time()` 的调用时机——导演 prompt §12 引导：
  - 场景时间发生明显变化时调用（换天、换时段）
  - 第一场戏初始化时间设定
  - 回忆/闪回场景开始前调用
  - 无时间变化时无需调用（延续上一场时间）

### 场景跳跃检测
- **D-11:** 跳跃检测基于 `days_elapsed` 差值——规则引擎纯函数：
  ```python
  def detect_timeline_jump_logic(state: dict) -> dict:
  ```
  对比 `time_periods` 中相邻条目的 `day` 差值：
  - 同一天内跳时段 → 正常（信息可能省略）
  - 跨 1-2 天 → 轻微跳跃（提醒但不禁断）
  - 跨 3+ 天 → 显著跳跃（导演 prompt 警告，建议插入过渡场景或 add_fact 解释）
- **D-12:** 跳跃检测不自动修正——返回提醒和建议，由导演决定处理方式。与 Phase 6/7/8/9/10 的"导演建议模式"一致。
- **D-13:** 跳跃检测结果结构：
  ```python
  {
      "status": "success",
      "jumps": [
          {
              "from_scene": 4,
              "to_scene": 5,
              "from_time": {"day": 1, "period": "夜晚"},
              "to_time": {"day": 4, "period": "清晨"},
              "day_gap": 3,
              "severity": "significant",  # "normal" | "minor" | "significant"
              "suggestion": "跨 3 天无过渡，建议插入过渡场景或用旁白说明时间流逝",
          }
      ],
      "max_gap": 3,
  }
  ```
- **D-14:** `severity` 级别定义：
  - `normal`：同一天内时段变化或跨 0 天
  - `minor`：跨 1-2 天
  - `significant`：跨 3+ 天
- **D-15:** 跳跃检测触发时机——与一致性检查对齐，在 `validate_consistency()` 中可选调用 `detect_timeline_jump_logic()`，同时在导演上下文的【时间线】段落中自动展示最近一次检测结果。

### 与 established_facts 交叉验证
- **D-16:** 时间线验证集成到一致性检查——`validate_consistency_logic()` 中新增时间线验证步骤：
  1. 检查 `established_facts` 中 `category: "event"` 事实的时序——如果事实 A（第 3 天发生）依赖事实 B（第 5 天发生），则标记时序矛盾
  2. 检查场景描述中的时间信息与 `timeline.current_time` 是否一致
- **D-17:** 时序矛盾作为 `contradictions` 的子类型——在 `validate_consistency_prompt()` 中新增指令："检查事件时序是否与时间线一致，注意事件的因果顺序"。
- **D-18:** 事实新增 `time_context` 可选字段——`add_fact()` 可选参数，记录事实发生的时间上下文：
  ```python
  def add_fact(fact, category, importance, time_context=None, tool_context):
  ```
  `time_context` 示例："第三天黄昏"——自动存入事实 dict。用于后续交叉验证。
- **D-19:** 不强制事实关联时间——`time_context` 为可选参数，缺失时不影响现有功能。导演可选择性地为关键事件标记时间上下文。

### 时间信息在上下文中的呈现
- **D-20:** 导演上下文新增【时间线】段落——`_build_timeline_section(state)` 完整实现：
  ```
  【时间线】
  当前：第三天黄昏 | 累计：3 天 | 场景覆盖：12 场
  💡 最近一次跳跃检测：第4场→第5场跨3天（显著跳跃）
  时间脉络：
  - 第1场～第3场：第一天清晨→夜晚
  - 第4场：第三天黄昏
  - 第5场：第四天清晨
  ```
- **D-21:** `_DIRECTOR_SECTION_PRIORITIES` 中 `"timeline"` 优先级为 `5`——与 facts、tension、arc_tracking 同级。时间线是一致性保障的重要组成部分。
- **D-22:** 演员上下文新增【当前时间】段落——在 `build_actor_context_from_memory()` 中新增：
  ```
  【当前时间】
  第三天黄昏
  ```
  优先级设为 `6`（与 anchor 同级——时间信息是角色行为的重要约束）。简洁一行，不展开时间脉络。
- **D-23:** 【时间线】段落整合到导演上下文构建——在 `build_director_context()` 的 sections 列表中，`timeline` 位于 `facts` 之后（两者相关性强，相邻展示）。

### 导演 Prompt 集成
- **D-24:** 导演 prompt 新增 §12 时间线管理段落：
  ```
  ## §12 时间线管理
  - 场景时间变化时调用 advance_time() 声明时间（换天、换时段、闪回）
  - 【时间线】段落显示跳跃检测提醒时，考虑用旁白补充时间过渡
  - 关键事件建议在 add_fact() 时附带 time_context 参数记录时间上下文
  - 时间线与已确立事实交叉验证——事件因果顺序必须与时间线一致
  ```
- **D-25:** §12 注入条件——与 §11 一致，在 STRATEGY 层中，当 `scene_count > 3` 时注入。时间线在早期场景（1-3 场）不太需要管理。

### 状态持久化
- **D-26:** 新增 `state["timeline"]` 顶层字段——结构：
  ```python
  timeline = {
      "current_time": "第一天",       # 描述性当前时间（D-04）
      "days_elapsed": 1,              # 累计天数（D-04）
      "current_period": None,         # 当前时段（TIME_PERIODS 之一，初始 None）
      "time_periods": [],             # 有序时间段列表（D-02）
      "last_jump_check": None,        # 最近一次跳跃检测结果摘要
  }
  ```
- **D-27:** `init_drama_state()` 初始化 `timeline` 子对象（所有字段默认值）。
- **D-28:** `load_progress()` 兼容旧存档——缺少 `timeline` 时初始化默认值。
- **D-29:** `advance_scene()` 中不自动推进时间——与 Phase 4 设计一致，场景编号推进不等于时间推进。时间推进由导演通过 `advance_time()` 控制。

### 新增模块
- **D-30:** 新建 `app/timeline_tracker.py` 模块——包含：
  - `advance_time_logic(state, time_description, day, period)` — 纯函数，更新 timeline 状态
  - `detect_timeline_jump_logic(state)` — 纯函数，跳跃检测
  - `parse_time_description(text)` — 从描述性文本解析 day 和 period
  - `TIME_PERIODS`、`TIMELINE_JUMP_THRESHOLDS` 常量
  - 辅助函数：`_chinese_num_to_int(text)`、`_extract_period(text)`、`_build_time脉络(state)`
  - 与 `coherence_checker.py`、`conflict_engine.py`、`arc_tracker.py` 同级

### Tool 函数
- **D-31:** `advance_time(time_description, day, period, tool_context)` — 导演声明时间推进
- **D-32:** `detect_timeline_jump(tool_context)` — 导演触发跳跃检测（也可自动触发）
- **D-33:** `add_fact()` 扩展——新增可选 `time_context` 参数（D-18）

### Claude's Discretion
- `parse_time_description()` 的精确实现方式（正则匹配中文数字 vs 查找表）
- `_chinese_num_to_int()` 的覆盖范围（一到九十九足够）
- `_build_time脉络(state)` 的精确格式和排版
- 导演 prompt §12 的具体措辞和长度
- 【时间线】段落的精确格式
- 【当前时间】段落的精确格式
- `TIMELINE_JUMP_THRESHOLDS` 的精确值（当前 minor=1-2, significant=3+）
- `time_periods` 保留条数上限（建议 20，超过时合并旧条目）
- `advance_time()` 中解析失败时的提醒措辞
- 跳跃检测在导演上下文中自动展示的频率（每场 vs 仅检测时）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 11 需求定义
- `.planning/ROADMAP.md` — Phase 11 成功标准：state["timeline"] 包含 current_time 和 days_elapsed、每场戏推进时间确定性更新、场景跳跃检测、时间线与已确立事实交叉验证
- `.planning/REQUIREMENTS.md` — COHERENCE-05（时间线追踪）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/10-coherence-system/10-CONTEXT.md` — established_facts 结构、coherence_checker 纯函数模式、_build_facts_section 格式、导演建议模式、validate_consistency 逻辑
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构，is_critical 标记
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分，token 预算控制
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — advance_scene 不自动推进时间的设计
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 导演 prompt 段落结构
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — 导演建议模式
- `.planning/phases/07-arc-tracking/07-CONTEXT.md` — plot_threads 结构，手动 Tool 创建模式
- `.planning/phases/08-dynamic-storm/08-CONTEXT.md` — Dynamic STORM 与一致性的关系
- `.planning/phases/09-progressive-storm/09-CONTEXT.md` — 渐进式 STORM

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/coherence_checker.py` — 纯函数模式参考（validate_consistency_logic, add_fact_logic, repair_contradiction_logic）
- `app/context_builder.py` — `_build_facts_section(state)` 完整实现，Phase 11 需新增 `_build_timeline_section(state)`；`build_actor_context_from_memory()` 需新增时间段落
- `app/context_builder.py` — `_DIRECTOR_SECTION_PRIORITIES` 需新增 `"timeline": 5`
- `app/tools.py` — 现有 Tool 函数模式，Phase 11 需新增 2 个工具函数 + 扩展 add_fact
- `app/agent.py` — `_improv_director` tools 列表需新增 2 个工具 + STRATEGY 层需新增 §12
- `app/state_manager.py` — `init_drama_state()` 需初始化 `timeline`；`load_progress()` 需兼容旧存档；`advance_scene()` 不改变
- `app/conflict_engine.py` — 纯函数模式参考
- `app/arc_tracker.py` — 手动 Tool 创建模式参考
- `app/state_manager.py` — `advance_scene()` 函数——场景编号推进逻辑，Phase 11 不修改

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `context_builder.py` 的 `_build_facts_section()` — 展示格式参考（中文标签 + 统计行 + 提醒行 + 条目列表）
- `context_builder.py` 的 `_DIRECTOR_SECTION_PRIORITIES` — 需新增 `"timeline": 5`
- `context_builder.py` 的 `build_actor_context_from_memory()` — 演员上下文构建，需新增时间段落
- `state_manager.py` 的 `init_drama_state()` / `load_progress()` — 状态初始化和兼容模式
- `coherence_checker.py` 的纯函数模式 — `validate_consistency_logic(state)` 只接收 state dict
- `coherence_checker.py` 的 `_filter_relevant_facts()` — 预筛选模式参考
- `coherence_checker.py` 的 `validate_consistency_prompt()` — LLM prompt 构建模式参考
- `coherence_checker.py` 的 `add_fact_logic()` — 事实添加逻辑，Phase 11 扩展 time_context 参数
- `tools.py` 的 `validate_consistency()` — LLM 调用 + 状态更新 + 返回结构化 dict 的完整范例
- `tools.py` 的 `add_fact()` — Tool 薄代理模式，Phase 11 扩展 time_context 参数
- `state_manager.py` 的 `advance_scene()` — 场景编号推进逻辑（不自动推进时间）
- `dynamic_storm.py` 的 LLM prompt 模式 — `discover_perspectives_prompt()` 返回 prompt 文本

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...额外字段}`
- State 路径：`tool_context.state["drama"]["timeline"]`
- 新模块模式：`app/timeline_tracker.py` — 与 `coherence_checker.py`、`conflict_engine.py`、`arc_tracker.py` 同级
- 导演上下文段落格式：【中文标签】+ 内容
- 导演 prompt 段落：§编号 + 标题 + 规则描述
- ID 生成：与 fact/thread/conflict/storm 模式对齐
- 常量命名：`UPPER_SNAKE_CASE`
- 测试模式：`_make_state(**overrides)` 构建测试用 state，测试纯函数
- 导演建议模式：Prompt 引导而非代码强制
- STRATEGY 层注入条件：`scene_count > 3`

### Integration Points
- `app/timeline_tracker.py` — 新增模块，核心交付
- `app/tools.py` — 新增 `advance_time`、`detect_timeline_jump` 2 个 Tool 函数 + 扩展 `add_fact`
- `app/agent.py` — `_improv_director` tools 列表注册 + STRATEGY 层 §12
- `app/context_builder.py` — `_build_timeline_section()` 完整实现 + `build_actor_context_from_memory()` 时间段落 + `_DIRECTOR_SECTION_PRIORITIES` 新增
- `app/state_manager.py` — `init_drama_state()` 初始化 `timeline` + `load_progress()` 兼容
- `app/coherence_checker.py` — `validate_consistency_logic()` 新增时间线验证步骤 + `validate_consistency_prompt()` 新增时序检查指令
- `app/actor_service.py` — `write_scene()` 新增 `time_label` 字段记录

</code_context>

<specifics>
## Specific Ideas

- `_build_timeline_section(state)` 完整格式：
  ```
  【时间线】
  当前：第三天黄昏 | 累计：3 天 | 场景覆盖：12 场
  💡 最近跳跃：第4场→第5场跨3天（显著跳跃），建议补充时间过渡
  时间脉络：
  - 第1场～第3场：第一天清晨→夜晚
  - 第4场：第三天黄昏
  - 第5场：第四天清晨
  ```
- 演员上下文【当前时间】段落格式：
  ```
  【当前时间】第三天黄昏
  ```
  简洁一行，不展开脉络
- `parse_time_description(text)` 实现策略：
  1. 匹配中文数字 + "天" → 提取 day：`re.search(r"第([一二三四五六七八九十百]+)天", text)`
  2. 匹配 TIME_PERIODS 中的时段关键词 → 提取 period
  3. 无匹配时返回 None，`advance_time_logic()` 仍更新 current_time 字符串
- `_chinese_num_to_int(text)` 实现：查找表 `{"一":1, "二":2, ..., "十":10, "十一":11, ..., "九十九":99}`，覆盖 1-99 天足够
- `_build_time脉络(state)` 实现：遍历 `time_periods`，合并相邻同天条目为范围格式（"第一天清晨→夜晚"），不同天分行
- `time_periods` 保留上限 `MAX_TIME_PERIODS = 20`——超过时合并最早的条目：同一天的多条目合并为一条，`scene_range` 扩展
- 跳跃检测自动展示——每次 `advance_time()` 后自动运行 `detect_timeline_jump_logic()`，结果存入 `timeline.last_jump_check`，在导演上下文中展示
- `add_fact()` 扩展——`time_context` 参数可选，传入时存入事实 dict 的 `"time_context"` 字段，不传入时不影响现有逻辑
- 事实与时间线交叉验证 prompt 增强——在 `validate_consistency_prompt()` 中新增："检查事件时序：事实中标记了 time_context 的，其因果顺序应与时间线一致。如果事实 A 发生在事实 B 之后但 time_context 更早，这是时序矛盾"

</specifics>

<deferred>
## Deferred Ideas

- 自适应时间推进——LLM 自动推断时间变化，无需导演手动调用 advance_time()（当前手动为主，后续可考虑 LLM 建议）
- 时间线可视化——展示时间线和事件的可视化图表
- 用户自定义时间规则——允许用户定义特定的时间约束（如"魔法在满月时最强"的月相周期）
- 时间线分支——平行宇宙/多线时间追踪
- 时间压缩/扩展机制——快进/慢放特定时间段
- 闪回标记的自动识别——当前依赖导演手动标记 flashback
- 时间线与天气/季节联动——自动生成环境描述

</deferred>

---

*Phase: 11-timeline-tracking*
*Context gathered: 2026-04-13*
