"""Conflict Engine — heuristic tension scoring and conflict injection.

冲突引擎：纯启发式张力评分 + 冲突注入逻辑。
本模块不依赖 ToolContext，所有函数接收 state: dict 参数，确保可测试性。

Core components:
- 4 heuristic signals (emotion variance, unresolved density, dialogue repetition, scenes since inject)
- Weighted tension scoring (0-100)
- 7 conflict templates with dedup window
- Conflict suggestion generation with urgency escalation
- State management for conflict_engine sub-dict
"""

import random

# ============================================================================
# Constants / 常量定义
# ============================================================================

# Emotion → tension weight mapping (per CONTEXT.md D-01 specifics)
# 情绪 → 张力权重映射
_EMOTION_WEIGHTS = {
    "neutral": 1,    # 平静
    "happy": 2,      # 喜悦
    "hopeful": 2,    # 充满希望
    "confused": 2,   # 困惑
    "anxious": 3,    # 焦虑
    "sad": 4,        # 悲伤
    "determined": 4, # 决绝
    "angry": 5,      # 愤怒
    "fearful": 5,    # 恐惧
}

# Conflict templates — 7 types per D-07
# 冲突模板 — 7 种类型（D-07）
CONFLICT_TEMPLATES = {
    "new_character": {
        "name": "新角色登场",
        "description": "引入新角色打破现有格局",
        "prompt_hint": "一个陌生的身影出现在故事中——他/她的到来将打破现有的平衡",
        "suggested_emotions": ["anxious", "confused", "determined"],
    },
    "secret_revealed": {
        "name": "秘密发现",
        "description": "隐藏信息被揭露，改变角色关系",
        "prompt_hint": "一个被深藏的秘密浮出水面——真相将重新定义所有人之间的关系",
        "suggested_emotions": ["fearful", "angry", "sad"],
    },
    "escalation": {
        "name": "矛盾升级",
        "description": "现有分歧激化为更严重的对抗",
        "prompt_hint": "现有分歧已到临界点——一个小火星就可能引爆全面对抗",
        "suggested_emotions": ["angry", "determined", "fearful"],
    },
    "betrayal": {
        "name": "信任背叛",
        "description": "盟友变敌或承诺被打破",
        "prompt_hint": "曾经的盟友突然倒戈——最信任的人成为了最大的威胁",
        "suggested_emotions": ["angry", "sad", "fearful"],
    },
    "accident": {
        "name": "意外事件",
        "description": "突发状况打乱计划",
        "prompt_hint": "突如其来的变故打乱了一切——没有人预料到这个转折",
        "suggested_emotions": ["confused", "fearful", "anxious"],
    },
    "external_threat": {
        "name": "外部威胁",
        "description": "外部力量介入迫使角色联合或分裂",
        "prompt_hint": "一个更大的威胁从外部逼近——它将迫使所有人做出选择",
        "suggested_emotions": ["fearful", "anxious", "determined"],
    },
    "dilemma": {
        "name": "抉择困境",
        "description": "角色面临两难选择，无论选哪个都有代价",
        "prompt_hint": "两难困境摆在面前——无论选择哪一边，都要付出沉重的代价",
        "suggested_emotions": ["anxious", "sad", "determined"],
    },
}

# Thresholds and limits / 阈值和限制
TENSION_LOW_THRESHOLD = 30       # 低于此值为低张力（D-02）
TENSION_HIGH_THRESHOLD = 70      # 高于此值为高张力（D-02）
MAX_TENSION_HISTORY = 20         # 最多保留 20 场评分历史（D-04）
DEDUP_WINDOW = 8                 # 同类型 8 场内不重复（D-08）
MAX_ACTIVE_CONFLICTS = 4         # 活跃冲突上限（D-10）

# Signal weights / 信号权重
_SIGNAL_WEIGHTS = {
    "emotion_variance": 0.30,
    "unresolved_density": 0.30,
    "dialogue_repetition": 0.20,
    "scenes_since_inject": 0.20,
}


# ============================================================================
# Signal calculation functions / 信号计算函数
# ============================================================================


