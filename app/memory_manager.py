"""Memory manager for the 3-tier drama memory architecture.

实现三层记忆管理：工作记忆（Tier 1）→ 场景摘要（Tier 2）→ 全局摘要（Tier 3）。
包含关键记忆保护、自动压缩触发、旧格式迁移功能。

Architecture:
    working_memory (max 5) → compress → scene_summaries (max 10) → compress → arc_summary
    critical_memories: 独立存储，永不压缩
"""

import json
import logging
from typing import Optional

from google.adk.tools import ToolContext

from .state_manager import _get_state, _set_state

logger = logging.getLogger(__name__)

# ============================================================================
# Constants (from D-01, D-02, D-06)
# ============================================================================

WORKING_MEMORY_LIMIT = 5
SCENE_SUMMARY_LIMIT = 10

CRITICAL_REASONS = [
    "首次登场",   # Character first appearance / relationship established
    "重大转折",   # Major plot turning point
    "情感高峰",   # Emotional peak
    "情感低谷",   # Emotional valley
    "未决事件",   # Unresolved event / suspense
    "用户标记",   # User explicitly marked via /mark
    "系统检测",   # System-detected high importance
]

# Keyword patterns for critical event detection (D-06)
_CRITICAL_PATTERNS = {
    "首次登场": ["第一次", "初见", "登场", "首次", "初遇", "相识"],
    "重大转折": ["转折", "突变", "揭露", "发现秘密", "真相大白", "意外发现"],
    "情感高峰": ["狂喜", "激动", "兴奋不已", "欣喜若狂", "热泪盈眶"],
    "情感低谷": ["绝望", "崩溃", "悲痛", "心碎", "万念俱灰"],
    "未决事件": ["悬念", "未知", "谜团", "尚未", "未解", "待续"],
}

# Emotion words that indicate emotional events
_EMOTION_WORDS = {
    "情感高峰": ["狂喜", "激动", "兴奋", "欣喜", "热泪", "欢呼", "兴奋不已"],
    "情感低谷": ["绝望", "崩溃", "悲痛", "心碎", "恐惧", "万念俱灰", "愤怒"],
}

# Maximum entry text length (T-01-01: prevent injection via overly long text)
ENTRY_TEXT_MAX_LENGTH = 500


# ============================================================================
# Public Functions
# ============================================================================


