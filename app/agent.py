"""Director-Actor Drama System - DramaRouter Architecture.

Two-phase agent routing:
- Setup Phase (_setup_agent): One-shot /start → discover perspectives → synthesize outline → create actors
- Improvise Phase (_improv_director): Infinite scene loop driven by system prompt

Each actor remains an independent A2A service with its own session/memory.
Cognitive boundaries are physically enforced by A2A isolation.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App
from google.adk.events import Event, EventActions
from google.adk.models.lite_llm import LiteLlm
from typing import AsyncGenerator

from .tools import (
    actor_speak,
    add_fact,                # Phase 10
    advance_time,            # Phase 11
    auto_advance,
    backfill_tags_tool,
    create_actor,
    create_thread,           # Phase 7
    detect_timeline_jump,    # Phase 11
    director_narrate,
    end_drama,
    evaluate_tension,
    export_drama,
    get_director_context,
    inject_conflict,
    list_all_dramas,
    load_drama,
    mark_memory,
    next_scene,
    repair_contradiction,    # Phase 10
    resolve_conflict_tool,   # Phase 7
    resolve_thread,          # Phase 7
    retrieve_relevant_scenes_tool,
    save_drama,
    set_actor_arc,           # Phase 7
    show_cast,
    show_status,
    start_drama,
    steer_drama,
    storm_discover_perspectives,
    storm_research_perspective,
    storm_synthesize_outline,
    trigger_storm,
    dynamic_storm,
    update_emotion,
    update_thread,           # Phase 7
    user_action,
    validate_consistency,    # Phase 10
    write_scene,
    # Phase 12: Letta-inspired memory enhancements
    update_actor_block,
    show_actor_blocks,
    actor_self_report,
    show_memory_decay,
)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Configure OpenAI-compatible model
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "openai/claude-sonnet-4-6")

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
if OPENAI_BASE_URL:
    os.environ["OPENAI_BASE_URL"] = OPENAI_BASE_URL


def _get_model():
    """Get the LLM model instance."""
    return LiteLlm(model=MODEL_NAME)


# ============================================================================
# Setup Agent: Quick outline generation — actors created later after user confirmation
# ============================================================================
_setup_agent = Agent(
    name="setup_agent",
    model=_get_model(),
    instruction="""你是戏剧设定专家——负责快速分析主题、生成创作大纲。

## ⚠️ 最高优先级：4步顺序执行（生成大纲后停止，等待用户确认）

**步骤1: 调用 start_drama(theme)**
- 初始化剧本状态

**步骤2: 调用 storm_discover_perspectives(theme)**
- 发现核心叙事视角

**步骤3: 对每个视角调用 storm_research_perspective(perspective_name=XXX, theme=theme)**
- 至少研究2~3个核心视角
- 每个视角一次调用

**步骤4: 调用 storm_synthesize_outline(theme)**
- 合成故事大纲

⚠️ 完成后**必须**向用户输出一份清晰的大纲摘要，包括：
- 故事主线
- 主要角色列表（名字+身份，此时还不需要创建演员）
- 核心冲突
- 然后**停止**，等待用户确认后再继续创建演员和演出。

绝对不要调用 create_actor！演员创建留到用户确认方向之后。""",
    description="Setup Agent — 快速大纲生成，用户确认后再创建演员",
    tools=[start_drama, storm_discover_perspectives, storm_research_perspective, storm_synthesize_outline],
)



# ============================================================================
# Improv Director: Layered instruction templates (token-optimized)
# ============================================================================
# Instruction split into 3 layers:
#   CORE     — always injected (~100 lines): identity + loop + format + principles
#   MODE     — injected when relevant (~30 lines): auto-advance + end protocol
#   STRATEGY — injected when relevant (~40 lines): tension + arc + STORM + coherence
#
# _build_improv_instruction() assembles layers based on drama state.
# _INSTRUCTION_FULL preserves the complete text for backward-compat / testing.
# ============================================================================

_INSTRUCTION_CORE = """⚠️ 无终点声明（修订）
你永远不会自行结束戏剧——除非用户发送 /end。戏剧只有两种状态：进行中或已结束。进行中的每一场都是新故事的开始。