def _calc_emotion_variance(state: dict) -> float:
    """Calculate emotion variance across all actors, normalized to 0-1.

    计算所有演员情绪的方差，归一化到 0-1。
    单个或零个演员返回 0.0。用 _EMOTION_WEIGHTS 将情绪映射为数值后计算方差，
    除以理论最大方差 4.0 归一化，clamp 到 [0, 1]。

    Args:
        state: Drama state dict containing actors with emotions field.

    Returns:
        Float 0-1 representing emotion diversity. 0 = uniform, 1 = max variance.
    """
    actors = state.get("actors", {})
    if not actors:
        return 0.0

    weights = []
    for name, data in actors.items():
        emotion = data.get("emotions", "neutral")
        weights.append(_EMOTION_WEIGHTS.get(emotion, 1))

    if len(weights) < 2:
        return 0.0

    mean = sum(weights) / len(weights)
    variance = sum((w - mean) ** 2 for w in weights) / len(weights)
    # Theoretical max variance ≈ 4.0 (extreme: all at weight 5 vs all at weight 1)
    # Normalize by dividing by 4.0, clamp to [0, 1]
    return min(1.0, variance / 4.0)


def _calc_unresolved_density(state: dict) -> float:
    """Calculate unresolved conflict density, normalized to 0-1.

    计算未决冲突密度，归一化到 0-1。
    统计 critical_memories 中 reason="未决事件" + arc_summary.structured.unresolved
    + conflict_engine.active_conflicts 的总数，除以 5.0 归一化，clamp 到 [0, 1]。

    Args:
        state: Drama state dict containing actors and conflict_engine.

    Returns:
        Float 0-1 representing unresolved density. 5+ items saturate at 1.0.
    """
    unresolved_count = 0
    for name, data in state.get("actors", {}).items():
        # Count critical_memories with reason="未决事件"
        for m in data.get("critical_memories", []):
            if m.get("reason") == "未决事件":
                unresolved_count += 1
        # Count arc_summary.structured.unresolved items
        arc = data.get("arc_summary", {}).get("structured", {})
        unresolved_count += len(arc.get("unresolved", []))

    # Add active conflicts from conflict_engine
    conflict_engine = state.get("conflict_engine", {})
    unresolved_count += len(conflict_engine.get("active_conflicts", []))

    # Normalize: 5 unresolved items = "high density", saturate above 5
    return min(1.0, unresolved_count / 5.0)


def _calc_dialogue_repetition(state: dict) -> float:
    """Calculate dialogue repetition in recent 3 scenes, inverted to 0-1 tension signal.

    计算最近 3 场对话重复度，反转后返回 0-1 张力信号。
    高重复度 → 低张力信号。使用前 20 字 + 角色名作为匹配键。

    Args:
        state: Drama state dict containing actors with working_memory and current_scene.

    Returns:
        Float 0-1. High repetition → low value (low tension).
        Returns 0.0 if < 2 scenes or < 2 entries.
    """
    current_scene = state.get("current_scene", 0)
    if current_scene < 2:
        return 0.0

    # Collect working_memory entries from recent 3 scenes
    # 使用前 20 字 + 角色名作为匹配键（降低短句误判）
    recent_entries = []
    for name, data in state.get("actors", {}).items():
        for e in data.get("working_memory", [])[-5:]:
            scene = e.get("scene", 0)
            if current_scene - scene <= 3:
                entry_text = e.get("entry", "")[:20]
                if entry_text:
                    # Match key: first 20 chars + actor name
                    recent_entries.append(f"{name}:{entry_text}")

    if len(recent_entries) < 2:
        return 0.0

    # Calculate duplicate ratio
    seen = set()
    duplicates = 0
    for entry in recent_entries:
        if entry in seen:
            duplicates += 1
        seen.add(entry)

    repetition_ratio = duplicates / len(recent_entries)
    # Invert: high repetition → low tension signal
    return 1.0 - repetition_ratio


def _calc_scenes_since_inject(state: dict) -> float:
    """Calculate scenes since last conflict inject, normalized via decay function.

    计算距上次冲突注入的场景衰减值。
    gap=0 → 0.0, gap=8 → 0.5, gap=16+ → 1.0。负值返回 0.0。

    Args:
        state: Drama state dict containing conflict_engine.last_inject_scene and current_scene.

    Returns:
        Float 0-1. 0 = just injected, 1 = long gap (16+ scenes).
    """
    conflict_engine = state.get("conflict_engine", {})
    last_inject = conflict_engine.get("last_inject_scene", 0)
    current_scene = state.get("current_scene", 0)

    gap = current_scene - last_inject

    if gap <= 0:
        return 0.0

    return min(1.0, gap / 16.0)


