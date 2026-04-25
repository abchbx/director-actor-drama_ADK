"""Memory manager for the 4-tier drama memory architecture.

实现四层记忆管理：工作记忆（Tier 1）→ 场景摘要（Tier 2）→ 全局摘要（Tier 3）→ 向量长期记忆（Tier 4）。
包含关键记忆保护、异步LLM压缩、向量语义检索、旧格式迁移功能。

Architecture:
    working_memory (max 5) → async LLM compress → scene_summaries (max 10) → async LLM compress → arc_summary
    critical_memories: 独立存储，永不压缩
    vector_memory (Tier 4): ChromaDB 向量存储，语义检索，与上述三层并行工作
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from google.adk.tools import ToolContext

from .state_manager import _get_state, _set_state

logger = logging.getLogger(__name__)

# ============================================================================
# Coreference Resolution - 代词展开（避免跨角色对话中的指代歧义）
# ============================================================================

# Chinese pronouns that commonly cause ambiguity in multi-actor dialogue
_AMBIGUOUS_PRONOUNS = {"他", "她", "它", "他们", "她们", "它们", "这", "那", "这里", "那里", "这时", "那时"}

# Fallback: static per-character coreferences for backward compat
# (used only when SceneContext is empty / unavailable)
_FALLBACK_COREFERENCES = {
    "苏念瑶": {
        "他": "她的退婚未婚夫",
    },
}

# Regex pattern to match Chinese pronouns in text
_PRONOUN_PATTERN = re.compile(r"(他|她|它|他们|她们|它们|这|那|这里|那里)")


def resolve_coreferences(text: str, speaker_name: str = "",
                         listener_name: str = "", tool_context=None) -> str:
    """Expand ambiguous pronouns in dialogue text using SceneContext.

    Resolution strategy (in priority order):
    1. SceneContext from state — dynamic, per-speaker pronoun mappings
    2. Fallback static _FALLBACK_COREFERENCES — backward compat
    3. If neither available, return text unchanged

    Args:
        text: The dialogue text to process.
        speaker_name: Name of the character who spoke (provides context).
        listener_name: Name of the character receiving the message (optional).
        tool_context: Tool context for accessing SceneContext state.

    Returns:
        Text with ambiguous pronouns expanded to explicit references.
    """
    if not text:
        return text

    # Try SceneContext-based resolution first
    if tool_context is not None:
        from .state_manager import get_scene_context
        scene_ctx = get_scene_context(tool_context)

        # Only resolve if we have some mappings available
        if scene_ctx.pronoun_map or scene_ctx.speaker_refs:
            return _resolve_with_scene_context(text, speaker_name, scene_ctx)

    # Fallback to static mappings
    if speaker_name:
        speaker_refs = _FALLBACK_COREFERENCES.get(speaker_name, {})
        if speaker_refs:
            result = text
            for pronoun, expansion in speaker_refs.items():
                result = result.replace(pronoun, f"{pronoun}（{expansion}）", 1)
            return result

    return text


def _resolve_with_scene_context(text: str, speaker_name: str,
                                scene_ctx) -> str:
    """Resolve pronouns using SceneContext data.

    For each ambiguous pronoun found in text:
    - Look up speaker-specific mapping first
    - Fall back to global pronoun_map
    - If resolved, append the entity description in parentheses
    """
    result = text

    # Find all pronouns in text and resolve them
    matches = list(_PRONOUN_PATTERN.finditer(text))
    if not matches:
        return result

    # Process matches in reverse order to preserve positions
    for match in reversed(matches):
        pronoun = match.group(1)
        entity_name, description = scene_ctx.resolve_pronoun(pronoun, speaker=speaker_name)

        if entity_name and description:
            # Expand: "他" → "他（李明，她的恋人）"
            expansion = f"{pronoun}（{entity_name}，{description}）"
            result = result[:match.start()] + expansion + result[match.end():]
        elif entity_name:
            # Expand: "他" → "他（李明）"
            expansion = f"{pronoun}（{entity_name}）"
            result = result[:match.start()] + expansion + result[match.end():]
        # If unresolvable, leave as-is (backward compat: preserve original text)

    return result


def extract_and_register_entities(text: str, speaker_name: str = "",
                                  tool_context=None) -> list[str]:
    """Extract entities mentioned in text and update SceneContext.

    This is a lightweight heuristic extractor that detects:
    - Character names already registered in SceneContext
    - Touches (marks as recently mentioned) any entity found

    Returns list of entity names found.
    """
    if tool_context is None:
        return []

    from .state_manager import get_scene_context, save_scene_context

    scene_ctx = get_scene_context(tool_context)
    found = []

    for entity_name in scene_ctx.entities:
        if entity_name in text:
            scene_ctx.touch_entity(entity_name)
            found.append(entity_name)

    if found:
        save_scene_context(scene_ctx, tool_context)

    return found


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
# Memory Blocks (inspired by Letta's memory_blocks — structured identity/relationship)
# ============================================================================

# Default block labels and their descriptions
MEMORY_BLOCK_LABELS = {
    "persona": "角色核心自我认知——你是谁，你的核心信念和价值观",
    "relationship": "与他人的关系认知——你如何看待与他人的关系",
    "worldview": "世界观认知——你对这个世界的理解",
    "goal": "当前目标——你现在最想做的事",
}

MEMORY_BLOCK_MAX_LENGTH = 500  # Max chars per block value


def init_memory_blocks(actor_name: str, actor_data: dict) -> dict:
    """Initialize memory blocks for an actor if not present.

    借鉴 Letta 的 memory_blocks 概念，为演员创建结构化身份记忆块。
    默认从 actor_data 中的已有信息（personality, background, knowledge_scope）
    自动生成初始 persona_block 和 relationship_block。

    Args:
        actor_name: The actor's name.
        actor_data: The actor data dict (mutated in place).

    Returns:
        The updated actor_data with memory_blocks initialized.
    """
    actor_data.setdefault("memory_blocks", {})

    # Auto-generate persona block from existing personality + background
    if "persona" not in actor_data["memory_blocks"]:
        personality = actor_data.get("personality", "")
        background = actor_data.get("background", "")
        persona_parts = []
        if personality:
            persona_parts.append(f"性格：{personality}")
        if background:
            persona_parts.append(f"背景：{background}")
        persona_value = "\n".join(persona_parts) if persona_parts else f"我是{actor_name}。"
        actor_data["memory_blocks"]["persona"] = {
            "label": "persona",
            "value": persona_value[:MEMORY_BLOCK_MAX_LENGTH],
            "updated_scene": 0,
            "source": "auto_init",
        }

    # Auto-generate relationship block from knowledge_scope (which often includes who they know)
    if "relationship" not in actor_data["memory_blocks"]:
        knowledge = actor_data.get("knowledge_scope", "")
        rel_value = f"我了解的范围：{knowledge}" if knowledge else "暂无明确的关系认知。"
        actor_data["memory_blocks"]["relationship"] = {
            "label": "relationship",
            "value": rel_value[:MEMORY_BLOCK_MAX_LENGTH],
            "updated_scene": 0,
            "source": "auto_init",
        }

    return actor_data


def update_memory_block(
    actor_name: str,
    block_label: str,
    block_value: str,
    tool_context: ToolContext,
) -> dict:
    """Update or create a memory block for an actor.

    更新或创建演员的结构化记忆块。借鉴 Letta 的 memory_blocks 概念，
    每个块有标签和值，代表角色的一个认知维度。

    Args:
        actor_name: The actor's name.
        block_label: Block label (e.g., "persona", "relationship", "worldview", "goal").
        block_value: The new value for the block.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    if not block_label or not block_label.strip():
        return {"status": "error", "message": "block_label 不能为空。"}

    # Truncate value
    block_value = block_value[:MEMORY_BLOCK_MAX_LENGTH]
    current_scene = state.get("current_scene", 0)

    actor_data = actors[actor_name]
    actor_data.setdefault("memory_blocks", {})

    old_value = actor_data["memory_blocks"].get(block_label, {}).get("value", "")

    actor_data["memory_blocks"][block_label] = {
        "label": block_label,
        "value": block_value,
        "updated_scene": current_scene,
        "source": "actor_self_edit",
    }

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    label_desc = MEMORY_BLOCK_LABELS.get(block_label, block_label)
    return {
        "status": "success",
        "message": f"✅ 「{actor_name}」的记忆块「{block_label}」已更新（{label_desc}）",
        "block_label": block_label,
        "old_value_preview": old_value[:80] + "..." if len(old_value) > 80 else old_value,
        "new_value_preview": block_value[:80] + "..." if len(block_value) > 80 else block_value,
    }


