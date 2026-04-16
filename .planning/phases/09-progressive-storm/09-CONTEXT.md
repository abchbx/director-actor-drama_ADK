# Phase 9: Progressive STORM - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

实现渐进式 STORM 注入和用户主动触发，避免一次性过载。

核心交付物：
1. 用户主动触发 `/storm`——不受 N 场间隔限制，Director 优先响应用户请求（DSTORM-04）
2. 每次仅注入 1-2 个新视角，避免剧情失焦——与 Phase 8 D-06 已对齐（DSTORM-05）
3. 渐进式融入——新视角标记 🆕 新鲜度，Director 在 2-3 场内逐步探索，非当场强行使用
4. `trigger_history` 已记录触发原因 auto/manual/tension_low（Phase 8 D-31 已实现）
5. 导演 prompt §10 更新——新增渐进融入指引和手动触发优先级规则
6. `_build_dynamic_storm_section()` 升级——显示 🆕 新视角及其新鲜度

**不包含：** 一致性检查（Phase 10）、时间线追踪（Phase 11）、自适应 STORM 间隔（deferred）、用户自定义 STORM 主题（v2 DSTORM-06）

</domain>

<decisions>
## Implementation Decisions

### 渐进融入机制
- **D-01:** 混合方案：轻量状态 + Prompt 引导——利用 Phase 8 已有的 `discovered_scene` 字段（每个 Dynamic STORM 发现的新视角都记录了 `discovered_scene`），在 `_build_dynamic_storm_section()` 中根据 `current_scene - discovered_scene` 计算视角新鲜度：
  - 0-2 场内：标注 🆕（"新视角"）
  - 3+ 场：视为常规视角，不再特殊标注
- **D-02:** 不新增状态字段——`integration_status` 等不需要，`discovered_scene` 已足够推导新鲜度。保持最小化变更
- **D-03:** 新鲜度计算逻辑在 `_build_dynamic_storm_section()` 中实现：
  ```python
  # 伪代码
  for p in discovered_perspectives:
      age = current_scene - p.get("discovered_scene", 0)
      if age <= 2:
          mark_as_new(p)  # 在输出中添加 🆕 标记
  ```
- **D-04:** Director prompt §10 新增渐进融入指引：
  - "🆕 标记的视角是最近发现的新角度，建议在 2-3 场内逐步探索和融入，不要当场强行使用"
  - "新视角可以先在旁白中暗示，再在角色对话中体现，最后成为核心冲突的驱动力"
  - 与 Phase 6/8 的"导演建议模式"精神一致——建议而非强制
- **D-05:** 3 场后 🆕 标记自然消失——不需要手动更新状态，纯计算得出。Director 在第 4 场起将该视角视为常规视角

### 用户主动触发的差异化
- **D-06:** 手动触发（`/storm`）与自动触发的差异化体现：
  1. **不受间隔限制**——用户随时可调用 `/storm`，即使 `scenes_since_last_storm < STORM_INTERVAL`。Phase 8 的间隔建议仅适用于自动触发
  2. **Prompt 优先级标注**——手动触发时，Director prompt 中标注"用户主动请求新视角发现"，Director 应优先响应用户意图
  3. **返回信息更丰富**——手动触发返回值中包含"融合建议"段落，提示用户如何引导新视角融入
  4. **trigger_type 区分**——Phase 8 D-31 已实现 `"manual"` 类型，Phase 9 确保 `dynamic_storm()` 接受并传递 `trigger_type` 参数
- **D-07:** `dynamic_storm()` 函数签名变更——新增 `trigger_type: str = "auto"` 参数：
  ```python
  async def dynamic_storm(focus_area: str, tool_context: ToolContext, trigger_type: str = "auto") -> dict:
  ```
  当 `/storm` 命令调用时，CLI/Router 传入 `trigger_type="manual"`
- **D-08:** `trigger_storm()` 别名函数传递 `trigger_type="manual"`——确保向后兼容的 `/storm` 路径走手动触发逻辑
- **D-09:** 手动触发的返回值新增 `integration_hint` 字段——内容示例：
  ```python
  "integration_hint": "新视角「权力暗流」已发现。建议先在下一场旁白中暗示权力斗争的存在，再逐步让角色卷入。用 /steer 可指定融入方向。"
  ```

