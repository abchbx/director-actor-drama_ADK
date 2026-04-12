"""Memory manager for the 3-tier drama memory architecture.

实现三层记忆管理：工作记忆（Tier 1）→ 场景摘要（Tier 2）→ 全局摘要（Tier 3）。
包含关键记忆保护、异步LLM压缩、旧格式迁移功能。

Architecture:
    working_memory (max 5) → async LLM compress → scene_summaries (max 10) → async LLM compress → arc_summary
    critical_memories: 独立存储，永不压缩
"""

import asyncio
import json
import logging
import os
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
# LLM Compression Prompt Builders (from RESEARCH.md §LLM Compression Design)
# ============================================================================


def _build_compression_prompt_working(entries: list[dict], actor_name: str) -> str:
    """Build the LLM prompt for working→scene compression."""
    entries_text = "\n".join(
        f"- [第{e.get('scene', '?')}场] {e['entry']}" for e in entries
    )
    return f"""你是一位戏剧记忆压缩助手。请将以下演员「{actor_name}」的工作记忆压缩为一段场景摘要。

## 输入（{len(entries)} 条工作记忆）
{entries_text}

## 压缩规则
1. 保留所有关键事件：角色首次登场、重大转折、情感变化、未决事件
2. 次要事件仅保留一句概述
3. 保持时间顺序
4. 使用第三人称叙述
5. 摘要长度控制在 150-200 字
6. 特别标注涉及{actor_name}的情感变化和决策

## 输出格式（严格 JSON）
{{{{
  "summary": "场景摘要文本...",
  "tags": ["角色:朱棣", "地点:皇宫", "情感:愤怒", "冲突:权力争夺", "秘密发现"]
}}}}

### 标签生成规则
- 从摘要中提取 3-8 个标签
- 标签格式：前缀:值，前缀包括：角色、地点、情感、冲突、事件
- 角色名必标（谁在场），冲突/事件类型必标（发生了什么）
- 情感和地点视情况标注
- 无前缀标签用于难以归类的重要关键词"""


def _build_compression_prompt_arc(
    summaries: list[dict],
    existing_arc: dict,
    actor_name: str,
) -> str:
    """Build the LLM prompt for scene→arc compression."""
    summaries_text = "\n\n".join(
        f"### 场景 {s.get('scenes_covered', '?')}\n{s['summary']}" for s in summaries
    )
    existing_narrative = existing_arc.get("narrative", "暂无")
    existing_structured = existing_arc.get("structured", {})

    return f"""你是一位戏剧故事弧线压缩助手。请将以下场景摘要融入演员「{actor_name}」的全局故事弧线摘要。

## 新增场景摘要
{summaries_text}

## 现有全局摘要
### 结构化信息
- 主题: {existing_structured.get('theme', '未确定')}
- 关键角色: {', '.join(existing_structured.get('key_characters', []))}
- 未决冲突: {'; '.join(existing_structured.get('unresolved', []))}
- 已解决冲突: {'; '.join(existing_structured.get('resolved', []))}

### 叙事概述
{existing_narrative}

## 压缩规则
1. 将新增摘要融入现有全局摘要，重写整个概述
2. 更新结构化字段：添加新角色、更新冲突状态（未决→已解决）
3. 叙事概述控制在 200-300 字
4. 保持故事连贯性，不要遗漏重要转折
5. 如有新主题浮现，更新主题字段

## 输出格式（严格 JSON）
{{{{
  "structured": {{{{
    "theme": "故事核心主题",
    "key_characters": ["角色1", "角色2"],
    "unresolved": ["未决冲突1", "未决冲突2"],
    "resolved": ["已解决冲突1"]
  }}}},
  "narrative": "完整的故事弧线概述..."
}}}}"""


# ============================================================================
# Async LLM Compression Functions
# ============================================================================


