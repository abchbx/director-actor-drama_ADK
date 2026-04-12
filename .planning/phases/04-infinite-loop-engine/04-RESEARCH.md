# Phase 4: Infinite Loop Engine - Research

**Researched:** 2026-04-12
**Domain:** Agent Router 重构 + 无限叙事循环引擎
**Confidence:** HIGH

## Summary

Phase 4 的核心任务是将现有的线性 4 阶段 STORM 流水线（StormRouter → 4 子 Agent）重构为 2 阶段 DramaRouter（setup + improvise），并实现基于 System Prompt 驱动的无限叙事循环。研究涵盖了 ADK BaseAgent 路由模式、3-in-1 Agent prompt 合并策略、场景衔接信息提取、旧状态迁移以及 A2A 演员服务兼容性。

当前代码库中 `StormRouter` 已实现了完整的路由逻辑（基于 `drama.status` 的 4 路分支），`_storm_director` 拥有完整的演出流程和工具集。重构的关键挑战在于：①如何合并 3 个 STORM Agent 的 prompt 而不丢失多视角探索能力；②如何让 `_improv_director` 的 prompt 驱动无限循环而非依赖代码级循环；③如何从现有 state 数据结构中高效提取场景衔接信息而不引入新 LLM 调用。

**Primary recommendation:** 保持 BaseAgent 路由模式不变，仅将路由逻辑从 status 细粒度判断简化为 actors 存在性判断；将循环行为完全交给 _improv_director 的 System Prompt 驱动，代码层面仅增强 next_scene() 返回值和 build_director_context() 的衔接段落。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 保留 `BaseAgent` 子类模式，重命名为 `DramaRouter`，只保留 2 个子 Agent（`_setup_agent` + `_improv_director`）
- **D-02:** 将 `_storm_discoverer` + `_storm_researcher` + `_storm_outliner` 合并为单个 `_setup_agent`，一个 system prompt 涵盖所有 setup 阶段，工具集合并
- **D-03:** Fallback 策略：路由找不到目标 Agent 时默认路由到 `_improv_director`（最安全的兜底）
- **D-04:** 路由判断依据：按 `state["actors"]` 是否非空判断——非空则 improvise，否则 setup。不再依赖 `drama.status` 细粒度状态
- **D-05:** 循环由 System Prompt 驱动——在 `_improv_director` 的 system prompt 中写明调用序列（next_scene → narrate → speak × N → write_scene），LLM 自主按序调用工具。每轮 `/next` 用户输入触发一轮完整场景
- **D-06:** 每场戏结束后等待用户输入——`/next` 继续、`/action` 注入、`/end` 结束。不自动推进多场
- **D-07:** 场景后评估步骤：在 prompt 中提示导演每场结束后回顾局势（调用 `get_director_context`），但代码层面不强制调用特定评估工具。为 Phase 6 `evaluate_tension()` 预留接口
- **D-08:** 衔接信息来源：增强现有 `build_director_context()` 函数，增加"上一场结局摘要"段落，从 `scenes[-1]` 中提取。不引入新工具
- **D-09:** 衔接信息粒度：精简三要素——①上一场结局（1-2句）②角色情绪状态 ③未决事件/悬念。不包含完整场景摘要以节省 token
- **D-10:** 衔接信息组织：两者结合——`next_scene()` 返回值中嵌入精简衔接段落（必看），导演可额外调用 `get_director_context()` 获取全局视野。信息不重复——`next_scene()` 返回衔接要点，`get_director_context()` 返回全局摘要
- **D-11:** Setup 完成判定：演员创建完毕即完成（`state["actors"]` 非空）。与 D-04 路由逻辑天然一致
- **D-12:** `/start` 流程：一站式 Setup——`_setup_agent` 在单轮对话中完成发现视角→合成大纲→引导用户确认→创建角色。用户只发一次 `/start <主题>`，Agent 自主推进到演员创建
- **D-13:** 首次引导：`next_scene()` 返回 `is_first_scene` 标记——当 `current_scene == 0` 时标注为 true，导演据此输出开场白和首场特殊引导
- **D-14:** 旧状态兼容：`load_drama()` 加载时自动升级旧状态——若有 actors 则统一改为 `"acting"`，否则改为 `"setup"`。用户无感迁移

### Claude's Discretion
- `_setup_agent` 和 `_improv_director` 的 system prompt 具体措辞和长度
- `_setup_agent` 内部步骤的详细编排（发现→研究→大纲的 prompt 逻辑）
- `build_director_context()` 增强段落的具体格式
- `next_scene()` 返回值中衔接信息的精确字段名
- 旧 STORM 工具（`storm_discover_perspectives`, `storm_ask_perspective_questions` 等）的保留/废弃策略

