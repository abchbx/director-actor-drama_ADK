"""Dynamic STORM — periodic perspective rediscovery for drama.

动态STORM：周期性视角重新发现，基于新视角生成新冲突并扩展故事世界。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- Perspective discovery prompt construction (D-01/D-02/D-03)
- Keyword overlap dedup (D-13/D-14/D-15)
- Conflict type suggestion from perspective description (D-21)
- LLM response parsing
- State management for dynamic_storm sub-dict (D-27/D-28)
"""

import json
import re


# ============================================================================
# Constants / 常量定义
# ============================================================================

STORM_INTERVAL = 8           # Default scenes between auto-triggers (D-11)
MAX_TRIGGER_HISTORY = 10     # Max trigger history entries to keep
VIRTUAL_WORDS = ["视角", "角度", "观点", "看法", "维度", "层面"]  # Words to strip for keyword extraction (D-14)
OVERLAP_THRESHOLD = 0.6      # Keyword overlap ratio threshold (D-13)

# Keyword → conflict type mapping (D-21)
CONFLICT_KEYWORD_MAP = {
    "隐藏": "secret_revealed", "秘密": "secret_revealed",
    "矛盾": "escalation", "升级": "escalation", "对抗": "escalation",
    "背叛": "betrayal", "倒戈": "betrayal",
    "意外": "accident", "突发": "accident",
    "威胁": "external_threat", "外部": "external_threat",
    "两难": "dilemma", "抉择": "dilemma",
    "新角色": "new_character", "登场": "new_character",
}


# ============================================================================
# Core functions / 核心函数
# ============================================================================


def discover_perspectives_prompt(state: dict, focus_area: str = "") -> str:
    """Build a structured LLM prompt for perspective discovery.

    构建视角发现的 LLM prompt，包含已有视角、张力状态、活跃冲突、
    休眠线索、角色弧线进展、近期场景和世界观设定（D-01/D-02/D-03）。

    Args:
        state: Drama state dict with storm, conflict_engine, plot_threads, actors, scenes.
        focus_area: Optional area to focus the discovery on.

    Returns:
        Complete prompt string for LLM perspective generation.
    """
    storm = state.get("storm", {})
    perspectives = storm.get("perspectives", [])
    outline = storm.get("outline", {})

    conflict_engine = state.get("conflict_engine", {})
    plot_threads = state.get("plot_threads", [])
    actors = state.get("actors", {})
    scenes = state.get("scenes", [])

    sections = []

    # Core instructions (D-03)
    sections.append(
        "基于当前剧情状态，发现 1-2 个尚未被探索的新视角或新角度。\n"
        "新视角应能引入新的冲突可能性或扩展故事世界的边界。\n"
        "不要重复已有视角（已列出），也不要与已有冲突直接重叠。\n"
        "新视角必须与已发生事件一致，是扩展而非推翻。"
    )

    # 已有视角
    if perspectives:
        names = [p.get("name", "") for p in perspectives]
        sections.append(f"已有视角：{'、'.join(names)}")

    # 当前张力状态
    tension_score = conflict_engine.get("tension_score", 0)
    is_boring = conflict_engine.get("is_boring", False)
    consecutive_low = conflict_engine.get("consecutive_low_tension", 0)
    tension_info = f"当前张力：{tension_score}/100"
    if is_boring:
        tension_info += "（低张力⚠️）"
    if consecutive_low >= 2:
        tension_info += f"，连续{consecutive_low}场低迷"
    sections.append(tension_info)

    # 活跃冲突
    active_conflicts = conflict_engine.get("active_conflicts", [])
    if active_conflicts:
        conflict_descs = [f"{c.get('type', '')}({c.get('description', '')})" for c in active_conflicts]
        sections.append(f"活跃冲突：{'、'.join(conflict_descs)}")

    # 休眠线索
    dormant_threads = [t for t in plot_threads if t.get("status") == "dormant"]
    if dormant_threads:
        thread_descs = [t.get("description", "") for t in dormant_threads]
        sections.append(f"休眠线索：{'、'.join(thread_descs)}")

    # 角色弧线进展
    arc_infos = []
    for name, data in actors.items():
        arc = data.get("arc_progress", {})
        if arc.get("arc_type") and arc.get("progress", 0) > 0:
            arc_infos.append(f"{name}（{arc['arc_type']}，进展{arc['progress']}%）")
    if arc_infos:
        sections.append(f"角色弧线进展：{'、'.join(arc_infos)}")

    # 近期场景 (last 3)
    recent_scenes = scenes[-3:] if len(scenes) >= 3 else scenes
    if recent_scenes:
        scene_summaries = []
        for s in recent_scenes:
            title = s.get("title", f"第{s.get('scene', '?')}场")
            summary = s.get("summary", "")
            scene_summaries.append(f"{title}：{summary}" if summary else title)
        sections.append(f"近期场景：{'；'.join(scene_summaries)}")

    # 世界观设定
    if outline:
        title = outline.get("title", "")
        premise = outline.get("premise", "")
        if title or premise:
            outline_parts = []
            if title:
                outline_parts.append(f"标题：{title}")
            if premise:
                outline_parts.append(f"前提：{premise}")
            sections.append(f"世界观设定：{'，'.join(outline_parts)}")

    # Focus area
    if focus_area:
        sections.append(f"特别聚焦方向：{focus_area}")

    # Output format instruction
    sections.append(
        "请返回 JSON 数组格式：\n"
        '[{"name": "视角名称", "description": "视角描述", "questions": ["引导问题1", "引导问题2"]}]'
    )

    return "\n\n".join(sections)


