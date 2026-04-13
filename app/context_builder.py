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
from .semantic_retriever import retrieve_relevant_scenes, _extract_auto_tags, _normalize_scene_range
from .conflict_engine import CONFLICT_TEMPLATES
from .arc_tracker import ARC_TYPES, ARC_STAGES, DORMANT_THRESHOLD

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
    "actor_threads": 5,  # Phase 7 (D-32)
    "anchor": 6,
    "actor_dna": 7,  # Phase 10 (D-26) — character consistency constraint
    "semantic_recall": 0,
}

# Section priorities for director context (higher = less likely to truncate)
_DIRECTOR_SECTION_PRIORITIES = {
    "storm": 3,
    "dynamic_storm": 3,
    "recent_scenes": 4,
    "conflicts": 4,
    "global_arc": 5,
    "facts": 5,
    "tension": 5,
    "arc_tracking": 5,  # Phase 7 (D-12)
    "actor_emotions": 6,
    "last_scene_transition": 7,
    "steer": 8,
    "epilogue": 9,
    "auto_advance": 9,
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


def _build_actor_dna_text(
    actor_name: str, actor_data: dict, tool_context: ToolContext
) -> str:
    """Build actor DNA anchor text for character consistency constraint.

    角色一致性约束锚点（D-23~D-27）——包含性格核心、关键记忆、已确立事实。
    三项内容均有则全部展示，缺少某项则省略该行。三项都无则返回空字符串。
    仅包含涉及当前演员的 high importance 事实（T-10-07: 不泄露其他演员事实）。

    Args:
        actor_name: The actor's name.
        actor_data: The actor data dict from state.
        tool_context: Tool context for state access.

    Returns:
        Formatted anchor text string, or empty string if no DNA content.
    """
    parts = []

    # Personality core (D-24)
    personality = actor_data.get("personality", "")
    if personality:
        parts.append(f"性格核心：{personality}")

    # Critical memory — take the most important 1 (D-24)
    critical_memories = actor_data.get("critical_memories", [])
    if critical_memories:
        mem = critical_memories[-1]  # most recent critical memory
        entry = mem.get("entry", "")
        scene = mem.get("scene", "?")
        parts.append(f"关键记忆：[第{scene}场] {entry}")

    # Established facts involving this actor (high importance only, T-10-07)
    state = _get_state(tool_context)
    established_facts = state.get("established_facts", [])
    actor_high_facts = [
        f
        for f in established_facts
        if isinstance(f, dict)
        and f.get("importance") == "high"
        and actor_name in f.get("actors", [])
    ]
    if actor_high_facts:
        fact = actor_high_facts[-1]  # take the most important recent one
        fact_text = fact.get("fact", "")
        scene = fact.get("scene", "?")
        parts.append(f"已确立事实：{fact_text}（第{scene}场）")

    if not parts:
        return ""

    return "【角色锚点】（你必须遵守的约束）\n" + "\n".join(parts)


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

    # Phase 10: Actor DNA anchor — character consistency constraint
    # (D-23~D-27, priority 7)
    dna_lines = _build_actor_dna_text(actor_name, actor_data, tool_context)
    if dna_lines:
        sections.append({
            "key": "actor_dna",
            "text": dna_lines,
            "priority": 7,  # D-26: highest priority, not truncatable
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

    # Phase 7: Actor's active threads + arc_progress (priority 5, D-29/D-31)
    plot_threads = tool_context.state.get("drama", {}).get("plot_threads", [])
    active_threads_for_actor = [
        t for t in plot_threads
        if actor_name in t.get("involved_actors", []) and t.get("status") == "active"
    ]
    arc_progress = actor_data.get("arc_progress", {})
    if active_threads_for_actor or arc_progress.get("arc_type"):
        thread_lines = []
        for t in active_threads_for_actor:
            thread_lines.append(f"- {t['description']}（涉及：{'、'.join(t['involved_actors'])}）")
        arc_lines = []
        arc_type_cn = ARC_TYPES.get(arc_progress.get("arc_type", ""), "")
        arc_stage_cn = ARC_STAGES.get(arc_progress.get("arc_stage", ""), "")
        if arc_type_cn:
            arc_lines.append(f"- [{arc_type_cn}] 你正在经历{arc_stage_cn}阶段（进展：{arc_progress.get('progress', 0)}%）")
        combined_lines = []
        if thread_lines:
            combined_lines.append("【你的剧情线索】")
            combined_lines.extend(thread_lines)
        if arc_lines:
            combined_lines.append("【你的角色弧线】")
            combined_lines.extend(arc_lines)
        sections.append({
            "key": "actor_threads",
            "text": "\n".join(combined_lines),
            "priority": _ACTOR_SECTION_PRIORITIES["actor_threads"],
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

    # Semantic recall section (priority 0, lowest — D-14/D-16)
    auto_tags = _extract_auto_tags(actor_data, tool_context)
    if auto_tags:
        state_ref = _get_state(tool_context)
        current_scene_num = state_ref.get("current_scene", 0)

        # Collect scene ranges already in sections to avoid duplication (Pitfall 2)
        existing_scene_ranges = set()
        for sec in sections:
            if sec.get("key") == "scene_summaries":
                # Parse scene ranges from the section text (e.g., "第3-5场")
                for match in re.finditer(r'第(\d+)(?:-(\d+))?场', sec.get("text", "")):
                    start = int(match.group(1))
                    end = int(match.group(2) or match.group(1))
                    existing_scene_ranges.update(range(start, end + 1))

        recall_results = retrieve_relevant_scenes(
            tags=auto_tags,
            current_scene=current_scene_num,
            tool_context=tool_context,
            actor_name=actor_name,  # D-07: actor limited to own memories
            top_k=5,  # Over-fetch to allow dedup filtering
        )

        # Filter out results whose scenes overlap with existing scene_summaries (Pitfall 2)
        filtered_results = []
        for r in recall_results:
            result_scenes = _normalize_scene_range(r.get("scenes_covered", ""))
            if not result_scenes.intersection(existing_scene_ranges):
                filtered_results.append(r)
            if len(filtered_results) >= 3:  # D-14: actor side top-3 after filtering
                break

        if filtered_results:
            recall_lines = []
            for r in filtered_results:
                recall_lines.append(
                    f"- 第{r['scenes_covered']}场：{r['text'][:100]} "
                    f"[匹配: {', '.join(r.get('matched_tags', []))}]"
                )
            sections.append({
                "key": "semantic_recall",
                "text": "【相关回忆】\n" + "\n".join(recall_lines),
                "priority": _ACTOR_SECTION_PRIORITIES["semantic_recall"],
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

    # Phase 5: Auto-advance status
    auto_remaining = state.get("remaining_auto_scenes", 0)
    if auto_remaining > 0:
        lines.append(f"自动推进: 剩余 {auto_remaining} 场")
        lines.append("⚠️ 每场 write_scene 后递减计数器，归零时回到手动模式")
        lines.append("输出后插入提示: [自动推进中... 剩余 N 场，输入任意内容中断]")

    # Phase 5: User steer direction
    steer = state.get("steer_direction")
    if steer:
        lines.append(f"用户引导: {steer}")
        lines.append("此引导仅本场生效，之后自动清除")

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
    """Build the active conflicts section (D-04 forward-compatible, expanded in Phase 6 D-15).

    展开每条冲突的详细信息（类型、描述、涉及角色）。
    张力状态摘要由 _build_tension_section 负责，此处不重复（Pitfall 7 mitigation）。

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

    lines = []
    for c in active:
        if isinstance(c, str):
            lines.append(f"- {c}")
        else:
            type_cn = CONFLICT_TEMPLATES.get(c.get("type", ""), {}).get("name", c.get("type", ""))
            desc = c.get("description", "")
            actors = "、".join(c.get("involved_actors", []))
            lines.append(f"- [{type_cn}] {desc}（涉及：{actors}）")

    text = "【活跃冲突】\n" + "\n".join(lines)
    return {"key": "conflicts", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["conflicts"], "truncatable": True}


def _build_tension_section(state: dict) -> dict:
    """Build the tension status section for director context (D-14).

    显示张力评分摘要（不展开冲突详情——详情由 _build_conflict_section 负责），
    避免信息重复（Pitfall 7 mitigation）。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for tension status.
    """
    conflict_engine = state.get("conflict_engine")
    if not conflict_engine:
        return {"key": "tension", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["tension"], "truncatable": False}

    score = conflict_engine.get("tension_score", 0)
    is_boring = conflict_engine.get("is_boring", False)
    active_count = len(conflict_engine.get("active_conflicts", []))
    consecutive_low = conflict_engine.get("consecutive_low_tension", 0)

    if is_boring:
        label = "低张力⚠️"
    elif score > 70:
        label = "高张力🔥"
    else:
        label = "正常✅"

    text = f"【张力状态】\n当前张力：{score}/100（{label}） | 活跃冲突：{active_count} 条 | 连续低张力：{consecutive_low} 场"

    return {"key": "tension", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["tension"], "truncatable": False}


def _build_arc_tracking_section(state: dict) -> dict:
    """Build the arc tracking section for director context (D-10/D-11).

    显示所有剧情线索（active/dormant/resolved）和休眠警告。
    dormant 自动检测：current_scene - last_updated_scene > DORMANT_THRESHOLD 的线程标记 ⚠️。
    注意：此函数不修改 state，仅在展示时标记 dormant。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for arc tracking.
    """
    plot_threads = state.get("plot_threads", [])
    if not plot_threads:
        return {"key": "arc_tracking", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["arc_tracking"], "truncatable": True}

    current_scene = state.get("current_scene", 0)

    # Categorize threads
    active_threads = []
    dormant_threads = []
    resolving_threads = []
    resolved_threads = []

    for t in plot_threads:
        status = t.get("status", "active")
        if status == "resolved":
            resolved_threads.append(t)
        elif status == "resolving":
            resolving_threads.append(t)
        elif status == "active":
            gap = current_scene - t.get("last_updated_scene", 0)
            if gap > DORMANT_THRESHOLD:
                dormant_threads.append((t, gap))
            else:
                active_threads.append(t)
        elif status == "dormant":
            gap = current_scene - t.get("last_updated_scene", 0)
            dormant_threads.append((t, gap))

    # Build header
    header = f"活跃线索：{len(active_threads)} 条 | 休眠线索：{len(dormant_threads)} 条 | 已解决：{len(resolved_threads)} 条"

    lines = [header]

    # List dormant threads with ⚠️ warning
    for item in dormant_threads:
        if isinstance(item, tuple):
            t, gap = item
        else:
            t = item
            gap = current_scene - t.get("last_updated_scene", 0)
        lines.append(f"⚠️ 休眠线索：[{t['id']}] \"{t['description']}\" — {gap} 场未更新")

    # List active threads
    for t in active_threads:
        actors_str = "、".join(t.get("involved_actors", []))
        lines.append(f"- [active] {t['id']}: \"{t['description']}\"（涉及：{actors_str}）")

    # List resolving threads
    for t in resolving_threads:
        actors_str = "、".join(t.get("involved_actors", []))
        lines.append(f"- [resolving] {t['id']}: \"{t['description']}\"（涉及：{actors_str}）")

    text = "【弧线追踪】\n" + "\n".join(lines)
    return {"key": "arc_tracking", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["arc_tracking"], "truncatable": True}


def _build_dynamic_storm_section(state: dict) -> dict:
    """Build the dynamic STORM section (D-32/D-33 fully implemented).

    构建 Dynamic STORM 上下文段落：距上次视角发现的场次数、建议间隔、
    最近发现摘要、张力低迷时强烈建议触发。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for dynamic STORM.
    """
    from .dynamic_storm import STORM_INTERVAL

    dynamic_storm = state.get("dynamic_storm")
    if not dynamic_storm:
        return {"key": "dynamic_storm", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["dynamic_storm"], "truncatable": True}

    lines = []
    scenes_since = dynamic_storm.get("scenes_since_last_storm", 0)
    lines.append(f"距上次视角发现：{scenes_since} 场 | 建议间隔：{STORM_INTERVAL} 场")

    # Most recent discovery
    trigger_history = dynamic_storm.get("trigger_history", [])
    if trigger_history:
        last = trigger_history[-1]
        scene_num = last.get("scene", "?")
        focus = last.get("focus_area", "")
        focus_str = f"——聚焦：{focus}" if focus else ""
        lines.append(f"最近发现：[第{scene_num}场]{focus_str} （发现 {last.get('perspectives_found', 0)} 个新视角）")

    # Suggestion when interval exceeded
    if scenes_since >= STORM_INTERVAL:
        lines.append(f"⚡ 已达建议间隔——建议调用 dynamic_storm() 发现新视角")

    # Strong suggestion when tension is low
    conflict_engine = state.get("conflict_engine", {})
    consecutive_low = conflict_engine.get("consecutive_low_tension", 0)
    if consecutive_low >= 3:
        lines.append("🔥 张力持续低迷——强烈建议调用 dynamic_storm() 发现新视角")

    # Phase 9: 🆕 freshness markers for recently discovered perspectives (D-01/D-03)
    discovered = dynamic_storm.get("discovered_perspectives", [])
    current_scene = state.get("current_scene", 0)
    fresh_names = set()  # track names already shown to avoid duplicates

    # Check discovered_perspectives list
    fresh_perspectives = []
    for p in discovered:
        age = current_scene - p.get("discovered_scene", 0)
        if 0 <= age <= 2:
            fresh_perspectives.append((p, age))
            fresh_names.add(p.get("name", ""))

    # Also check storm.perspectives for dynamic_storm sourced ones with freshness
    storm = state.get("storm", {})
    perspectives = storm.get("perspectives", [])
    for p in perspectives:
        if p.get("source") == "dynamic_storm" and p.get("name", "") not in fresh_names:
            age = current_scene - p.get("discovered_scene", 0)
            if 0 <= age <= 2:
                fresh_perspectives.append((p, age))
                fresh_names.add(p.get("name", ""))

    if fresh_perspectives:
        lines.append("")  # blank line separator
        for p, age in fresh_perspectives:
            name = p.get("name", "未命名视角")
            desc = p.get("description", "")
            desc_short = desc[:40] + "..." if len(desc) > 40 else desc
            age_label = f"{age}场前发现" if age > 0 else "本场发现"
            lines.append(f"🆕 {name}（{age_label}）——{desc_short}")
        lines.append("💡 建议逐步融入新视角：第1场旁白暗示 → 第2场角色感知 → 第3场成为驱动力")

    text = "【Dynamic STORM】\n" + "\n".join(lines)
    return {"key": "dynamic_storm", "text": text, "priority": _DIRECTOR_SECTION_PRIORITIES["dynamic_storm"], "truncatable": True}


def _build_facts_section(state: dict) -> dict:
    """Build the established facts section with importance labels and check reminders.

    展示 high/medium importance 事实 + 检查提醒（D-05/D-28）。
    high importance 标记为 [核心]，medium 标记为 [category 中文名]。
    距上次检查 ≥ COHERENCE_CHECK_INTERVAL 场时显示检查提醒。
    兼容旧格式 facts（isinstance 检查 list 中元素是 str 还是 dict）（T-10-06）。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for established facts.
    """
    from .coherence_checker import COHERENCE_CHECK_INTERVAL

    facts = state.get("established_facts", [])
    coherence_checks = state.get("coherence_checks", {})
    current_scene = state.get("current_scene", 0)

    # Category and importance labels (D-05/D-28)
    CATEGORY_LABELS = {
        "event": "事件",
        "identity": "身份",
        "location": "地点",
        "relationship": "关系",
        "rule": "规则",
    }
    IMPORTANCE_LABELS = {"high": "核心", "medium": ""}

    lines = []

    # Filter and format facts (T-10-06: compatible with old format)
    display_facts = []
    for f in facts:
        if isinstance(f, str):
            # Old format: plain string — treat as medium event
            display_facts.append({
                "fact": f,
                "importance": "medium",
                "category": "event",
                "scene": 0,
                "actors": [],
            })
        elif isinstance(f, dict):
            # Only show high/medium importance (D-05/D-28)
            if f.get("importance") in ("high", "medium"):
                display_facts.append(f)

    # Header line
    if display_facts or coherence_checks.get("last_check_scene", 0) > 0:
        total_count = len(facts) if isinstance(facts, list) else 0
        header_parts = [f"事实总数：{total_count} 条"]

        last_check_scene = coherence_checks.get("last_check_scene", 0)
        if last_check_scene > 0:
            last_result = coherence_checks.get("last_result", None)
            if last_result == "clean" or last_result == 0:
                result_str = "无矛盾"
            elif isinstance(last_result, int) and last_result > 0:
                result_str = f"发现{last_result}处矛盾"
            else:
                result_str = "无矛盾"
            header_parts.append(
                f"上次检查：第{last_check_scene}场（{result_str}）"
            )

        lines.append(" | ".join(header_parts))

    # Check reminder (D-17/D-28)
    last_check_scene = coherence_checks.get("last_check_scene", 0)
    scenes_since_check = current_scene - last_check_scene
    if (
        current_scene > 0
        and scenes_since_check >= COHERENCE_CHECK_INTERVAL
        and display_facts
    ):
        lines.append(
            f"💡 距上次检查已 {scenes_since_check} 场，"
            f"建议调用 validate_consistency() 检查一致性"
        )

    # Fact lines
    for f in display_facts:
        importance = f.get("importance", "medium")
        category = f.get("category", "event")
        fact_text = f.get("fact", str(f))
        scene = f.get("scene", 0)
        actors = f.get("actors", [])

        # Label
        importance_label = IMPORTANCE_LABELS.get(importance, "")
        if importance_label:
            label = f"[{importance_label}]"
        else:
            category_label = CATEGORY_LABELS.get(category, category)
            label = f"[{category_label}]"

        # Actors
        actors_str = ""
        if actors:
            actors_str = f"，涉及：{'、'.join(actors)}"

        # Scene
        scene_str = f"（第{scene}场确立{actors_str}）" if scene > 0 else ""

        lines.append(f"{label} {fact_text}{scene_str}")

    text = "【已确立事实】\n" + "\n".join(lines) if lines else ""
    return {
        "key": "facts",
        "text": text,
        "priority": _DIRECTOR_SECTION_PRIORITIES["facts"],
        "truncatable": True,
    }


def _build_steer_section(state: dict) -> dict:
    """Build the user steer guidance section (D-08/D-09).

    当用户使用 /steer 设置方向引导时，此段落注入导演上下文。
    效力仅下一场，之后 next_scene() 自动清除 steer_direction。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for the steer guidance.
    """
    steer = state.get("steer_direction")
    if not steer:
        return {"key": "steer", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["steer"], "truncatable": False}
    return {
        "key": "steer",
        "text": f"【用户引导】\n用户建议方向：{steer}\n请在此方向上发挥创意，但不必拘泥。此引导仅本场生效。",
        "priority": _DIRECTOR_SECTION_PRIORITIES["steer"],
        "truncatable": False,
    }


def _build_epilogue_section(state: dict) -> dict:
    """Build the epilogue mode section (D-24).

    当 drama_status == "ended" 时，标注番外篇模式，
    导演以更轻松、回顾性的风格叙事。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for the epilogue mode.
    """
    if state.get("status") != "ended":
        return {"key": "epilogue", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["epilogue"], "truncatable": False}
    return {
        "key": "epilogue",
        "text": "【番外篇模式】\n本剧已正式结束，当前为番外篇/后日谈。请以更轻松、回顾性的风格叙事。场景编号继续递增，但标注「番外第 X 场」。",
        "priority": _DIRECTOR_SECTION_PRIORITIES["epilogue"],
        "truncatable": False,
    }


def _build_auto_advance_section(state: dict) -> dict:
    """Build the auto-advance status section (D-01/D-03).

    当 remaining_auto_scenes > 0 时，提示导演当前处于自动推进模式，
    以及计数器递减和中断规则。

    Args:
        state: The drama state dict.

    Returns:
        Section dict for the auto-advance status.
    """
    remaining = state.get("remaining_auto_scenes", 0)
    if remaining <= 0:
        return {"key": "auto_advance", "text": "", "priority": _DIRECTOR_SECTION_PRIORITIES["auto_advance"], "truncatable": False}
    return {
        "key": "auto_advance",
        "text": (
            f"【自动推进模式】\n"
            f"当前正在自动推进，剩余 {remaining} 场。"
            f"每场 write_scene 后递减计数器，归零时回到手动模式。"
            f"输出后插入提示：[自动推进中... 剩余 N 场，输入任意内容中断]"
        ),
        "priority": _DIRECTOR_SECTION_PRIORITIES["auto_advance"],
        "truncatable": False,
    }


def _extract_scene_transition(state: dict) -> dict:
    """Extract scene transition info from state (D-08/D-09/D-10).

    三要素：①上一场结局 ②角色情绪状态 ③未决事件/悬念
    纯函数，不调用 LLM。与 next_scene() 返回的衔接信息不重复（D-10）：
    next_scene() 返回即时衔接要点，此处返回更完整的上下文视野。

    Args:
        state: The drama state dict.

    Returns:
        dict with is_first_scene, last_ending, actor_emotions, unresolved fields.
    """
    scenes = state.get("scenes", [])
    actors = state.get("actors", {})
    current_scene = state.get("current_scene", 0)

    if not scenes:
        return {
            "is_first_scene": True,
            "last_ending": "",
            "actor_emotions": {},
            "unresolved": [],
        }

    last_scene = scenes[-1]

    # ① Last scene ending: from description + content tail
    last_ending = last_scene.get("description", "")
    content = last_scene.get("content", "")
    if content and len(content) > 50:
        last_ending += ("..." + content[-150:]) if len(content) > 150 else content
    if len(last_ending) > 300:
        last_ending = last_ending[-300:]

    # ② Actor emotions
    actor_emotions = {}
    for name, data in actors.items():
        emotion = data.get("emotions", "neutral")
        actor_emotions[name] = _EMOTION_CN.get(emotion, emotion)

    # ③ Unresolved events: from critical_memories + arc_summary.unresolved
    unresolved = []
    seen = set()
    for name, data in actors.items():
        for m in data.get("critical_memories", []):
            if m.get("reason") == "未决事件":
                entry = f"{name}: {m['entry'][:80]}"
                if entry not in seen:
                    unresolved.append(entry)
                    seen.add(entry)
        arc = data.get("arc_summary", {}).get("structured", {})
        for u in arc.get("unresolved", []):
            if u not in seen:
                unresolved.append(f"- {u}")
                seen.add(u)

    return {
        "is_first_scene": current_scene == 0,
        "last_ending": last_ending,
        "actor_emotions": actor_emotions,
        "unresolved": unresolved[:5],  # Max 5 items to save tokens
    }


def _build_last_scene_transition_section(state: dict) -> dict:
    """Build the last scene transition section for director context (D-08/D-09).

    与 next_scene() 返回的衔接信息不重复（D-10）：
    next_scene() 返回即时衔接要点（精简），此处返回更完整的上下文视野。
    Priority 7: higher than recent_scenes but lower than current_status.
    Not truncatable: transition info must always be shown.
    """
    scenes = state.get("scenes", [])
    if not scenes:
        return {
            "key": "last_scene_transition",
            "text": "",
            "priority": _DIRECTOR_SECTION_PRIORITIES["last_scene_transition"],
            "truncatable": False,
        }

    transition = _extract_scene_transition(state)

    if transition["is_first_scene"]:
        return {
            "key": "last_scene_transition",
            "text": "",
            "priority": _DIRECTOR_SECTION_PRIORITIES["last_scene_transition"],
            "truncatable": False,
        }

    last_scene = scenes[-1]
    parts = []

    # Last scene ending
    parts.append(f"【上一场衔接】\n上一场「{last_scene.get('title', '未命名')}」：{transition['last_ending']}")

    # Actor emotions
    if transition["actor_emotions"]:
        emotion_lines = []
        for name, emo in transition["actor_emotions"].items():
            role = state.get("actors", {}).get(name, {}).get("role", "")
            emotion_lines.append(f"- {name}（{role}）：{emo}")
        parts.append("当前角色情绪：\n" + "\n".join(emotion_lines))

    # Unresolved events
    if transition["unresolved"]:
        parts.append("未决事件：\n" + "\n".join(f"- {u}" if not u.startswith("-") else u for u in transition["unresolved"]))

    text = "\n".join(parts)
    return {
        "key": "last_scene_transition",
        "text": text,
        "priority": _DIRECTOR_SECTION_PRIORITIES["last_scene_transition"],
        "truncatable": False,
    }


def build_director_context(
    tool_context: ToolContext,
    token_budget: int = DEFAULT_DIRECTOR_TOKEN_BUDGET,
) -> str:
    """Build context for the Director agent with all available state info + D-04 forward compat.

    组装导演上下文：全局弧线 + 当前状态 + 上一场衔接 + 近期场景 + 演员情绪 + STORM视角 +
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
        _build_current_status_section(state),           # priority 10
        _build_epilogue_section(state),                 # priority 9 — Phase 5
        _build_auto_advance_section(state),             # priority 9 — Phase 5
        _build_steer_section(state),                    # priority 8 — Phase 5
        _build_last_scene_transition_section(state),    # priority 7 — LOOP-03
        _build_actor_emotions_section(state),           # priority 6
        _build_global_arc_section(state),               # priority 5
        _build_facts_section(state),                    # priority 5
        _build_tension_section(state),                  # priority 5 — Phase 6
        _build_arc_tracking_section(state),             # priority 5 — Phase 7
        _build_recent_scenes_section(state),            # priority 4
        _build_conflict_section(state),                 # priority 4
        _build_storm_section(state),                    # priority 3
        _build_dynamic_storm_section(state),            # priority 3
    ]

    # Filter out empty sections before truncation
    sections = [s for s in sections if s.get("text")]

    # Truncate if needed
    sections = _truncate_sections(sections, token_budget)

    if not sections:
        return "暂无戏剧上下文"

    return "\n\n".join(s["text"] for s in sections)