def get_memory_blocks(actor_name: str, tool_context: ToolContext) -> dict:
    """Get all memory blocks for an actor.

    获取演员的所有结构化记忆块。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        dict with blocks data.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。", "blocks": {}}

    actor_data = actors[actor_name]
    # Ensure initialized
    actor_data = init_memory_blocks(actor_name, actor_data)
    if "memory_blocks" not in actor_data or not actor_data["memory_blocks"]:
        _set_state(state, tool_context)

    return {
        "status": "success",
        "blocks": actor_data.get("memory_blocks", {}),
    }


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
# Vector Memory Integration (Tier 4)
# ============================================================================


def _store_to_vector_memory(
    actor_name: str,
    content: str,
    importance: str,
    scene: int,
    tool_context=None,
) -> None:
    """Best-effort store a memory entry to the vector memory (Tier 4).

    非阻塞、尽力的向量记忆存储。失败不影响主流程。
    """
    try:
        from .vector_memory import store_actor_memory
        store_actor_memory(
            actor_name=actor_name,
            content=content,
            metadata={
                "scene": scene,
                "importance": importance,
                "type": "working_memory",
            },
            tool_context=tool_context,
        )
    except ImportError:
        logger.debug("chromadb not installed, skipping vector memory store")
    except Exception as e:
        logger.warning(f"Vector memory store failed for {actor_name}: {e}")


def search_vector_memory(
    actor_name: str,
    query: str,
    n_results: int = 5,
    tool_context=None,
) -> list[dict]:
    """Search an actor's vector memory (Tier 4) for semantically relevant entries.

    基于语义相似度搜索演员的长期向量记忆。

    Args:
        actor_name: The actor's name.
        query: The search query text.
        n_results: Maximum number of results.
        tool_context: Tool context for state access.

    Returns:
        List of memory dicts with content, metadata, and relevance score.
    """
    try:
        from .vector_memory import search_actor_memory
        return search_actor_memory(actor_name, query, n_results, tool_context)
    except ImportError:
        logger.debug("chromadb not installed, returning empty vector search results")
        return []
    except Exception as e:
        logger.warning(f"Vector memory search failed for {actor_name}: {e}")
        return []


def build_vector_context(
    actor_name: str,
    current_scene: str | int = "",
    n_results: int = 8,
    query: str | None = None,
    tool_context=None,
) -> str:
    """Build vector memory context text for an actor (Tier 4).

    自动检索最相关的向量记忆，格式化为可注入 LLM 的上下文文本。

    Args:
        actor_name: The actor's name.
        current_scene: Current scene for query generation.
        n_results: Maximum number of results.
        query: Optional explicit search query.
        tool_context: Tool context for state access.

    Returns:
        Formatted context text. Empty string if vector memory unavailable.
    """
    try:
        from .vector_memory import build_actor_vector_context
        return build_actor_vector_context(
            actor_name, current_scene, n_results, query, tool_context
        )
    except ImportError:
        logger.debug("chromadb not installed, skipping vector context build")
        return ""
    except Exception as e:
        logger.warning(f"Vector context build failed for {actor_name}: {e}")
        return ""


def update_memory_summary(actor_name: str, tool_context) -> dict:
    """Update the memorySummary field for an actor based on current memory state.

    在每次记忆变更后自动更新演员的"当前认知状态"摘要，
    用于 Android 端 ActorInfo 的 memorySummary 字段。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        dict with status and summary.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]

    # Build summary from all tiers
    parts = []

    # Arc summary (most condensed)
    arc = actor_data.get("arc_summary", {})
    arc_narrative = arc.get("narrative", "")
    if arc_narrative:
        parts.append(arc_narrative[:150])

    # Recent scene summaries
    scene_summaries = actor_data.get("scene_summaries", [])
    if scene_summaries:
        latest_summary = scene_summaries[-1].get("summary", "")
        if latest_summary:
            parts.append(latest_summary[:100])

    # Critical memories
    critical = actor_data.get("critical_memories", [])
    if critical:
        critical_texts = [c.get("entry", "")[:40] for c in critical[-3:]]
        parts.append("关键记忆：" + "；".join(critical_texts))

    # Vector memory summary (Tier 4)
    try:
        from .vector_memory import generate_memory_summary
        vector_summary = generate_memory_summary(actor_name, tool_context)
        if vector_summary:
            parts.append(vector_summary[:100])
    except (ImportError, Exception):
        pass

    summary = "。".join(parts) if parts else "暂无记忆摘要。"
    summary = summary[:300]  # Hard limit

    # Update state
    actor_data["memorySummary"] = summary
    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"「{actor_name}」的记忆摘要已更新。",
        "memorySummary": summary,
    }


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
    # Memory Blocks (Phase 12)
    actor_data.setdefault("memory_blocks", {})
    if not actor_data["memory_blocks"]:
        actor_data = init_memory_blocks(actor_name, actor_data)

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

    # Tier 4: Also store to vector memory (non-blocking, best-effort)
    _store_to_vector_memory(actor_name, entry, importance, current_scene, tool_context)

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

    # Update memorySummary after critical memory change
    update_memory_summary(actor_name, tool_context)

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
    # Memory Blocks (Phase 12)
    actor_data["memory_blocks"] = {}
    actor_data = init_memory_blocks(actor_name, actor_data)
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


