"""Short-term memory module for the 3-tier drama memory architecture.

实现 Mem0/Letta/ReMe 式分层记忆机制的 L2（短期记忆）层：
- 存储近期 N 场的压缩摘要（每场一个摘要）
- 轻量级关键词+标签检索，无需 LLM 实时参与
- 容量超限后触发向 L3（长期记忆/向量库）的异步迁移

Architecture:
    short_term_memories (max 8) → overflow → async compress → vector_memory (Tier 3)
    检索方式: keyword matching + tag weighted scoring (纯 Python, 零外部依赖)

与现有架构的关系:
    - 从 scene_summaries 中提炼出更纯粹的"短期摘要"
    - scene_summaries 保留不变（向后兼容），short_term_memory 是新增的独立字段
    - 场景切换时，工作记忆(work_memory)的溢出会自动进入 short_term_memory
"""

import logging
import math
from typing import Optional

from google.adk.tools import ToolContext

from .state_manager import _get_state, _set_state
from .semantic_retriever import _compute_tag_score

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

SHORT_TERM_MEMORY_LIMIT = 8  # Max short-term memory entries per actor
SHORT_TERM_SCENE_WINDOW = 5  # How many recent scenes to keep in working memory

# RIR (Recency, Importance, Relevance) scoring weights for L3 retrieval
RIR_WEIGHT_RELEVANCE = 0.40
RIR_WEIGHT_RECENCY = 0.35
RIR_WEIGHT_IMPORTANCE = 0.25

# Importance numeric mapping for scoring
_IMPORTANCE_SCORES = {"critical": 1.0, "high": 0.8, "medium": 0.5, "normal": 0.3}

# ============================================================================
# Short-term Memory Entry Management
# ============================================================================


def add_short_term_memory(
    actor_name: str,
    summary: str,
    scene_range: str,
    tags: list[str],
    tool_context: ToolContext,
) -> dict:
    """Add a compressed scene summary to an actor's short-term memory (L2).

    在场景切换或工作记忆压缩时调用，将近期场景的摘要存入短期记忆。

    Args:
        actor_name: The actor's name.
        summary: Compressed scene summary text.
        scene_range: Scene range string, e.g., "3-5".
        tags: List of tags for retrieval.
        tool_context: Tool context for state access.

    Returns:
        dict with status and overflow info.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]
    actor_data.setdefault("short_term_memory", [])

    entry = {
        "summary": summary[:500],  # Hard limit
        "scene_range": scene_range,
        "tags": tags or [],
        "added_scene": state.get("current_scene", 0),
        "access_count": 0,  # Track how many times this entry was recalled
    }

    actor_data["short_term_memory"].append(entry)

    # Check overflow
    overflow = []
    if len(actor_data["short_term_memory"]) > SHORT_TERM_MEMORY_LIMIT:
        overflow = actor_data["short_term_memory"][:-SHORT_TERM_MEMORY_LIMIT]
        actor_data["short_term_memory"] = actor_data["short_term_memory"][-SHORT_TERM_MEMORY_LIMIT:]

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    result = {
        "status": "success",
        "message": f"短期记忆已添加。",
        "short_term_count": len(actor_data["short_term_memory"]),
    }

    if overflow:
        result["overflow_count"] = len(overflow)
        # Best-effort: store overflow to vector memory (L3)
        for old_entry in overflow:
            _migrate_to_long_term(actor_name, old_entry, tool_context)

    return result


def search_short_term_memory(
    actor_name: str,
    query_tags: list[str],
    tool_context: ToolContext,
    top_k: int = 3,
) -> list[dict]:
    """Search an actor's short-term memory (L2) by tag-weighted matching.

    轻量级检索，纯 Python 计算，无需 LLM 或向量数据库。
    按标签匹配分数降序返回。

    Args:
        actor_name: The actor's name.
        query_tags: Tags to search for.
        tool_context: Tool context for state access.
        top_k: Maximum number of results.

    Returns:
        List of short-term memory entries with scores.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return []

    actor_data = actors[actor_name]
    stm = actor_data.get("short_term_memory", [])
    if not stm or not query_tags:
        return []

    results = []
    for entry in stm:
        entry_tags = entry.get("tags", [])
        score = _compute_tag_score(query_tags, entry_tags)
        if score > 0:
            results.append({
                "summary": entry.get("summary", ""),
                "scene_range": entry.get("scene_range", ""),
                "tags": entry_tags,
                "score": score,
                "source": "short_term_memory",
            })

    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def build_short_term_context(
    actor_name: str,
    tool_context: ToolContext,
    max_entries: int = 5,
) -> str:
    """Build injectable short-term memory context text for an actor (L2).

    按时间倒序取最近 N 条短期记忆，格式化为 LLM 上下文文本。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.
        max_entries: Maximum entries to include.

    Returns:
        Formatted context text. Empty string if no short-term memories.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return ""

    actor_data = actors[actor_name]
    stm = actor_data.get("short_term_memory", [])
    if not stm:
        return ""

    # Take most recent entries
    recent = stm[-max_entries:]

    lines = [f"## 「{actor_name}」的短期记忆（近期场景摘要）"]
    lines.append("")

    for entry in recent:
        scene_range = entry.get("scene_range", "")
        summary = entry.get("summary", "")
        tags = entry.get("tags", [])

        tag_str = f" [标签: {', '.join(tags)}]" if tags else ""
        lines.append(f"- 第{scene_range}场：{summary}{tag_str}")

    lines.append("")
    return "\n".join(lines)


def migrate_working_to_short_term(
    actor_name: str,
    tool_context: ToolContext,
) -> dict:
    """Migrate current working memory entries to short-term memory (L2).

    在场景切换时调用：将工作记忆压缩后移入短期记忆。
    如果工作记忆条目不足 SHORT_TERM_SCENE_WINDOW 条，则保留不迁移。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        dict with migration status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]
    working = actor_data.get("working_memory", [])

    if len(working) < 2:
        return {"status": "info", "message": "工作记忆条目过少，无需迁移。"}

    # Build a simple concatenation summary from working memory
    # (In production, this would call an LLM for compression)
    scenes = sorted(set(e.get("scene", 0) for e in working))
    scene_range = f"{scenes[0]}-{scenes[-1]}" if len(scenes) > 1 else str(scenes[0])

    # Simple heuristic summary: concatenate first sentence of each entry
    parts = []
    for e in working:
        entry_text = e.get("entry", "")
        first_sentence = entry_text.split("。")[0] if entry_text else ""
        if first_sentence:
            parts.append(first_sentence + "。")

    summary = " ".join(parts)[:400] if parts else f"第{scene_range}场经历。"

    # Extract simple tags from entries (heuristic)
    tags = []
    seen = set()
    for e in working:
        text = e.get("entry", "")
        # Simple noun extraction heuristic: look for role mentions
        for prefix in ["角色", "地点", "情感", "冲突", "事件"]:
            import re
            pattern = rf"{prefix}[:：](\S+)"
            matches = re.findall(pattern, text)
            for m in matches:
                tag = f"{prefix}:{m}"
                if tag not in seen:
                    tags.append(tag)
                    seen.add(tag)

    # Add to short-term memory
    result = add_short_term_memory(
        actor_name=actor_name,
        summary=summary,
        scene_range=scene_range,
        tags=tags,
        tool_context=tool_context,
    )

    # Clear working memory after migration
    actor_data["working_memory"] = []
    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"已将「{actor_name}」的工作记忆迁移至短期记忆（{len(working)} 条 → 1 条摘要）。",
        "scene_range": scene_range,
        "summary_preview": summary[:80],
        "short_term_result": result,
    }


