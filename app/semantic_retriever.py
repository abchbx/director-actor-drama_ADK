"""Semantic retrieval engine for drama memory recall.

实现标签加权匹配检索算法，支持三层记忆搜索（scene_summaries > working_memory/critical_memories），
按加权相关度排序，同一场景去重，纯 Python 计算无需外部向量数据库。

Architecture:
    retrieve_relevant_scenes(tags, current_scene, tool_context) → top-K results
    _search_scene_summaries  — weighted tag matching (primary)
    _search_text_layer       — keyword matching on working/critical memories (secondary)
    _dedup_results           — scene-range based deduplication
    _parse_tags_from_llm_output — extract tags from LLM response
    _extract_auto_tags       — generate query tags from actor context for auto-injection
    backfill_tags            — batch tag generation for legacy scene_summaries
"""

import json
import logging
import re
from typing import Optional

from google.adk.tools import ToolContext

from .state_manager import _get_state, _set_state

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Tag prefix weights (D-09): higher weight = more important in matching
TAG_WEIGHTS = {"角色": 3.0, "冲突": 2.0, "事件": 2.0, "情感": 1.5, "地点": 1.0}

# Tag prefix whitelist for validation (T-03-01)
TAG_PREFIXES = set(TAG_WEIGHTS.keys()) | {"其他"}

# Regex for extracting tags from LLM output (fallback)
_TAG_REGEX = re.compile(
    r'["\']?(角色|地点|情感|冲突|事件|其他)[:：]([^"\'，,、\]\n。；\s]+)["\']?',
    re.IGNORECASE,
)


# ============================================================================
# Tag Parsing (RESEARCH.md Pattern 2)
# ============================================================================


def _parse_tags_from_llm_output(text: str) -> list[str]:
    """Parse tags from LLM output text with JSON-first, regex-fallback strategy.

    从 LLM 输出中提取标签列表。优先尝试 JSON 解析，失败则回退到正则匹配。
    标签提取失败不阻塞流程，返回空列表。

    Args:
        text: Raw LLM response text, may contain JSON or plain text with tags.

    Returns:
        List of tag strings (e.g., ["角色:朱棣", "地点:皇宫"]). Empty list if nothing found.
    """
    if not text or not text.strip():
        return []

    # Strategy 1: Try JSON parse (handles ```json fences)
    cleaned = text.strip()
    if "```json" in cleaned:
        try:
            json_part = cleaned.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(json_part)
            return _extract_tags_from_json(parsed)
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    elif "```" in cleaned:
        try:
            json_part = cleaned.split("```")[1].split("```")[0].strip()
            parsed = json.loads(json_part)
            return _extract_tags_from_json(parsed)
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    else:
        # Try direct JSON parse
        try:
            parsed = json.loads(cleaned)
            return _extract_tags_from_json(parsed)
        except json.JSONDecodeError:
            pass

    # Strategy 2: Regex fallback
    matches = _TAG_REGEX.findall(text)
    if matches:
        return [f"{prefix}:{value.strip()}" for prefix, value in matches]

    return []


def _extract_tags_from_json(parsed) -> list[str]:
    """Extract tags list from a parsed JSON object.

    Handles both {"tags": [...]} format and bare list format.
    """
    if isinstance(parsed, list):
        return [str(t) for t in parsed if t]
    if isinstance(parsed, dict):
        tags = parsed.get("tags", [])
        if isinstance(tags, list):
            return [str(t) for t in tags if t]
    return []


# ============================================================================
# Tag Weight and Score Computation
# ============================================================================


def _get_tag_weight(tag: str) -> float:
    """Get the weight for a tag based on its prefix.

    提取标签前缀并返回对应权重。无前缀标签权重为 1.0。

    Args:
        tag: Tag string, e.g., "角色:朱棣" or "皇宫".

    Returns:
        Weight value from TAG_WEIGHTS or 1.0 for no-prefix tags.
    """
    if ":" in tag:
        prefix = tag.split(":")[0].strip()
        return TAG_WEIGHTS.get(prefix, 1.0)
    return 1.0