def check_keyword_overlap(new_name: str, existing_names: list[str]) -> dict:
    """Check keyword overlap between a new perspective name and existing ones.

    检查新视角名称与已有视角名称的关键词重叠度（D-13/D-14/D-15）。
    使用 2-4 字滑动窗口提取中文关键词，去除虚词后计算重叠比。
    重叠仅产生警告，不阻止生成。

    Args:
        new_name: The new perspective name to check.
        existing_names: List of existing perspective names.

    Returns:
        dict with overlap_ratio, overlap_warning (str|None), overlapping_with (list).
    """
    def _extract_keywords(name: str) -> set[str]:
        """Extract 2-4 char Chinese segments, filtering out virtual words."""
        segments = set()
        # Sliding window: 2, 3, 4 char segments
        for length in (2, 3, 4):
            for i in range(len(name) - length + 1):
                segment = name[i:i + length]
                # Check if segment is all Chinese chars
                if re.match(r'^[\u4e00-\u9fff]+$', segment):
                    # Filter out segments that are entirely virtual words
                    if segment not in VIRTUAL_WORDS:
                        segments.add(segment)
        return segments

    new_keywords = _extract_keywords(new_name)

    if not new_keywords:
        return {"overlap_ratio": 0.0, "overlap_warning": None, "overlapping_with": []}

    overlap_ratio = 0.0
    overlapping_with = []

    for existing in existing_names:
        existing_keywords = _extract_keywords(existing)
        if not existing_keywords:
            continue
        intersection = new_keywords & existing_keywords
        if intersection:
            ratio = len(intersection) / len(new_keywords)
            if ratio > overlap_ratio:
                overlap_ratio = ratio
                overlapping_with.append(existing)

    overlap_warning = None
    if overlap_ratio > OVERLAP_THRESHOLD and overlapping_with:
        overlap_warning = f"新视角'{new_name}'与已有视角'{overlapping_with[-1]}'可能重叠"

    return {
        "overlap_ratio": overlap_ratio,
        "overlap_warning": overlap_warning,
        "overlapping_with": overlapping_with,
    }


