# Phase 6: Tension Scoring & Conflict Engine - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

实现张力评分和自动冲突注入，当剧情平淡时自动注入转折事件，防止"流水账"。

核心交付物：
1. `evaluate_tension(tool_context)` 工具——返回 `tension_score`（0-100）、`is_boring`、`suggested_action`
2. `inject_conflict(conflict_type, tool_context)` 工具——自动生成并注入冲突事件
3. 冲突模板库（7 种类型）——新角色登场、秘密发现、矛盾升级、信任背叛、意外事件、外部威胁、抉择困境
4. `used_conflict_types` 追踪——同一类型 8 场内不重复
5. `conflict_engine` 状态管理——活跃冲突、张力历史、已用冲突类型追踪
6. 导演 prompt 集成——张力评分段落 + 低张力应对指引

**不包含：** 弧线追踪（Phase 7）、Dynamic STORM 多视角发现（Phase 8）、渐进式 STORM（Phase 9）、一致性检查（Phase 10）
</domain>

<decisions>
## Implementation Decisions

### 张力评分机制
- **D-01:** 纯启发式规则，不调用 LLM——基于 4 个信号加权计算：
  1. 情感方差（权重 30%）——所有演员 `emotions` 的离散度，中性情绪占比越高分越低
  2. 未决冲突密度（权重 30%）——`critical_memories` 中 reason="未决事件" 的数量 + `arc_summary.structured.unresolved` 的数量，越多张力越高
  3. 对话重复度（权重 20%）——最近 3 场 `working_memory` 条目的文本相似度，越重复分越低
  4. 距上次注入场次数（权重 20%）——距 `conflict_engine.last_inject_scene` 的场景间隔，越长分越低
- **D-02:** 张力评分范围 0-100，阈值：`< 30` 为"低张力"（is_boring=True），30-70 为"正常"，`> 70` 为"高张力"
- **D-03:** 评分在 `write_scene()` 之后由导演 prompt 触发调用——导演每场 write_scene 后主动调用 `evaluate_tension()`，而非代码级自动调用。尊重 ADK turn-based 模型，由 LLM 决定何时评估
- **D-04:** 评分结果写入 `state["conflict_engine"]["tension_history"]`（每场一条记录：`{scene, score, is_boring, signals}`），保留最近 20 场历史

### 冲突注入方式
- **D-05:** 冲突注入为"导演建议"模式——`inject_conflict()` 返回一个结构化的冲突建议（类型+描述+涉及角色+提示词），导演 LLM 在下一场中自由发挥如何融入，而非强制执行。保证创意灵活性
- **D-06:** 冲突模板库为 Python 常量字典（`CONFLICT_TEMPLATES`），每种类型包含：`name`（中文名）、`description`（描述）、`prompt_hint`（给导演的提示词片段）、`suggested_emotions`（建议触发的角色情绪列表）。不使用 LLM 生成模板
- **D-07:** 7 种冲突类型定义：
  1. `new_character` — 新角色登场：引入新角色打破现有格局
  2. `secret_revealed` — 秘密发现：隐藏信息被揭露，改变角色关系
  3. `escalation` — 矛盾升级：现有分歧激化为更严重的对抗
  4. `betrayal` — 信任背叛：盟友变敌或承诺被打破
  5. `accident` — 意外事件：突发状况打乱计划
  6. `external_threat` — 外部威胁：外部力量介入迫使角色联合或分裂
  7. `dilemma` — 抉择困境：角色面临两难选择，无论选哪个都有代价

### 冲突去重与节奏
- **D-08:** 同类型 8 场内不重复——`used_conflict_types` 列表记录 `{type, scene_used}`，注入前检查距上次使用的场景间隔，`< 8` 则跳过此类型。8 场窗口合理——约覆盖 2-3 轮完整场景循环
- **D-09:** 连续多场低张力的渐进升级——第 1 场低张力时建议注入，导演可选择不执行；连续 2 场低张力时 `inject_conflict()` 返回更强的提示（`urgency: "high"`）；连续 3+ 场低张力时导演 prompt 中自动包含"必须处理低张力"的强制指引。不强制代码级注入，但通过 prompt 递增紧迫感
- **D-10:** 活跃冲突上限 3-4 条——当 `active_conflicts` 达到 4 条时，`inject_conflict()` 返回"当前活跃冲突已达上限，建议先解决一条"的建议，而非继续注入