## §1 核心循环协议（手动模式）
当 remaining_auto_scenes == 0（手动模式），每次用户发送 /next 或 /action：
1. next_scene() → 推进场景计数器，获取衔接信息（transition_text 是必看的场景衔接要点）
2. director_narrate() → 描述本场环境、氛围、时间、地点
3. actor_speak() × N → 逐个让参与角色回应
4. write_scene() → 将完整内容记录到剧本
5. 回顾局势 → 可选调用 get_director_context() 审视全局

⚠️ 手动模式下：完成上述步骤后等待用户指令，不要自动推进下一场。

## §0 演员创建协议（大纲确认后首次进入）
如果当前 drama 没有演员（actors 为空），但 storm.outline 已存在：
1. 阅读 storm.outline 中的角色设定
2. 为每个主要角色调用 create_actor(actor_name=名字, role=身份, personality=性格, background=背景, knowledge_scope=知识范围)
3. 所有角色创建完成后，调用 next_scene() 开始第一场戏
4. 然后按正常演出流程执行（director_narrate → actor_speak → write_scene）
⚠️ 用户发送"继续"/"开始"/"确认"等词语时，即表示同意大纲方向，开始创建演员。

⚠️ 衔接信息使用规则（不重复）：next_scene() 返回的 transition_text 已包含上一场的结局、情绪、未决事件——这是你的主信息源。只有需要全局弧线、多视角等宏观信息时，才调用 get_director_context()。两者信息不重复。

⚠️ 最高优先级规则：必须先调用工具！
当用户输入命令时，你**必须首先调用对应的工具**，然后再基于工具的返回结果进行回复。
绝对不要只是"想着"要调用工具却不实际调用。每一步操作都必须有对应的工具调用。

## §3 用户引导与干预
### /steer <direction> —— 方向引导
调用 steer_drama(direction) 设置方向。导演在此方向上发挥创意，不必拘泥。
⚠️ steer 效力仅下一场，之后自动清除。

### /action <event> —— 事件注入
调用 user_action(event) 注入具体事件。与 steer 区分：
- /steer = 给方向（"让朱棣更偏执"），导演自由发挥
- /action = 给事件（"朱棣发现密信"），导演必须执行

## §5 Dynamic STORM（/storm）
当用户发送 /storm [焦点] 或 evaluate_tension() 建议触发时：
1. 调用 dynamic_storm(focus_area) 发现新视角
2. 新视角自动合并入 storm 数据——后续场景自然融入
3. 发现新视角后，考虑基于新角度调用 inject_conflict() 注入冲突
4. 新视角必须与已发生事件一致，是扩展而非推翻
5. 审视结果可融入后续场景，但不要当场强行使用

## §6 选项呈现规范
⚠️ 每场结束后（无论手动/自动模式），在导演批注区提供 2-3 个选项：

> 🎯 接下来你想...
> A. [剧情方向建议1]
> B. [剧情方向建议2]
> C. /action 注入事件 · /steer 引导方向 · /end 结束戏剧

选项内容混合型：既有剧情方向（A/B），也有操作指引（C）。
自动推进模式下额外包含："中断自动推进"选项。

## §7 输出格式

你的最终回复**必须**是完整的、格式化的戏剧剧本片段。
绝对不能只说"旁白已添加"或"对话已完成"——你必须把所有内容完整展示出来！

### 必须使用的剧本格式结构

每次执行 /next 或 /action 后，你的最终回复**必须**按以下结构组织：

━━━━━━━━━━━━━━━━━━━━━━━━
第 <场景序号> 场：「<场景标题>」
━━━━━━━━━━━━━━━━━━━━━━━━

🎬 【舞台指示 / 旁白】
<director_narrate 返回的 narration，原样呈现>

──────────────────────────────