def ensure_actor_memory_fields(actor_data: dict, actor_name: str = "") -> dict:
    """Ensure actor data dict has all new memory fields.

    Utility function to add missing fields to actor dicts that were
    created before the memory architecture was implemented.
    Also initializes memory_blocks if not present.

    Args:
        actor_data: The actor data dict to check/update.
        actor_name: The actor's name (needed for memory_blocks init).

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
    # Memory Blocks (Phase 12+)
    actor_data.setdefault("memory_blocks", {})
    if actor_name and not actor_data["memory_blocks"]:
        actor_data = init_memory_blocks(actor_name, actor_data)
    return actor_data


# ============================================================================
# Pre-Reasoning Hook (inspired by ReMe's pre_reasoning_hook pattern)
# ============================================================================


def pre_reasoning_hook(
    actor_name: str,
    tool_context: ToolContext,
    *,
    enable_compression: bool = True,
    enable_recall: bool = True,
) -> dict:
    """Unified memory preparation hook called before each actor reasoning step.

    借鉴 ReMe 的 pre_reasoning_hook 模式，在每次演员推理前自动执行：
    1. 合并待处理的压缩结果（_merge_pending_compression）
    2. 检查记忆容量并触发压缩（check_and_compress）
    3. 可选：语义召回相关记忆片段（retrieve_relevant_scenes）
    4. 应用记忆衰减权重（_apply_decay_weights）

    这确保演员在每次回应前，记忆状态是最新的且经过优化的，
    而非依赖零散的、分散在不同调用点的记忆管理。

    Args:
        actor_name: The actor whose memory to prepare.
        tool_context: Tool context for state access.
        enable_compression: Whether to run check_and_compress (default True).
        enable_recall: Whether to run semantic recall for auto-tags (default True).

    Returns:
        dict with hook execution results:
        - status: "success" or "error"
        - merged: bool — whether pending compression was merged
        - compression: result from check_and_compress (if enabled)
        - recall: list of recalled memory fragments (if enabled)
        - recall_tags: auto-generated tags used for recall
        - decay_applied: bool — whether decay was applied
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]
    result = {"status": "success", "merged": False, "compression": None, "recall": [], "recall_tags": [], "decay_applied": False}

    # Step 1: Merge any completed pending compression results
    # This ensures the latest compressed data is available before building context
    merged = _merge_pending_compression(actor_name, actor_data, tool_context)
    result["merged"] = merged

    # Step 2: Check memory tier sizes and trigger compression if needed
    # This keeps memory within limits before the actor sees it
    if enable_compression:
        compression_result = check_and_compress(actor_name, tool_context)
        result["compression"] = compression_result

    # Step 2.5: Apply memory decay weights
    decay_result = _apply_decay_weights(actor_name, tool_context)
    result["decay_applied"] = decay_result.get("applied", False)

    # Step 3: Semantic recall — find relevant past memories based on auto-tags
    # Inspired by ReMe's memory_search but adapted to our tag-weighted system
    if enable_recall:
        from .semantic_retriever import _extract_auto_tags, retrieve_relevant_scenes
        from .context_builder import estimate_tokens

        # Refresh state after compression
        state = _get_state(tool_context)
        actor_data = state.get("actors", {}).get(actor_name, {})

        auto_tags = _extract_auto_tags(actor_data, tool_context)
        result["recall_tags"] = auto_tags

        if auto_tags:
            current_scene = state.get("current_scene", 0)
            # Actor-side recall: top-3, limited to own memories (D-07)
            recall_results = retrieve_relevant_scenes(
                tags=auto_tags,
                current_scene=current_scene,
                tool_context=tool_context,
                actor_name=actor_name,
                top_k=3,
            )
            result["recall"] = [
                {
                    "scenes_covered": r.get("scenes_covered", ""),
                    "text": r.get("text", "")[:150],
                    "matched_tags": r.get("matched_tags", []),
                    "score": r.get("score", 0),
                }
                for r in recall_results
            ]

    # Step 4: Vector memory recall (Tier 4) — semantic search in long-term memory
    if enable_recall:
        current_scene = state.get("current_scene", 0) if 'state' in dir() else 0
        # Refresh state
        state = _get_state(tool_context)
        try:
            vector_results = search_vector_memory(
                actor_name=actor_name,
                query=f"第{current_scene}场 最近的经历",
                n_results=3,
                tool_context=tool_context,
            )
            if vector_results:
                result["vector_recall"] = [
                    {
                        "content": r.get("content", "")[:150],
                        "relevance": r.get("relevance", 0),
                        "scene": r.get("metadata", {}).get("scene", ""),
                    }
                    for r in vector_results
                ]
        except Exception as e:
            logger.debug(f"Vector recall skipped for {actor_name}: {e}")

    return result