def add_working_memory(
    actor_name: str,
    entry: str,
    importance: str,
    critical_reason: Optional[str],
    tool_context: ToolContext,
) -> dict:
    """Add a memory entry to an actor's working memory.

    添加工作记忆。如果 importance 为 "critical"，同时写入 critical_memories。
    添加后调用 check_and_compress() 检查是否需要压缩。

    Args:
        actor_name: The actor's name.
        entry: The memory text.
        importance: "normal" or "critical".
        critical_reason: Required when importance="critical", must be one of CRITICAL_REASONS.
        tool_context: Tool context for state access.

    Returns:
        dict with status and compression info.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    if importance not in ("normal", "critical"):
        return {"status": "error", "message": f"importance 必须为 'normal' 或 'critical'，收到: {importance}"}

    if importance == "critical":
        if not critical_reason or critical_reason not in CRITICAL_REASONS:
            return {
                "status": "error",
                "message": f"关键记忆必须提供有效的 critical_reason（{', '.join(CRITICAL_REASONS)}），收到: {critical_reason}",
            }

    # T-01-01: Truncate entry text to prevent injection
    entry = entry[:ENTRY_TEXT_MAX_LENGTH]

    actor_data = actors[actor_name]
    current_scene = state.get("current_scene", 0)

    # Ensure new fields exist (for actors created before migration)
    actor_data.setdefault("working_memory", [])
    actor_data.setdefault("critical_memories", [])
    actor_data.setdefault("scene_summaries", [])
    actor_data.setdefault("arc_summary", {
        "structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []},
        "narrative": "",
    })

    # Add to working_memory (D-12 structure)
    memory_entry = {
        "entry": entry,
        "importance": importance,
        "scene": current_scene,
    }
    actor_data["working_memory"].append(memory_entry)

    # If critical, also add to critical_memories (D-07)
    if importance == "critical":
        critical_entry = {
            "entry": entry,
            "reason": critical_reason,
            "scene": current_scene,
        }
        actor_data["critical_memories"].append(critical_entry)

    # Save state
    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    # Check if compression is needed
    compression_result = check_and_compress(actor_name, tool_context)

    return {
        "status": "success",
        "message": f"记忆已添加到「{actor_name}」的工作记忆。",
        "importance": importance,
        "working_memory_count": len(actor_data["working_memory"]),
        "compression": compression_result,
    }


def check_and_compress(actor_name: str, tool_context: ToolContext) -> dict:
    """Check memory tier sizes and trigger compression if limits exceeded.

    检查各层记忆容量，超过阈值时触发压缩。
    - working_memory > WORKING_MEMORY_LIMIT (5): 触发 compress_working_to_scene()
    - scene_summaries > SCENE_SUMMARY_LIMIT (10): 触发 compress_scene_to_arc()

    在 Plan 01 中，压缩是同步的 stub 实现（不调用 LLM）。
    Plan 03 将替换为真正的异步 LLM 压缩。

    Args:
        actor_name: The actor whose memory to check.
        tool_context: Tool context for state access.

    Returns:
        dict with compression status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]
    compressed = []

    # Check working_memory overflow (D-04)
    working = actor_data.get("working_memory", [])
    if len(working) > WORKING_MEMORY_LIMIT:
        overflow = working[:-WORKING_MEMORY_LIMIT]
        actor_data["working_memory"] = working[-WORKING_MEMORY_LIMIT:]

        # Stub compression: create a simple scene summary from overflow entries
        # (Plan 03 will replace with LLM-based async compression)
        scenes = sorted(set(e.get("scene", 0) for e in overflow))
        scenes_covered = f"{scenes[0]}-{scenes[-1]}" if len(scenes) > 1 else str(scenes[0])
        summary_text = "；".join(e["entry"][:50] for e in overflow)
        key_events = [e["entry"].split("。")[0] + "。" for e in overflow if "。" in e["entry"]]

        scene_summary = {
            "summary": summary_text,
            "scenes_covered": scenes_covered,
            "key_events": key_events,
        }
        actor_data["scene_summaries"].append(scene_summary)
        compressed.append(f"working→scene: {len(overflow)} 条")

    # Check scene_summaries overflow (D-05)
    summaries = actor_data.get("scene_summaries", [])
    if len(summaries) > SCENE_SUMMARY_LIMIT:
        overflow_summaries = summaries[:-SCENE_SUMMARY_LIMIT]
        actor_data["scene_summaries"] = summaries[-SCENE_SUMMARY_LIMIT:]

        # Stub: merge overflow summaries into arc_summary
        # (Plan 03 will replace with LLM-based rewrite)
        existing_arc = actor_data.get("arc_summary", {})
        existing_narrative = existing_arc.get("narrative", "")

        new_events = "；".join(s.get("summary", "")[:80] for s in overflow_summaries)
        updated_narrative = f"{existing_narrative}。近期：{new_events}" if existing_narrative else f"近期：{new_events}"

        actor_data["arc_summary"] = {
            "structured": existing_arc.get("structured", {
                "theme": "", "key_characters": [], "unresolved": [], "resolved": [],
            }),
            "narrative": updated_narrative[:500],  # Hard limit per Pitfall 3
        }
        compressed.append(f"scene→arc: {len(overflow_summaries)} 条")

    # Save state if anything changed
    if compressed:
        actors[actor_name] = actor_data
        state["actors"] = actors
        _set_state(state, tool_context)

    return {
        "status": "success",
        "compressed": compressed,
        "message": f"压缩检查完成: {', '.join(compressed)}" if compressed else "无需压缩",
    }