# ============================================================================
# Core function: calculate_tension / 核心函数：张力评分
# ============================================================================


def calculate_tension(state: dict) -> dict:
    """Calculate current drama tension score based on 4 heuristic signals.

    基于启发式规则评估当前剧情张力，4 信号加权计算，无需 LLM 调用。
    返回 tension_score (0-100)、is_boring、suggested_action、signals。

    Signal weights (D-01):
    - emotion_variance: 30%
    - unresolved_density: 30%
    - dialogue_repetition: 20%
    - scenes_since_inject: 20%

    Thresholds (D-02):
    - < 30: low tension (is_boring=True)
    - 30-70: normal
    - > 70: high tension

    Args:
        state: Drama state dict with actors, conflict_engine, current_scene.

    Returns:
        dict with tension_score (int 0-100), is_boring (bool),
        suggested_action (str), signals (dict).
    """
    signals = {
        "emotion_variance": _calc_emotion_variance(state),
        "unresolved_density": _calc_unresolved_density(state),
        "dialogue_repetition": _calc_dialogue_repetition(state),
        "scenes_since_inject": _calc_scenes_since_inject(state),
    }

    score = (
        signals["emotion_variance"] * _SIGNAL_WEIGHTS["emotion_variance"]
        + signals["unresolved_density"] * _SIGNAL_WEIGHTS["unresolved_density"]
        + signals["dialogue_repetition"] * _SIGNAL_WEIGHTS["dialogue_repetition"]
        + signals["scenes_since_inject"] * _SIGNAL_WEIGHTS["scenes_since_inject"]
    )

    tension_score = int(score * 100)
    tension_score = max(0, min(100, tension_score))

    is_boring = tension_score < TENSION_LOW_THRESHOLD

    # Determine suggested_action (D-02)
    if is_boring:
        suggested_action = "inject_conflict"
    elif tension_score > TENSION_HIGH_THRESHOLD:
        suggested_action = "cool_down"
    else:
        suggested_action = "maintain"

    return {
        "tension_score": tension_score,
        "is_boring": is_boring,
        "suggested_action": suggested_action,
        "signals": signals,
    }


# ============================================================================
# Conflict selection and injection / 冲突选择与注入
# ============================================================================


def select_conflict_type(state: dict) -> str | None:
    """Select a conflict type that hasn't been used within the dedup window.

    选择一个在去重窗口内未使用过的冲突类型。
    同类型 8 场内不重复（D-08）。所有类型都在窗口内则返回 None。

    Args:
        state: Drama state dict with conflict_engine.used_conflict_types and current_scene.

    Returns:
        Conflict type string (key from CONFLICT_TEMPLATES), or None if all exhausted.
    """
    available = set(CONFLICT_TEMPLATES.keys())
    used = state.get("conflict_engine", {}).get("used_conflict_types", [])
    current_scene = state.get("current_scene", 0)

    # Remove types used within dedup window
    for entry in used:
        if current_scene - entry.get("scene_used", 0) < DEDUP_WINDOW:
            available.discard(entry.get("type"))

    if not available:
        return None

    return random.choice(list(available))