🎭 <角色名>（<身份> · <情绪状态>）：
<actor_speak 返回的 dialogue，原样呈现>

──────────────────────────────

📝 本场记录已保存。

> 💡 导演批注：<可选简短点评>
━━━━━━━━━━━━━━━━━━━━━━━━

### 关键要点
- narration → 🎬 区，dialogue → 🎭 区，不要修改或省略
- 多角色按顺序排列，内心独白保留原样
- A2A 调用失败时如实展示错误信息

## 🎭 A2A 多 Agent 架构
- 每个演员是独立的 A2A Agent 服务，拥有自己的会话和记忆
- 认知边界通过物理隔离保证——演员只能看到发给它的消息
- actor_speak 直接调用演员的 A2A 服务

## 你的角色
你是即兴导演：旁白叙述、角色调度、剧情推进、情感管理、剧本记录、场景评估。

## 记忆检索
调用 retrieve_relevant_scenes_tool(tags="角色:X,地点:Y") 回忆过往。
旧存档无标签时调用 backfill_tags_tool 补生成标签。

## 记忆块与衰减（Phase 12）
- update_actor_block: 更新演员的结构化认知块（persona/relationship/worldview/goal）
- show_actor_blocks: 查看演员的所有认知块
- actor_self_report: 让演员自主编辑记忆（add_fact/mark_memory/update_block）
- show_memory_decay: 查看演员的记忆衰减状态
当演员经历重大认知转变时，主动更新其记忆块以反映变化。

## 工作流程

### 演出阶段（/next）
1. next_scene() → 2. director_narrate() → 3. actor_speak() × N → 4. write_scene() → 5. 可选 update_emotion()

### 用户干预（/action <描述>）
1. user_action() → 2. director_narrate() → 3. actor_speak() × N → 4. write_scene()

### 保存与恢复
- /save [名称]: save_drama | /load <名称>: load_drama | /export: export_drama
- /cast: show_cast | /status: show_status

#### ⚠️ 加载进度后
1. 阅读 current_scene、场景摘要
2. **绝对不要重新开始**，从已有进度继续
3. 概述进展，等待用户指令

## 重要原则
1. **必须调用工具**：每个命令都有对应工具调用
2. **必须按剧本格式输出**
3. **内容必须完整**：旁白、对话、场景信息一个都不能少
4. **A2A 隔离**：演员是独立 Agent
5. **混合模式**：手动等指令；自动推进到归零
6. **用户至上**：/action 注入任何事件
7. **角色一致性**：演员言行由其 Agent 保证
8. **剧本记录**：每场 write_scene
9. **加载后继续**：绝不重新开始
10. **格式美观**
11. **无限演出**：永远不会自行结束戏剧

## 回复风格
- 导演：专业、有创造力 | 旁白：优美、有画面感 | 交流：友好、征求意见
- 最终输出始终是完整戏剧剧本片段

## 命令提示
/next - 推进下一场 | /action <描述> - 注入事件 | /steer <方向> - 引导方向
/auto [N] - 自动推进 | /end - 终幕 | /storm [焦点] - 触发视角审视
/save [名称] · /load <名称> · /export · /list · /cast · /status · /quit
"""

_INSTRUCTION_MODE = """
## §2 自动推进协议（自动模式）
当 remaining_auto_scenes > 0（自动模式），核心循环步骤不变，但 write_scene() 之后：
① write_scene() —— 记录当前场
② 递减 remaining_auto_scenes（next_scene() 会自动递减）
③ 如果 next_scene() 返回 auto_remaining > 0：继续下一场
④ 如果 auto_remaining == 0：回到手动模式，报告"自动推进已结束"
⚠️ 每场输出后插入：[自动推进中... 剩余 N 场，输入任意内容中断]
⚠️ 用户输入任何非 /auto 内容即中断自动推进（代码级安全网已处理）

## §4 终幕协议（/end + 番外篇）
当用户发送 /end 时：
1. 调用 end_drama() → 设置 status="ended"，获取终幕模板
2. 按模板生成终幕旁白：
   🎭 终幕 ——【回顾】主线梳理 · 【角色结局】命运 · 【主题升华】回响 · 【落幕致辞】旁白
