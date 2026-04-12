# Phase 5: Mixed Autonomy Mode - Research

**Researched:** 2026-04-12
**Domain:** AI 自主推进 + 用户干预混合模式、ADK Tool 函数设计、Prompt 工程
**Confidence:** HIGH

## Summary

Phase 5 在 Phase 4 (Infinite Loop Engine) 的基础上，为 DramaRouter 架构添加 4 种新的交互模式：自动推进 (`/auto`)、轻量引导 (`/steer`)、终幕机制 (`/end`)、视角审视 (`/storm`)。核心架构模式已锁定——全部通过 Prompt 驱动 + 代码级计数器/状态标记实现，不改变 ADK turn-based 模型。

研究确认：所有 4 个新 Tool 函数（`auto_advance`、`steer_drama`、`end_drama`、`trigger_storm`）可以遵循现有 `tools.py` 中的 `def tool_name(param, tool_context) -> dict` 模式，无需引入新的架构层。`_improv_director` prompt 从 160+ 行扩展到约 280-320 行（7 段结构），这是可管理的。`build_director_context()` 需新增 2 个段落构建函数（【用户引导】+ 番外篇标记），优先级设定为 8（高于 actor_emotions 的 6，低于 current_status 的 10）。

最关键的技术挑战是 **自动推进模式下的计数器递减时机**——必须在 `write_scene()` 之后、`next_scene()` 之前递减，以确保当前场完整记录后再决定是否继续。这需要在 prompt 中用极其明确的指令保证 LLM 遵循调用顺序。

**Primary recommendation:** 遵循 D-01 "Prompt 驱动为主 + 代码级计数器为辅" 的混合机制，4 个新 Tool 函数只负责设置状态，prompt 负责驱动 LLM 行为。这是与 ADK turn-based 模型最兼容的方案。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 混合驱动机制——Prompt 驱动为主（LLM 自主决定何时调用下一场工具），代码级计数器 `remaining_auto_scenes` 为辅（LLM 每场后递减，归零则停止）
- **D-02:** 任意输入中断——用户在自动推进期间输入任何非空消息即中断，剩余场次作废
- **D-03:** 场景间短暂间隔提示——每场输出后插入 `[自动推进中... 剩余 N 场，输入任意内容中断]`
- **D-04:** `/auto` 无参数时默认推进 3 场
- **D-05:** 软上限 10 场 + 警告
- **D-06:** 新增 `auto_advance(scenes, tool_context)` Tool 函数
- **D-07:** `/steer <direction>` = 方向指引，`/action <event>` = 具体事件
- **D-08:** steer 信息注入 `build_director_context()` 新增【用户引导】段落
- **D-09:** steer 效力仅下一场
- **D-10:** 新增 `steer_drama(direction, tool_context)` Tool 函数
- **D-11:** `/end` 触发终幕旁白 + 剧本导出，两步合一
- **D-12:** 终幕旁白采用模板 + LLM 填充
- **D-13:** `/end` 后可继续番外篇
- **D-14:** `/end` 时自动保存存档
- **D-15:** 新增 `end_drama(tool_context)` 独立 Tool 函数
- **D-16:** Prompt 驱动 + 格式约束——在导演 prompt 中要求"每场结束后在导演批注区提供 2-3 个选项"
- **D-17:** 混合型选项内容——既有剧情方向也有操作指引
- **D-18:** 所有模式都显示选项
- **D-19:** Phase 5 实现轻量版 `/storm`——命令入口 + `trigger_storm(focus_area, tool_context)` Tool 函数
- **D-20:** `/storm` 结果存入 `state["drama"]["storm"]["last_review"]`
- **D-21:** 高频字段放 `drama` 顶层
- **D-22:** `storm` 单独分组
- **D-23:** 新增状态字段：`remaining_auto_scenes`、`steer_direction`、`storm.last_review`、`status="ended"`
- **D-24:** `build_director_context()` 检查 `drama_status == "ended"`，附加番外篇标记
- **D-25:** 重构重写 `_improv_director` 的 system prompt
- **D-26:** Prompt 新段落结构（7个段落）
- **D-27:** 现有命令行为不变
- **D-28:** 旧状态加载兼容

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

