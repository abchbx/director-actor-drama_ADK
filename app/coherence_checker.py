"""Coherence Checker — fact tracking, consistency checking, and contradiction repair.

一致性检查器：事实追踪、一致性检查和矛盾修复的纯函数模块。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- FACT_CATEGORIES / COHERENCE_CHECK_INTERVAL / MAX_FACTS constants
- add_fact_logic for fact creation with dedup and validation
- validate_consistency_logic / validate_consistency_prompt for LLM-driven consistency checks
- generate_repair_narration_prompt for contradiction narration
- repair_contradiction_logic for appending repair notes
- parse_contradictions for LLM response parsing with multi-layer fallback
- Helper functions: _extract_actor_names, _check_fact_overlap, _filter_relevant_facts, _generate_fact_id
"""

import json
import re
from datetime import datetime

# ============================================================================
# Constants / 常量定义
# ============================================================================

# Fact categories per D-02
# 事实类别（D-02）
FACT_CATEGORIES = {"event", "identity", "location", "relationship", "rule"}

# Check interval per D-35
# 检查间隔（D-35）
COHERENCE_CHECK_INTERVAL = 5

# Max facts per D-11
# 事实上限（D-11）
MAX_FACTS = 50

# Max check history entries per D-32
# 检查历史上限（D-32）
MAX_CHECK_HISTORY = 10


# ============================================================================
# Helper functions / 辅助函数
# ============================================================================


def _extract_actor_names(fact_text: str, known_actors: list[str]) -> list[str]:
    """Extract actor names from fact text by matching against known actors.

    从事实文本中提取已知角色名（D-09）。
    使用简单字符串包含匹配，遍历 known_actors 检查 fact_text 是否包含角色名。

    Args:
        fact_text: The fact text to search for actor names.
        known_actors: List of known actor names to match against.

    Returns:
        List of actor names found in the fact text.
    """
    return [name for name in known_actors if name in fact_text]


def _check_fact_overlap(new_fact: str, existing_facts: list[dict]) -> dict:
    """Check overlap between a new fact and existing facts.

    检测事实去重——前 20 字 80% 重叠检测（D-10）。
    取 new_fact 前 20 字，与每个 existing fact 的 fact 字段前 20 字比较，
    计算相同字符占比（交集/并集），> 80% 则标记重叠。

    Args:
        new_fact: The new fact text to check.
        existing_facts: List of existing fact dicts with "fact" key.

    Returns:
        dict with is_duplicate (bool) and overlapping_with (str|None).
    """
    new_prefix = new_fact[:20]

    for existing in existing_facts:
        existing_prefix = existing.get("fact", "")[:20]
        if not new_prefix or not existing_prefix:
            continue

        # Calculate character-level overlap ratio (intersection / union)
        new_chars = set(new_prefix)
        existing_chars = set(existing_prefix)
        intersection = new_chars & existing_chars
        union = new_chars | existing_chars

        if not union:
            continue

        overlap_ratio = len(intersection) / len(union)
        if overlap_ratio > 0.8:
            return {
                "is_duplicate": True,
                "overlapping_with": existing.get("fact", ""),
            }

    return {"is_duplicate": False, "overlapping_with": None}


def _generate_fact_id(
    fact: str, current_scene: int, established_facts: list[dict]
) -> str:
    """Generate a unique fact ID following fact_{scene}_{keyword}_{index} format.

    生成事实 ID（D-04）。使用 re.search 提取中文 2-4 字关键词，
    无中文匹配时 keyword="fact"。index 为同前缀的已有数量+1。

    Args:
        fact: The fact text to extract keyword from.
        current_scene: The current scene number.
        established_facts: List of existing fact dicts.

    Returns:
        Unique fact ID string.
    """
    # Extract 2-4 character Chinese keyword
    match = re.search(r"[\u4e00-\u9fff]{2,4}", fact)
    keyword = match.group(0) if match else "fact"

    prefix = f"fact_{current_scene}_{keyword}"
    existing_count = sum(
        1 for f in established_facts if f.get("id", "").startswith(prefix)
    )
    index = existing_count + 1

    return f"fact_{current_scene}_{keyword}_{index}"