### Deferred Ideas (OUT OF SCOPE)
- `/auto N` 自动推进 N 场功能 — 属于 Phase 5: Mixed Autonomy Mode
- `evaluate_tension()` 张力评分工具 — 属于 Phase 6: Tension Scoring & Conflict Engine
- `inject_conflict()` 冲突注入工具 — 属于 Phase 6
- `/storm` 命令和 Dynamic STORM — 属于 Phase 8
- `/steer <direction>` 轻量引导 — 属于 Phase 5
- `/end` 终幕旁白和完整剧本导出 — 属于 Phase 5（LOOP-04）
- 代码级循环（while loop 自动多场）— 违背 ADK turn-based 模型，不建议实现
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOOP-01 | 无限叙事循环 — 场景→评估张力→注入冲突(如需)→下一场，无预设终点，直至用户发出终止命令 | D-05 System Prompt 驱动循环 + D-06 用户等待 + D-07 评估预留接口；DramaRouter 路由简化移除硬编码终点 |
| LOOP-03 | 场景自然衔接 — 每场戏的 prompt 自动包含上一场的关键信息（结局、情绪、未决事件），确保逻辑自然延续 | D-08/D-09/D-10 衔接信息三要素 + next_scene() 返回值增强 + build_director_context() 增加段落 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | >=1.15.0,<2.0.0 | Agent 框架（BaseAgent, Agent, ToolContext） | 项目已锁定依赖，ADK 提供 BaseAgent 路由模式 [VERIFIED: pyproject.toml] |
| a2a-sdk | ~=0.3.22 | Actor A2A 通信协议 | 项目已锁定，actor_speak() 依赖此 SDK [VERIFIED: pyproject.toml] |
| LiteLlm | (from ADK) | 多模型支持 | 项目通过 LiteLlm 接入 OpenAI 兼容模型 [VERIFIED: agent.py:66] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.3.4 | 单元测试 | 验证路由逻辑、衔接信息提取、状态迁移 |
| pytest-asyncio | >=0.23.8 | 异步测试 | 测试 DramaRouter._run_async_impl |
| ruff | >=0.4.6 | 代码规范 | lint + format |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BaseAgent 路由 | ADK LoopAgent | LoopAgent 需要 escalate 退出机制，不适合用户交互驱动的 turn-based 循环 [ASSUMED] |
| System Prompt 驱动循环 | 代码级 while 循环 | while 循环违背 ADK turn-based 事件模型，一个用户 turn 不应产出多场戏 [VERIFIED: ADK docs] |
| 2 子 Agent | 1 个合并 Agent | 1 Agent 的 prompt 会过长（setup+improvise 逻辑差异大），路由丢失灵活性 |

**Installation:** 无需新安装——所有依赖已在 pyproject.toml 中。

**Version verification:** 已从 pyproject.toml 确认版本范围，无需额外验证。

## Architecture Patterns

### Recommended Project Structure
```
app/
├── agent.py           # DramaRouter + _setup_agent + _improv_director（重构主战场）
├── tools.py           # next_scene() 增强 + load_drama() 兼容 + 旧 STORM 工具保留/迁移
├── context_builder.py # build_director_context() 增加衔接段落
├── state_manager.py   # load_progress() 状态迁移逻辑
├── memory_manager.py  # 不变（Phase 1 交付）
├── semantic_retriever.py  # 不变（Phase 3 交付）
├── actor_service.py   # 不变
└── actors/            # 运行时生成的 Actor 文件，不变
```

### Pattern 1: BaseAgent Router（DramaRouter）

**What:** 继承 `BaseAgent`，实现 `_run_async_impl()` 根据状态路由到子 Agent
**When to use:** 替代当前 StormRouter 的 4 路分支为 2 路分支

**Example:**
```python
# Source: ADK cheatsheet BaseAgent pattern + current agent.py
class DramaRouter(BaseAgent):
    """Routes user input to setup_agent or improv_director based on actors existence."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        # Check for utility commands that should route to improv_director
        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = ["/save", "/load", "/export", "/cast", "/status", "/list"]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            # Improvise phase: actors exist → route to _improv_director
            agent = self._sub_agents_map.get("improv_director")
        else:
            # Setup phase: no actors yet → route to _setup_agent
            agent = self._sub_agents_map.get("setup_agent")

        # D-03: Fallback to improv_director
        if agent is None:
            agent = self._sub_agents_map.get("improv_director")

        async for event in agent.run_async(ctx):
            yield event

    @property
    def _sub_agents_map(self) -> dict:
        return {sa.name: sa for sa in self.sub_agents}
```