def _compute_tag_score(query_tags: list[str], entry_tags: list[str]) -> float:
    """Compute weighted tag matching score between query and entry.

    加权匹配算法（D-10）：
    - 精确匹配（前缀+值完全一致）：score += max(weight(qt), weight(et))
    - 仅值匹配（query 无前缀但值匹配）：score += 1.0
    - 无匹配：0 分

    Args:
        query_tags: Tags from the search query.
        entry_tags: Tags from the memory entry.

    Returns:
        Total matching score (float).
    """
    score = 0.0
    for qt in query_tags:
        qt_value = qt.split(":")[-1].strip() if ":" in qt else qt.strip()
        for et in entry_tags:
            et_value = et.split(":")[-1].strip() if ":" in et else et.strip()
            if qt == et:
                # Exact match (prefix + value)
                score += max(_get_tag_weight(qt), _get_tag_weight(et))
            elif ":" in qt and qt_value == et_value:
                # Query has prefix, value matches entry value
                score += min(_get_tag_weight(qt), _get_tag_weight(et))
            elif ":" not in qt and qt_value == et_value:
                # Value-only match (lower weight to avoid gaming)
                score += 1.0
    return score


# ============================================================================
# Scene Range Normalization
# ============================================================================


def _normalize_scene_range(scenes_covered) -> set[int]:
    """Convert scenes_covered field to a set of scene integers.

    将场景范围字符串转换为整数集合。支持多种格式：
    "3-5" → {3,4,5}，整数 3 → {3}，"3" → {3}。

    Args:
        scenes_covered: Scene range in various formats (str, int).

    Returns:
        Set of scene integers.
    """
    if isinstance(scenes_covered, (int, float)):
        return {int(scenes_covered)}

    s = str(scenes_covered).strip()
    if not s:
        return set()

    # Handle range "3-5"
    if "-" in s:
        parts = s.split("-", 1)
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            return set(range(start, end + 1))
        except (ValueError, IndexError):
            pass

    # Handle comma-separated "3,4,5"
    if "," in s:
        result = set()
        for part in s.split(","):
            try:
                result.add(int(part.strip()))
            except ValueError:
                continue
        return result

    # Single number
    try:
        return {int(s)}
    except ValueError:
        return set()


# ============================================================================
# Three-Layer Search
# ============================================================================


def _search_scene_summaries(
    query_tags: list[str], summaries: list[dict]
) -> list[dict]:
    """Search scene_summaries using weighted tag matching (primary layer).

    遍历 scene_summaries，对每个条目计算加权标签匹配分数。
    只返回分数 > 0 的结果。

    Args:
        query_tags: Tags from the search query.
        summaries: List of scene summary dicts with "tags" field.

    Returns:
        List of result dicts: {"source", "scenes_covered", "text", "matched_tags", "score"}.
    """
    results = []
    for s in summaries:
        entry_tags = s.get("tags", [])
        if not entry_tags:
            continue
        score = _compute_tag_score(query_tags, entry_tags)
        if score > 0:
            # Find which query tags matched
            matched = []
            for qt in query_tags:
                qt_value = qt.split(":")[-1].strip() if ":" in qt else qt.strip()
                for et in entry_tags:
                    et_value = et.split(":")[-1].strip() if ":" in et else et.strip()
                    if qt_value == et_value or qt == et:
                        matched.append(qt)
                        break
            results.append({
                "source": "scene_summaries",
                "scenes_covered": s.get("scenes_covered", ""),
                "text": s.get("summary", ""),
                "matched_tags": matched,
                "score": score,
            })
    return results


def _search_text_layer(
    query_tags: list[str], entries: list[dict], source_name: str
) -> list[dict]:
    """Search working_memory or critical_memories using keyword matching (secondary layer).

    对每条记忆条目，检查 query tag 的值是否出现在条目文本中。
    匹配分数固定为 1.0（D-11）。

    Args:
        query_tags: Tags from the search query.
        entries: List of memory entry dicts with "entry" and "scene" fields.
        source_name: "working_memory" or "critical_memories".

    Returns:
        List of result dicts with fixed score 1.0.
    """
    results = []
    for e in entries:
        text = e.get("entry", "")
        if not text:
            continue
        matched = []
        for qt in query_tags:
            value = qt.split(":")[-1].strip() if ":" in qt else qt.strip()
            if value and value in text:
                matched.append(qt)
        if matched:
            results.append({
                "source": source_name,
                "scenes_covered": str(e.get("scene", "")),
                "text": text,
                "matched_tags": matched,
                "score": 1.0,
            })
    return results


# ============================================================================
# Deduplication (D-12)
# ============================================================================