def _filter_relevant_facts(state: dict) -> list[dict]:
    """Filter relevant facts for consistency checking based on heuristic rules.

    启发式预筛选——从 established_facts 中筛选出与当前场景相关的事实（D-16）。
    筛选条件：
    1. importance 为 high 或 medium（low 级别跳过）
    2. 事实的 actors 与最近 2 场出现的角色有交集，或 category 为 "rule"（全局规则始终检查）
    3. 事实的 scene < current_scene（跳过本场景刚添加的事实）

    Args:
        state: Drama state dict with established_facts, scenes, current_scene.

    Returns:
        List of filtered fact dicts relevant for consistency checking.
    """
    established_facts = state.get("established_facts", [])
    current_scene = state.get("current_scene", 0)
    scenes = state.get("scenes", [])

    # Get actors from recent 2 scenes
    recent_scenes = scenes[-2:] if len(scenes) >= 2 else scenes
    recent_actors = set()
    for scene in recent_scenes:
        for actor_name in scene.get("actors_present", []):
            recent_actors.add(actor_name)

    relevant = []
    for fact in established_facts:
        # Rule 3: Skip facts from current scene
        if fact.get("scene", 0) >= current_scene:
            continue

        # Rule 1: Only high/medium importance
        if fact.get("importance") not in ("high", "medium"):
            continue

        # Rule 2: actors overlap with recent scenes OR category is "rule"
        fact_actors = set(fact.get("actors", []))
        has_actor_overlap = bool(fact_actors & recent_actors)
        is_rule = fact.get("category") == "rule"

        if has_actor_overlap or is_rule:
            relevant.append(fact)

    return relevant


# ============================================================================
# Core functions / 核心函数
# ============================================================================


def add_fact_logic(fact: str, category: str, importance: str, state: dict) -> dict:
    """Add a new established fact with validation, dedup check, and auto-generated ID.

    添加新事实——验证类别/重要性，去重检查，提取角色，生成 ID（D-01/D-06/D-09/D-10/D-11）。

    Args:
        fact: The fact text.
        category: Fact category (must be in FACT_CATEGORIES).
        importance: Fact importance (high/medium/low).
        state: Drama state dict with established_facts, actors, current_scene.

    Returns:
        dict with status and fact info. Status can be "success", "error", or "info".
    """
    established_facts = state.get("established_facts", [])

    # Validate category (D-02)
    if category not in FACT_CATEGORIES:
        return {
            "status": "error",
            "message": f"无效的事实类别: {category}，可用：{', '.join(sorted(FACT_CATEGORIES))}",
        }

    # Validate importance (D-03)
    if importance not in ("high", "medium", "low"):
        return {
            "status": "error",
            "message": f"无效的重要性级别: {importance}，可用：high, medium, low",
        }

    # Dedup check (D-10)
    overlap = _check_fact_overlap(fact, established_facts)
    if overlap["is_duplicate"]:
        return {
            "status": "info",
            "message": f"⚠️ 可能重复：{overlap['overlapping_with']}",
        }

    # Check MAX_FACTS (D-11)
    if len(established_facts) >= MAX_FACTS:
        return {
            "status": "info",
            "message": f"⚠️ 事实已达上限 {MAX_FACTS} 条，建议清理低 importance 事实",
        }

    # Extract actors from fact text (D-09)
    known_actors = list(state.get("actors", {}).keys())
    actors = _extract_actor_names(fact, known_actors)

    # Generate fact_id (D-04)
    current_scene = state.get("current_scene", 0)
    fact_id = _generate_fact_id(fact, current_scene, established_facts)

    # Create fact object (D-01)
    new_fact = {
        "id": fact_id,
        "fact": fact,
        "category": category,
        "actors": actors,
        "scene": current_scene,
        "importance": importance,
        "added_at": datetime.now().isoformat(),
    }

    established_facts.append(new_fact)
    state["established_facts"] = established_facts

    return {
        "status": "success",
        "fact_id": fact_id,
        "fact": new_fact,
    }