### Pattern 2: System Prompt 驱动循环

**What:** 在 _improv_director 的 instruction 中写明工具调用序列和循环行为，LLM 自主按序调用
**When to use:** 实现无限叙事循环，无需代码级 while 循环

**Example:**
```python
# Source: [ASSUMED] based on current _storm_director instruction pattern
_improv_director = Agent(
    name="improv_director",
    model=_get_model(),
    instruction="""你是戏剧导演，处于**无限演出模式**——没有预设终点，故事可以永远继续。

## ⚠️ 核心循环协议
每次用户发送 /next 或 /action，你必须按以下顺序执行：

1. **next_scene()** → 推进场景计数器，获取衔接信息
2. **director_narrate()** → 描述本场环境、氛围、时间、地点
3. **actor_speak() × N** → 逐个让参与角色的 A2A 服务回应
4. **write_scene()** → 将完整内容记录到剧本
5. **回顾局势** → 考虑是否需要调用 get_director_context() 审视全局

输出完整剧本格式片段后，等待用户下一步指令。

## ⚠️ 无终点声明
你**永远不会**自行结束戏剧。只有用户发送 /end 时才终止。
每一场都是新故事的开始——即使上一场看似结束，下一场也可以有新的转折。
""",
    tools=[...],
)
```

### Pattern 3: 场景衔接信息提取

**What:** 从现有 state 数据中提取三要素衔接信息，不引入新 LLM 调用
**When to use:** next_scene() 返回值增强 和 build_director_context() 增加段落

**Example:**
```python
# Source: [VERIFIED: state_manager.py + context_builder.py 现有数据结构]
def _extract_scene_transition(state: dict) -> dict:
    """Extract scene transition info from the last scene in state.

    三要素：①上一场结局 ②角色情绪状态 ③未决事件/悬念
    纯函数，不调用 LLM。
    """
    scenes = state.get("scenes", [])
    actors = state.get("actors", {})
    
    if not scenes:
        return {"is_first_scene": True, "last_ending": "", "actor_emotions": {}, "unresolved": []}
    
    last_scene = scenes[-1]
    current_scene = state.get("current_scene", 0)
    
    # ① 上一场结局：从场景描述和内容末尾提取
    # 取场景 description（通常是舞台指示）和 content 末尾
    last_ending = last_scene.get("description", "")
    if len(last_ending) > 200:
        last_ending = last_ending[-200:]  # 截取末尾 200 字符
    
    # ② 角色情绪状态
    actor_emotions = {}
    for name, data in actors.items():
        emotion = data.get("emotions", "neutral")
        actor_emotions[name] = _EMOTION_CN.get(emotion, emotion)
    
    # ③ 未决事件：从 critical_memories 中提取 reason 为 "未决事件" 的条目
    unresolved = []
    for name, data in actors.items():
        for m in data.get("critical_memories", []):
            if m.get("reason") == "未决事件":
                unresolved.append(f"{name}: {m['entry'][:100]}")
        # 也检查 arc_summary 中的 unresolved
        arc = data.get("arc_summary", {}).get("structured", {})
        for u in arc.get("unresolved", []):
            if u not in unresolved:
                unresolved.append(u)
    
    return {
        "is_first_scene": current_scene == 0,
        "last_ending": last_ending,
        "actor_emotions": actor_emotions,
        "unresolved": unresolved[:5],  # 最多 5 条，节省 token
    }
```