def _dedup_results(results: list[dict]) -> list[dict]:
    """Deduplicate results by scene range overlap, keeping highest score.

    按场景范围去重：如果两个结果的场景范围有交集，只保留分数更高的。
    无交集的结果全部保留。

    Args:
        results: List of result dicts with "scenes_covered" and "score".

    Returns:
        Deduplicated list of results.
    """
    if not results:
        return []

    # Sort by score descending first
    sorted_results = sorted(results, key=lambda r: r.get("score", 0), reverse=True)

    kept = []
    kept_ranges: list[set[int]] = []

    for result in sorted_results:
        result_range = _normalize_scene_range(result.get("scenes_covered", ""))
        if not result_range:
            # No scene info — keep it
            kept.append(result)
            continue

        # Check overlap with already-kept results
        overlaps = False
        for kr in kept_ranges:
            if result_range & kr:
                overlaps = True
                break

        if not overlaps:
            kept.append(result)
            kept_ranges.append(result_range)

    return kept


# ============================================================================
# Main Retrieval Function (D-05/D-06/D-07/D-08)
# ============================================================================


def retrieve_relevant_scenes(
    tags: list[str],
    current_scene: int,
    tool_context: ToolContext,
    actor_name: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve relevant scene memories by tags with weighted matching.

    按标签检索相关历史记忆。支持三种搜索层：
    1. scene_summaries（标签加权匹配，主要层）
    2. working_memory（关键词匹配，次要层）
    3. critical_memories（关键词匹配，次要层）

    结果按分数降序排列，同一场景去重，返回 top-K。

    Args:
        tags: Query tag list, e.g., ["角色:朱棣", "情感:愤怒"].
        current_scene: Current scene number (for context).
        tool_context: Tool context for state access.
        actor_name: If provided, search only this actor's memories (D-07: actor boundary).
                    If None, search all actors globally (director mode).
        top_k: Maximum number of results to return.

    Returns:
        List of {"source", "scenes_covered", "text", "matched_tags", "score"}, sorted by score descending.
    """
    state = _get_state(tool_context)
    actors = state.get("actors", {})

    if not actors or not tags:
        return []

    all_results = []

    # Determine which actors to search
    if actor_name:
        search_actors = {actor_name: actors.get(actor_name, {})} if actor_name in actors else {}
    else:
        search_actors = actors

    for name, actor_data in search_actors.items():
        # Layer 1: scene_summaries (tag matching)
        summaries = actor_data.get("scene_summaries", [])
        all_results.extend(_search_scene_summaries(tags, summaries))

        # Layer 2: working_memory (keyword matching)
        working = actor_data.get("working_memory", [])
        all_results.extend(_search_text_layer(tags, working, "working_memory"))

        # Layer 3: critical_memories (keyword matching)
        critical = actor_data.get("critical_memories", [])
        all_results.extend(_search_text_layer(tags, critical, "critical_memories"))

    # Deduplicate by scene range
    deduped = _dedup_results(all_results)

    # Sort by score descending and return top_k
    deduped.sort(key=lambda r: r.get("score", 0), reverse=True)
    return deduped[:top_k]


# ============================================================================
# Auto-Tag Extraction (D-15)
# ============================================================================


def _extract_auto_tags(
    actor_data: dict, tool_context: ToolContext
) -> list[str]:
    """Extract auto-tags from actor's working memory and current scene for auto-injection.

    从演员的最新工作记忆和当前场景中提取标签，用于自动注入相关回忆。
    最多返回 8 个标签。

    策略：
    1. 从最新 working_memory 条目中提取角色名和关键名词
    2. 从当前场景描述中提取关键信息
    3. 从 actor 已有 scene_summaries 的 tags 中复用高频标签

    Args:
        actor_data: The actor data dict from state.
        tool_context: Tool context for state access.

    Returns:
        List of tag strings, up to 8 items.
    """
    tags = []
    seen_values = set()

    def _add_tag(tag: str):
        value = tag.split(":")[-1].strip() if ":" in tag else tag.strip()
        if value and value not in seen_values and len(tags) < 8:
            tags.append(tag)
            seen_values.add(value)

    # Source 1: Latest working_memory entries
    working = actor_data.get("working_memory", [])
    for entry in working[-3:]:  # Last 3 entries
        text = entry.get("entry", "")
        # Extract character names mentioned in the text
        # Simple heuristic: look for common patterns like character names
        # We extract nouns/phrases that might be tags
        for prefix in ["角色", "地点", "情感", "冲突", "事件"]:
            pattern = rf"{prefix}[:：](\S+)"
            matches = re.findall(pattern, text)
            for m in matches:
                _add_tag(f"{prefix}:{m}")

    # Source 2: Existing scene_summaries tags (reuse high-frequency tags)
    summaries = actor_data.get("scene_summaries", [])
    tag_counts: dict[str, int] = {}
    for s in summaries[-5:]:  # Recent 5 summaries
        for t in s.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    # Sort by frequency, take top tags
    for t, _ in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
        _add_tag(t)

    # Source 3: Current scene description (if available)
    state = _get_state(tool_context)
    scenes = state.get("scenes", [])
    if scenes:
        current_scene = state.get("current_scene", 0)
        # Find the current scene
        for sc in scenes:
            if sc.get("scene_number") == current_scene:
                desc = sc.get("description", "")
                title = sc.get("title", "")
                # Extract potential tags from title/description
                for prefix in ["角色", "地点", "情感", "冲突", "事件"]:
                    pattern = rf"{prefix}[:：](\S+)"
                    matches = re.findall(pattern, f"{title} {desc}")
                    for m in matches:
                        _add_tag(f"{prefix}:{m}")
                break

    # Source 4: Actor's role and personality as fallback tags
    role = actor_data.get("role", "")
    name = actor_data.get("name", "")
    if role:
        _add_tag(f"角色:{role}")
    if name:
        _add_tag(f"角色:{name}")

    return tags


# ============================================================================
# Backfill Tags (D-02)
# ============================================================================


async def backfill_tags(tool_context: ToolContext) -> dict:
    """Backfill tags for existing scene summaries that lack tags using LLM.

    对已有的 scene_summaries 批量生成标签（调用 LLM）。
    执行后标记 tags_backfilled=True，避免重复执行。

    Args:
        tool_context: Tool context for state access.

    Returns:
        dict with backfill status and count of tagged summaries.
    """
    state = _get_state(tool_context)

    # Check if already backfilled
    if state.get("tags_backfilled"):
        return {
            "status": "info",
            "message": "标签已回填过，跳过重复执行。",
            "tagged_count": 0,
        }

    from .memory_manager import _call_llm

    actors = state.get("actors", {})
    tagged_count = 0

    for actor_name, actor_data in actors.items():
        summaries = actor_data.get("scene_summaries", [])
        # Batch process: 3-5 summaries per prompt (Pitfall 3)
        batch_size = 4
        for i in range(0, len(summaries), batch_size):
            batch = summaries[i : i + batch_size]
            # Only process summaries without tags
            need_tags = [s for s in batch if not s.get("tags")]
            if not need_tags:
                continue

            # Build prompt for batch
            summaries_text = "\n\n".join(
                f"场景{idx}: {s.get('summary', '')}"
                for idx, s in enumerate(need_tags)
            )
            prompt = f"""请为以下场景摘要生成标签。每个场景生成3-8个标签。

标签格式：前缀:值，前缀包括：角色、地点、情感、冲突、事件
角色名必标，冲突/事件类型必标。

## 场景摘要
{summaries_text}

## 输出格式（严格 JSON）
{{{{
  "scenes": [
    {{{{"summary_index": 0, "tags": ["角色:朱棣", "地点:皇宫"]}}}},
    {{{{"summary_index": 1, "tags": ["冲突:权力争夺"]}}}}
  ]
}}}}"""

            try:
                response = await _call_llm(prompt)
                parsed_tags = _parse_tags_from_llm_output(response)

                # Try to extract per-scene tags from JSON
                try:
                    json_text = response.strip()
                    if "```json" in json_text:
                        json_text = json_text.split("```json")[1].split("```")[0].strip()
                    result = json.loads(json_text)
                    scenes_list = result.get("scenes", [])
                    for scene_info in scenes_list:
                        idx = scene_info.get("summary_index", -1)
                        scene_tags = scene_info.get("tags", [])
                        if 0 <= idx < len(need_tags) and scene_tags:
                            need_tags[idx]["tags"] = scene_tags
                            tagged_count += 1
                except (json.JSONDecodeError, KeyError, IndexError):
                    # Fallback: assign all parsed tags to first summary
                    if parsed_tags and need_tags:
                        need_tags[0]["tags"] = parsed_tags
                        tagged_count += 1

            except Exception as e:
                logger.warning(f"Backfill tags failed for batch: {e}")
                continue

    # Mark as backfilled
    state["tags_backfilled"] = True
    _set_state(state, tool_context)

    return {
        "status": "success",
        "message": f"已为 {tagged_count} 个场景摘要生成标签。",
        "tagged_count": tagged_count,
    }