def validate_consistency_logic(state: dict) -> dict:
    """Run heuristic pre-filtering and return relevant facts for consistency checking.

    一致性检查逻辑——启发式预筛选 + 返回待检查事实列表和场景（D-12/D-15/D-16）。
    无相关事实时返回成功但空的结果。

    Args:
        state: Drama state dict with established_facts, scenes, current_scene.

    Returns:
        dict with status, relevant_facts, recent_scenes, facts_checked, scenes_analyzed.
    """
    # Heuristic pre-filtering (D-16)
    relevant_facts = _filter_relevant_facts(state)

    if not relevant_facts:
        return {
            "status": "success",
            "message": "✅ 无需检查",
            "contradictions": [],
            "facts_checked": 0,
            "scenes_analyzed": 0,
        }

    # Get recent 2 scenes (D-12)
    scenes = state.get("scenes", [])
    recent_scenes = scenes[-2:] if len(scenes) >= 2 else scenes

    return {
        "status": "success",
        "relevant_facts": relevant_facts,
        "recent_scenes": recent_scenes,
        "facts_checked": len(relevant_facts),
        "scenes_analyzed": len(recent_scenes),
    }


def validate_consistency_prompt(facts: list[dict], recent_scenes: list[dict]) -> str:
    """Build LLM prompt for consistency checking with structured format.

    构建一致性检查的 LLM prompt（D-14），包含矛盾定义、事实列表、
    近期场景内容和 JSON 输出格式要求。

    Args:
        facts: List of relevant fact dicts to check.
        recent_scenes: List of recent scene dicts.

    Returns:
        Complete prompt string for LLM consistency check.
    """
    sections = []

    # Core instruction (D-14)
    sections.append(
        "对比以下已确立事实与近期场景内容，判断是否存在逻辑矛盾。\n"
        "矛盾定义：与已确立事实直接冲突的陈述（同一时间同一地点不可能同时为真）\n"
        "非矛盾：时间推移导致的变化、角色视角差异、新信息的补充\n"
        "仅报告确信的矛盾，忽略模糊或可解释的差异"
    )

    # Phase 11: Temporal consistency check instruction (D-17)
    sections.append(
        "检查事件时序：事实中标记了 time_context 的，其因果顺序应与时间线一致。"
        "如果事实 A 发生在事实 B 之后但 time_context 更早，这是时序矛盾。"
    )

    # Facts list
    fact_lines = []
    for i, f in enumerate(facts, 1):
        actors_str = f"涉及：{'、'.join(f['actors'])}" if f.get("actors") else ""
        fact_lines.append(
            f"{i}. [{f.get('category', 'event')}] {f['fact']}（{actors_str}）"
        )
    sections.append("已确立事实：\n" + "\n".join(fact_lines))

    # Recent scenes (D-14: content truncated to first 200 chars)
    scene_lines = []
    for s in recent_scenes:
        scene_num = s.get("scene_number", s.get("scene", "?"))
        content = s.get("content", "")[:200]
        scene_lines.append(f"第{scene_num}场：{content}")
    sections.append("近期场景内容：\n" + "\n".join(scene_lines))

    # Output format
    sections.append(
        "请返回 JSON 格式：\n"
        '{"contradictions": [{"fact_id": "...", "fact_text": "...", '
        '"scene_text": "...", "explanation": "..."}], '
        '"has_contradiction": true/false}'
    )

    return "\n\n".join(sections)