def generate_conflict_suggestion(state: dict, conflict_type: str | None = None) -> dict:
    """Generate a structured conflict suggestion for the director.

    生成结构化的冲突建议供导演参考（D-05 "导演建议"模式）。
    支持渐进升级：1场→urgency=normal，2场→urgency=high，3+场→urgency=critical（D-09）。
    活跃冲突达到上限时返回 limit_reached 建议（D-10）。

    Args:
        state: Drama state dict with actors, conflict_engine, current_scene.
        conflict_type: Optional conflict type override. If None, auto-selects via select_conflict_type.

    Returns:
        dict with status ("success"|"all_exhausted"|"limit_reached") and suggestion details.
    """
    # If no conflict_type specified, auto-select
    if conflict_type is None:
        conflict_type = select_conflict_type(state)

    # Validate conflict_type (T-06-01 mitigation)
    if conflict_type is not None and conflict_type not in CONFLICT_TEMPLATES:
        return {
            "status": "error",
            "message": f"无效的冲突类型: {conflict_type}，必须是: {', '.join(CONFLICT_TEMPLATES.keys())}",
        }

    # All types exhausted
    if conflict_type is None:
        return {
            "status": "all_exhausted",
            "message": "所有冲突类型在近8场内均已使用，建议先解决已有冲突",
            "urgency": "high",
        }

    template = CONFLICT_TEMPLATES[conflict_type]
    conflict_engine = state.get("conflict_engine", {})
    active_conflicts = conflict_engine.get("active_conflicts", [])
    consecutive_low = conflict_engine.get("consecutive_low_tension", 0)
    current_scene = state.get("current_scene", 0)

    # Determine urgency based on consecutive low tension (D-09)
    if consecutive_low >= 3:
        urgency = "critical"
    elif consecutive_low >= 2:
        urgency = "high"
    else:
        urgency = "normal"

    # Check active conflict limit (D-10)
    if len(active_conflicts) >= MAX_ACTIVE_CONFLICTS:
        # Include oldest conflict info (Pitfall 6 mitigation)
        oldest = active_conflicts[0] if active_conflicts else None
        oldest_info = ""
        if oldest:
            oldest_info = f"建议优先解决：{oldest.get('description', '未知冲突')}（已持续 {current_scene - oldest.get('introduced_scene', 0)} 场）"
        return {
            "status": "limit_reached",
            "message": f"当前活跃冲突已达上限，建议优先解决已有冲突。{oldest_info}",
            "urgency": urgency,
        }

    # Generate conflict_id (per CONTEXT.md specifics)
    conflict_id = f"conflict_{current_scene}_{conflict_type}_{len(active_conflicts) + 1}"

    # Determine involved_actors: pick 2 actors with highest emotion weights
    actors = state.get("actors", {})
    sorted_actors = sorted(
        actors.items(),
        key=lambda item: _EMOTION_WEIGHTS.get(item[1].get("emotions", "neutral"), 1),
        reverse=True,
    )
    involved_actors = [name for name, _ in sorted_actors[:2]]

    # Build prompt_hint with urgency prefix
    prompt_hint = template["prompt_hint"]
    if urgency == "high":
        prompt_hint = f"⚠️ 紧急：{prompt_hint}"
    elif urgency == "critical":
        prompt_hint = f"🚨 必须处理：{prompt_hint}"

    return {
        "status": "success",
        "conflict_id": conflict_id,
        "type": conflict_type,
        "type_cn": template["name"],
        "description": template["description"],
        "prompt_hint": prompt_hint,
        "involved_actors": involved_actors,
        "urgency": urgency,
        "suggested_emotions": template["suggested_emotions"],
    }


# ============================================================================
# State management / 状态管理
# ============================================================================


def _init_conflict_engine_defaults() -> dict:
    """Return default conflict_engine sub-dict values (D-16, D-22 Phase 7).

    返回 conflict_engine 子对象的默认值。
    """
    return {
        "tension_score": 0,
        "is_boring": False,
        "tension_history": [],
        "active_conflicts": [],
        "used_conflict_types": [],
        "last_inject_scene": 0,
        "consecutive_low_tension": 0,
        "resolved_conflicts": [],  # Phase 7 (D-22)
    }


