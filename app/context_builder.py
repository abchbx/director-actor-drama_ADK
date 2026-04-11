"""Context builder for assembling precise LLM context per scene.

Implements token budget control and priority-based truncation for both
actor and director contexts. Provides:
- estimate_tokens(): Character-based token approximation (D-02)
- _truncate_sections(): Priority-aware section truncation
- build_actor_context_from_memory(): Enhanced actor context with budget control
- build_actor_context(): Backward-compatible wrapper
- build_director_context(): Director context with global arc + STORM + D-04 forward compat

Architecture (D-03): context_builder handles all context assembly + token budget;
memory_manager handles only CRUD + compression.
"""

import logging
import re
from typing import Optional

from google.adk.tools import ToolContext

from .memory_manager import _merge_pending_compression
from .state_manager import _get_state, _set_state

logger = logging.getLogger(__name__)

# ============================================================================
# Constants (from D-02)
# ============================================================================

_CHAR_TOKEN_RATIO = 1.5   # CJK character → tokens
_WORD_TOKEN_RATIO = 1.0   # English word → tokens
_SAFETY_MARGIN = 1.1      # 10% safety margin

_CJK_PATTERN = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff'
    r'\U00020000-\U0002a6df\U0002a700-\U0002b73f'
    r'\u3000-\u303f\uff00-\uffef]'
)

DEFAULT_ACTOR_TOKEN_BUDGET = 8000
DEFAULT_DIRECTOR_TOKEN_BUDGET = 30000

# Section priorities for actor context (higher = less likely to truncate)
_ACTOR_SECTION_PRIORITIES = {
    "working_memory": 1,
    "pending_memory": 1,
    "scene_summaries": 2,
    "arc_summary": 3,
    "critical_memories": 4,
    "emotion": 5,
    "anchor": 6,
}

# Section priorities for director context (higher = less likely to truncate)
_DIRECTOR_SECTION_PRIORITIES = {
    "storm": 3,
    "dynamic_storm": 3,
    "recent_scenes": 4,
    "conflicts": 4,
    "global_arc": 5,
    "facts": 5,
    "actor_emotions": 6,
    "current_status": 10,
}

# Emotion mapping (shared with memory_manager.py)
_EMOTION_CN = {
    "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
    "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
    "anxious": "焦虑", "hopeful": "充满希望",
}