### Deferred Ideas (OUT OF SCOPE)
- `/auto` 无限模式（无上限直到用户中断）
- 完整 Dynamic STORM 多视角发现 — Phase 8
- 渐进式 STORM 注入 — Phase 9
- `/steer <direction> N` 持续 N 场语法
- 场景后选项的 Tool 函数生成方式
- `/stop` 显式中断命令
- 代码级循环（Python while loop 自动多场）
- 多用户并发干预
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOOP-02 | 混合推进模式 — AI 自主推进剧情发展，用户可随时通过命令注入事件、改变方向、添加角色，两者无缝切换 | D-01~D-06 实现 `/auto` + 计数器机制；D-07~D-10 实现 `/steer` 方向引导；D-16~D-18 实现场景后选项呈现；D-19~D-20 实现 `/storm` 视角审视 |
| LOOP-04 | 用户终止机制 — 明确的 `/end` 命令结束戏剧，触发终幕旁白和完整剧本导出 | D-11~D-15 实现 `/end` + 终幕旁白 + 自动导出 + 自动保存；D-13 番外篇模式让结束不锁死 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | ≥1.15.0,<2.0.0 | Agent 框架，提供 Agent/ToolContext/Runner | 项目已锁定，所有 Agent 和 Tool 基于此 [VERIFIED: pyproject.toml] |
| a2a-sdk | ~=0.3.22 | Agent-to-Agent 通信协议 | Actor 隔离核心依赖 [VERIFIED: pyproject.toml] |
| LiteLlm | (in ADK) | OpenAI-compatible model wrapper | 已用于 claude-sonnet-4-6 [VERIFIED: agent.py:50] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | (dev) | 单元测试 | 每次实现后验证 [VERIFIED: pyproject.toml dev deps] |
| ruff | (dev) | Linting + formatting | 代码质量保证 [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Prompt 驱动自动推进 | 代码级 while loop | 代码级违背 ADK turn-based 模型，已在 D-01/deferred 中否决 |
| Tool 函数递减计数器 | Prompt 内自述计数 | Prompt 自述不可靠（LLM 可能忘记递减），代码级计数器更安全 [CITED: CONTEXT.md D-01] |

**Installation:** 无新依赖需要安装

## Architecture Patterns

### Recommended Project Structure (Changes Only)
```
app/
├── agent.py              # DramaRouter 新增 /auto /steer /end /storm 命令路由；_improv_director prompt 7段重写
├── tools.py              # 新增 auto_advance, steer_drama, end_drama, trigger_storm 四个 Tool 函数
├── context_builder.py    # build_director_context() 新增【用户引导】段 + 番外篇标记段
├── state_manager.py      # init_drama_state() 新增默认字段；load_progress() 兼容旧存档
```

### Pattern 1: Prompt-Driven Auto-Advance with Code-Level Guard
**What:** LLM 根据 prompt 中的指令自主调用 `next_scene()` → `write_scene()` 循环，代码通过 `remaining_auto_scenes` 计数器作为安全网防止失控
**When to use:** `/auto [N]` 自动推进模式
**Example:**
```python
# Tool function: sets state only, doesn't drive the loop
def auto_advance(scenes: int, tool_context: ToolContext) -> dict:
    """Enable auto-advance mode for N scenes. Sets the remaining_auto_scenes counter."""
    state = _get_state(tool_context)
    if scenes > 10:
        return {
            "status": "info",
            "message": f"⚠️ 请求推进 {scenes} 场超过软上限(10)。建议分批推进。",
            "remaining_auto_scenes": state.get("remaining_auto_scenes", 0),
        }
    state["remaining_auto_scenes"] = scenes
    _set_state(state, tool_context)
    return {"status": "success", "message": f"🎬 自动推进模式已启动，将推进 {scenes} 场。"}

# Prompt instruction drives the loop behavior:
# "当 remaining_auto_scenes > 0 时，每场 write_scene 后立即调用 next_scene 继续下一场。
#  每场输出后插入 [自动推进中... 剩余 N 场，输入任意内容中断]。
#  write_scene 后递减 remaining_auto_scenes，归零时停止并回到手动模式。"
```

### Pattern 2: Steer as Ephemeral Context Injection
**What:** steer 信息写入 state，`build_director_context()` 在构建上下文时自动注入【用户引导】段落，下场后自动清除
**When to use:** `/steer <direction>` 轻量引导
**Example:**
```python
def steer_drama(direction: str, tool_context: ToolContext) -> dict:
    """Set a directional guidance for the next scene only."""
    state = _get_state(tool_context)
    state["steer_direction"] = direction
    _set_state(state, tool_context)
    return {"status": "success", "message": f"🧭 方向已设置：{direction}（下一场生效后自动清除）"}

# In build_director_context():
def _build_steer_section(state: dict) -> dict:
    steer = state.get("steer_direction")
    if not steer:
        return {"key": "steer", "text": "", "priority": 8, "truncatable": False}
    return {
        "key": "steer",
        "text": f"【用户引导】\n用户建议方向：{steer}\n请在此方向上发挥创意，但不必拘泥。",
        "priority": 8,
        "truncatable": False,
    }
```

### Pattern 3: End Drama as Multi-Step Tool
**What:** `end_drama()` 设置状态 + 触发终幕旁白 prompt + 自动保存 + 自动导出，一站式完成
**When to use:** `/end` 终幕命令
**Example:**
```python
def end_drama(tool_context: ToolContext) -> dict:
    """End the drama with epilogue narration, auto-save, and script export."""
    state = _get_state(tool_context)
    state["status"] = "ended"
    _set_state(state, tool_context)
    # Return structured data for the LLM to generate epilogue
    return {
        "status": "success",
        "message": "🎭 终幕已触发！请按照终幕协议生成终幕旁白。",
        "drama_status": "ended",
        "template": "🎭 终幕 ——\n1. 回顾全剧\n2. 各角色结局\n3. 主题升华\n4. 落幕致辞",
    }
```

### Pattern 4: Command Routing Extension
**What:** 在 DramaRouter 的 `utility_commands` 列表中添加新命令，确保路由到 `_improv_director`
**When to use:** 任何新的斜杠命令
**Example:**
```python
# In DramaRouter._run_async_impl():
utility_commands = [
    "/save", "/load", "/export", "/cast", "/status", "/list",
    "/auto", "/steer", "/end", "/storm",  # Phase 5 additions
]
```

### Anti-Patterns to Avoid
- **不要在 Tool 函数中实现循环逻辑：** ADK 是 turn-based 模型，Tool 函数应只设置状态，由 prompt 驱动 LLM 行为 [CITED: CONTEXT.md deferred ideas]
- **不要在 state 中用布尔标记区分手动/自动模式：** `remaining_auto_scenes == 0` 即手动模式，无需额外布尔值 [CITED: CONTEXT.md specifics]
- **不要让 steer 持续多场：** steer 效力仅下一场，想持续可 re-steer [CITED: CONTEXT.md D-09]
- **不要在 auto_advance 中硬性拒绝 > 10 场：** 只返回警告（soft cap），不硬性拒绝 [CITED: CONTEXT.md D-05]
- **不要用 `_improv_director` 之外的 Agent 处理新命令：** 所有新命令都路由到同一个 improv_director，由 prompt 内不同段落控制行为 [CITED: CONTEXT.md D-25/D-26]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 自动推进循环 | Python while loop 递归调用 next_scene | Prompt 驱动 + remaining_auto_scenes 计数器 | ADK turn-based 模型不支持代码级循环，违反架构约束 [CITED: CONTEXT.md D-01/deferred] |
| 终幕旁白结构 | 在 Tool 函数中硬编码完整旁白文本 | 返回模板结构 + 让 LLM 填充内容 | LLM 更擅长创意性文本生成，模板保证结构完整 [CITED: CONTEXT.md D-12] |
| 场景后选项生成 | 新增 generate_options() Tool 函数 | Prompt 驱动 + 格式约束 | 保持轻量，当前 prompt 方式足够 [CITED: CONTEXT.md D-16] |
| steer 持久化 | 复杂的 steer 生命周期管理 | 简单的"上场设置、下场清除"模式 | 持续引导需求可 re-steer，不需要复杂管理 [CITED: CONTEXT.md D-09] |
| 中断检测 | 代码级监听用户输入 | Prompt 指示 LLM 检查用户消息 | ADK turn-based 模型中，用户下一次输入自然中断当前 LLM 行为 [CITED: CONTEXT.md D-02] |

**Key insight:** 整个 Phase 5 的核心设计哲学是"Prompt 驱动为主，代码级状态为辅"——Tool 函数只设置/读取状态，不包含行为逻辑。行为逻辑全部在 `_improv_director` 的 prompt 中通过指令驱动。

## Common Pitfalls

### Pitfall 1: 自动推进计数器递减时机错误
**What goes wrong:** 如果在 `next_scene()` 之前递减 `remaining_auto_scenes`，可能导致当前场还未完整记录就减少了计数；如果在 `write_scene()` 之前递减，可能跳过场景记录
**Why it happens:** Prompt 中的调用顺序指令不够明确，LLM 可能不严格按序执行
**How to avoid:** 在 prompt 中用编号步骤明确："① write_scene() ② 递减 remaining_auto_scenes ③ 如果 > 0 则 next_scene()"
**Warning signs:** 自动推进模式下场景记录缺失，或计数器不递减

### Pitfall 2: 用户中断后 LLM 继续自动推进
**What goes wrong:** 用户在自动推进期间输入新消息（意图中断），但 LLM 未检测到中断信号继续推进
**Why it happens:** ADK turn-based 模型中，用户新消息会开始新的 LLM turn，但如果 state 中 `remaining_auto_scenes` 未清零，LLM 可能根据 prompt 指令继续自动推进
**How to avoid:** `DramaRouter._run_async_impl()` 在路由到 `_improv_director` 之前，检查 state 中的 `remaining_auto_scenes > 0` 且用户输入不是 `/auto` 命令时，自动清零 `remaining_auto_scenes`——这是代码级安全网，不依赖 LLM 判断
**Warning signs:** 用户输入非 `/auto` 消息后系统仍自动推进下一场

### Pitfall 3: 终幕旁白后无法继续番外篇
**What goes wrong:** `/end` 设置 `status="ended"` 后，导演 prompt 完全停止生成内容
**Why it happens:** prompt 中对 "ended" 状态的处理过于严格
**How to avoid:** 在 prompt 的终幕协议段落中明确："ended 状态下，如果用户发送 /next 或 /action，以番外篇/后日谈风格继续叙事，标注'番外第 X 场'"，并在 `build_director_context()` 中注入番外篇提示 [CITED: CONTEXT.md D-13/D-24]
**Warning signs:** `/end` 后 `/next` 不响应或报错

### Pitfall 4: steer 方向信息丢失
**What goes wrong:** 用户使用 `/steer` 设置方向，但导演在下一场中完全忽略了引导方向
**Why it happens:** `steer_direction` 已写入 state，但 `build_director_context()` 未将其纳入上下文，或清除时机不对
**How to avoid:** (1) `build_director_context()` 必须包含【用户引导】段落；(2) 清除逻辑放在 `next_scene()` 调用之后——即 `next_scene()` 读取 `steer_direction` 并返回，然后清除 [CITED: CONTEXT.md D-08]
**Warning signs:** steer 后的下一场看不出方向变化

### Pitfall 5: 旧存档加载时缺少新字段
**What goes wrong:** 加载 Phase 4 或更早的存档时，`state["drama"]` 缺少 `remaining_auto_scenes`、`steer_direction`、`storm` 字段，导致代码 KeyError
**Why it happens:** 新字段在 Phase 5 引入，旧存档没有
**How to avoid:** 在 `load_progress()` 中添加字段迁移：如果字段缺失，设置默认值（`remaining_auto_scenes=0`、`steer_direction=None`、`storm={"last_review": {}}`）[CITED: CONTEXT.md D-28]
**Warning signs:** 加载旧存档后 KeyError 崩溃

### Pitfall 6: Prompt 过长导致 LLM 行为异常
**What goes wrong:** `_improv_director` prompt 从 160+ 行扩展到 280-320 行后，LLM 可能遗忘早期指令或产生矛盾行为
**Why it happens:** 7 段结构的 prompt 信息量大，LLM 对中间段落指令的遵循度可能降低
**How to avoid:** (1) 每段开头用 ⚠️ 标记关键规则；(2) 在 prompt 开头放"最高优先级"摘要；(3) 避免段落间矛盾（如手动模式说"等待用户"vs 自动模式说"不等待"）——用条件判断："如果 remaining_auto_scenes > 0 则...否则..."
**Warning signs:** LLM 在自动模式下等待用户输入，或在手动模式下不等待

## Code Examples

### auto_advance() Tool 函数
```python
def auto_advance(scenes: int, tool_context: ToolContext) -> dict:
    """Enable auto-advance mode for N scenes. The director will advance N scenes autonomously.

    设置自动推进模式，AI 将自主推进指定场数的戏剧。用户可随时输入任何内容中断。

    Args:
        scenes: Number of scenes to auto-advance. Default 3, soft cap at 10.

    Returns:
        dict with auto-advance status and guidance.
    """
    state = _get_state(tool_context)
    
    # D-05: Soft cap at 10 with warning
    if scenes > 10:
        current = state.get("remaining_auto_scenes", 0)
        return {
            "status": "info",
            "message": (
                f"⚠️ 请求推进 {scenes} 场超过建议上限(10场)。\n"
                f"大量自动推进可能消耗较多 token。建议使用 /auto 10 以内。\n"
                f"如果确认，请再次发送 /auto {scenes}"
            ),
            "remaining_auto_scenes": current,
        }
    
    # D-04: Default handled by prompt (caller should pass 3 if no arg)
    state["remaining_auto_scenes"] = scenes
    _set_state(state, tool_context)
    
    return {
        "status": "success",
        "message": (
            f"🎬 自动推进模式已启动！将自主推进 {scenes} 场戏。\n"
            f"每场结束后会提示剩余场数。\n"
            f"输入任何内容即可中断，回到手动模式。"
        ),
        "remaining_auto_scenes": scenes,
    }
```

### steer_drama() Tool 函数
```python
def steer_drama(direction: str, tool_context: ToolContext) -> dict:
    """Set a directional guidance for the next scene. Lighter than /action which injects specific events.

    设置下一场的方向引导，导演会在此方向上发挥创意。
    与 /action 不同：/steer 给方向（"让朱棣更偏执"），/action 给事件（"朱棣发现密信"）。

    Args:
        direction: The direction or guidance for the next scene.

    Returns:
        dict with confirmation that the steer is set.
    """
    state = _get_state(tool_context)
    state["steer_direction"] = direction
    _set_state(state, tool_context)
    
    return {
        "status": "success",
        "message": (
            f"🧭 方向已设置：{direction}\n"
            f"下一场将在此方向上发挥创意。\n"
            f"效力仅一场，之后自动清除。"
        ),
        "steer_direction": direction,
    }
```

### end_drama() Tool 函数
```python
def end_drama(tool_context: ToolContext) -> dict:
    """End the drama with epilogue narration, auto-save, and script export.

    触发终幕机制：设置 drama_status 为 ended，提示导演生成终幕旁白，
    自动保存存档，并导出完整剧本。结束后可继续番外篇。

    Returns:
        dict with end status and epilogue template.
    """
    state = _get_state(tool_context)
    state["status"] = "ended"
    _set_state(state, tool_context)
    
    return {
        "status": "success",
        "message": (
            "🎭 终幕已触发！\n"
            "请按照终幕协议生成终幕旁白：\n"
            "1. 回顾全剧主线\n"
            "2. 各角色结局\n"
            "3. 主题升华\n"
            "4. 落幕致辞\n\n"
            "生成终幕旁白后，自动调用 save_drama 和 export_drama。\n"
            "结束后用户仍可用 /next 继续番外篇。"
        ),
        "drama_status": "ended",
        "epilogue_template": (
            "🎭 终幕 ——\n"
            "【回顾】全剧主线梳理\n"
            "【角色结局】各角色命运\n"
            "【主题升华】核心主题回响\n"
            "【落幕致辞】最后的旁白"
        ),
    }
```

### trigger_storm() Tool 函数
```python
def trigger_storm(focus_area: str, tool_context: ToolContext) -> dict:
    """Trigger a lightweight perspective review of the current drama.

    手动触发视角审视——让导演重新审视当前剧情，发现新的角度或未探索方向。
    轻量版（Phase 5），Phase 8 将升级为完整 Dynamic STORM。

    Args:
        focus_area: Optional area to focus the review on (e.g., "角色关系", "权力斗争").

    Returns:
        dict with storm review status.
    """
    state = _get_state(tool_context)
    
    # Ensure storm sub-dict exists (D-22)
    if "storm" not in state:
        state["storm"] = {"last_review": {}, "perspectives": state.get("storm", {}).get("perspectives", [])}
    
    return {
        "status": "success",
        "message": (
            f"🔍 视角审视已触发！聚焦领域：{focus_area}\n"
            f"请重新审视当前剧情，输出 1-2 个新角度或未探索方向。\n"
            f"格式：以【视角审视】标记输出。"
        ),
        "focus_area": focus_area,
    }
```

### build_director_context() 新增段落
```python
# 新增 steer 段落 (D-08)
def _build_steer_section(state: dict) -> dict:
    """Build the user steer guidance section (D-08/D-09)."""
    steer = state.get("steer_direction")
    if not steer:
        return {"key": "steer", "text": "", "priority": 8, "truncatable": False}
    return {
        "key": "steer",
        "text": f"【用户引导】\n用户建议方向：{steer}\n请在此方向上发挥创意，但不必拘泥。此引导仅本场生效。",
        "priority": 8,
        "truncatable": False,
    }

# 新增番外篇标记 (D-24)
def _build_epilogue_section(state: dict) -> dict:
    """Build the epilogue mode section (D-24)."""
    if state.get("status") != "ended":
        return {"key": "epilogue", "text": "", "priority": 9, "truncatable": False}
    return {
        "key": "epilogue",
        "text": "【番外篇模式】\n本剧已正式结束，当前为番外篇/后日谈。请以更轻松、回顾性的风格叙事。场景编号继续递增，但标注'番外第 X 场'。",
        "priority": 9,
        "truncatable": False,
    }

# 新增自动推进状态段落
def _build_auto_advance_section(state: dict) -> dict:
    """Build the auto-advance status section."""
    remaining = state.get("remaining_auto_scenes", 0)
    if remaining <= 0:
        return {"key": "auto_advance", "text": "", "priority": 9, "truncatable": False}
    return {
        "key": "auto_advance",
        "text": f"【自动推进模式】\n当前正在自动推进，剩余 {remaining} 场。每场 write_scene 后递减计数器，归零时回到手动模式。输出后插入提示：[自动推进中... 剩余 N 场，输入任意内容中断]",
        "priority": 9,
        "truncatable": False,
    }

# 在 _DIRECTOR_SECTION_PRIORITIES 中添加：
# "steer": 8,
# "epilogue": 9,
# "auto_advance": 9,
```

### DramaRouter 中断安全网
```python
# 在 DramaRouter._run_async_impl() 中添加中断逻辑 (D-02)
async def _run_async_impl(self, ctx):
    drama = ctx.session.state.get("drama", {})
    actors = drama.get("actors", {})
    
    # Extract user message
    user_message = ""
    if ctx.user_content and ctx.user_content.parts:
        for part in ctx.user_content.parts:
            text = getattr(part, 'text', None) or ''
            user_message += text.lower()
    
    # D-02: Auto-interrupt — any non-/auto input clears remaining_auto_scenes
    if drama.get("remaining_auto_scenes", 0) > 0:
        if "/auto" not in user_message:
            # User sent non-auto input during auto-advance → interrupt
            ctx.session.state["drama"]["remaining_auto_scenes"] = 0
    
    # Route: utility commands + Phase 5 new commands → improv_director
    utility_commands = [
        "/save", "/load", "/export", "/cast", "/status", "/list",
        "/auto", "/steer", "/end", "/storm",  # Phase 5
    ]
    force_improvise = any(cmd in user_message for cmd in utility_commands)
    
    # ... rest of routing logic unchanged
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 单一 /next 手动推进 | /auto + /next + /steer + /end + /storm 混合模式 | Phase 5 | 用户可选择参与程度 |
| 无终止机制 | /end 终幕 + 番外篇延续 | Phase 5 | 戏剧可优雅结束 |
| /action 仅事件注入 | /steer 方向引导 + /action 事件注入双通道 | Phase 5 | 语义更清晰 |
| 单一 prompt 段落 | 7 段结构化 prompt | Phase 5 (D-26) | 指令组织更清晰，遵循度更高 |

**Deprecated/outdated:**
- Phase 4 D-06 "每场后等待用户输入" 在 Phase 5 被 `/auto` 打破——自动推进模式下不等用户

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ADK turn-based 模型下，用户新消息自然中断当前 LLM turn，无需代码级中断机制 | Pattern 4 / Pitfall 2 | 如果 ADK 在同一 turn 内处理多条用户消息，中断可能不生效 |
| A2 | `_improv_director` prompt 扩展到 280-320 行后 LLM 仍能可靠遵循所有指令 | Architecture | LLM 可能遗忘中间段落指令，需要测试验证 |
| A3 | 场景后选项的 Prompt 驱动方式足够稳定，不需要 Tool 函数生成 | Don't Hand-Roll | 如果选项质量不稳定，需要改为 Tool 函数 |
| A4 | `remaining_auto_scenes` 递减由 LLM 通过 prompt 指令执行，LLM 会可靠执行 | Pattern 1 | LLM 可能忘记递减，导致无限自动推进 |
| A5 | `steer_direction` 在下一场结束后由 `next_scene()` 清除足够可靠 | Pattern 2 | 如果 next_scene 不被调用（如 /end 后），steer 可能残留 |

**Mitigation for A4 (highest risk):** 在 `next_scene()` Tool 函数中添加代码级递减：当 `remaining_auto_scenes > 0` 时自动递减 1。这样即使 LLM 忘记递减，代码级安全网也会生效。这是双重保险，既 prompt 指示 LLM 递减，又代码实际执行。

**Mitigation for A5:** 在 `end_drama()` 中也清除 `steer_direction`，确保终幕时不残留。

## Open Questions (RESOLVED)

1. **计数器递减的安全网位置**
   - What we know: D-01 确定 Prompt 驱动为主 + 代码计数器为辅
   - What's unclear: 代码级递减应该放在 `next_scene()` 还是 `write_scene()` 中
   - Recommendation: 放在 `next_scene()` 中（开始新场时递减），因为 `write_scene()` 是记录当前场，不应改变推进状态

2. **CLI banner 需要更新**
   - What we know: cli.py 的 `print_banner()` 列出当前命令
   - What's unclear: 是否在本 Phase 中更新 banner 添加新命令
   - Recommendation: 是，更新 banner 添加 /auto、/steer、/end、/storm 命令说明

3. **自动推进模式下的工具调用显示**
   - What we know: cli.py 的 `_send_message()` 对某些 function_call 打印 `⚙️ fn_name(args)`
   - What's unclear: 自动推进多场时，工具调用输出是否会刷屏
   - Recommendation: 自动推进模式下，工具调用日志可以简化显示

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified — Phase 5 is purely code/config changes to existing Python modules)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None (default discovery) |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/unit/ tests/integration/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOOP-02 | auto_advance() 设置 remaining_auto_scenes 计数器 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_auto_advance -x` | ❌ Wave 0 |
| LOOP-02 | auto_advance() 软上限 >10 返回警告 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_auto_advance_soft_cap -x` | ❌ Wave 0 |
| LOOP-02 | steer_drama() 设置 steer_direction 状态 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_steer_drama -x` | ❌ Wave 0 |
| LOOP-02 | end_drama() 设置 status=ended + 返回模板 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_end_drama -x` | ❌ Wave 0 |
| LOOP-02 | trigger_storm() 返回审视指引 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_trigger_storm -x` | ❌ Wave 0 |
| LOOP-02 | DramaRouter 识别新命令路由 | unit | `uv run pytest tests/unit/test_agent.py::test_routes_auto_to_improv -x` | ❌ Wave 0 |
| LOOP-02 | build_director_context() 包含【用户引导】段 | unit | `uv run pytest tests/unit/test_context_builder.py::test_steer_section -x` | ❌ Wave 0 |
| LOOP-02 | build_director_context() 包含番外篇标记 | unit | `uv run pytest tests/unit/test_context_builder.py::test_epilogue_section -x` | ❌ Wave 0 |
| LOOP-02 | 自动推进中断清零 remaining_auto_scenes | unit | `uv run pytest tests/unit/test_agent.py::test_auto_interrupt -x` | ❌ Wave 0 |
| LOOP-02 | next_scene() 中递减 remaining_auto_scenes | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_auto_decrement -x` | ❌ Wave 0 |
| LOOP-04 | end_drama() 触发终幕旁白 | unit | `uv run pytest tests/unit/test_tools_phase5.py::test_end_drama_epilogue -x` | ❌ Wave 0 |
| LOOP-04 | /end 后番外篇模式可用 | unit | `uv run pytest tests/unit/test_context_builder.py::test_epilogue_mode -x` | ❌ Wave 0 |
| LOOP-04 | load_progress 兼容旧存档（新字段默认值）| unit | `uv run pytest tests/unit/test_integration.py::test_load_legacy_phase5 -x` | ❌ Wave 0 |
| LOOP-02 | _improv_director prompt 包含7段结构 | unit | `uv run pytest tests/unit/test_agent.py::test_improv_prompt_sections -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ tests/integration/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_tools_phase5.py` — covers auto_advance, steer_drama, end_drama, trigger_storm
- [ ] Update `tests/unit/test_agent.py` — add routing tests for new commands, auto-interrupt test, prompt section test
- [ ] Update `tests/unit/test_context_builder.py` — add steer section, epilogue section, auto-advance section tests
- [ ] Update `tests/unit/conftest.py` — add remaining_auto_scenes, steer_direction, storm to mock state
- [ ] Update `tests/unit/test_integration.py` — add legacy state migration test

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user mode, no auth |
| V3 Session Management | no | Single session, InMemorySessionService |
| V4 Access Control | no | Single-user mode |
| V5 Input Validation | yes | Python type hints + runtime checks in Tool functions |
| V6 Cryptography | no | No encryption needed |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via /steer | Tampering | Steer is user-facing by design; no untrusted input flows through steer |
| State manipulation via ToolContext | Tampering | ToolContext access limited to server-side code |
| Auto-advance token consumption | Denial of Service | Soft cap 10 + warning (D-05); code-level remaining_auto_scenes countdown prevents infinite loops |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `app/agent.py`, `app/tools.py`, `app/context_builder.py`, `app/state_manager.py` — all read and verified in this session
- CONTEXT.md: D-01 through D-28 locked decisions — authoritative source
- REQUIREMENTS.md: LOOP-02, LOOP-04 definitions
- Phase 4 CONTEXT.md: Direct prerequisite architecture

### Secondary (MEDIUM confidence)
- `.planning/research/FEATURES.md` — User Intervention patterns validated against current code
- `.planning/codebase/CONCERNS.md` — Known bugs and fragile areas (especially StormRouter command detection via string search)

### Tertiary (LOW confidence)
- None — all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, using existing ADK patterns
- Architecture: HIGH — all patterns follow established conventions from Phase 1-4
- Pitfalls: HIGH — based on concrete analysis of ADK turn-based model constraints and existing codebase issues

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable — no fast-moving dependencies)