async def _call_llm(prompt: str) -> str:
    """Call LLM for compression. Try LiteLlm first, fallback to httpx.

    LiteLlm 是 ADK 内置的 LLM 封装，支持 OpenAI 兼容 API。
    如果 LiteLlm 不可用（A2 假设），回退到 httpx 直接调用。
    """
    model_name = os.environ.get("MODEL_NAME", "openai/claude-sonnet-4-6")

    # Try LiteLlm first
    try:
        from google.adk.models.lite_llm import LiteLlm
        model = LiteLlm(model=model_name)
        response = await model.generate_content_async([prompt])
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
    except Exception as e:
        logger.info(f"LiteLlm call failed ({e}), falling back to httpx")

    # Fallback: httpx direct API call
    try:
        import httpx
        api_base = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        api_key = os.environ.get("OPENAI_API_KEY", os.environ.get("LLM_API_KEY", ""))

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=60)) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name.replace("openai/", ""),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"httpx fallback also failed: {e}")
        # Return a basic concatenation as last resort
        return "压缩失败：请参考原始记忆条目。"


async def compress_working_to_scene(
    actor_name: str,
    entries: list[dict],
    tool_context: ToolContext,
) -> dict:
    """Async LLM compression of working memory → scene summary.

    使用 LLM 将工作记忆条目压缩为场景摘要。
    先尝试 LiteLlm，失败时回退到 httpx 直接 API 调用。
    标签提取失败不阻塞压缩——tags 默认为空列表。

    Args:
        actor_name: The actor whose memory to compress.
        entries: Working memory entries to compress.
        tool_context: Tool context for state access.

    Returns:
        dict with summary, scenes_covered, key_events, tags.
    """
    prompt = _build_compression_prompt_working(entries, actor_name)

    # Try LiteLlm first (A2 from RESEARCH.md)
    response_text = await _call_llm(prompt)

    # Parse JSON response for summary + tags
    summary_text = response_text
    tags = []

    try:
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(json_text)
        if isinstance(parsed, dict):
            summary_text = parsed.get("summary", response_text)
            tags = parsed.get("tags", [])
            if not isinstance(tags, list):
                tags = []
    except (json.JSONDecodeError, KeyError, IndexError):
        # Fallback: use raw text as summary, try regex tag extraction
        logger.warning(f"Failed to parse working→scene JSON for {actor_name}, using raw text")
        from .semantic_retriever import _parse_tags_from_llm_output
        tags = _parse_tags_from_llm_output(response_text)

    # Determine scenes covered
    scenes = sorted(set(e.get("scene", 0) for e in entries))
    scenes_covered = f"{scenes[0]}-{scenes[-1]}" if len(scenes) > 1 else str(scenes[0])

    # Extract key events
    key_events = []
    for e in entries:
        first_sentence = e["entry"].split("。")[0]
        if first_sentence:
            key_events.append(first_sentence + "。" if "。" not in first_sentence else first_sentence)

    return {
        "summary": summary_text,
        "scenes_covered": scenes_covered,
        "key_events": key_events,
        "tags": tags,
    }


async def compress_scene_to_arc(
    actor_name: str,
    summaries: list[dict],
    tool_context: ToolContext,
) -> dict:
    """Async LLM compression of scene summaries → arc summary.

    使用 LLM 将场景摘要压缩入全局摘要。
    Per D-10: 每次重写整个全局摘要。

    Args:
        actor_name: The actor whose memory to compress.
        summaries: Scene summaries to compress.
        tool_context: Tool context for state access.

    Returns:
        dict with structured and narrative fields (the new arc_summary).
    """
    state = _get_state(tool_context)
    actor_data = state.get("actors", {}).get(actor_name, {})
    existing_arc = actor_data.get("arc_summary", {})

    prompt = _build_compression_prompt_arc(summaries, existing_arc, actor_name)
    response_text = await _call_llm(prompt)

    # Parse JSON response (A3 from RESEARCH.md: may need fault-tolerant parsing)
    try:
        # Try to extract JSON from response (LLM may add markdown fences)
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        result = json.loads(json_text)
        # Validate structure
        structured = result.get("structured", existing_arc.get("structured", {}))
        narrative = result.get("narrative", response_text[:500])

        return {
            "structured": {
                "theme": structured.get("theme", ""),
                "key_characters": structured.get("key_characters", []),
                "unresolved": structured.get("unresolved", []),
                "resolved": structured.get("resolved", []),
            },
            "narrative": narrative[:500],  # Hard limit per Pitfall 3
        }
    except (json.JSONDecodeError, KeyError, IndexError):
        # Fallback: use raw text as narrative
        logger.warning(f"Failed to parse arc compression JSON for {actor_name}, using raw text")
        return {
            "structured": existing_arc.get("structured", {
                "theme": "", "key_characters": [], "unresolved": [], "resolved": [],
            }),
            "narrative": response_text[:500],
        }