### 张力与现有系统的集成
- **D-11:** `evaluate_tension()` 注册为 `_improv_director` 的 Tool 函数——导演可主动调用，也可在 prompt 中引导每场 write_scene 后调用
- **D-12:** `inject_conflict()` 注册为 `_improv_director` 的 Tool 函数——当 `evaluate_tension()` 返回 `is_boring=True` 时，导演调用此工具获取冲突建议
- **D-13:** 导演 prompt 新增 §8 张力评估段落：
  ```
  ## §8 张力评估与冲突注入
  每场 write_scene 后，调用 evaluate_tension() 检查张力水平。
  如果 is_boring=True，调用 inject_conflict() 获取冲突建议，融入下一场。
  活跃冲突上限 4 条，超出时优先解决已有冲突。
  ```
- **D-14:** `build_director_context()` 新增【张力状态】段落——包含当前 tension_score、is_boring 状态、活跃冲突列表、最近注入冲突类型。使用已有的 `_DIRECTOR_SECTION_PRIORITIES` 新增 `"tension": 5` 优先级
- **D-15:** `build_director_context()` 中已有的 `_build_conflict_section()` 开始生效——读取 `conflict_engine.active_conflicts` 生成【活跃冲突】段落

### 状态持久化
- **D-16:** 新增 `state["conflict_engine"]` 子对象，结构如下：
  ```python
  conflict_engine = {
      "tension_score": 0,           # 当前张力评分
      "is_boring": False,           # 是否低张力
      "tension_history": [],        # 最近 20 场评分历史 [{scene, score, is_boring, signals}]
      "active_conflicts": [],       # 活跃冲突列表 [{id, type, description, involved_actors, introduced_scene}]
      "used_conflict_types": [],    # 已用冲突类型 [{type, scene_used}]
      "last_inject_scene": 0,       # 上次注入冲突的场景号
      "consecutive_low_tension": 0,  # 连续低张力场数
  }
  ```
- **D-17:** `init_drama_state()` 初始化 `conflict_engine` 子对象，所有字段设为默认值
- **D-18:** `load_progress()` 兼容旧存档——缺少 `conflict_engine` 时自动初始化默认值

### 新增模块
- **D-19:** 新建 `app/conflict_engine.py` 模块——包含 `evaluate_tension()`、`inject_conflict()`、`CONFLICT_TEMPLATES` 常量、辅助函数。与 `memory_manager.py` 同级，职责单一

### Claude's Discretion
- 4 个评分信号的具体权重微调
- 对话重复度的具体计算方式（文本哈希 vs 关键词提取 vs 简单字符串匹配）
- 冲突模板中 `prompt_hint` 的具体措辞
- `inject_conflict()` 返回的结构化建议的精确字段
- 张力评分结果呈现给用户的格式
- `tension_history` 的保留条数（20 条为默认，可调整）
- 活跃冲突的 `id` 生成策略
- 导演 prompt §8 的具体措辞和长度
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 需求定义
- `.planning/ROADMAP.md` — Phase 6 成功标准：evaluate_tension 可用、张力评分基于启发式规则、低张力自动注入、7 种冲突模板、8 场去重
- `.planning/REQUIREMENTS.md` — CONFLICT-01（张力评分）、CONFLICT-02（低张力自动注入）、CONFLICT-03（冲突模板库）、CONFLICT-04（冲突去重）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构（D-01~D-13），关键记忆保护，6 类事件检测（D-06 包含"未决事件"）
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分（D-03），token 预算控制（D-02），D-04 前向兼容预留（conflict_engine 字段存在则纳入）
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — DramaRouter 架构（D-01~D-14），场景衔接，循环驱动方式，D-07 预留 evaluate_tension() 调用位置
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — 混合推进模式（D-01~D-28），storm 子对象结构（D-22），导演 prompt 7 段结构（D-26）

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/context_builder.py` — `build_director_context()` 中已有 `_build_conflict_section()` （D-04 前向兼容），需扩展读取 `conflict_engine`；`_DIRECTOR_SECTION_PRIORITIES` 需新增 `"tension": 5`
- `app/tools.py` — 现有 Tool 函数模式，新增 `evaluate_tension` 和 `inject_conflict` 需遵循相同签名模式
- `app/agent.py` — `_improv_director` 的 tools 列表需新增 2 个工具，prompt 需新增 §8 张力评估段落
- `app/state_manager.py` — `init_drama_state()` 需初始化 `conflict_engine`，`load_progress()` 需兼容旧存档

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `context_builder.py` 的 `_build_conflict_section()` — 已有 D-04 前向兼容逻辑，读取 `state.get("conflict_engine")` → `active_conflicts`，Phase 6 实现后自动生效
- `context_builder.py` 的 `_DIRECTOR_SECTION_PRIORITIES` — 已有 `"conflicts": 4` 和预留的 `"dynamic_storm": 3`，需新增 `"tension": 5`
- `context_builder.py` 的 `_build_current_status_section()` — 可扩展显示当前张力评分和活跃冲突数
- `state_manager.py` 的 `init_drama_state()` — 已有 Phase 5 字段初始化模式（D-21/D-22/D-23），可直接复制模式
- `state_manager.py` 的 `load_progress()` — 已有旧存档兼容模式（D-28），`setdefault()` 模式
- `memory_manager.py` 的 `detect_importance()` — 已有 6 类事件检测（D-06），可复用"未决事件"检测逻辑
- `tools.py` 的 `auto_advance()` / `steer_drama()` — Phase 5 新增 Tool 函数的签名和返回格式参考

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...}`
- State 路径：`tool_context.state["drama"]["conflict_engine"]`
- 新模块模式：`app/conflict_engine.py` — 与 `memory_manager.py`、`semantic_retriever.py` 同级
- 导演上下文段落格式：【中文标签】+ 内容
- 导演 prompt 段落：§编号 + 标题 + 规则描述

