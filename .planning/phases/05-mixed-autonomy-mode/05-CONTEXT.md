# Phase 5: Mixed Autonomy Mode - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

实现 AI 自主推进 + 用户随时干预的无缝切换，并提供明确的终止机制。

核心交付物：
1. `/auto [N]` 自动推进模式——AI 自主推进 N 场戏，用户可随时中断
2. `/steer <direction>` 轻量引导——给方向不给细节，与 `/action` 事件注入区分
3. `/end` 终幕机制——触发终幕旁白 + 剧本导出，结束后可继续番外篇
4. `/storm` 轻量版——手动触发视角重新审视（Phase 8 升级为完整 Dynamic STORM）
5. 场景后选项呈现——每场后提供 2-3 个选项引导用户参与
6. `_improv_director` prompt 重构——统一编排手动/自动/steer/end 协议

**不包含：** 张力评分和冲突注入（Phase 6）、完整 Dynamic STORM 多视角发现（Phase 8）、渐进式 STORM（Phase 9）
</domain>

<decisions>
## Implementation Decisions

### 自动推进模式（/auto [N]）
- **D-01:** 混合驱动机制——Prompt 驱动为主（LLM 自主决定何时调用下一场工具），代码级计数器 `remaining_auto_scenes` 为辅（LLM 每场后递减，归零则停止）。尊重 ADK turn-based 模型，同时有代码级防护防止失控
- **D-02:** 任意输入中断——用户在自动推进期间输入任何非空消息即中断，剩余场次作废。中断后导演将用户输入视为当场的 `/action` 事件注入，然后回到手动模式
- **D-03:** 场景间短暂间隔提示——每场输出后插入一行 `[自动推进中... 剩余 N 场，输入任意内容中断]`，让用户有中断的机会感
- **D-04:** `/auto` 无参数时默认推进 3 场——安全起步，用户可 `/auto 5` 增加场数
- **D-05:** 软上限 10 场 + 警告——超过 10 场时 `auto_advance()` 返回警告信息，导演 prompt 中提示用户确认。不硬性拒绝但保护用户免受意外 token 消耗
- **D-06:** 新增 `auto_advance(scenes, tool_context)` Tool 函数——设置 `state["drama"]["remaining_auto_scenes"]` 计数器，返回当前自动推进状态和指引

### 用户引导与干预（/steer）
- **D-07:** `/steer <direction>` = 方向指引，`/action <event>` = 具体事件——steer 给方向导演自由发挥如何体现（"让朱棣更偏执"），action 给事件导演必须执行（"朱棣发现密信"）。语义清晰不混淆
- **D-08:** steer 信息注入 `build_director_context()` 新增【用户引导】段落——导演每场构建上下文时自然看到。不修改 `next_scene()` 返回值
- **D-09:** steer 效力仅下一场——steer 是轻量推一下不是持续约束。下一场结束后 `steer_direction` 自动清除。想持续可每场 re-steer
- **D-10:** 新增 `steer_drama(direction, tool_context)` Tool 函数——设置 `state["drama"]["steer_direction"]`，返回确认信息

### 终幕与结束机制（/end）
- **D-11:** `/end` 触发终幕旁白 + 剧本导出，两步合一——用户体验最顺畅。导演先生成终幕旁白，然后自动调用 `export_drama()` 导出完整剧本
- **D-12:** 终幕旁白采用模板 + LLM 填充——预置终幕结构（开场回顾→角色结局→主题升华→落幕），LLM 填充具体内容。既保证结构完整又保留创意
- **D-13:** `/end` 后可继续番外篇——用户仍可 `/next` 继续，但导演上下文中会标注"本剧已正式结束，当前为番外篇/后日谈"。戏剧不锁死
- **D-14:** `/end` 时自动保存存档——方便用户回溯正式结局前的状态
- **D-15:** 新增 `end_drama(tool_context)` 独立 Tool 函数——设置 `drama_status = "ended"` + 触发终幕旁白 prompt + 自动保存 + 导出剧本。明确入口，职责清晰

### 场景后选项呈现
- **D-16:** Prompt 驱动 + 格式约束——在导演 prompt 中要求"每场结束后在导演批注区提供 2-3 个选项"，用结构化格式约束输出（`> 🎯 选项:` 标记）。不新增 Tool 函数，保持轻量
- **D-17:** 混合型选项内容——既有剧情方向（"A. 朱棣发动政变"），也有操作指引（"注入事件"/"结束戏剧"），让用户既能引导剧情也能控制系统
- **D-18:** 所有模式都显示选项——每场后都提供选项，降低参与门槛。自动推进模式下选项额外包含"中断自动推进"选项