# ============================================================================
# Serialization Helpers for _pending_compression
# ============================================================================


def _serialize_pending_for_save(actor_data: dict) -> dict:
    """Strip non-serializable objects from _pending_compression before saving.

    asyncio.Task objects cannot be JSON serialized (A3 from RESEARCH.md).
    Only preserve pending_entries (raw data) for re-compression on load.
    """
    pending = actor_data.get("_pending_compression", {})
    if not pending:
        return actor_data

    # Keep only serializable fields
    actor_data["_pending_compression"] = {
        "working_to_scene": None,   # Task reference stripped
        "scene_to_arc": None,       # Task reference stripped
        "pending_entries": pending.get("pending_entries", []),
        "result": None,             # Result already merged or cleared
    }
    return actor_data


def _deserialize_pending_on_load(actor_data: dict) -> dict:
    """Restore _pending_compression structure after loading from disk.

    If pending_entries exist from a previous session, they need to be
    re-compressed. The actual re-compression will happen on the next
    check_and_compress() or build_actor_context() call.
    """
    pending = actor_data.get("_pending_compression", {})
    if not pending:
        return actor_data

    # Ensure structure is complete
    actor_data["_pending_compression"] = {
        "working_to_scene": None,
        "scene_to_arc": None,
        "pending_entries": pending.get("pending_entries", []),
        "result": None,
    }
    return actor_data


def save_state_clean(tool_context: ToolContext) -> None:
    """Clean _pending_compression in all actors before state save.

    Call this before _set_state() to strip non-serializable objects.
    This is a no-op if no pending compression exists.

    NOTE: Mutates actor_data dicts in-place within the state dict.
    Call this BEFORE _set_state() — the mutations are visible through
    the state dict reference.
    """
    state = _get_state(tool_context)
    for actor_name, actor_data in state.get("actors", {}).items():
        _serialize_pending_for_save(actor_data)


# ============================================================================
# Pending Compression Merge
# ============================================================================