### Integration Points
- `app/conflict_engine.py` — 新增模块，核心交付
- `app/tools.py` — 新增 `evaluate_tension()` 和 `inject_conflict()` 2 个 Tool 函数
- `app/agent.py` — `_improv_director` tools 列表注册 + prompt §8 张力评估段落
- `app/context_builder.py` — 新增 `_build_tension_section()` + `_build_conflict_section()` 扩展 + `_DIRECTOR_SECTION_PRIORITIES` 新增
- `app/state_manager.py` — `init_drama_state()` 初始化 + `load_progress()` 兼容

</code_context>

<specifics>
## Specific Ideas

- `evaluate_tension()` 的情感方差计算：将中文情绪映射为张力权重（"平静"=1, "困惑"=2, "焦虑"=3, "悲伤"=4, "愤怒"=5, "恐惧"=5, "决绝"=4, "喜悦"=2, "充满希望"=2），计算方差
- 对话重复度采用简单方案：最近 3 场 working_memory 条目中，前 20 字相同的条目占比（避免引入 NLP 库）
- `inject_conflict()` 返回结构：`{conflict_id, type, type_cn, description, prompt_hint, involved_actors, urgency, suggested_emotions}` — 导演可直接在 prompt 中使用 `prompt_hint` 和 `suggested_emotions`
- 张力状态在导演上下文中以【张力状态】标记，格式统一：`当前张力：45/100（正常） | 活跃冲突：2 条 | 连续低张力：0 场`
- `conflict_engine` 子对象与 `storm` 子对象同级，均位于 `state["drama"]` 顶层
- 活跃冲突的 `id` 采用 `conflict_{scene}_{type}_{index}` 格式，如 `conflict_5_escalation_1`
- 冲突模板的 `prompt_hint` 应简洁且富有创意引导性，如矛盾升级："现有分歧已到临界点——一个小火星就可能引爆全面对抗"

</specifics>

<deferred>
## Deferred Ideas

- LLM 辅助的张力评分——当前纯启发式足够，后续可考虑 LLM 评估作为增强
- 自适应权重调整——根据剧情类型自动调整 4 个信号的权重
- 用户自定义冲突模板——允许用户添加自定义冲突类型
- 高张力冷却机制——持续高压后自动引入缓和场景（v2 需求 CONFLICT-06）
- 冲突解决指引——当活跃冲突过多时，主动建议导演解决某条冲突的具体方式
- 张力曲线可视化——导出张力评分历史为图表
- 冲突模板的 LLM 生成——当前硬编码 7 种足够，后续可用 LLM 动态生成

</deferred>

---

*Phase: 06-tension-scoring-conflict-engine*
*Context gathered: 2026-04-12*
