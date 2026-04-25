"""Dynamic STORM — periodic perspective rediscovery for drama.

动态STORM：周期性视角重新发现，基于新视角生成新冲突并扩展故事世界。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- Perspective discovery prompt construction (D-01/D-02/D-03)
- Keyword overlap dedup (D-13/D-14/D-15)
- Conflict type suggestion from perspective description (D-21)
- LLM response parsing
- State management for dynamic_storm sub-dict (D-27/D-28)
- Protagonist behavior weight evaluation (P-01)
- Key choice detection & arc progress update (P-02/P-03)
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
# Protagonist Behavior Weight / 主角行为权重常量 (P-01)
# ============================================================================

# 关键行为权重等级
PROTAGONIST_WEIGHT = {
    "critical": 3,    # 决定性选择：反叛、缔结盟约、重大牺牲
    "major": 2,       # 重要行动：改变立场、揭露秘密、关键对话
    "minor": 1,       # 普通行动：日常对话、观察、小决定
    "passive": 0,     # 被动行为：旁观、沉默
}

# 关键选择关键词 → 行为权重 + 弧线影响映射 (P-02)
KEY_CHOICE_PATTERNS = {
    # 反叛类
    "反叛": {"weight": "critical", "arc_delta": 25, "arc_stage_hint": "climax", "narrative_tag": "反叛"},
    "背叛": {"weight": "critical", "arc_delta": 25, "arc_stage_hint": "climax", "narrative_tag": "背叛"},
    "反抗": {"weight": "critical", "arc_delta": 20, "arc_stage_hint": "development", "narrative_tag": "反抗"},
    "决裂": {"weight": "critical", "arc_delta": 25, "arc_stage_hint": "climax", "narrative_tag": "决裂"},
    # 盟约类
    "接受盟约": {"weight": "critical", "arc_delta": 20, "arc_stage_hint": "development", "narrative_tag": "结盟"},
    "结盟": {"weight": "critical", "arc_delta": 20, "arc_stage_hint": "development", "narrative_tag": "结盟"},
    "联盟": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "development", "narrative_tag": "结盟"},
    "拒绝": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "development", "narrative_tag": "拒绝"},
    # 抉择类
    "选择": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "development", "narrative_tag": "抉择"},
    "决定": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "development", "narrative_tag": "决定"},
    "牺牲": {"weight": "critical", "arc_delta": 25, "arc_stage_hint": "climax", "narrative_tag": "牺牲"},
    "放弃": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "development", "narrative_tag": "放弃"},
    # 揭示类
    "揭露": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "climax", "narrative_tag": "揭露"},
    "真相": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "climax", "narrative_tag": "真相揭示"},
    "坦白": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "development", "narrative_tag": "坦白"},
    # 转变类
    "转变": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "climax", "narrative_tag": "转变"},
    "觉醒": {"weight": "major", "arc_delta": 15, "arc_stage_hint": "climax", "narrative_tag": "觉醒"},
    "成长": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "development", "narrative_tag": "成长"},
    "顿悟": {"weight": "major", "arc_delta": 10, "arc_stage_hint": "climax", "narrative_tag": "顿悟"},
}

# 弧线类型推断规则 (P-03)
ARC_TYPE_INFERENCE = {
    "反叛": "transformation", "背叛": "fall", "反抗": "transformation",
    "决裂": "transformation", "结盟": "growth", "拒绝": "growth",
    "牺牲": "redemption", "揭露": "transformation", "觉醒": "growth",
    "成长": "growth", "顿悟": "growth", "转变": "transformation",
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

    # ★ 主角行为权重评估 (P-01)：在视角发现 prompt 中体现主角影响力
    protagonist_weight = evaluate_protagonist_weight(state)
    if protagonist_weight["weight_level"] != "passive":
        weight_desc = (
            f"主角行为权重：{protagonist_weight['weight_level']}"
            f"（分数{protagonist_weight['weight_score']}）"
        )
        if protagonist_weight["is_pivotal"]:
            weight_desc += "⚠️ 关键转折"
        weight_desc += f"\n{protagonist_weight['narrative_impact']}"
        # 列出关键行动
        pivotal_actions = [
            d for d in protagonist_weight["action_details"]
            if d["weight"] in ("critical", "major")
        ]
        if pivotal_actions:
            action_strs = [
                f"「{a['action'][:40]}」({a['weight']})"
                for a in pivotal_actions[:3]
            ]
            weight_desc += f"\n关键行动：{'；'.join(action_strs)}"
        sections.append(weight_desc)

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


# ============================================================================
# Protagonist Behavior Weight / 主角行为权重评估 (P-01)
# ============================================================================


def evaluate_protagonist_weight(state: dict, recent_actions: list[str] | None = None) -> dict:
    """Evaluate the protagonist's behavior weight in recent scenes.

    评估主角（用户）在近期场景中的行为权重，量化主角对剧情的影响力。
    权重越高，主角对剧情走向的决定性越强，导演应更加重视主角的意图。

    Args:
        state: Drama state dict with actors, dynamic_storm, scenes, conversation_log.
        recent_actions: Optional explicit list of recent action descriptions.
            If None, extracted from conversation_log of the current scene.

    Returns:
        dict with:
        - weight_level: "critical"|"major"|"minor"|"passive"
        - weight_score: Integer score (sum of action weights)
        - action_details: List of {action, weight, matched_keyword} dicts
        - narrative_impact: Description of protagonist's narrative influence
        - is_pivotal: True if any critical action was detected
    """
    # Extract recent actions if not provided
    if recent_actions is None:
        recent_actions = _extract_protagonist_actions(state)

    if not recent_actions:
        return {
            "weight_level": "passive",
            "weight_score": 0,
            "action_details": [],
            "narrative_impact": "主角暂无显著行动",
            "is_pivotal": False,
        }

    # Evaluate each action
    action_details = []
    total_score = 0
    has_critical = False

    for action_text in recent_actions:
        matched = _match_key_choice(action_text)
        if matched:
            weight_val = PROTAGONIST_WEIGHT[matched["weight"]]
            total_score += weight_val
            if matched["weight"] == "critical":
                has_critical = True
            action_details.append({
                "action": action_text[:100],
                "weight": matched["weight"],
                "matched_keyword": matched["keyword"],
                "narrative_tag": matched.get("narrative_tag", ""),
            })
        else:
            # Default to minor for unmatched actions
            total_score += PROTAGONIST_WEIGHT["minor"]
            action_details.append({
                "action": action_text[:100],
                "weight": "minor",
                "matched_keyword": None,
                "narrative_tag": "",
            })

    # Determine overall weight level
    if has_critical or total_score >= PROTAGONIST_WEIGHT["critical"]:
        weight_level = "critical"
    elif total_score >= PROTAGONIST_WEIGHT["major"]:
        weight_level = "major"
    elif total_score > 0:
        weight_level = "minor"
    else:
        weight_level = "passive"

    # Generate narrative impact description
    narrative_impact = _generate_narrative_impact(weight_level, action_details)

    return {
        "weight_level": weight_level,
        "weight_score": total_score,
        "action_details": action_details,
        "narrative_impact": narrative_impact,
        "is_pivotal": has_critical,
    }


def _extract_protagonist_actions(state: dict) -> list[str]:
    """Extract protagonist (user) action descriptions from conversation log.

    从对话记录中提取主角的行动描述。
    """
    conversation_log = state.get("conversation_log", [])
    current_scene = state.get("current_scene", 0)

    actions = []
    for entry in conversation_log:
        # Only look at current scene and user actions
        if entry.get("scene") != current_scene:
            continue
        if entry.get("speaker") == "主角" or entry.get("type") == "action":
            content = entry.get("content", "").strip()
            if content:
                actions.append(content)

    return actions


def _match_key_choice(action_text: str) -> dict | None:
    """Check if an action text matches any key choice pattern.

    检测行动文本是否匹配关键选择模式。
    返回第一个匹配的关键选择配置，或 None。
    """
    for keyword, config in KEY_CHOICE_PATTERNS.items():
        if keyword in action_text:
            return {"keyword": keyword, **config}
    return None


def _generate_narrative_impact(weight_level: str, action_details: list[dict]) -> str:
    """Generate a narrative impact description based on weight evaluation.

    根据权重评估生成主角叙事影响力的描述。
    """
    if weight_level == "critical":
        tags = [d["narrative_tag"] for d in action_details if d.get("narrative_tag")]
        tag_str = "、".join(set(tags)) if tags else "关键抉择"
        return f"主角做出了决定性行动（{tag_str}），剧情走向将因此发生重大转折。"
    elif weight_level == "major":
        tags = [d["narrative_tag"] for d in action_details if d.get("narrative_tag")]
        tag_str = "、".join(set(tags)) if tags else "重要行动"
        return f"主角采取了重要行动（{tag_str}），对剧情发展产生显著影响。"
    elif weight_level == "minor":
        return "主角有参与行动，但对剧情走向影响有限。"
    else:
        return "主角暂无显著行动，剧情主要由其他角色推动。"


# ============================================================================
# Key Choice Detection & Arc Progress Update / 关键选择检测与弧线更新 (P-02/P-03)
# ============================================================================


def detect_key_choice_and_update_arc(
    action_description: str,
    state: dict,
    auto_update: bool = True,
) -> dict:
    """Detect if a user action is a key choice and optionally update arc progress.

    检测用户行动是否为关键性选择，并可选地立即更新主角的 Arc Progress。
    关键选择包括：反叛、接受盟约、重大牺牲、决定性抉择等。

    当检测到关键选择时：
    1. 识别匹配的关键选择模式
    2. 计算弧线进展增量
    3. 推断弧线类型（如尚未设定）
    4. 更新弧线阶段提示
    5. 记录剧情转折标记

    Args:
        action_description: The user's action description text.
        state: Drama state dict with actors.
        auto_update: If True, immediately update the protagonist's arc_progress in state.

    Returns:
        dict with:
        - is_key_choice: Whether a key choice was detected
        - matched_patterns: List of matched {keyword, config} dicts
        - arc_update: The arc progress update applied (or would be applied)
        - narrative_tag: Combined narrative tag for the choice
        - protagonist_arc_after: Arc progress state after update (if auto_update)
    """
    matched_patterns = []

    # Scan for key choice keywords
    for keyword, config in KEY_CHOICE_PATTERNS.items():
        if keyword in action_description:
            matched_patterns.append({"keyword": keyword, **config})

    if not matched_patterns:
        return {
            "is_key_choice": False,
            "matched_patterns": [],
            "arc_update": None,
            "narrative_tag": "",
            "protagonist_arc_after": None,
        }

    # Calculate combined arc delta
    total_arc_delta = sum(p["arc_delta"] for p in matched_patterns)
    # Cap at 100
    total_arc_delta = min(total_arc_delta, 100)

    # Determine the dominant (highest delta) pattern for stage/type inference
    dominant = max(matched_patterns, key=lambda p: p["arc_delta"])
    arc_stage_hint = dominant["arc_stage_hint"]
    narrative_tags = list(dict.fromkeys(p["narrative_tag"] for p in matched_patterns if p.get("narrative_tag")))
    narrative_tag = "、".join(narrative_tags)

    # Infer arc_type from dominant keyword
    arc_type_hint = ARC_TYPE_INFERENCE.get(dominant["keyword"], "")

    # Build arc update specification
    arc_update = {
        "progress_delta": total_arc_delta,
        "arc_stage_hint": arc_stage_hint,
        "arc_type_hint": arc_type_hint,
        "narrative_tag": narrative_tag,
    }

    # Apply update to protagonist's arc_progress if auto_update
    protagonist_arc_after = None
    if auto_update:
        protagonist_arc_after = _apply_arc_update_to_protagonist(state, arc_update, action_description)

    return {
        "is_key_choice": True,
        "matched_patterns": matched_patterns,
        "arc_update": arc_update,
        "narrative_tag": narrative_tag,
        "protagonist_arc_after": protagonist_arc_after,
    }


def _apply_arc_update_to_protagonist(state: dict, arc_update: dict, action_description: str) -> dict | None:
    """Apply arc progress update to the protagonist ("你") in state.

    将弧线进展更新应用到主角"你"的 arc_progress。
    仅在字段为空或进度更低时更新，不会降级已有设定。

    Args:
        state: Drama state dict with actors (mutated in-place).
        arc_update: Arc update specification from detect_key_choice_and_update_arc.
        action_description: The original action text (for related_threads context).

    Returns:
        Updated arc_progress dict, or None if protagonist not found.
    """
    actors = state.get("actors", {})
    protagonist = actors.get("你")
    if not protagonist:
        return None

    arc_progress = protagonist.get("arc_progress", {})
    if not arc_progress:
        arc_progress = {
            "arc_type": "",
            "arc_stage": "",
            "progress": 0,
            "related_threads": [],
        }

    # Update progress (additive, capped at 100)
    current_progress = arc_progress.get("progress", 0)
    new_progress = min(100, current_progress + arc_update["progress_delta"])
    arc_progress["progress"] = new_progress

    # Set arc_type only if currently empty
    if not arc_progress.get("arc_type") and arc_update.get("arc_type_hint"):
        arc_progress["arc_type"] = arc_update["arc_type_hint"]

    # Update arc_stage to hint if progress warrants advancement
    if arc_update.get("arc_stage_hint"):
        stage_order = ["setup", "development", "climax", "resolution"]
        current_stage = arc_progress.get("arc_stage", "")
        hint_stage = arc_update["arc_stage_hint"]
        # Only advance, never regress
        if not current_stage or (
            hint_stage in stage_order
            and stage_order.index(hint_stage) > stage_order.index(current_stage)
            if current_stage in stage_order else True
        ):
            arc_progress["arc_stage"] = hint_stage

    # Add action to related_threads as a narrative marker
    related = arc_progress.get("related_threads", [])
    marker = f"[转折] {action_description[:60]}"
    if marker not in related:
        related.append(marker)
        # Keep within reasonable bounds
        arc_progress["related_threads"] = related[-10:]

    # Write back
    protagonist["arc_progress"] = arc_progress
    state["actors"] = actors

    return arc_progress


# ============================================================================
# Scene Summary Protagonist Tracking / 场景总结主角追踪 (P-04)
# ============================================================================


def build_protagonist_contribution_summary(state: dict) -> dict:
    """Build a summary of the protagonist's contributions and plot turning points for the current scene.

    构建当前场景中主角的贡献和剧情重大转折的摘要。
    供 write_scene 调用，确保每次场景结束时准确记录主角的贡献。

    Args:
        state: Drama state dict with actors, conversation_log, current_scene.

    Returns:
        dict with:
        - protagonist_actions: List of protagonist actions in this scene
        - key_choices: List of key choices detected
        - weight_level: Overall protagonist weight level
        - narrative_impact: Description of protagonist's narrative influence
        - turning_points: List of plot turning points caused by protagonist
        - arc_progress_snapshot: Current arc progress of the protagonist
    """
    # Evaluate protagonist weight
    weight_result = evaluate_protagonist_weight(state)

    # Extract protagonist actions
    actions = _extract_protagonist_actions(state)

    # Detect key choices from actions
    key_choices = []
    turning_points = []
    for action_text in actions:
        match = _match_key_choice(action_text)
        if match:
            key_choices.append({
                "action": action_text[:100],
                "keyword": match["keyword"],
                "weight": match["weight"],
                "narrative_tag": match.get("narrative_tag", ""),
            })
            if match["weight"] == "critical":
                turning_points.append({
                    "type": "major_turning_point",
                    "description": action_text[:100],
                    "keyword": match["keyword"],
                    "narrative_tag": match.get("narrative_tag", ""),
                })
            elif match["weight"] == "major":
                turning_points.append({
                    "type": "minor_turning_point",
                    "description": action_text[:100],
                    "keyword": match["keyword"],
                    "narrative_tag": match.get("narrative_tag", ""),
                })

    # Get protagonist arc progress snapshot
    actors = state.get("actors", {})
    protagonist = actors.get("你", {})
    arc_snapshot = protagonist.get("arc_progress", {})

    return {
        "protagonist_actions": actions,
        "key_choices": key_choices,
        "weight_level": weight_result["weight_level"],
        "narrative_impact": weight_result["narrative_impact"],
        "turning_points": turning_points,
        "arc_progress_snapshot": arc_snapshot,
    }