def _merge_pending_compression(actor_name: str, actor_data: dict, tool_context) -> bool:
    """Merge any completed compression results into the actor's state.

    在 build_actor_context() 开头调用，确保使用最新数据。
    返回 True 如果有合并发生（需要重新保存 state）。

    Args:
        actor_name: The actor's name.
        actor_data: The actor data dict (mutated in place if merged).
        tool_context: Tool context for state access.

    Returns:
        True if any merge happened, False otherwise.
    """
    pending = actor_data.get("_pending_compression", {})
    if not pending:
        return False

    merged = False

    # Check working→scene result
    task_w2s = pending.get("working_to_scene")
    if task_w2s and hasattr(task_w2s, 'done') and task_w2s.done():
        try:
            result = task_w2s.result()
            actor_data["scene_summaries"].append(result)
            # Clear compressed entries from pending
            pending["pending_entries"] = []
            pending["working_to_scene"] = None
            merged = True
        except Exception as e:
            # Compression failed — keep entries in pending as fallback
            logger.warning(f"Working→scene compression failed for {actor_name}: {e}")
            pending["working_to_scene"] = None

    # Check scene→arc result
    task_s2a = pending.get("scene_to_arc")
    if task_s2a and hasattr(task_s2a, 'done') and task_s2a.done():
        try:
            result = task_s2a.result()
            actor_data["arc_summary"] = result
            pending["scene_to_arc"] = None
            merged = True
        except Exception as e:
            logger.warning(f"Scene→arc compression failed for {actor_name}: {e}")
            pending["scene_to_arc"] = None

    if merged:
        state = _get_state(tool_context)
        state["actors"][actor_name] = actor_data
        _set_state(state, tool_context)

    return merged


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
    """Check memory tier sizes and trigger async compression if limits exceeded.

    检查各层记忆容量，超过阈值时触发异步 LLM 压缩。
    压缩结果通过 _pending_compression 延迟合并，避免竞态条件。

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

    # Ensure _pending_compression field exists
    actor_data.setdefault("_pending_compression", {
        "working_to_scene": None,
        "scene_to_arc": None,
        "pending_entries": [],
        "result": None,
    })

    # Check working_memory overflow (D-04)
    working = actor_data.get("working_memory", [])
    if len(working) > WORKING_MEMORY_LIMIT:
        overflow = working[:-WORKING_MEMORY_LIMIT]
        actor_data["working_memory"] = working[-WORKING_MEMORY_LIMIT:]

        # Store overflow in pending for async compression
        pending = actor_data["_pending_compression"]
        pending["pending_entries"] = pending.get("pending_entries", []) + overflow

        # Launch async compression task
        try:
            loop = asyncio.get_running_loop()
            # There's a running loop: create a task
            task = loop.create_task(
                compress_working_to_scene(actor_name, overflow, tool_context)
            )
            pending["working_to_scene"] = task
        except RuntimeError:
            # No running loop: run synchronously
            try:
                result = asyncio.run(
                    compress_working_to_scene(actor_name, overflow, tool_context)
                )
                actor_data["scene_summaries"].append(result)
                overflow_ids = set(id(e) for e in overflow)
                pending["pending_entries"] = [
                    e for e in pending.get("pending_entries", [])
                    if id(e) not in overflow_ids
                ]
            except RuntimeError:
                # No event loop at all: keep entries in pending, compress later
                logger.warning(f"Cannot compress memory for {actor_name}: no event loop available. Entries retained in pending.")
                pass

        compressed.append(f"working→scene: {len(overflow)} 条")

    # Check scene_summaries overflow (D-05)
    summaries = actor_data.get("scene_summaries", [])
    if len(summaries) > SCENE_SUMMARY_LIMIT:
        overflow_summaries = summaries[:-SCENE_SUMMARY_LIMIT]
        actor_data["scene_summaries"] = summaries[-SCENE_SUMMARY_LIMIT:]

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                compress_scene_to_arc(actor_name, overflow_summaries, tool_context)
            )
            actor_data["_pending_compression"]["scene_to_arc"] = task
        except RuntimeError:
            # No running loop: run synchronously
            try:
                result = asyncio.run(
                    compress_scene_to_arc(actor_name, overflow_summaries, tool_context)
                )
                actor_data["arc_summary"] = result
            except RuntimeError:
                logger.warning(f"Cannot compress scene→arc for {actor_name}: no event loop available. Entries retained in pending.")
                pass

        compressed.append(f"scene→arc: {len(overflow_summaries)} 条")

    # Save state if anything changed
    if compressed:
        # Strip asyncio.Task objects (not JSON-serializable) before saving
        _serialize_pending_for_save(actor_data)
        actors[actor_name] = actor_data
        state["actors"] = actors
        _set_state(state, tool_context)

    return {
        "status": "success",
        "compressed": compressed,
        "message": f"压缩检查完成: {', '.join(compressed)}" if compressed else "无需压缩",
    }


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

    if not working or memory_index < 0 or memory_index >= len(working):
        return {"status": "error", "message": f"索引 {memory_index} 超出范围。工作记忆为空或索引无效。"}

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

    WARNING: Uses substring matching which can produce false positives.
    For example, "兴奋" in 情感高峰 patterns matches normal text like "兴奋地跑来".
    Critical detections should be confirmed by the director before marking.

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


# Phase 2: Re-export for backward compatibility
# build_actor_context has been migrated to context_builder.py
# Using lazy import to avoid circular import (context_builder imports _merge_pending_compression from us)
def __getattr__(name):
    if name == "build_actor_context":
        from .context_builder import build_actor_context
        return build_actor_context
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