### /storm 轻量版
- **D-19:** Phase 5 实现轻量版 `/storm`——命令入口 + `trigger_storm(focus_area, tool_context)` Tool 函数。内部逻辑：让导演重新审视当前剧情，输出 1-2 个新角度或未探索方向。Phase 8 再升级为完整 Dynamic STORM（多视角发现 + 冲突注入 + 世界观扩展）
- **D-20:** `/storm` 结果存入 `state["drama"]["storm"]["last_review"]`（轻量版），与 Phase 8 的 `state["drama"]["storm"]["perspectives"]` 字段名区分，避免升级冲突

### 状态持久化
- **D-21:** 高频字段放 `drama` 顶层——`remaining_auto_scenes`、`steer_direction` 单独存放，简单频繁访问
- **D-22:** `storm` 单独分组——`state["drama"]["storm"]` 子对象，Phase 8 会大幅扩展（perspectives、trigger_history 等），预留结构
- **D-23:** 新增状态字段汇总：
  - `drama.remaining_auto_scenes: int` — 自动推进剩余场数（0=手动模式）
  - `drama.steer_direction: str | null` — 当前引导方向（仅下一场生效）
  - `drama.storm.last_review: dict` — 最近一次 storm 审视结果
  - `drama.status` 新增 `"ended"` 值 — 终幕已触发

### 番外篇模式
- **D-24:** `build_director_context()` 检查 `drama_status == "ended"`，若为 ended 则附加"本剧已正式结束，当前为番外篇/后日谈，请以更轻松、回顾性的风格叙事"。轻量标记，不需要独立 prompt

### 导演 Prompt 重构
- **D-25:** 重构重写 `_improv_director` 的 system prompt——当前 160+ 行追加新内容会臃肿混乱，统一编排更清晰。核心循环协议保留，新增自动推进/选项/steer/end/storm 逻辑组织为独立段落
- **D-26:** Prompt 新段落结构：
  1. 核心循环协议（手动模式）——保留现有
  2. 自动推进协议（自动模式）——新增
  3. 用户引导与干预（/steer + /action）——增强
  4. 终幕协议（/end + 番外篇）——新增
  5. 视角审视（/storm）——新增
  6. 选项呈现规范——新增
  7. 输出格式——保留

### 向后兼容
- **D-27:** 现有 `/next`、`/action`、`/save`、`/load` 命令行为不变——Phase 4 已实现的命令保持原有语义
- **D-28:** 旧状态加载兼容——`load_drama()` 加载无 `remaining_auto_scenes`/`steer_direction` 的存档时，默认 `remaining_auto_scenes=0`（手动模式）、`steer_direction=None`

### Claude's Discretion
- `_improv_director` 重构后 prompt 的具体措辞和长度
- `auto_advance()` 函数内部计数器递减的精确触发时机
- `steer_drama()` 返回的确认信息格式
- `end_drama()` 终幕旁白模板的具体文本结构
- `trigger_storm()` 轻量版审视的具体 prompt 内容
- 场景后选项的精确格式（emoji、缩进、编号方式）
- 选项中剧情方向建议的创意 vs 操作指引的比例
- 自动推进中断后回到手动模式的具体过渡提示
- 软上限警告的具体措辞
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 需求定义
- `.planning/ROADMAP.md` — Phase 5 成功标准：/action 注入、/steer 引导、/storm 手动触发、/end 终幕、场景后选项、向后兼容
- `.planning/REQUIREMENTS.md` — LOOP-02（混合推进模式）、LOOP-04（用户终止机制）需求定义
- `.planning/PROJECT.md` — 项目愿景（Core Value: 无限畅写，逻辑不断）、约束（单用户模式、A2A 进程隔离）

### Phase 4 已锁定决策（Phase 5 的直接前置）
- `.planning/phases/04-infinite-loop-engine/04-CONTEXT.md` — DramaRouter 架构（D-01~D-14）、场景衔接、循环驱动方式、/start 流程。D-06"每场后等待用户输入"在 Phase 5 被 /auto 打破

### Phase 1/2/3 已锁定决策（可复用基础）
- `.planning/phases/01-memory-foundation/01-CONTEXT.md` — 3 层记忆架构（D-01~D-13），关键记忆保护
- `.planning/phases/02-context-builder/02-CONTEXT.md` — context_builder 职责划分（D-03），token 预算控制（D-02），前向兼容预留（D-04）
- `.planning/phases/03-semantic-retrieval/03-CONTEXT.md` — 语义检索决策，retrieve_relevant_scenes

### 研究文档
- `.planning/research/ARCHITECTURE.md` — 架构演进设计：Router 重构方案，循环驱动方式
- `.planning/research/FEATURES.md` — 功能需求研究：用户干预、混合推进模式
- `.planning/research/PITFALLS.md` — 已知陷阱：上下文耗尽、用户意图误判