def generate_repair_narration_prompt(contradiction: dict, repair_type: str) -> str:
    """Build LLM prompt for generating repair narration.

    构建矛盾修复旁白的 LLM prompt（D-20）。
    支持两种修复方式：补充式（supplement）和修正式（correction）。

    Args:
        contradiction: Contradiction dict with fact_id, fact_text, scene_text, explanation.
        repair_type: Type of repair ("supplement" or "correction").

    Returns:
        Complete prompt string for LLM repair narration generation.
    """
    if repair_type == "supplement":
        style_instruction = (
            "修复方式：补充式（用'之前未曾提及的是...'语气补充信息）\n"
            "要求：1-2 句自然旁白，补充前文未明说但合理的信息，"
            "不要直接说'这是矛盾'"
        )
    else:
        style_instruction = (
            "修复方式：修正式（用'其实...'、'原来...'语气圆回）\n"
            "要求：1-2 句自然旁白，通过视角转换或新发现让叙事自洽，"
            "不要直接说'这是矛盾'"
        )

    return (
        f"以下是一段戏剧中发现的逻辑矛盾，请生成1-2句自然的修复性旁白：\n"
        f"矛盾：事实「{contradiction.get('fact_text', '')}」"
        f"与场景描述「{contradiction.get('scene_text', '')}」冲突\n"
        f"说明：{contradiction.get('explanation', '')}\n"
        f"{style_instruction}"
    )


def repair_contradiction_logic(
    fact_id: str,
    repair_type: str,
    repair_note: str,
    state: dict,
) -> dict:
    """Repair a contradiction by appending a repair_note to the fact.

    矛盾修复逻辑——追加 repair_note 而不修改原始事实（D-22）。
    验证 repair_type 为 supplement/correction，验证 fact_id 存在性，
    更新 coherence_checks.total_contradictions 计数。

    Args:
        fact_id: The ID of the fact to repair.
        repair_type: Type of repair ("supplement" or "correction").
        repair_note: The repair note text.
        state: Drama state dict with established_facts, coherence_checks.

    Returns:
        dict with status and repair info.
    """
    # Validate repair_type
    if repair_type not in ("supplement", "correction"):
        return {
            "status": "error",
            "message": f"无效的修复方式: {repair_type}，可用：supplement, correction",
        }

    # Find fact by ID
    established_facts = state.get("established_facts", [])
    target_fact = None
    for f in established_facts:
        if f.get("id") == fact_id:
            target_fact = f
            break

    if target_fact is None:
        return {
            "status": "error",
            "message": f"事实 {fact_id} 不存在",
        }

    # Append repair_note without modifying original fact text (D-22)
    target_fact["repair_type"] = repair_type
    target_fact["repair_note"] = repair_note
    target_fact["repaired_at"] = datetime.now().isoformat()

    # Update coherence_checks counter
    coherence_checks = state.get("coherence_checks", {})
    coherence_checks["total_contradictions"] = (
        coherence_checks.get("total_contradictions", 0) + 1
    )
    state["coherence_checks"] = coherence_checks

    return {
        "status": "success",
        "fact_id": fact_id,
        "repair_type": repair_type,
        "message": "✅ 矛盾已标记修复",
    }


def parse_contradictions(response_text: str, relevant_facts: list[dict]) -> list[dict]:
    """Parse LLM response for contradiction detection results.

    解析 LLM 一致性检查响应，多层 JSON 解析 fallback（D-14/T-10-03）。
    先尝试 ```json 块提取，再 fallback 到正则匹配 JSON 对象。
    为每个 contradiction 添加 severity 字段（从对应 fact 的 importance 继承）。
    解析失败返回空列表而非崩溃。

    Args:
        response_text: Raw LLM response text.
        relevant_facts: List of relevant fact dicts for severity lookup.

    Returns:
        List of contradiction dicts with fact_id, fact_text, scene_text,
        explanation, and severity fields. Empty list on parse failure.
    """
    parsed = None

    # Strategy 1: Extract from ```json code block
    json_block_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
    if json_block_match:
        try:
            parsed = json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            parsed = None

    # Strategy 2: Regex match JSON object
    if parsed is None:
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                parsed = None

    # Parse failure: return empty list
    if parsed is None:
        return []

    # Extract contradictions
    if not parsed.get("has_contradiction", False):
        return []

    contradictions = parsed.get("contradictions", [])
    if not contradictions:
        return []

    # Build severity lookup from relevant_facts
    severity_map = {f["id"]: f.get("importance", "medium") for f in relevant_facts}

    # Add severity to each contradiction
    for c in contradictions:
        fact_id = c.get("fact_id", "")
        c["severity"] = severity_map.get(fact_id, "medium")

    return contradictions