### 融入节奏与 Prompt 策略
- **D-10:** "建议逐步融入"而非"必须"——与 Phase 6/8 导演建议模式一致。🆕 标记作为视觉提示，prompt 用建议性语言引导
- **D-11:** 渐进融入的三个阶段 prompt 描述：
  - **第 1 场（发现场）：** 新视角仅作为背景暗示出现在旁白中，角色尚未感知
  - **第 2 场（萌芽场）：** 新视角相关的线索被角色注意，但尚未成为核心驱动力
  - **第 3 场（融入场）：** 新视角正式成为剧情的一部分，可驱动冲突和角色行动
- **D-12:** Director prompt §10 更新后的完整结构：
  ```
  ## §10 Dynamic STORM（视角重新发现）
  - 每 8 场左右（或张力持续低迷时），调用 dynamic_storm() 重新发现新视角
  - evaluate_tension() 返回 suggested_action="dynamic_storm" 时，优先调用
  - 用户可通过 /storm [焦点] 手动触发（不受间隔限制，优先响应）
  - 新视角发现后，考虑基于新角度调用 inject_conflict() 注入冲突
  - 新视角必须与已发生事件一致，是扩展而非推翻
  - 🆕 标记的视角是最近 2 场内发现的新角度，建议逐步融入：
    第 1 场：旁白暗示 → 第 2 场：角色感知 → 第 3 场：成为驱动力
  ```

### _build_dynamic_storm_section() 升级
- **D-13:** 升级 `_build_dynamic_storm_section(state)` 以展示新视角新鲜度：
  ```
  【Dynamic STORM】
  距上次视角发现：2 场 | 建议间隔：8 场
  最近发现：[第12场] （发现 2 个新视角）
  🆕 权力暗流（2场前发现）——从权力运作的隐秘机制审视剧情
  🆕 被遗忘的角落（2场前发现）——边缘人物的命运折射
  ```
- **D-14:** 🆕 标注仅展示最近 2 场内发现的视角——3 场前的视角不再特殊展示，避免信息过载
- **D-15:** 当没有 🆕 视角时，段落格式与 Phase 8 保持一致，无新增内容

### trigger_storm() 路径更新
- **D-16:** `trigger_storm(focus_area, tool_context)` 别名函数传递 `trigger_type="manual"`：
  ```python
  def trigger_storm(focus_area: str, tool_context: ToolContext) -> dict:
      # ... 内部调用 dynamic_storm(focus_area, tool_context, trigger_type="manual")
  ```
- **D-17:** 确保 `/storm` CLI 命令路由到 `trigger_storm()` → `dynamic_storm(trigger_type="manual")`。当前路由已存在，无需修改 CLI 层

### 状态持久化
- **D-18:** 不新增状态字段——Phase 9 的所有功能基于已有字段计算得出：
  - `dynamic_storm.discovered_perspectives[].discovered_scene` — 新鲜度计算
  - `dynamic_storm.trigger_history[].trigger_type` — 触发类型区分
  - `state.current_scene` — 当前场景编号
- **D-19:** `discovered_perspectives` 中每个视角的 `discovered_scene` 已由 Phase 8 保证存在（`dynamic_storm()` 设置 `p["discovered_scene"] = current_scene`）

### Claude's Discretion
- `_build_dynamic_storm_section()` 中 🆕 标记的精确格式和排版
- `integration_hint` 的具体措辞和模板
- Director prompt §10 更新的具体措辞和长度
- 新鲜度计算中"0-2 场"的精确边界（含不含发现场本身）
- 手动触发返回值中 `integration_hint` 的生成逻辑（基于新视角的 description 和 questions 组合）
- `dynamic_storm()` 签名变更中 `trigger_type` 的默认值和验证逻辑

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 9 需求定义
- `.planning/ROADMAP.md` — Phase 9 成功标准：/storm 不受间隔限制、每次 1-2 个新视角、2-3 场逐步融入、trigger_history 记录触发原因
- `.planning/REQUIREMENTS.md` — DSTORM-04（用户触发的 STORM）、DSTORM-05（渐进式 STORM）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离、200K token 上限）

### 已锁定决策的前置 Phase
- `.planning/phases/08-dynamic-storm/08-CONTEXT.md` — Dynamic STORM 完整决策（D-01~D-34），dynamic_storm() 实现，trigger_storm 别名，discovered_scene 字段，trigger_history 结构
- `.planning/phases/05-mixed-autonomy-mode/05-CONTEXT.md` — /storm 轻量版（D-19/D-20），trigger_storm 初始实现，导演 prompt 7 段结构
- `.planning/phases/06-tension-scoring-conflict-engine/06-CONTEXT.md` — evaluate_tension() suggested_action 机制，导演建议模式
- `.planning/phases/07-arc-tracking/07-CONTEXT.md` — 弧线追踪，plot_threads 结构

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计
- `.planning/research/FEATURES.md` — 功能需求研究
- `.planning/research/PITFALLS.md` — 已知陷阱