# ============================================================================
# L3 RIR (Recency, Importance, Relevance) Scoring
# ============================================================================


def compute_rir_score(
    relevance: float,
    entry_scene: int,
    current_scene: int,
    importance: str = "normal",
) -> float:
    """Compute RIR (Recency, Importance, Relevance) composite score.

    综合评分公式：
    score = 0.4 * relevance + 0.35 * recency + 0.25 * importance

    - relevance: 0.0~1.0 (向量语义相似度)
    - recency: 基于场景距离的指数衰减，当前场景=1.0，越旧越低
    - importance: critical=1.0, high=0.8, medium=0.5, normal=0.3

    Args:
        relevance: Vector semantic relevance score (0.0-1.0).
        entry_scene: The scene when the memory was created.
        current_scene: The current scene number.
        importance: Memory importance level.

    Returns:
        Composite score (0.0-1.0).
    """
    # Recency: exponential decay based on scene gap
    scene_gap = max(0, current_scene - entry_scene)
    if scene_gap == 0:
        recency = 1.0
    else:
        # After ~10 scenes, recency drops to ~0.35; after ~20 scenes, ~0.12
        recency = math.exp(-0.1 * scene_gap)

    # Importance
    imp_score = _IMPORTANCE_SCORES.get(importance, 0.3)

    # Composite
    score = (
        RIR_WEIGHT_RELEVANCE * relevance
        + RIR_WEIGHT_RECENCY * recency
        + RIR_WEIGHT_IMPORTANCE * imp_score
    )
    return round(score, 3)


def rank_vector_results_by_rir(
    vector_results: list[dict],
    current_scene: int,
) -> list[dict]:
    """Rank vector memory results by RIR composite score.

    Args:
        vector_results: List of dicts from vector_memory.search_actor_memory().
        current_scene: Current scene number.

    Returns:
        Results sorted by RIR score descending, with 'rir_score' added.
    """
    scored = []
    for r in vector_results:
        meta = r.get("metadata", {})
        scene = meta.get("scene", current_scene)
        importance = meta.get("importance", "normal")
        relevance = r.get("relevance", 0.0)

        rir = compute_rir_score(relevance, scene, current_scene, importance)
        r["rir_score"] = rir
        scored.append(r)

    scored.sort(key=lambda x: x["rir_score"], reverse=True)
    return scored


# ============================================================================
# Private Helpers
# ============================================================================


def _migrate_to_long_term(
    actor_name: str,
    entry: dict,
    tool_context: ToolContext,
) -> None:
    """Best-effort migrate a short-term memory entry to vector long-term memory (L3).

    非阻塞、尽力操作。失败不影响主流程。
    """
    try:
        from .vector_memory import store_actor_memory
        store_actor_memory(
            actor_name=actor_name,
            content=entry.get("summary", ""),
            metadata={
                "scene": entry.get("scene_range", ""),
                "importance": "normal",
                "type": "short_term_overflow",
                "source": "short_term_migration",
            },
            tool_context=tool_context,
        )
    except Exception as e:
        logger.debug(f"Short-term overflow migration failed for {actor_name}: {e}")


def ensure_short_term_memory_fields(actor_data: dict) -> dict:
    """Ensure actor data has short_term_memory field initialized.

    用于向后兼容：旧存档没有 short_term_memory 字段时自动初始化。
    """
    actor_data.setdefault("short_term_memory", [])
    return actor_data