### 现有代码（必须读取理解）
- `app/agent.py` — DramaRouter + _setup_agent + _improv_director 定义（第 97-355 行），需大幅更新 _improv_director prompt 和新增 Tool 注册
- `app/tools.py` — 现有 Tool 函数（next_scene, director_narrate, actor_speak, write_scene, user_action, save_drama, load_drama, export_drama），需新增 auto_advance, steer_drama, end_drama, trigger_storm
- `app/context_builder.py` — build_director_context() 需新增【用户引导】段落和番外篇标记
- `app/state_manager.py` — 状态管理，需适配新增状态字段和 ended 状态

### 代码库映射
- `.planning/codebase/ARCHITECTURE.md` — 双层状态管理架构
- `.planning/codebase/CONVENTIONS.md` — 编码规范（ToolContext 模式、返回 dict 格式、中英双语 docstring）
- `.planning/codebase/CONCERNS.md` — 已知问题清单

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DramaRouter._run_async_impl()` (agent.py:307-333): 路由逻辑骨架，需扩展识别 `/auto`、`/steer`、`/end`、`/storm` 命令
- `_improv_director` (agent.py:106-291): 当前即兴导演 prompt 和 Tool 列表，需大幅重构
- `user_action()` (tools.py:565-585): 现有 /action 实现，steer_drama 可参考此模式
- `next_scene()` (tools.py:493-562): 场景推进，auto_advance 需要与之配合的计数器逻辑
- `export_drama()` (tools.py:762-791): 现有剧本导出，end_drama 可复用
- `build_director_context()` (context_builder.py): 导演上下文构建，需新增 steer 和番外篇段落
- `save_drama()` (tools.py:588-621): 现有保存逻辑，end_drama 可复用自动保存
- `load_drama()` (tools.py:624-759): 加载逻辑，需适配新状态字段默认值

### Established Patterns
- Tool 函数签名：`def tool_name(param: type, tool_context: ToolContext) -> dict`
- 返回格式：`{"status": "success/error", "message": "...", ...}`
- State 路径：`tool_context.state["drama"]["actors"][name]`，新字段 `tool_context.state["drama"]["remaining_auto_scenes"]`
- 中英双语 docstring（英文首行，中文细节）
- 命令路由：utility_commands 列表 + user_message 匹配（agent.py:320-321）
- Prompt 中文标签格式：【全局故事弧线】【近期场景】【用户引导】

### Integration Points
- `app/agent.py` — _improv_director prompt 重构 + 新 Tool 注册（auto_advance, steer_drama, end_drama, trigger_storm）
- `app/tools.py` — 新增 4 个 Tool 函数
- `app/context_builder.py` — build_director_context() 新增 steer 段落 + 番外篇标记
- `app/state_manager.py` — 新状态字段适配 + load 兼容默认值

</code_context>

<specifics>
## Specific Ideas

- `_improv_director` prompt 中的自动推进协议应明确："当 `remaining_auto_scenes > 0` 时，每场 write_scene 后立即调用 next_scene 开始下一场，不等待用户输入。每场输出后插入 [自动推进中... 剩余 N 场] 提示"
- steer 信息在导演上下文中应以【用户引导】标记，与现有【全局故事弧线】【近期场景】格式统一
- 终幕旁白模板应包含：🎭 终幕 —— 回顾全剧→各角色结局→主题升华→落幕致辞
- `/end` 输出应与正常剧本格式一致，但标题用「终幕」而非「第 N 场」
- 场景后选项格式建议：`> 🎯 接下来你想...\n> A. [剧情方向1]\n> B. [剧情方向2]\n> C. /action 注入事件 / /end 结束戏剧`
- `auto_advance()` 的计数器递减应在 `write_scene()` 之后、`next_scene()` 之前——确保当前场已被完整记录
- `/storm` 轻量版输出应标注为【视角审视】，与 Phase 8 的【视角发现】区分
- 番外篇模式下的场景编号应继续递增，但标注"番外第 X 场"
- `remaining_auto_scenes` 为 0 时即手动模式，无需额外布尔标记

</specifics>

<deferred>
## Deferred Ideas

- `/auto` 无限模式（`/auto` 无上限直到用户中断）— 可作为后续增强，当前默认 3 场 + 软上限 10 场已足够
- 完整 Dynamic STORM 多视角发现 — Phase 8（DSTORM-01/02/03）
- 渐进式 STORM 注入 — Phase 9（DSTORM-05）
- `/steer <direction> N` 持续 N 场语法 — 当前仅下一场，持续模式可后续增加
- 场景后选项的 Tool 函数生成方式 — 当前 Prompt 驱动足够，若质量不稳定可后续改为 Tool 函数
- `/stop` 显式中断命令 — 当前任意输入中断已覆盖，但 `/stop` 可作为更明确的语义入口
- 代码级循环（Python while loop 自动多场）— 违背 ADK turn-based 模型，不建议实现
- 多用户并发干预 — 当前架构为单用户，Out of Scope

</deferred>

---

*Phase: 05-mixed-autonomy-mode*
*Context gathered: 2026-04-12*