# ============================================================================
# Agent Self-Edit Functions (inspired by Letta's agent self-edit)
# ============================================================================


def actor_self_add_fact(
    actor_name: str,
    fact: str,
    category: str = "event",
    tool_context: ToolContext = None,
) -> dict:
    """Allow an actor to self-report a fact they consider important.

    借鉴 Letta 的 Agent 自主记忆编辑概念。演员可以主动报告一个
    他们认为重要的事实。与导演的 add_fact 不同：
    - 演员报告的事实自动附带 actor_name 作为来源标记
    - 默认 importance 为 medium（演员不能自行标记为 high）
    - 事实会同时记录到演员的 working_memory 中

    Args:
        actor_name: The actor reporting the fact.
        fact: The fact the actor wants to record.
        category: Fact category — event, identity, location, relationship, rule.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    from .coherence_checker import add_fact_logic

    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    if not fact or not fact.strip():
        return {"status": "error", "message": "事实内容不能为空。"}

    # Truncate
    fact = fact.strip()[:500]
    state.setdefault("established_facts", [])

    # Add fact with actor as source (medium importance, actor cannot set high)
    result = add_fact_logic(fact, category, "medium", state)
    if result["status"] == "success":
        # Mark the fact as actor-sourced
        for f in state["established_facts"]:
            if f.get("id") == result["fact_id"]:
                f["source"] = "actor_self_report"
                f["actor"] = actor_name
                break
        _set_state(state, tool_context)

        # Also add to actor's working memory
        add_working_memory(
            actor_name=actor_name,
            entry=f"我记住了一个事实：{fact[:200]}",
            importance="normal",
            critical_reason=None,
            tool_context=tool_context,
        )

        return {
            "status": "success",
            "fact_id": result["fact_id"],
            "message": f"✅ 「{actor_name}」自主记录了事实：{fact[:100]}",
        }
    return result


def actor_self_mark_memory(
    actor_name: str,
    memory_text: str,
    reason: str,
    tool_context: ToolContext = None,
) -> dict:
    """Allow an actor to mark a specific memory as critical.

    借鉴 Letta 的 Agent 自主记忆编辑概念。演员可以主动标记
    一段经历为关键记忆（如果记忆文本匹配最近的 working_memory 条目）。
    与导演的 /mark 命令不同：
    - 演员通过描述记忆内容来标记，而非索引
    - 自动匹配最近的 working_memory 条目

    Args:
        actor_name: The actor marking the memory.
        memory_text: Text describing the memory to mark (matched against recent entries).
        reason: Why this is critical (must be from CRITICAL_REASONS).
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

    if not working:
        return {"status": "error", "message": f"演员「{actor_name}」没有工作记忆可标记。"}

    # Find best matching entry by substring match
    matched_idx = -1
    for i in range(len(working) - 1, -1, -1):  # Search from newest
        entry_text = working[i].get("entry", "")
        if memory_text and memory_text in entry_text:
            matched_idx = i
            break

    if matched_idx == -1:
        # Fallback: mark the last entry
        matched_idx = len(working) - 1

    entry = working.pop(matched_idx)
    critical_entry = {
        "entry": entry["entry"],
        "reason": reason,
        "scene": entry.get("scene", 0),
        "source": "actor_self_mark",
    }
    actor_data["critical_memories"].append(critical_entry)
    actor_data["working_memory"] = working

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"✅ 「{actor_name}」自主标记了关键记忆（{reason}）",
        "critical_entry": critical_entry,
    }