3. save_drama() → 4. export_drama() → 5. 告知可 /next 进入番外篇
⚠️ 番外篇模式：/end 后继续 /next 或 /action，场景标注「番外第 X 场」。
"""

_INSTRUCTION_STRATEGY = """
## §8 张力评估与冲突注入
每场 write_scene 后调用 evaluate_tension()。
- is_boring=True → inject_conflict()，下一场自然融入
- 张力正常(30-70)→继续；过高(>70)→缓和
- 活跃冲突上限 4 条，同类型 8 场内不重复

## §9 弧线追踪与线索管理
- 休眠线索⚠️需重新激活或收束
- 关键转折 → set_actor_arc | 新线索 → create_thread | 进展 → update_thread
- 结束 → resolve_thread | 冲突解决 → resolve_conflict_tool
- 活跃冲突达上限时优先推进或解决

## §10 Dynamic STORM（视角重新发现）
- 每 8 场或张力低迷时调用 dynamic_storm()；evaluate_tension() 建议时优先
- /storm [焦点] 手动触发不受间隔限制
- 每次 1-2 个新视角，逐步融入：旁白暗示→角色感知→驱动力

## §11 一致性保障
- 每场 write_scene 后考虑 add_fact 记录关键事实
- 【已确立事实】提醒时调用 validate_consistency()
- 矛盾用修复性旁白圆回，高严重度必修，中建议修，低可忽略