### 现有代码（必须读取理解）
- `app/dynamic_storm.py` — `discover_perspectives_prompt()`、`update_dynamic_storm_state()`、`STORM_INTERVAL` 常量。Phase 9 需理解 discovered_scene 字段和 trigger_history 结构
- `app/tools.py` — `dynamic_storm()` 函数（第772行），需新增 `trigger_type` 参数；`trigger_storm()` 别名（第870行），需传递 `trigger_type="manual"`；`evaluate_tension()` 函数（第890行），需理解 suggested_storm_focus 字段
- `app/context_builder.py` — `_build_dynamic_storm_section(state)` 函数（第746行），需升级以显示 🆕 新鲜度标记
- `app/agent.py` — `_improv_director` prompt §10 段落需更新渐进融入指引

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dynamic_storm.py` 的 `update_dynamic_storm_state()` — 已处理 trigger_type、discovered_perspectives 附加
- `tools.py` 的 `dynamic_storm()` — 已实现完整视角发现流程，新增 trigger_type 参数为最小变更
- `tools.py` 的 `trigger_storm()` — 别名函数，仅需传递 trigger_type="manual"
- `context_builder.py` 的 `_build_dynamic_storm_section()` — 已实现距上次发现、建议间隔、最近发现摘要，升级 🆕 标记为追加内容
- `dynamic_storm.py` 的 `discovered_scene` 字段 — 每个新视角的发现场编号，Phase 9 新鲜度计算的基础

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...额外字段}`
- 导演建议模式：Prompt 引导而非代码强制（Phase 6 D-03、Phase 8 D-07/D-12）
- 导演 prompt 段落：§编号 + 标题 + 规则描述
- 新鲜度/年龄计算：`current_X - discovered_X` 模式（与 Phase 7 dormant 检测 `current_scene - last_updated_scene` 对齐）
- 🆕/⚠️ emoji 标注模式（与 `_build_arc_tracking_section()` 的 ⚠️ 休眠线索标注对齐）

### Integration Points
- `app/tools.py` — `dynamic_storm()` 新增 `trigger_type` 参数 + `trigger_storm()` 传递 "manual"
- `app/context_builder.py` — `_build_dynamic_storm_section()` 升级 🆕 新鲜度标记
- `app/agent.py` — `_improv_director` prompt §10 更新渐进融入指引

</code_context>

<specifics>
## Specific Ideas

- 🆕 标记格式：`🆕 {视角名}（{N}场前发现）——{视角描述截断}`，与现有 `_build_dynamic_storm_section()` 格式统一
- `integration_hint` 模板：`"新视角「{name}」已发现。建议先在下一场旁白中暗示{关键词}，再逐步让角色卷入。用 /steer 可指定融入方向。"`——关键词从视角 questions 中提取
- Director prompt §10 的三阶段融入描述应简洁：`第1场：旁白暗示 → 第2场：角色感知 → 第3场：成为驱动力`
- 新鲜度计算边界：发现场为第 0 场（即 `age = current_scene - discovered_scene`），age=0,1,2 标注 🆕，共覆盖发现场及后 2 场
- 手动触发时 `integration_hint` 的生成：从新视角的 `questions` 字段中取第一个问题作为融入方向暗示，无需 LLM 调用

</specifics>

<deferred>
## Deferred Ideas

- 自适应 STORM 间隔——根据剧情复杂度动态调整触发间隔（当前固定 8 场，与 Phase 8 一致）
- 用户自定义 STORM 主题——指定下次 Dynamic STORM 的探索方向（v2 需求 DSTORM-06）
- 视角影响力追踪——追踪每个新视角被实际使用了多少场，评估 STORM 有效性
- 多轮 STORM 对话——用户对生成的新视角不满意时可要求重新生成
- 渐进融入的硬性代码强制——当前为建议模式，未来可考虑代码级限制 Director 在发现场不能直接以新视角驱动核心冲突
- 视角融合提示——当多个 🆕 视角可交叉时，建议 Director 探索视角交叉点

</deferred>

---

*Phase: 09-progressive-storm*
*Context gathered: 2026-04-13*