def actor_self_update_block(
    actor_name: str,
    block_label: str,
    block_value: str,
    tool_context: ToolContext = None,
) -> dict:
    """Allow an actor to update their own memory block.

    借鉴 Letta 的 Agent 自主记忆编辑概念。演员可以主动更新
    自己的结构化记忆块（persona, relationship, goal 等），
    反映角色在剧情中的认知变化。

    Args:
        actor_name: The actor updating the block.
        block_label: Block label to update.
        block_value: New value for the block.
        tool_context: Tool context for state access.

    Returns:
        dict with status.
    """
    return update_memory_block(actor_name, block_label, block_value, tool_context)


# ============================================================================
# Memory Decay System (inspired by Letta's forgetting curve)
# ============================================================================

# Decay parameters
# Scene-based decay: memories lose weight as scenes pass
# Using Ebbinghaus-inspired exponential decay: weight = e^(-λ * scene_gap)
DECAY_LAMBDA = 0.1  # Decay rate: after ~7 scenes, weight drops to ~50%
DECAY_MIN_WEIGHT = 0.2  # Minimum weight before memory is prunable
DECAY_CHECK_INTERVAL = 5  # Run decay check every N scenes
MAX_DECAYED_ENTRIES = 3  # Max decayed (low-weight) entries to keep per tier