### Anti-Patterns to Avoid
- **代码级 while 循环自动推进多场：** ADK 的 turn-based 模型每个用户输入只应触发一轮 Agent 响应。代码级循环会导致事件流混乱、状态不一致。[VERIFIED: ADK docs — BaseAgent._run_async_impl yields events for one agent run]
- **路由逻辑依赖细粒度 status：** 当前 StormRouter 依赖 5 种 status 值路由，任何遗漏都导致错误路由。D-04 锁定用 actors 存在性判断，更简单可靠。[VERIFIED: agent.py:422-433 当前路由逻辑]
- **3 个 STORM Agent 的 prompt 逻辑分散到 _improv_director：** Setup 和 Improvise 是截然不同的阶段，混在一起会让 prompt 过长且逻辑冲突。D-01/D-02 锁定 2 个 Agent。[VERIFIED: CONTEXT.md D-01/D-02]
- **新引入 LLM 调用来提取衔接信息：** 每场额外调用 LLM 提取衔接信息会增加延迟和 token 成本。D-08 锁定从现有 state 数据提取。[VERIFIED: CONTEXT.md D-08]
- **静默 fallback 到第一个子 Agent：** 当前 StormRouter 在 agent=None 时 fallback 到 `self._sub_agents[0]`（即 _storm_discoverer），这是错误路由。D-03 锁定 fallback 到 _improv_director。[VERIFIED: agent.py:436 + CONCERNS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent 路由框架 | 自定义路由调度器 | ADK BaseAgent + sub_agents | ADK 已提供完整的 agent 生命周期管理、事件传递、状态共享 [VERIFIED: ADK cheatsheet] |
| 循环控制 | while 循环 + 计数器 | System Prompt 指导 LLM 自主循环 | ADK turn-based 模型不支持代码级循环，prompt 驱动符合框架设计 [VERIFIED: ADK docs] |
| 状态迁移 | 复杂的 schema 版本管理 | load_progress() 中的简单条件判断 | 旧状态只需区分"有 actors"和"没 actors"，无需复杂迁移 [ASSUMED] |
| 场景摘要提取 | LLM 调用总结上一场 | 从 scenes[-1].description 提取 + critical_memories | 避免额外 LLM 延迟和 token 开销 [VERIFIED: CONTEXT.md D-08] |

**Key insight:** ADK 框架已经提供了 Agent 路由、事件传递、状态共享的完整基础设施。Phase 4 的核心工作不是"构建循环引擎"，而是"重组现有组件 + 调整 prompt 策略"。

## Runtime State Inventory

> Phase 4 涉及 Router 重构和状态迁移，需要检查运行时状态。

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `state.json` 中 `drama.status` 字段（"brainstorming"/"storm_discovering"/"storm_researching"/"storm_outlining"/"acting"） | code edit — load_progress() 中将旧 status 映射为 "setup"/"acting" |
| Live service config | A2A actor services（运行中进程不受 Router 重构影响） | 无 — actor_speak() A2A 调用接口不变 |
| OS-registered state | 无 — 不涉及 OS 级注册 | None — verified by code inspection |
| Secrets/env vars | OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME | 无 — env 读取逻辑不变 |
| Build artifacts | `app/actors/actor_*.py` 运行时生成文件 | 无 — actor service 生成逻辑不变 |

## Common Pitfalls

### Pitfall 1: _setup_agent Prompt 合并后能力退化

**What goes wrong:** 将 3 个独立 STORM Agent 的 prompt 合并为 1 个后，LLM 可能跳过某些阶段（如直接从发现跳到创建角色），导致多视角探索不充分
**Why it happens:** 单个 prompt 中混合多个阶段指令时，LLM 倾向于走最短路径完成任务
**How to avoid:** 在 _setup_agent 的 prompt 中使用显式的步骤标记和检查点，例如"步骤 1：你必须先调用 storm_discover_perspectives""步骤 2：你必须对每个视角调用研究工具""步骤 3：你必须调用 storm_synthesize_outline 并获得用户确认后才能创建角色"
**Warning signs:** 用户 /start 后直接被要求确认角色，跳过了视角探索

### Pitfall 2: next_scene() 衔接信息与 get_director_context() 信息重复

**What goes wrong:** next_scene() 返回了完整的场景摘要，get_director_context() 也包含相同的近期场景信息，导致 token 浪费和 LLM 困惑
**Why it happens:** 两个函数都从 scenes 列表提取信息，但粒度不同
**How to avoid:** D-10 明确信息不重复——next_scene() 只返回精简衔接三要素（1-2句结局 + 情绪 + 未决事件），get_director_context() 返回全局摘要（10场概览 + 弧线 + 冲突）。实现时在 next_scene() 中使用专门的 _extract_scene_transition() 函数，不调用 build_director_context()
**Warning signs:** 导演 prompt 中同一场景信息出现两次

### Pitfall 3: 旧状态 status 值导致路由死锁

**What goes wrong:** 用户加载一个旧存档（status 为 "storm_researching" 或 "storm_outlining"），但 DramaRouter 不再识别这些 status 值，路由到错误的 Agent
**Why it happens:** DramaRouter 的路由只看 actors 存在性，不看 status。但旧存档可能有 status="storm_researching" + actors={} 的情况（比如用户在 STORM 研究阶段保存了）
**How to avoid:** D-14 锁定在 load_progress() 中自动升级旧状态。具体实现：加载后检查 actors 是否非空，非空则 status="acting"，否则 status="setup"。不保留旧的 STORM 中间状态值
**Warning signs:** /load 后用户命令被路由到错误的 Agent

### Pitfall 4: _improv_director 的 LLM 自行决定结束戏剧

**What goes wrong:** 尽管没有 /end 命令，LLM 可能在某个"自然的"故事终点自行宣布戏剧结束
**Why it happens:** LLM 训练数据中故事通常有结局，模型倾向"收尾"
**How to avoid:** 在 _improv_director 的 system prompt 中使用强约束语言："你永远不会自行结束戏剧"、"每一场都是新故事的开始"、"即使看似结局，下一场也可以有新的转折"。将此约束放在 prompt 的最高优先级位置
**Warning signs:** 导演输出中出现"全剧终"或"故事到此结束"但用户没有发 /end

### Pitfall 5: 演员 A2A 服务在循环中断后丢失

**What goes wrong:** 用户在 improvise 阶段 /load 了一个不同的戏剧，当前运行的 A2A actor 服务进程没有停止，端口被占用
**Why it happens:** load_drama() 会重启 A2A 服务，但旧进程如果没有正确清理，新进程可能启动失败
**How to avoid:** load_drama() 已经在重启前调用 stop_all_actor_services()（需确认），如果没有则需添加。同时端口冲突检测逻辑需要加强（CONCERNS.md 已记录端口碰撞风险）
**Warning signs:** /load 后 actor_speak() 返回连接失败

### Pitfall 6: 合并后的 _setup_agent 工具集过大

**What goes wrong:** _setup_agent 继承了 3 个 STORM Agent 的所有工具，工具列表过长导致 LLM 选择困难
**Why it happens:** discoverer + researcher + outliner + create_actor 的工具合并后可能有 7-8 个工具
**How to avoid:** 精简 _setup_agent 的工具集——只保留必需的工具（start_drama, storm_discover_perspectives, storm_synthesize_outline, create_actor），移除中间步骤工具（storm_ask_perspective_questions, storm_research_perspective 可以由 LLM 自然推理替代，因为当前这些工具产生的是占位符数据 [VERIFIED: CONCERNS.md]）
**Warning signs:** _setup_agent 调用了不恰当的工具或跳过了关键步骤

## Code Examples

### DramaRouter 完整实现

```python
# Source: [VERIFIED: agent.py 现有 StormRouter + ADK cheatsheet BaseAgent pattern]
from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from typing import AsyncGenerator

class DramaRouter(BaseAgent):
    """Routes user input to setup_agent or improv_director.

    Routing logic (D-04):
    - If actors exist in state → improv_director
    - If no actors → setup_agent
    - Utility commands (/save, /load, etc.) → improv_director
    - Fallback (D-03) → improv_director
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        # Check for utility commands
        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = ["/save", "/load", "/export", "/cast", "/status", "/list"]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            agent = self._sub_agents_map.get("improv_director")
        else:
            agent = self._sub_agents_map.get("setup_agent")

        # D-03: Fallback to improv_director (safest default)
        if agent is None:
            agent = self._sub_agents_map.get("improv_director")

        async for event in agent.run_async(ctx):
            yield event

    @property
    def _sub_agents_map(self) -> dict:
        return {sa.name: sa for sa in self.sub_agents}
```

### next_scene() 返回值增强

```python
# Source: [VERIFIED: tools.py:493-528 现有 next_scene() + CONTEXT.md D-09/D-10/D-13]
def next_scene(tool_context: ToolContext) -> dict:
    """Advance to the next scene with transition info."""
    result = advance_scene(tool_context)
    state = tool_context.state.get("drama", {})
    scene_num = state.get("current_scene", 1)

    # Extract transition info (D-08/D-09/D-10)
    transition = _extract_scene_transition(state)

    # Build transition paragraph for director prompt
    transition_text = ""
    if transition["is_first_scene"]:
        transition_text = "🎬 这是本剧的第一场戏！请输出开场白，介绍故事背景和主要角色。"
    else:
        parts = []
        if transition["last_ending"]:
            parts.append(f"上一场结局：{transition['last_ending']}")
        if transition["actor_emotions"]:
            emotions_str = "、".join(
                f"{name}（{emo}）" for name, emo in transition["actor_emotions"].items()
            )
            parts.append(f"角色情绪：{emotions_str}")
        if transition["unresolved"]:
            parts.append(f"未决事件：{'；'.join(transition['unresolved'][:3])}")
        transition_text = "【上一场衔接】\n" + "\n".join(parts)

    actors_data = state.get("actors", {})
    actor_names = list(actors_data.keys())
    actor_list = "、".join(actor_names) if actor_names else "（尚无演员）"

    return {
        "status": "success",
        "current_scene": scene_num,
        "is_first_scene": transition["is_first_scene"],
        "transition": transition,
        "transition_text": transition_text,
        "actors_available": actor_names,
        "message": (
            f"▶️ 已推进至第 {scene_num} 场。\n\n"
            f"{transition_text}\n\n"
            f"当前可用演员: {actor_list}\n\n"
            f"请按以下顺序执行：\n"
            f"  ① director_narrate —— 描述本场环境\n"
            f"  ② actor_speak —— 让角色对话\n"
            f"  ③ write_scene —— 记录本场\n\n"
            f"输出完整剧本格式片段后等待用户指令。"
        ),
    }
```

### build_director_context() 增加衔接段落

```python
# Source: [VERIFIED: context_builder.py:629-673 现有 build_director_context()]
def _build_last_scene_transition_section(state: dict) -> dict:
    """Build the last scene transition section for director context.

    D-08/D-09: 精简三要素——上一场结局 + 角色情绪 + 未决事件。
    与 next_scene() 返回的衔接信息不重复（D-10）：
    next_scene() 返回即时衔接要点，此处返回更完整的上下文视野。
    """
    scenes = state.get("scenes", [])
    if not scenes:
        return {"key": "last_scene_transition", "text": "", "priority": 7, "truncatable": False}

    last_scene = scenes[-1]
    
    # 上一场结局
    last_ending = last_scene.get("description", "")
    content = last_scene.get("content", "")
    if content and len(content) > 50:
        # 取内容末尾作为结局摘要
        last_ending += "..." + content[-150:] if len(content) > 150 else content
    if len(last_ending) > 300:
        last_ending = last_ending[-300:]

    # 角色情绪
    actors = state.get("actors", {})
    emotion_lines = []
    for name, data in actors.items():
        role = data.get("role", "")
        emotion = data.get("emotions", "neutral")
        emotion_cn = _EMOTION_CN.get(emotion, emotion)
        emotion_lines.append(f"- {name}（{role}）：{emotion_cn}")

    # 未决事件
    unresolved_lines = []
    for name, data in actors.items():
        for m in data.get("critical_memories", []):
            if m.get("reason") == "未决事件":
                unresolved_lines.append(f"- {name}: {m['entry'][:80]}")
        arc = data.get("arc_summary", {}).get("structured", {})
        for u in arc.get("unresolved", []):
            if u not in "；".join(unresolved_lines):
                unresolved_lines.append(f"- {u}")

    parts = [f"【上一场衔接】\n上一场「{last_scene.get('title', '未命名')}」：{last_ending}"]
    if emotion_lines:
        parts.append("当前角色情绪：\n" + "\n".join(emotion_lines))
    if unresolved_lines:
        parts.append("未决事件：\n" + "\n".join(unresolved_lines[:5]))

    text = "\n".join(parts)
    return {"key": "last_scene_transition", "text": text, "priority": 7, "truncatable": False}
```

### load_progress() 旧状态迁移

```python
# Source: [VERIFIED: state_manager.py:403-467 现有 load_progress()]
# 在 load_progress() 的 state.update(save_data) 之后添加：
def _migrate_legacy_status(state: dict) -> dict:
    """Migrate old STORM status values to new DramaRouter status (D-14).

    Old statuses: "", "brainstorming", "storm_discovering", 
                  "storm_researching", "storm_outlining", "acting"
    New statuses: "setup", "acting"
    
    Rule: actors exist → "acting", otherwise → "setup"
    """
    actors = state.get("actors", {})
    if actors and len(actors) > 0:
        state["status"] = "acting"
    else:
        state["status"] = "setup"
    return state
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 4 个 STORM 子 Agent 线性流水线 | 2 个子 Agent（setup + improvise） | Phase 4 | Router 大幅简化，Setup 一站式完成 |
| status 驱动的细粒度路由 | actors 存在性驱动的 2 路路由 | Phase 4 | 路由逻辑更简单可靠，避免中间状态死锁 |
| STORM 研究/大纲阶段分开 | Setup 合并为单 Agent 单轮对话 | Phase 4 | 用户体验更流畅，但需要精心设计合并后的 prompt |
| _storm_director 无限演出但无显式循环声明 | _improv_director 显式声明无限模式 | Phase 4 | Prompt 约束 LLM 不自行结束戏剧 |
| next_scene() 只返回场景编号 | next_scene() 返回衔接信息 + is_first_scene | Phase 4 | 导演上下文更完整，场景过渡更自然 |

**Deprecated/outdated:**
- `_storm_discoverer` Agent: 合并入 _setup_agent [VERIFIED: CONTEXT.md D-02]
- `_storm_researcher` Agent: 合并入 _setup_agent [VERIFIED: CONTEXT.md D-02]
- `_storm_outliner` Agent: 合并入 _setup_agent [VERIFIED: CONTEXT.md D-02]
- `StormRouter` 类: 重命名为 DramaRouter [VERIFIED: CONTEXT.md D-01]
- `storm_researching`/`storm_outlining` status 值: 迁移为 "setup"/"acting" [VERIFIED: CONTEXT.md D-14]
- `storm_ask_perspective_questions()` 工具: 可选废弃（产生占位符数据 [VERIFIED: CONCERNS.md]）
- `storm_research_perspective()` 工具: 可选废弃（产生占位符数据 [VERIFIED: CONCERNS.md]）

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ADK LoopAgent 不适合用户交互驱动的 turn-based 循环 | Standard Stack / Alternatives | 如果 LoopAgent 可以用，可能提供更结构化的循环控制 |
| A2 | 旧状态迁移只需区分"有 actors"和"没 actors" | Common Pitfalls / 状态迁移 | 可能存在有 actors 但 status 非 "acting" 的边缘情况 |
| A3 | storm_ask_perspective_questions 和 storm_research_perspective 可以废弃 | Code Examples | 如果 _setup_agent 需要这些工具来引导 LLM 进行研究，废弃后可能能力退化 |
| A4 | _improv_director 的强约束 prompt 能有效阻止 LLM 自行结束戏剧 | Common Pitfalls | LLM 可能忽略 prompt 约束，需要运行时验证 |
| A5 | 现有 A2A actor 服务在 Router 重构后完全不受影响 | Runtime State Inventory | 如果 Router 改变了传递给 actor_speak() 的上下文，演员行为可能变化 |

## Open Questions (RESOLVED)

1. **旧 STORM 工具的保留策略** — RESOLVED by Plan 04-01
   - What we know: storm_ask_perspective_questions() 和 storm_research_perspective() 当前产生占位符数据（CONCERNS.md 记录），实际不提供有用信息
   - What's unclear: _setup_agent 合并后是否需要保留这些工具给 LLM 调用（即使它们当前产生占位符数据），还是应该移除并让 LLM 自然推理
   - Recommendation: 保留 storm_discover_perspectives() 和 storm_synthesize_outline()（它们产生有意义的结构化数据），移除 ask/research 中间步骤工具。_setup_agent 的 prompt 引导 LLM 在单轮中完成"发现→推理→合成"，不需要中间工具
   - **RESOLVED:** Plan 04-01 Action 第2步采用了此 Recommendation——_setup_agent 工具集包含 start_drama + storm_discover_perspectives + storm_synthesize_outline + create_actor（4 工具），移除了 ask_perspective_questions 和 research_perspective

2. **build_director_context() 衔接段落的优先级** — RESOLVED by Plan 04-02
   - What we know: 当前 director context 的优先级体系中，current_status=10, actor_emotions=6, recent_scenes=4, storm=3
   - What's unclear: 新增的 last_scene_transition 段落应设置什么优先级
   - Recommendation: 设置优先级 7（高于 recent_scenes 但低于 current_status），因为衔接信息比近期场景列表更重要，但不应高于当前状态
   - **RESOLVED:** Plan 04-02 Action 第4步将 last_scene_transition 优先级设为 7，且 truncatable=False（不可截断），完全采纳了此 Recommendation

3. **_setup_agent 是否需要 /next 命令来推进 Setup 阶段** — RESOLVED by Plan 04-01
   - What we know: D-12 锁定一站式 Setup，用户只发 /start <主题>
   - What's unclear: 如果 LLM 在单轮中无法完成所有 setup 步骤（如 token 限制），是否需要支持多轮 setup
   - Recommendation: _setup_agent 的 prompt 应明确"在单轮中完成所有步骤"，但如果 LLM 请求用户确认大纲后再创建角色，这是合理的交互中断点。Router 的路由逻辑不需要改——只要 actors 还没创建，用户下一次输入仍然路由到 _setup_agent
   - **RESOLVED:** Plan 04-01 的 DramaRouter 路由逻辑（D-04）天然支持多轮 setup——只要 actors 为空，用户输入始终路由到 _setup_agent。_setup_agent prompt 明确要求"一站式完成"，但若需用户确认大纲，自然中断后重新路由回来

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified — Phase 4 是纯代码重构，所有外部依赖如 ADK、a2a-sdk 已在 pyproject.toml 中锁定)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.3.4 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/unit/ -x -q` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOOP-01 | DramaRouter 路由到 _setup_agent（无 actors） | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_setup -x` | ❌ Wave 0 |
| LOOP-01 | DramaRouter 路由到 _improv_director（有 actors） | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_improvise -x` | ❌ Wave 0 |
| LOOP-01 | DramaRouter fallback 到 _improv_director | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_fallback -x` | ❌ Wave 0 |
| LOOP-01 | _improv_director prompt 包含无限循环声明 | unit | `uv run pytest tests/unit/test_agent.py::test_improv_director_no_ending -x` | ❌ Wave 0 |
| LOOP-03 | next_scene() 返回 is_first_scene=True（首场） | unit | `uv run pytest tests/unit/test_tools.py::test_next_scene_first_scene -x` | ❌ Wave 0 |
| LOOP-03 | next_scene() 返回衔接信息（非首场） | unit | `uv run pytest tests/unit/test_tools.py::test_next_scene_transition -x` | ❌ Wave 0 |
| LOOP-03 | build_director_context() 包含衔接段落 | unit | `uv run pytest tests/unit/test_context_builder.py::test_director_context_transition -x` | ❌ Wave 0 |
| D-14 | load_progress() 迁移旧 status | unit | `uv run pytest tests/unit/test_state_manager.py::test_migrate_legacy_status -x` | ❌ Wave 0 |
| D-04 | utility commands 路由到 _improv_director | unit | `uv run pytest tests/unit/test_agent.py::test_drama_router_utility_commands -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_agent.py` — covers LOOP-01 (DramaRouter routing)
- [ ] `tests/unit/test_tools.py` — covers LOOP-03 (next_scene transition info)
- [ ] `tests/unit/test_context_builder.py` — additional test for transition section (file exists, needs new test)
- [ ] `tests/unit/test_state_manager.py` — covers D-14 (status migration)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — 单用户 CLI 工具 |
| V3 Session Management | no | N/A — ADK 管理会话 |
| V4 Access Control | no | N/A — 无多用户 |
| V5 Input Validation | yes | tool_context.state dict access — Python type checking |
| V6 Cryptography | no | N/A — 无加密需求 |

### Known Threat Patterns for ADK Agent System

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via /action | Tampering | Actor cognitive boundaries (A2A isolation) + director prompt constraints |
| State corruption via concurrent tool calls | Tampering | ADK session state is per-session; global mutable state in state_manager.py is a known concern (CONCERNS.md) |
| Misrouting to wrong agent | Denial of Service | D-03 fallback to _improv_director + D-04 simple routing logic |

## Sources

### Primary (HIGH confidence)
- `app/agent.py` — StormRouter + 4 sub-agents implementation (read in full)
- `app/tools.py` — All tool functions including next_scene(), STORM tools (read in full)
- `app/context_builder.py` — Director/actor context builder (read in full)
- `app/state_manager.py` — State management + load_progress() (read in full)
- `04-CONTEXT.md` — User decisions from discuss phase (read in full)
- ADK cheatsheet — BaseAgent pattern, LoopAgent, Agent configuration (verified)

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — Architecture evolution design (partial read)
- `.planning/codebase/CONCERNS.md` — Known issues including STORM placeholder data and router fallback bug
- `.planning/codebase/CONVENTIONS.md` — Code style, naming patterns, import organization
- `.planning/ROADMAP.md` — Phase 4 success criteria and requirements
- `.planning/REQUIREMENTS.md` — LOOP-01, LOOP-03 definitions

### Tertiary (LOW confidence)
- Phase 1/2/3 CONTEXT.md — Prior phase decisions that inform current design constraints

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 所有依赖已在项目中锁定，无新增依赖
- Architecture: HIGH — BaseAgent 路由模式已在代码库中验证，重构模式清晰
- Pitfalls: HIGH — 基于 CONCERNS.md 已知问题 + CONTEXT.md 决策推导

**Research date:** 2026-04-12
**Valid until:** 30 days (stable — 核心框架 ADK 不太可能有 breaking change)