def build_actor_context(actor_name: str, tool_context: ToolContext) -> str:
    """Build the complete memory context string for an actor_speak() call.

    替换 tools.py:201-213 中的扁平 memory_str 构建。
    按优先级组装：角色锚点 → 关键记忆 → 全局摘要 → 场景摘要 → 工作记忆。

    Args:
        actor_name: The actor whose context to build.
        tool_context: Tool context for state access.

    Returns:
        Formatted context string for the actor prompt.
    """
    state = _get_state(tool_context)
    actor_data = state.get("actors", {}).get(actor_name, {})

    if not actor_data:
        return "暂无记忆"

    parts = []

    # Tier 0: Character anchor (prevents backstory forgetting — PITFALLS #3)
    role = actor_data.get("role", "")
    personality = actor_data.get("personality", "")
    parts.append(f"【角色锚点】你是{actor_name}，{role}。{personality}")

    # Current emotion
    emotion = actor_data.get("emotions", "neutral")
    emotion_cn = {
        "neutral": "平静", "angry": "愤怒", "sad": "悲伤", "happy": "喜悦",
        "fearful": "恐惧", "confused": "困惑", "determined": "决绝",
        "anxious": "焦虑", "hopeful": "充满希望",
    }.get(emotion, emotion)
    parts.append(f"【当前情绪】{emotion_cn}")

    # Critical memories (D-07: always included, never compressed)
    critical = actor_data.get("critical_memories", [])
    if critical:
        lines = [f"- [第{m['scene']}场] {m['entry']} [{m['reason']}]" for m in critical]
        parts.append("【关键记忆（永久保留）】\n" + "\n".join(lines))

    # Tier 3: Arc summary (always included — small)
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
        arc_text = arc["narrative"]
        if header:
            parts.append(f"【你的故事弧线】\n{header}\n{arc_text}")
        else:
            parts.append(f"【你的故事弧线】\n{arc_text}")

    # Tier 2: Scene summaries
    summaries = actor_data.get("scene_summaries", [])
    if summaries:
        lines = [f"- 第{s['scenes_covered']}场：{s['summary']}" for s in summaries[-10:]]
        parts.append("【近期场景摘要】\n" + "\n".join(lines))

    # Tier 1: Working memory (full detail, last 5)
    working = actor_data.get("working_memory", [])
    if working:
        lines = [f"  第{e.get('scene', '?')}场: {e['entry']}" for e in working[-5:]]
        parts.append("【最近的经历（详细）】\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else "暂无记忆"


def mark_critical_memory(
    actor_name: str,
    memory_index: int,
    reason: str,
    tool_context: ToolContext,
) -> dict:
    """Mark an existing working memory entry as critical.

    将工作记忆中的指定条目提升为关键记忆，从 working_memory 移至 critical_memories。
    用于 /mark 命令。

    Args:
        actor_name: The actor's name.
        memory_index: 0-based index in working_memory list.
        reason: Why this memory is critical (must be from CRITICAL_REASONS).
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    if reason not in CRITICAL_REASONS:
        return {"status": "error", "message": f"无效的 reason: {reason}，必须是: {', '.join(CRITICAL_REASONS)}"}

    actor_data = actors[actor_name]
    working = actor_data.get("working_memory", [])

    if memory_index < 0 or memory_index >= len(working):
        return {"status": "error", "message": f"索引 {memory_index} 超出范围（0-{len(working)-1}）。"}

    entry = working.pop(memory_index)

    # Add to critical_memories
    critical_entry = {
        "entry": entry["entry"],
        "reason": reason,
        "scene": entry.get("scene", 0),
    }
    actor_data["critical_memories"].append(critical_entry)
    actor_data["working_memory"] = working

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"已将「{actor_name}」的第 {memory_index} 条工作记忆标记为关键记忆（{reason}）。",
        "critical_entry": critical_entry,
    }


def migrate_legacy_memory(actor_name: str, tool_context: ToolContext) -> dict:
    """Migrate old flat actor.memory to new 3-tier structure.

    检测旧格式 actor.memory（扁平列表），将全部条目倒入 working_memory。
    旧 memory 字段保留（D-13）。

    Args:
        actor_name: The actor whose memory to migrate.
        tool_context: Tool context for state access.

    Returns:
        dict with migration status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]

    # Already migrated?
    if "working_memory" in actor_data:
        return {"status": "info", "message": f"演员「{actor_name}」已是新格式，无需迁移。"}

    old_memories = actor_data.get("memory", [])

    # Convert old format to new working_memory format
    new_working = []
    for m in old_memories:
        entry_text = m.get("entry", "")
        if not entry_text:
            continue  # Skip corrupted entries (Pitfall 4)
        new_working.append({
            "entry": entry_text,
            "importance": "normal",
            "scene": 0,  # Unknown scene number
        })

    # Apply new fields
    actor_data["working_memory"] = new_working
    actor_data["scene_summaries"] = []
    actor_data["arc_summary"] = {
        "structured": {
            "theme": "",
            "key_characters": [],
            "unresolved": [],
            "resolved": [],
        },
        "narrative": "",
    }
    actor_data["critical_memories"] = []
    # Keep old "memory" field (D-13: read-only preservation)

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"演员「{actor_name}」记忆已迁移: {len(old_memories)} 条旧记忆 → working_memory",
        "migrated_count": len(old_memories),
    }


def detect_importance(entry_text: str, situation: str = "") -> tuple[bool, Optional[str]]:
    """Detect if a memory entry matches any critical event pattern (D-06).

    使用关键词模式检测 6 类关键事件。用于自动识别重要记忆。

    Args:
        entry_text: The memory entry text to analyze.
        situation: The situation context (may contain additional clues).

    Returns:
        Tuple of (is_critical, reason_or_none).
        If critical, reason is one of CRITICAL_REASONS.
    """
    combined_text = f"{entry_text} {situation}"

    # Check each critical pattern category
    for reason, keywords in _CRITICAL_PATTERNS.items():
        for keyword in keywords:
            if keyword in combined_text:
                return (True, reason)

    # Check emotion word patterns
    for reason, emotion_words in _EMOTION_WORDS.items():
        for word in emotion_words:
            if word in combined_text:
                return (True, reason)

    return (False, None)


def ensure_actor_memory_fields(actor_data: dict) -> dict:
    """Ensure actor data dict has all new memory fields.

    Utility function to add missing fields to actor dicts that were
    created before the memory architecture was implemented.

    Args:
        actor_data: The actor data dict to check/update.

    Returns:
        The updated actor data dict (mutated in place and returned).
    """
    actor_data.setdefault("working_memory", [])
    actor_data.setdefault("scene_summaries", [])
    actor_data.setdefault("arc_summary", {
        "structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []},
        "narrative": "",
    })
    actor_data.setdefault("critical_memories", [])
    return actor_data