def suggest_conflict_types(perspective_description: str) -> list[str]:
    """Suggest conflict types based on perspective description keywords.

    基于视角描述中的关键词建议冲突类型（D-21）。
    匹配 CONFLICT_KEYWORD_MAP 中的关键词，返回去重的冲突类型列表。

    Args:
        perspective_description: The perspective description text.

    Returns:
        List of matching conflict type strings (deduplicated).
    """
    matched = []
    for keyword, conflict_type in CONFLICT_KEYWORD_MAP.items():
        if keyword in perspective_description:
            matched.append(conflict_type)

    # Deduplicate preserving order
    return list(dict.fromkeys(matched))


def parse_llm_perspectives(response_text: str) -> list[dict]:
    """Parse LLM response text into structured perspective list.

    解析 LLM 返回的视角数据（支持 ```json 代码块和纯 JSON 数组）。
    验证每个视角的 name 和 description 字段，缺失字段使用默认值。
    解析失败时优雅降级，返回空列表。

    Args:
        response_text: Raw LLM response text.

    Returns:
        List of validated perspective dicts with name, description, questions.
    """
    # Try to extract JSON from ```json blocks
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
    if json_match:
        json_text = json_match.group(1).strip()
    else:
        # Try to find a JSON array directly
        array_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if array_match:
            json_text = array_match.group(0)
        else:
            json_text = response_text.strip()

    try:
        parsed = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    result = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        description = item.get("description", "")
        # Validate: name and description must be non-empty strings
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(description, str) or not description.strip():
            continue
        questions = item.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        # Ensure all questions are strings
        questions = [str(q) for q in questions if q]

        result.append({
            "name": name.strip(),
            "description": description.strip(),
            "questions": questions,
        })

    return result


# ============================================================================
# State management / 状态管理
# ============================================================================


def _init_dynamic_storm_defaults() -> dict:
    """Return default dynamic_storm sub-dict values (D-27/D-28).

    返回 dynamic_storm 子对象的默认值。
    """
    return {
        "scenes_since_last_storm": 0,
        "trigger_history": [],
        "discovered_perspectives": [],
    }


def update_dynamic_storm_state(
    state: dict,
    trigger_type: str = "",
    focus_area: str = "",
    perspectives_found: int = 0,
    new_perspectives: list | None = None,
) -> dict:
    """Update dynamic_storm state after a trigger or scene advance.

    更新 dynamic_storm 状态（D-30/D-31）。
    触发时重置计数器并记录历史，支持新增视角合并。

    Args:
        state: Drama state dict with dynamic_storm, current_scene.
        trigger_type: "auto"|"manual"|"tension_low" or empty string.
        focus_area: The focus area used for this trigger.
        perspectives_found: Number of perspectives found in this trigger.
        new_perspectives: Optional list of new perspectives to append.

    Returns:
        Updated dynamic_storm dict (caller persists to state).
    """
    # Get or init dynamic_storm sub-dict
    dynamic_storm = state.get("dynamic_storm")
    if not dynamic_storm:
        dynamic_storm = _init_dynamic_storm_defaults()

    # Ensure all fields exist (backward compatibility)
    defaults = _init_dynamic_storm_defaults()
    for key, default_val in defaults.items():
        dynamic_storm.setdefault(key, default_val)

    # If triggered, reset counter and append to history
    if trigger_type:
        dynamic_storm["scenes_since_last_storm"] = 0
        dynamic_storm["trigger_history"].append({
            "scene": state.get("current_scene", 0),
            "trigger_type": trigger_type,
            "focus_area": focus_area,
            "perspectives_found": perspectives_found,
        })
        # Trim to MAX_TRIGGER_HISTORY
        dynamic_storm["trigger_history"] = dynamic_storm["trigger_history"][-MAX_TRIGGER_HISTORY:]

    # Extend discovered_perspectives if provided
    if new_perspectives:
        dynamic_storm["discovered_perspectives"].extend(new_perspectives)

    return dynamic_storm