def update_conflict_engine_state(
    state: dict,
    tension_result: dict,
    conflict_suggestion: dict | None = None,
) -> dict:
    """Update conflict_engine state based on tension result and optional conflict injection.

    更新 conflict_engine 状态。管理张力历史、连续低张力计数、
    活跃冲突列表和已用冲突类型。返回更新后的 conflict_engine 字典，
    调用者负责持久化到 state。

    State fields (D-16):
    - tension_score, is_boring: updated from tension_result
    - tension_history: appended and trimmed to MAX_TENSION_HISTORY
    - consecutive_low_tension: increment if is_boring, reset to 0 otherwise
    - active_conflicts: appended on successful conflict injection
    - used_conflict_types: appended on successful conflict injection
    - last_inject_scene: updated on successful conflict injection

    Args:
        state: Drama state dict with conflict_engine, current_scene.
        tension_result: Output from calculate_tension().
        conflict_suggestion: Optional output from generate_conflict_suggestion().

    Returns:
        Updated conflict_engine dict (caller persists to state).
    """
    # Get or init conflict_engine sub-dict
    conflict_engine = state.get("conflict_engine", {})
    if not conflict_engine:
        conflict_engine = _init_conflict_engine_defaults()

    # Ensure all fields exist (backward compatibility)
    defaults = _init_conflict_engine_defaults()
    for key, default_val in defaults.items():
        conflict_engine.setdefault(key, default_val)

    # Update tension_score and is_boring
    conflict_engine["tension_score"] = tension_result.get("tension_score", 0)
    conflict_engine["is_boring"] = tension_result.get("is_boring", False)

    # Update consecutive_low_tension
    if conflict_engine["is_boring"]:
        conflict_engine["consecutive_low_tension"] = conflict_engine.get("consecutive_low_tension", 0) + 1
    else:
        conflict_engine["consecutive_low_tension"] = 0

    # Append to tension_history
    current_scene = state.get("current_scene", 0)
    conflict_engine["tension_history"].append({
        "scene": current_scene,
        "score": tension_result.get("tension_score", 0),
        "is_boring": tension_result.get("is_boring", False),
        "signals": tension_result.get("signals", {}),
    })
    # Trim to MAX_TENSION_HISTORY (Pitfall 4 mitigation)
    conflict_engine["tension_history"] = conflict_engine["tension_history"][-MAX_TENSION_HISTORY:]

    # Handle conflict injection
    if conflict_suggestion is not None and conflict_suggestion.get("status") == "success":
        # Append to active_conflicts
        conflict_engine["active_conflicts"].append({
            "id": conflict_suggestion["conflict_id"],
            "type": conflict_suggestion["type"],
            "description": conflict_suggestion["description"],
            "involved_actors": conflict_suggestion["involved_actors"],
            "introduced_scene": current_scene,
        })
        # Append to used_conflict_types (Pitfall 3 mitigation)
        conflict_engine["used_conflict_types"].append({
            "type": conflict_suggestion["type"],
            "scene_used": current_scene,
        })
        # Update last_inject_scene
        conflict_engine["last_inject_scene"] = current_scene

    return conflict_engine


def resolve_conflict(conflict_id: str, state: dict) -> dict:
    """Resolve an active conflict by moving it to resolved_conflicts list.

    将活跃冲突标记为已解决，从 active_conflicts 移到 resolved_conflicts（D-20）。
    不删除历史——保留已解决冲突供后续 Dynamic STORM 分析。

    Args:
        conflict_id: The ID of the conflict to resolve.
        state: Drama state dict with conflict_engine.

    Returns:
        dict with status and resolved conflict info.
    """
    conflict_engine = state.get("conflict_engine", {})
    if not conflict_engine:
        conflict_engine = _init_conflict_engine_defaults()

    # Ensure resolved_conflicts exists
    conflict_engine.setdefault("resolved_conflicts", [])

    active_conflicts = conflict_engine.get("active_conflicts", [])

    # Find conflict in active list
    target_conflict = None
    for c in active_conflicts:
        if c.get("id") == conflict_id:
            target_conflict = c
            break

    if target_conflict is None:
        return {
            "status": "error",
            "message": f"冲突 {conflict_id} 不存在或已解决",
        }

    # Remove from active list
    active_conflicts.remove(target_conflict)

    # Add resolved_at_scene and move to resolved
    current_scene = state.get("current_scene", 0)
    target_conflict["resolved_at_scene"] = current_scene
    conflict_engine["resolved_conflicts"].append(target_conflict)

    # Trim resolved_conflicts to MAX_RESOLVED_CONFLICTS
    from .arc_tracker import MAX_RESOLVED_CONFLICTS
    if len(conflict_engine["resolved_conflicts"]) > MAX_RESOLVED_CONFLICTS:
        conflict_engine["resolved_conflicts"] = conflict_engine["resolved_conflicts"][-MAX_RESOLVED_CONFLICTS:]

    return {
        "status": "success",
        "conflict_id": conflict_id,
        "resolved_at_scene": current_scene,
    }