# ============================================================================
# Token Estimation (D-02)
# ============================================================================


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using character-based approximation.

    使用字符数近似估算 token 数：1 中文字 ≈ 1.5 token，1 英文词 ≈ 1 token，
    加 10% 安全裕度。零外部依赖。

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count. Returns 0 for empty or None input.
    """
    if not text:
        return 0

    # Count CJK characters
    cjk_chars = _CJK_PATTERN.findall(text)
    cjk_count = len(cjk_chars)

    # Remove CJK chars, then count remaining words
    remaining = _CJK_PATTERN.sub(' ', text)
    word_count = len(remaining.split())

    # Apply ratios and safety margin
    return int((cjk_count * _CHAR_TOKEN_RATIO + word_count * _WORD_TOKEN_RATIO) * _SAFETY_MARGIN) + 1


# ============================================================================
# Section Truncation
# ============================================================================


def _truncate_sections(sections: list[dict], token_budget: int) -> list[dict]:
    """Truncate sections to fit within token budget using priority-based strategy.

    两阶段裁剪：
    1. 逐条裁剪：对 truncatable=True 且有 items 的 section，从最旧条目开始删除
    2. 整段裁剪：若仍超预算，清空最低优先级的 truncatable section

    Never truncates sections with truncatable=False.

    Args:
        sections: List of section dicts, each with:
            - key: str, section identifier
            - text: str, assembled text for this section
            - priority: int, higher = less likely to truncate
            - truncatable: bool, whether this section can be truncated
            - items: list (optional), individual items for item-level truncation
        token_budget: Maximum token count allowed.

    Returns:
        Filtered list of sections with total tokens within budget.
    """
    if not sections:
        return []

    # Calculate current total
    total_tokens = sum(estimate_tokens(s.get("text", "")) for s in sections)

    if total_tokens <= token_budget:
        return sections

    logger.info(f"Truncation needed: {total_tokens} tokens > {token_budget} budget")

    # Phase 1: Item-level truncation (progressive, lowest priority first)
    truncatable_with_items = [
        s for s in sections
        if s.get("truncatable", False) and s.get("items") is not None
    ]
    truncatable_with_items.sort(key=lambda s: s.get("priority", 0))

    for section in truncatable_with_items:
        while total_tokens > token_budget and section.get("items"):
            removed = section["items"].pop(0)  # Remove oldest item
            # Rebuild section text
            header = section.get("header", "")
            items_text = "\n".join(str(item) for item in section["items"])
            if header and items_text:
                section["text"] = f"{header}\n{items_text}"
            elif items_text:
                section["text"] = items_text
            else:
                section["text"] = ""
            total_tokens = sum(estimate_tokens(s.get("text", "")) for s in sections)
            logger.debug(f"Removed item from '{section['key']}': tokens now {total_tokens}")

    # Phase 2: Section-level truncation (empty lowest priority truncatable sections)
    if total_tokens > token_budget:
        truncatable_sections = [
            s for s in sections if s.get("truncatable", False)
        ]
        truncatable_sections.sort(key=lambda s: s.get("priority", 0))

        for section in truncatable_sections:
            if total_tokens <= token_budget:
                break
            if section.get("text"):
                logger.info(f"Emptying section '{section['key']}' (priority {section.get('priority', 0)})")
                section["text"] = ""
                total_tokens = sum(estimate_tokens(s.get("text", "")) for s in sections)

    # Filter out empty sections
    return [s for s in sections if s.get("text")]


# ============================================================================
# Actor Context Assembly
# ============================================================================


def _assemble_actor_sections(
    actor_name: str, actor_data: dict, tool_context: ToolContext
) -> list[dict]:
    """Assemble actor context sections in priority order.

    按优先级组装演员上下文的各个部分：
    角色锚点(6) → 情绪(5) → 关键记忆(4) → 弧线(3) → 场景摘要(2) → 工作记忆(1) → 待压缩(1)

    Args:
        actor_name: The actor's name.
        actor_data: The actor data dict from state.
        tool_context: Tool context for state access.

    Returns:
        List of section dicts ready for truncation and joining.
    """
    # MUST call _merge_pending_compression at start (Pitfall 4 from RESEARCH.md)
    _merge_pending_compression(actor_name, actor_data, tool_context)

    sections = []

    # Tier 0: Character anchor (priority 6, never truncated)
    role = actor_data.get("role", "")
    personality = actor_data.get("personality", "")
    anchor_text = f"【角色锚点】你是{actor_name}，{role}。{personality}"
    sections.append({
        "key": "anchor",
        "text": anchor_text,
        "priority": _ACTOR_SECTION_PRIORITIES["anchor"],
        "truncatable": False,
    })

    # Current emotion (priority 5, never truncated)
    emotion = actor_data.get("emotions", "neutral")
    emotion_cn = _EMOTION_CN.get(emotion, emotion)
    sections.append({
        "key": "emotion",
        "text": f"【当前情绪】{emotion_cn}",
        "priority": _ACTOR_SECTION_PRIORITIES["emotion"],
        "truncatable": False,
    })

    # Critical memories (priority 4, never truncated — D-07)
    critical = actor_data.get("critical_memories", [])
    if critical:
        lines = [f"- [第{m['scene']}场] {m['entry']} [{m['reason']}]" for m in critical]
        sections.append({
            "key": "critical_memories",
            "text": "【关键记忆（永久保留）】\n" + "\n".join(lines),
            "priority": _ACTOR_SECTION_PRIORITIES["critical_memories"],
            "truncatable": False,
        })

    # Tier 3: Arc summary (priority 3, truncatable, max 500 chars)
    arc = actor_data.get("arc_summary", {})
    if arc.get("narrative"):
        structured = arc.get("structured", {})
        theme = structured.get("theme", "")
        unresolved = "；".join(structured.get("unresolved", []))
        resolved = "；".join(structured.get("resolved", []))
        header = f"主题：{theme}" if theme else ""
        if unresolved:
            header += f" | 未决：{unresolved}"
        if resolved:
            header += f" | 已解决：{resolved}"
        arc_text = arc["narrative"][:500]  # Hard limit per Pitfall 3
        if header:
            arc_full = f"【你的故事弧线】\n{header}\n{arc_text}"
        else:
            arc_full = f"【你的故事弧线】\n{arc_text}"
        sections.append({
            "key": "arc_summary",
            "text": arc_full,
            "priority": _ACTOR_SECTION_PRIORITIES["arc_summary"],
            "truncatable": True,
        })

    # Tier 2: Scene summaries (priority 2, truncatable with items)
    summaries = actor_data.get("scene_summaries", [])
    if summaries:
        recent = summaries[-10:]
        items = [f"- 第{s['scenes_covered']}场：{s['summary']}" for s in recent]
        sections.append({
            "key": "scene_summaries",
            "text": "【近期场景摘要】\n" + "\n".join(items),
            "priority": _ACTOR_SECTION_PRIORITIES["scene_summaries"],
            "truncatable": True,
            "header": "【近期场景摘要】",
            "items": items,
        })

    # Tier 1: Working memory (priority 1, truncatable with items)
    working = actor_data.get("working_memory", [])
    if working:
        recent = working[-5:]
        items = [f"  第{e.get('scene', '?')}场: {e['entry']}" for e in recent]
        sections.append({
            "key": "working_memory",
            "text": "【最近的经历（详细）】\n" + "\n".join(items),
            "priority": _ACTOR_SECTION_PRIORITIES["working_memory"],
            "truncatable": True,
            "header": "【最近的经历（详细）】",
            "items": items,
        })

    # Fallback: pending entries not yet compressed (D-09)
    pending = actor_data.get("_pending_compression", {})
    if pending.get("pending_entries"):
        pending_lines = [
            f"  第{e.get('scene', '?')}场（待压缩）: {e['entry']}"
            for e in pending["pending_entries"]
        ]
        sections.append({
            "key": "pending_memory",
            "text": "【待压缩记忆】\n" + "\n".join(pending_lines),
            "priority": _ACTOR_SECTION_PRIORITIES["pending_memory"],
            "truncatable": True,
        })

    return sections


def build_actor_context_from_memory(
    actor_name: str,
    tool_context: ToolContext,
    token_budget: int = DEFAULT_ACTOR_TOKEN_BUDGET,
) -> str:
    """Build actor context with token budget control.

    使用三步流程组装演员上下文：组装 → 估算 → 裁剪。
    按优先级排序：角色锚点 → 关键记忆 → 弧线 → 场景摘要 → 工作记忆。

    Args:
        actor_name: The actor whose context to build.
        tool_context: Tool context for state access.
        token_budget: Maximum token count (default 8000).

    Returns:
        Formatted context string for the actor prompt.
    """
    state = _get_state(tool_context)
    actor_data = state.get("actors", {}).get(actor_name, {})

    if not actor_data:
        return "暂无记忆"

    # Assemble sections
    sections = _assemble_actor_sections(actor_name, actor_data, tool_context)

    # Truncate if needed
    sections = _truncate_sections(sections, token_budget)

    if not sections:
        return "暂无记忆"

    return "\n\n".join(s["text"] for s in sections)


def build_actor_context(actor_name: str, tool_context: ToolContext) -> str:
    """Backward-compatible wrapper — calls build_actor_context_from_memory with default budget.

    向后兼容接口，供现有代码 `from .memory_manager import build_actor_context` 使用。

    Args:
        actor_name: The actor whose context to build.
        tool_context: Tool context for state access.

    Returns:
        Formatted context string for the actor prompt.
    """
    return build_actor_context_from_memory(actor_name, tool_context)


# ============================================================================
# Director Context Assembly
# ============================================================================


def _build_global_arc_section(state: dict) -> dict:
    """Build the global story arc section from all actors' arc summaries.

    合并所有演员的 arc_summary，包含主题、未决冲突、已解决冲突。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for the global arc.
    """
    actors = state.get("actors", {})
    if not actors:
        return {"key": "global_arc", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["global_arc"], "truncatable": True}

    all_themes = []
    all_unresolved = []
    all_resolved = []
    narratives = []

    for name, data in actors.items():
        arc = data.get("arc_summary", {})
        structured = arc.get("structured", {})
        theme = structured.get("theme", "")
        if theme:
            all_themes.append(theme)
        all_unresolved.extend(structured.get("unresolved", []))
        all_resolved.extend(structured.get("resolved", []))
        narrative = arc.get("narrative", "")
        if narrative:
            narratives.append(f"- {name}：{narrative[:300]}")

    parts = []
    if all_themes:
        parts.append(f"主题：{'；'.join(set(all_themes))}")
    if all_unresolved:
        parts.append(f"未决冲突：{'；'.join(all_unresolved)}")
    if all_resolved:
        parts.append(f"已解决冲突：{'；'.join(all_resolved)}")
    if narratives:
        parts.append("\n".join(narratives))

    text = "【全局故事弧线】\n" + "\n".join(parts) if parts else ""
    return {"key": "global_arc", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["global_arc"], "truncatable": True}


def _build_recent_scenes_section(state: dict) -> dict:
    """Build the recent scenes section.

    展示最近 10 场的标题和关键事件。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for recent scenes.
    """
    scenes = state.get("scenes", [])
    if not scenes:
        return {"key": "recent_scenes", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["recent_scenes"], "truncatable": True, "header": "【近期场景】", "items": []}

    recent = scenes[-10:]
    items = [f"- 第{s.get('scene_number', '?')}场「{s.get('title', '未命名')}」：{s.get('description', '')[:100]}" for s in recent]
    text = "【近期场景】\n" + "\n".join(items)
    return {"key": "recent_scenes", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["recent_scenes"], "truncatable": True, "header": "【近期场景】", "items": items}


def _build_current_status_section(state: dict) -> dict:
    """Build the current status section.

    包含当前场景编号、戏剧状态。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for current status.
    """
    current_scene = state.get("current_scene", 0)
    status = state.get("status", "unknown")
    theme = state.get("theme", "")

    lines = [f"戏剧主题：{theme}" if theme else "",
             f"当前场景：第{current_scene}场",
             f"状态：{status}"]
    text = "【当前状态】\n" + "\n".join(line for line in lines if line)
    return {"key": "current_status", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["current_status"], "truncatable": False}


def _build_actor_emotions_section(state: dict) -> dict:
    """Build the actor emotions snapshot section.

    每个演员一行：名称（角色）：情绪。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for actor emotions.
    """
    actors = state.get("actors", {})
    if not actors:
        return {"key": "actor_emotions", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["actor_emotions"], "truncatable": False}

    lines = []
    for name, data in actors.items():
        role = data.get("role", "")
        emotion = data.get("emotions", "neutral")
        emotion_cn = _EMOTION_CN.get(emotion, emotion)
        lines.append(f"- {name}（{role}）：{emotion_cn}")

    text = "【演员情绪快照】\n" + "\n".join(lines)
    return {"key": "actor_emotions", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["actor_emotions"], "truncatable": False}


def _build_storm_section(state: dict) -> dict:
    """Build the STORM perspectives section.

    展示 STORM 视角列表，含名称和描述。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for STORM perspectives.
    """
    storm = state.get("storm", {})
    perspectives = storm.get("perspectives", [])
    if not perspectives:
        return {"key": "storm", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["storm"], "truncatable": True}

    lines = []
    for p in perspectives:
        name = p.get("name", "")
        desc = p.get("description", "")[:200]
        lines.append(f"- {name}：{desc}")

    text = "【STORM视角】\n" + "\n".join(lines)
    return {"key": "storm", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["storm"], "truncatable": True}


def _build_conflict_section(state: dict) -> dict:
    """Build the active conflicts section (D-04 forward-compatible).

    仅当 state 中存在 conflict_engine 且有 active_conflicts 时才生成内容。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for conflicts.
    """
    conflict_engine = state.get("conflict_engine")
    if not conflict_engine:
        return {"key": "conflicts", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["conflicts"], "truncatable": True}

    active = conflict_engine.get("active_conflicts", [])
    if not active:
        return {"key": "conflicts", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["conflicts"], "truncatable": True}

    lines = [f"- {c}" if isinstance(c, str) else f"- {c.get('description', str(c))}" for c in active]
    text = "【活跃冲突】\n" + "\n".join(lines)
    return {"key": "conflicts", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["conflicts"], "truncatable": True}


def _build_dynamic_storm_section(state: dict) -> dict:
    """Build the dynamic STORM section (D-04 forward-compatible).

    仅当 state 中存在 dynamic_storm 且有 trigger_history 时才生成内容。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for dynamic STORM.
    """
    dynamic_storm = state.get("dynamic_storm")
    if not dynamic_storm:
        return {"key": "dynamic_storm", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["dynamic_storm"], "truncatable": True}

    triggers = dynamic_storm.get("trigger_history", [])
    if not triggers:
        return {"key": "dynamic_storm", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["dynamic_storm"], "truncatable": True}

    lines = [f"- {t}" if isinstance(t, str) else f"- {t.get('event', str(t))}" for t in triggers]
    text = "【最新STORM发现】\n" + "\n".join(lines)
    return {"key": "dynamic_storm", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["dynamic_storm"], "truncatable": True}


def _build_facts_section(state: dict) -> dict:
    """Build the established facts section (D-04 forward-compatible).

    仅当 state 中存在 established_facts 且非空时才生成内容。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for established facts.
    """
    facts = state.get("established_facts")
    if not facts:
        return {"key": "facts", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["facts"], "truncatable": True}

    if isinstance(facts, list):
        lines = [f"- {f}" if isinstance(f, str) else f"- {f.get('fact', str(f))}" for f in facts]
    else:
        lines = [str(facts)]

    text = "【已确立事实】\n" + "\n".join(lines)
    return {"key": "facts", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["facts"], "truncatable": True}


def build_director_context(
    tool_context: ToolContext,
    token_budget: int = DEFAULT_DIRECTOR_TOKEN_BUDGET,
) -> str:
    """Build context for the Director agent with all available state info + D-04 forward compat.

    组装导演上下文：全局弧线 + 当前状态 + 近期场景 + 演员情绪 + STORM视角 +
    D-04 占位（conflict_engine/dynamic_storm/established_facts）。
    通过字段存在性检查实现向前兼容。

    Args:
        tool_context: Tool context for state access.
        token_budget: Maximum token count (default 30000).

    Returns:
        Formatted context string for the director prompt.
    """
    state = _get_state(tool_context)

    # Return early if no drama initialized
    if not state.get("theme"):
        return "暂无戏剧上下文"

    # Assemble all sections
    sections = [
        _build_current_status_section(state),
        _build_actor_emotions_section(state),
        _build_global_arc_section(state),
        _build_facts_section(state),
        _build_recent_scenes_section(state),
        _build_conflict_section(state),
        _build_storm_section(state),
        _build_dynamic_storm_section(state),
    ]

    # Filter out empty sections before truncation
    sections = [s for s in sections if s.get("text")]

    # Truncate if needed
    sections = _truncate_sections(sections, token_budget)

    if not sections:
        return "暂无戏剧上下文"

    return "\n\n".join(s["text"] for s in sections)