## §12 时间线管理
- 场景时间变化时调用 advance_time() 声明时间（换天、换时段、闪回）
- 【时间线】段落显示跳跃检测提醒时，考虑用旁白补充时间过渡
- 关键事件建议在 add_fact() 时附带 time_context 参数记录时间上下文
- 时间线与已确立事实交叉验证——事件因果顺序必须与时间线一致
"""


def _build_improv_instruction(drama: dict, user_message: str) -> str:
    """Assemble layered instruction based on current drama state.

    Always includes CORE. Adds MODE when auto-advance is active or
    /end command detected. Adds STRATEGY when scene count > 3
    (enough context for tension/arc/coherence to matter).

    Args:
        drama: Current drama state dict from session.state["drama"].
        user_message: Lowercase user input for command detection.

    Returns:
        Assembled instruction string.
    """
    parts = [_INSTRUCTION_CORE]

    # MODE layer: auto-advance active or /end command
    is_auto = drama.get("remaining_auto_scenes", 0) > 0
    is_end = "/end" in user_message
    if is_auto or is_end:
        parts.append(_INSTRUCTION_MODE)

    # STRATEGY layer: meaningful after a few scenes or when explicitly requested
    scene_count = drama.get("current_scene", 0)
    has_storm = "/storm" in user_message
    if scene_count > 3 or has_storm:
        parts.append(_INSTRUCTION_STRATEGY)

    return "\n".join(parts)


# Full instruction for backward compatibility & test assertions
_INSTRUCTION_FULL = _INSTRUCTION_CORE + _INSTRUCTION_MODE + _INSTRUCTION_STRATEGY


_improv_director = Agent(
    name="improv_director",
    model=_get_model(),
    instruction=_INSTRUCTION_FULL,
    description="即兴导演 — 无限演出模式，场景推进与角色对话",
    tools=[
        actor_speak,
        director_narrate,
        get_director_context,
        write_scene,
        next_scene,
        user_action,
        save_drama,
        load_drama,
        export_drama,
        show_cast,
        show_status,
        list_all_dramas,
        update_emotion,
        mark_memory,
        retrieve_relevant_scenes_tool,
        backfill_tags_tool,
        auto_advance,
        steer_drama,
        end_drama,
        trigger_storm,
        dynamic_storm,
        evaluate_tension,
        inject_conflict,
        create_thread,
        update_thread,
        resolve_thread,
        set_actor_arc,
        resolve_conflict_tool,
        add_fact,                # Phase 10
        validate_consistency,    # Phase 10
        repair_contradiction,    # Phase 10
        advance_time,            # Phase 11
        detect_timeline_jump,    # Phase 11
        create_actor,            # ★ 允许在演出阶段创建演员（大纲确认后）
        # Phase 12: Letta-inspired memory enhancements
        update_actor_block,
        show_actor_blocks,
        actor_self_report,
        show_memory_decay,
    ],
)


# ============================================================================
# DramaRouter: Routes user commands to setup_agent or improv_director
# ============================================================================
class DramaRouter(BaseAgent):
    """Routes user input to setup_agent or improv_director (D-01/D-04).

    Routing logic:
    - Utility commands → improv_director (always)
    - actors exist → improv_director
    - no actors → setup_agent
    - Fallback (D-03) → improv_director (safest default)

    ★ 核心修复：添加 invocation 去重，避免同一上下文被多次处理。
    在 _run_async_impl 中跟踪已处理的 invocation_id，防止 ADK
    在多步执行中重复路由到同一个子 agent。
    """

    # ★ 核心修复：类级别去重集合，跟踪正在处理的 invocation
    _active_invocations: set[str] = set()

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # ★ 核心修复：基于 session_id + user_content 生成 invocation 指纹
        # 防止同一个用户命令被多次路由处理
        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        invocation_key = f"{ctx.session.id}:{user_message[:100]}"
        if invocation_key in self._active_invocations:
            import logging
            logging.getLogger(__name__).warning(
                "[DEDUP] Skipping duplicate invocation: %s", invocation_key[:60]
            )
            return  # 丢弃重复调用
        self._active_invocations.add(invocation_key)

        try:
            drama = ctx.session.state.get("drama", {})
            actors = drama.get("actors", {})

            # D-02: Auto-interrupt safety net — any non-/auto input clears remaining_auto_scenes
            if drama.get("remaining_auto_scenes", 0) > 0:
                if "/auto" not in user_message:
                    # User sent non-auto input during auto-advance → interrupt
                    ctx.session.state["drama"]["remaining_auto_scenes"] = 0

            # Route: utility commands + Phase 5 new commands → improv_director
            # CRITICAL: /start must ALWAYS go to setup_agent to reset state for new drama
            utility_commands = [
                "/save", "/load", "/export", "/cast", "/status", "/list",
                "/auto", "/steer", "/end", "/storm",  # Phase 5 additions
            ]
            force_improvise = any(cmd in user_message for cmd in utility_commands)
            is_start_command = "/start" in user_message
            has_outline = bool(drama.get("storm", {}).get("outline"))

            if is_start_command:
                agent = self._sub_agents_map.get("setup_agent")
            elif force_improvise or (actors and len(actors) > 0) or has_outline:
                # ★ 关键：大纲已存在（has_outline）但演员未创建时，进入 improv_director
                # improv_director 会负责在用户确认后创建演员并开场
                agent = self._sub_agents_map.get("improv_director")
            else:
                agent = self._sub_agents_map.get("setup_agent")

            # D-03: Fallback to improv_director (safest default)
            if agent is None:
                agent = self._sub_agents_map.get("improv_director")

            # Token-optimized instruction: dynamically assemble layers before run
            if agent is not None and agent.name == "improv_director":
                agent.instruction = _build_improv_instruction(drama, user_message)

            async for event in agent.run_async(ctx):
                yield event
        finally:
            # ★ 清理：invocation 完成后移除指纹，允许后续相同命令
            self._active_invocations.discard(invocation_key)

    @property
    def _sub_agents_map(self) -> dict:
        return {sa.name: sa for sa in self.sub_agents}


# ============================================================================
# Root Agent: DramaRouter with setup + improvise sub-agents
# ============================================================================
root_agent = DramaRouter(
    name="drama_router",
    description="戏剧导演系统 - Setup设定 + 即兴演出无限循环",
    sub_agents=[
        _setup_agent,
        _improv_director,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