def _calculate_decay_weight(entry_scene: int, current_scene: int, importance: str = "normal") -> float:
    """Calculate memory weight based on scene distance (Ebbinghaus-inspired).

    借鉴 Letta 的遗忘曲线概念。记忆权重随场景距离指数衰减：
    - normal 记忆：标准衰减 λ=0.1
    - critical 记忆：永不衰减（权重恒为 1.0）
    - 衰减公式：weight = e^(-λ * scene_gap)

    Args:
        entry_scene: The scene when the memory was created.
        current_scene: The current scene number.
        importance: Memory importance ("normal" or "critical").

    Returns:
        Float weight between 0.0 and 1.0.
    """
    # Critical memories never decay
    if importance == "critical":
        return 1.0

    scene_gap = max(0, current_scene - entry_scene)
    if scene_gap == 0:
        return 1.0

    import math
    weight = math.exp(-DECAY_LAMBDA * scene_gap)
    return max(weight, DECAY_MIN_WEIGHT)


def _apply_decay_weights(actor_name: str, tool_context: ToolContext) -> dict:
    """Apply decay weights to working memory entries and prune heavily decayed ones.

    借鉴 Letta 的遗忘曲线概念。在 pre_reasoning_hook 中调用：
    1. 计算每条 working_memory 的衰减权重
    2. 权重低于阈值的标记为 decayed
    3. 清理超过保留数量的 decayed 条目

    不会删除 critical_memories（永不衰减）。

    Args:
        actor_name: The actor whose memory to decay-check.
        tool_context: Tool context for state access.

    Returns:
        dict with decay status.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "applied": False}

    actor_data = actors[actor_name]
    working = actor_data.get("working_memory", [])
    current_scene = state.get("current_scene", 0)

    if not working:
        return {"status": "success", "applied": False, "pruned": 0}

    # Check if decay check is needed (interval-based)
    last_decay_scene = actor_data.get("_last_decay_scene", 0)
    if current_scene - last_decay_scene < DECAY_CHECK_INTERVAL:
        return {"status": "success", "applied": False, "pruned": 0}

    # Calculate weights and categorize
    kept = []
    decayed_count = 0
    for entry in working:
        importance = entry.get("importance", "normal")
        weight = _calculate_decay_weight(entry.get("scene", 0), current_scene, importance)

        # Store weight for context_builder to use
        entry["decay_weight"] = round(weight, 3)

        if weight <= DECAY_MIN_WEIGHT and importance != "critical":
            decayed_count += 1
        else:
            kept.append(entry)

    # Keep at most MAX_DECAYED_ENTRIES decayed items (oldest ones get pruned)
    decayed_entries = [e for e in kept if e.get("decay_weight", 1.0) <= 0.3]
    fresh_entries = [e for e in kept if e.get("decay_weight", 1.0) > 0.3]

    if len(decayed_entries) > MAX_DECAYED_ENTRIES:
        # Sort by decay_weight ascending (most decayed first to prune)
        decayed_entries.sort(key=lambda e: e.get("decay_weight", 0))
        pruned_count = len(decayed_entries) - MAX_DECAYED_ENTRIES
        decayed_entries = decayed_entries[-MAX_DECAYED_ENTRIES:]  # Keep the least-decayed
    else:
        pruned_count = 0

    # Rebuild working_memory: fresh first, then retained decayed
    actor_data["working_memory"] = fresh_entries + decayed_entries
    actor_data["_last_decay_scene"] = current_scene

    actors[actor_name] = actor_data
    state["actors"] = actors
    _set_state(state, tool_context)

    return {
        "status": "success",
        "applied": True,
        "pruned": pruned_count,
        "decayed_flagged": decayed_count,
        "total_kept": len(actor_data["working_memory"]),
    }


def get_memory_with_decay(
    actor_name: str,
    tool_context: ToolContext,
) -> dict:
    """Get actor's memory state with decay weights applied.

    返回演员当前记忆状态，包含衰减权重信息。供调试和展示使用。

    Args:
        actor_name: The actor's name.
        tool_context: Tool context for state access.

    Returns:
        dict with memory state and decay info.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if actor_name not in actors:
        return {"status": "error", "message": f"演员「{actor_name}」不存在。"}

    actor_data = actors[actor_name]
    current_scene = state.get("current_scene", 0)

    # Calculate weights for all tiers
    working = actor_data.get("working_memory", [])
    weighted_working = []
    for e in working:
        w = _calculate_decay_weight(e.get("scene", 0), current_scene, e.get("importance", "normal"))
        weighted_working.append({
            "entry": e.get("entry", "")[:80],
            "scene": e.get("scene", 0),
            "importance": e.get("importance", "normal"),
            "decay_weight": round(w, 3),
        })

    summaries = actor_data.get("scene_summaries", [])
    weighted_summaries = []
    for s in summaries:
        # Scene summaries have lower decay rate
        w = _calculate_decay_weight(0, 0, "normal")  # Summaries don't decay as fast
        weighted_summaries.append({
            "scenes_covered": s.get("scenes_covered", ""),
            "weight": 1.0,  # Summaries are already compressed, keep full weight
        })

    return {
        "status": "success",
        "actor_name": actor_name,
        "current_scene": current_scene,
        "working_memory": weighted_working,
        "scene_summaries_count": len(summaries),
        "critical_count": len(actor_data.get("critical_memories", [])),
        "memory_blocks": list(actor_data.get("memory_blocks", {}).keys()),
    }


# Phase 2: Re-export for backward compatibility
# build_actor_context has been migrated to context_builder.py
# Using lazy import to avoid circular import (context_builder imports _merge_pending_compression from us)
def __getattr__(name):
    if name == "build_actor_context":
        from .context_builder import build_actor_context
        return build_actor_context
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
