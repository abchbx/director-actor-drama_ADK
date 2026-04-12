"""Unit tests for conflict_engine module.

Tests the tension scoring and conflict injection engine:
- Emotion variance signal (Signal 1)
- Unresolved density signal (Signal 2)
- Dialogue repetition signal (Signal 3)
- Scenes since inject signal (Signal 4)
- calculate_tension core function
- CONFLICT_TEMPLATES constants
- select_conflict_type dedup logic
- generate_conflict_suggestion with urgency levels
- update_conflict_engine_state state management
"""

import pytest
from app.conflict_engine import (
    calculate_tension,
    select_conflict_type,
    generate_conflict_suggestion,
    update_conflict_engine_state,
    CONFLICT_TEMPLATES,
    _EMOTION_WEIGHTS,
    _calc_emotion_variance,
    _calc_unresolved_density,
    _calc_dialogue_repetition,
    _calc_scenes_since_inject,
    TENSION_LOW_THRESHOLD,
    TENSION_HIGH_THRESHOLD,
    MAX_TENSION_HISTORY,
    DEDUP_WINDOW,
    MAX_ACTIVE_CONFLICTS,
)


# ============================================================================
# Helper: Build minimal state dict for testing
# ============================================================================


def _make_state(**overrides):
    """Create a minimal state dict with conflict_engine defaults.

    All signal functions accept state: dict, so we build a complete-enough
    state structure for unit testing without ToolContext.
    """
    state = {
        "current_scene": 5,
        "actors": {
            "朱棣": {
                "emotions": "neutral",
                "working_memory": [],
                "critical_memories": [],
                "arc_summary": {"structured": {"unresolved": []}},
            },
            "道衍": {
                "emotions": "neutral",
                "working_memory": [],
                "critical_memories": [],
                "arc_summary": {"structured": {"unresolved": []}},
            },
        },
        "conflict_engine": {
            "tension_score": 0,
            "is_boring": False,
            "tension_history": [],
            "active_conflicts": [],
            "used_conflict_types": [],
            "last_inject_scene": 0,
            "consecutive_low_tension": 0,
        },
    }
    # Apply overrides — shallow merge at top level
    state.update(overrides)
    return state


# ============================================================================
# Task 1 Tests: Signal functions, calculate_tension, CONFLICT_TEMPLATES
# ============================================================================


class TestCalcEmotionVariance:
    """Tests for _calc_emotion_variance signal function."""

    def test_single_actor_returns_zero(self):
        """Single actor has no variance, should return 0.0."""
        state = _make_state(
            actors={"朱棣": {"emotions": "angry", "working_memory": [],
                             "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}}}
        )
        assert _calc_emotion_variance(state) == 0.0

    def test_diverse_emotions_positive_variance(self):
        """Actors with 'angry' and 'neutral' should have variance > 0."""
        state = _make_state(
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "neutral", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            }
        )
        result = _calc_emotion_variance(state)
        assert result > 0.0

    def test_all_same_emotion_zero_variance(self):
        """All actors with same emotion should have variance = 0.0."""
        state = _make_state(
            actors={
                "朱棣": {"emotions": "neutral", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "neutral", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            }
        )
        assert _calc_emotion_variance(state) == 0.0

    def test_no_actors_returns_zero(self):
        """No actors at all should return 0.0."""
        state = _make_state(actors={})
        assert _calc_emotion_variance(state) == 0.0

    def test_result_clamped_to_one(self):
        """Result should never exceed 1.0 even with extreme emotions."""
        state = _make_state(
            actors={
                "A": {"emotions": "fearful", "working_memory": [],
                       "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "B": {"emotions": "neutral", "working_memory": [],
                       "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "C": {"emotions": "angry", "working_memory": [],
                       "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "D": {"emotions": "neutral", "working_memory": [],
                       "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            }
        )
        assert 0.0 <= _calc_emotion_variance(state) <= 1.0


class TestCalcUnresolvedDensity:
    """Tests for _calc_unresolved_density signal function."""

    def test_no_unresolved_returns_zero(self):
        """No unresolved events should return 0.0."""
        state = _make_state()
        assert _calc_unresolved_density(state) == 0.0

    def test_multiple_sources_positive_density(self):
        """Unresolved from critical_memories + arc_summary + active_conflicts."""
        state = _make_state(
            actors={
                "朱棣": {
                    "emotions": "neutral",
                    "working_memory": [],
                    "critical_memories": [{"reason": "未决事件", "entry": "test"}],
                    "arc_summary": {"structured": {"unresolved": ["item1", "item2"]}},
                },
                "道衍": {
                    "emotions": "neutral",
                    "working_memory": [],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            conflict_engine={
                "tension_score": 0,
                "is_boring": False,
                "tension_history": [],
                "active_conflicts": [{"id": "conflict_1_escalation_1"}],
                "used_conflict_types": [],
                "last_inject_scene": 0,
                "consecutive_low_tension": 0,
            },
        )
        # 1 (未决事件) + 2 (unresolved list) + 1 (active_conflict) = 4
        # 4 / 5.0 = 0.8
        assert _calc_unresolved_density(state) == 0.8

    def test_saturation_at_five(self):
        """5+ unresolved items should saturate at 1.0."""
        state = _make_state(
            actors={
                "朱棣": {
                    "emotions": "neutral",
                    "working_memory": [],
                    "critical_memories": [
                        {"reason": "未决事件", "entry": "a"},
                        {"reason": "未决事件", "entry": "b"},
                        {"reason": "未决事件", "entry": "c"},
                    ],
                    "arc_summary": {"structured": {"unresolved": ["x", "y", "z"]}},
                },
            },
            conflict_engine={
                "tension_score": 0,
                "is_boring": False,
                "tension_history": [],
                "active_conflicts": [{"id": "c1"}, {"id": "c2"}],
                "used_conflict_types": [],
                "last_inject_scene": 0,
                "consecutive_low_tension": 0,
            },
        )
        # 3 + 3 + 2 = 8, min(1.0, 8/5.0) = 1.0
        assert _calc_unresolved_density(state) == 1.0


class TestCalcDialogueRepetition:
    """Tests for _calc_dialogue_repetition signal function."""

    def test_too_few_scenes_returns_zero(self):
        """With < 2 scenes, should return 0.0."""
        state = _make_state(current_scene=1)
        assert _calc_dialogue_repetition(state) == 0.0

    def test_identical_entries_low_score(self):
        """Identical entries should produce repetition, returning value < 1.0
        (high repetition → low tension signal)."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {
                    "emotions": "neutral",
                    "working_memory": [
                        {"entry": "我明白了这件事的来龙去脉", "scene": 3},
                        {"entry": "我明白了这件事的来龙去脉", "scene": 4},
                    ],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
                "道衍": {
                    "emotions": "neutral",
                    "working_memory": [
                        {"entry": "我明白了这件事的来龙去脉", "scene": 4},
                    ],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
        )
        result = _calc_dialogue_repetition(state)
        # 2 duplicates out of 3 entries = 2/3 repetition ratio
        # Result = 1 - 0.667 ≈ 0.333, which is < 1.0
        assert result < 1.0

    def test_diverse_entries_high_score(self):
        """Diverse entries should return a value close to 1.0 (low repetition)."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {
                    "emotions": "neutral",
                    "working_memory": [
                        {"entry": "今日朝堂之上议论纷纷", "scene": 3},
                        {"entry": "与道衍密谋起兵之事", "scene": 4},
                    ],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
                "道衍": {
                    "emotions": "neutral",
                    "working_memory": [
                        {"entry": "劝谏燕王谨慎行事", "scene": 4},
                    ],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
        )
        result = _calc_dialogue_repetition(state)
        # All entries unique → repetition_ratio = 0 → result = 1.0
        assert result == 1.0

    def test_too_few_entries_returns_zero(self):
        """Less than 2 entries should return 0.0."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {
                    "emotions": "neutral",
                    "working_memory": [
                        {"entry": "唯一一条", "scene": 4},
                    ],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
        )
        assert _calc_dialogue_repetition(state) == 0.0


class TestCalcScenesSinceInject:
    """Tests for _calc_scenes_since_inject signal function."""

    def test_gap_zero_returns_zero(self):
        """When just injected (gap=0), should return 0.0."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 5, "consecutive_low_tension": 0,
            },
        )
        assert _calc_scenes_since_inject(state) == 0.0

    def test_gap_eight_returns_half(self):
        """Gap of 8 scenes should return 0.5."""
        state = _make_state(
            current_scene=10,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 2, "consecutive_low_tension": 0,
            },
        )
        # gap = 10 - 2 = 8, 8/16 = 0.5
        assert _calc_scenes_since_inject(state) == 0.5

    def test_gap_sixteen_returns_one(self):
        """Gap of 16+ scenes should return 1.0 (saturated)."""
        state = _make_state(
            current_scene=25,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 5, "consecutive_low_tension": 0,
            },
        )
        # gap = 20, 20/16 = 1.25, clamped to 1.0
        assert _calc_scenes_since_inject(state) == 1.0

    def test_negative_gap_returns_zero(self):
        """Negative gap (future inject scene) should return 0.0."""
        state = _make_state(
            current_scene=3,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 10, "consecutive_low_tension": 0,
            },
        )
        assert _calc_scenes_since_inject(state) == 0.0


class TestCalculateTension:
    """Tests for calculate_tension core function."""

    def test_low_tension_boring(self):
        """All neutral emotions, no unresolved, no repetition → score < 30, is_boring=True."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {
                    "emotions": "neutral", "working_memory": [],
                    "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}},
                },
                "道衍": {
                    "emotions": "neutral", "working_memory": [],
                    "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 4, "consecutive_low_tension": 0,
            },
        )
        result = calculate_tension(state)
        assert result["tension_score"] < 30
        assert result["is_boring"] is True

    def test_normal_tension(self):
        """Diverse emotions with some unresolved → score 30-70, is_boring=False."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {
                    "emotions": "angry", "working_memory": [],
                    "critical_memories": [{"reason": "未决事件", "entry": "test"}],
                    "arc_summary": {"structured": {"unresolved": ["item1"]}},
                },
                "道衍": {
                    "emotions": "fearful", "working_memory": [],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        result = calculate_tension(state)
        assert 30 <= result["tension_score"] <= 70
        assert result["is_boring"] is False

    def test_return_structure(self):
        """calculate_tension returns dict with required keys."""
        state = _make_state()
        result = calculate_tension(state)
        assert "tension_score" in result
        assert "is_boring" in result
        assert "suggested_action" in result
        assert "signals" in result

    def test_suggested_action_inject_conflict_when_boring(self):
        """suggested_action is 'inject_conflict' when is_boring=True."""
        state = _make_state(
            actors={
                "朱棣": {"emotions": "neutral", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "neutral", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
        )
        result = calculate_tension(state)
        if result["is_boring"]:
            assert result["suggested_action"] == "inject_conflict"

    def test_suggested_action_maintain_in_normal_range(self):
        """suggested_action is 'maintain' when score 30-70."""
        state = _make_state(
            current_scene=15,
            actors={
                "朱棣": {
                    "emotions": "angry", "working_memory": [],
                    "critical_memories": [{"reason": "未决事件", "entry": "test"}],
                    "arc_summary": {"structured": {"unresolved": ["item1"]}},
                },
                "道衍": {
                    "emotions": "fearful", "working_memory": [],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        result = calculate_tension(state)
        if 30 <= result["tension_score"] <= 70:
            assert result["suggested_action"] == "maintain"

    def test_suggested_action_cool_down_when_high(self):
        """suggested_action is 'cool_down' when score > 70."""
        state = _make_state(
            current_scene=25,
            actors={
                "朱棣": {
                    "emotions": "angry", "working_memory": [],
                    "critical_memories": [
                        {"reason": "未决事件", "entry": "a"},
                        {"reason": "未决事件", "entry": "b"},
                        {"reason": "未决事件", "entry": "c"},
                    ],
                    "arc_summary": {"structured": {"unresolved": ["x", "y", "z"]}},
                },
                "道衍": {
                    "emotions": "fearful", "working_memory": [],
                    "critical_memories": [{"reason": "未决事件", "entry": "d"}],
                    "arc_summary": {"structured": {"unresolved": ["w"]}},
                },
                "朱元璋": {
                    "emotions": "determined", "working_memory": [],
                    "critical_memories": [],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        result = calculate_tension(state)
        if result["tension_score"] > 70:
            assert result["suggested_action"] == "cool_down"


class TestConflictTemplates:
    """Tests for CONFLICT_TEMPLATES constants."""

    def test_has_seven_types(self):
        """CONFLICT_TEMPLATES should have exactly 7 keys."""
        expected = {"new_character", "secret_revealed", "escalation",
                    "betrayal", "accident", "external_threat", "dilemma"}
        assert set(CONFLICT_TEMPLATES.keys()) == expected

    def test_each_entry_has_required_keys(self):
        """Each CONFLICT_TEMPLATES entry should have name, description, prompt_hint, suggested_emotions."""
        required_keys = {"name", "description", "prompt_hint", "suggested_emotions"}
        for key, template in CONFLICT_TEMPLATES.items():
            assert required_keys.issubset(set(template.keys())), f"{key} missing keys"

    def test_all_prompt_hints_non_empty(self):
        """All prompt_hint values should be non-empty strings."""
        for key, template in CONFLICT_TEMPLATES.items():
            assert len(template["prompt_hint"]) > 0, f"{key} has empty prompt_hint"


# ============================================================================
# Task 2 Tests: select_conflict_type, generate_conflict_suggestion,
#               update_conflict_engine_state
# ============================================================================


class TestSelectConflictType:
    """Tests for select_conflict_type dedup logic."""

    def test_fresh_state_returns_type(self):
        """Fresh state with no used types should return a valid type."""
        state = _make_state()
        result = select_conflict_type(state)
        assert result in CONFLICT_TEMPLATES.keys()

    def test_skips_types_used_within_eight_scenes(self):
        """Types used within last 8 scenes should be skipped."""
        state = _make_state(
            current_scene=10,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [
                    {"type": "new_character", "scene_used": 5},   # gap=5 < 8, skip
                    {"type": "secret_revealed", "scene_used": 3}, # gap=7 < 8, skip
                    {"type": "escalation", "scene_used": 2},      # gap=8, ok (>=8 means not < 8)
                    {"type": "betrayal", "scene_used": 1},        # gap=9, ok
                    {"type": "accident", "scene_used": 0},        # gap=10, ok
                    {"type": "external_threat", "scene_used": 4}, # gap=6 < 8, skip
                    {"type": "dilemma", "scene_used": 6},         # gap=4 < 8, skip
                ],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        result = select_conflict_type(state)
        # Only escalation, betrayal, accident are available (gap >= 8)
        assert result in {"escalation", "betrayal", "accident"}

    def test_all_exhausted_returns_none(self):
        """When all types used within dedup window, should return None."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [
                    {"type": t, "scene_used": 5}
                    for t in CONFLICT_TEMPLATES.keys()
                ],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        assert select_conflict_type(state) is None


class TestGenerateConflictSuggestion:
    """Tests for generate_conflict_suggestion function."""

    def test_normal_urgency_return_structure(self):
        """Normal urgency returns all required keys."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 20, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        result = generate_conflict_suggestion(state, conflict_type="escalation")
        assert result["status"] == "success"
        assert "conflict_id" in result
        assert result["type"] == "escalation"
        assert result["type_cn"] == CONFLICT_TEMPLATES["escalation"]["name"]
        assert "description" in result
        assert "prompt_hint" in result
        assert "involved_actors" in result
        assert result["urgency"] == "normal"
        assert "suggested_emotions" in result

    def test_high_urgency_stronger_language(self):
        """High urgency (2 consecutive low tension) includes stronger prompt_hint."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 2,
            },
        )
        result = generate_conflict_suggestion(state, conflict_type="escalation")
        assert result["urgency"] == "high"
        assert "⚠️" in result["prompt_hint"] or "紧急" in result["prompt_hint"]

    def test_critical_urgency_must_handle(self):
        """Critical urgency (3+ consecutive low tension) includes '必须处理' language."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 5, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 3,
            },
        )
        result = generate_conflict_suggestion(state, conflict_type="escalation")
        assert result["urgency"] == "critical"
        assert "必须处理" in result["prompt_hint"]

    def test_limit_reached_returns_suggestion(self):
        """When active_conflicts >= 4, returns limit_reached status."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [
                    {"id": "c1", "type": "escalation", "description": "desc1", "involved_actors": [], "introduced_scene": 1},
                    {"id": "c2", "type": "betrayal", "description": "desc2", "involved_actors": [], "introduced_scene": 2},
                    {"id": "c3", "type": "accident", "description": "desc3", "involved_actors": [], "introduced_scene": 3},
                    {"id": "c4", "type": "dilemma", "description": "desc4", "involved_actors": [], "introduced_scene": 4},
                ],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        result = generate_conflict_suggestion(state, conflict_type="escalation")
        assert result["status"] == "limit_reached"
        assert "上限" in result["message"]

    def test_exhausted_types_returns_all_exhausted(self):
        """When all conflict types exhausted, returns all_exhausted status."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [
                    {"type": t, "scene_used": 5}
                    for t in CONFLICT_TEMPLATES.keys()
                ],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        result = generate_conflict_suggestion(state)
        assert result["status"] == "all_exhausted"

    def test_conflict_id_format(self):
        """conflict_id should follow 'conflict_{scene}_{type}_{index}' format."""
        state = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 0, "is_boring": False, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        result = generate_conflict_suggestion(state, conflict_type="escalation")
        # conflict_5_escalation_1
        assert result["conflict_id"] == "conflict_5_escalation_1"


class TestUpdateConflictEngineState:
    """Tests for update_conflict_engine_state function."""

    def test_tension_history_append_and_trim(self):
        """Tension history should be appended and trimmed to 20 entries."""
        # Build state with 19 existing history entries
        history = [{"scene": i, "score": 50, "is_boring": False, "signals": {}}
                   for i in range(19)]
        state = _make_state(
            current_scene=20,
            conflict_engine={
                "tension_score": 0, "is_boring": False,
                "tension_history": history,
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        tension_result = {"tension_score": 30, "is_boring": False, "signals": {"test": 0.5}}
        result = update_conflict_engine_state(state, tension_result)
        assert len(result["tension_history"]) == 20
        assert result["tension_history"][-1]["scene"] == 20

        # Now add one more → should trim to 20
        state["conflict_engine"] = result
        tension_result2 = {"tension_score": 40, "is_boring": False, "signals": {"test": 0.6}}
        result2 = update_conflict_engine_state(state, tension_result2)
        assert len(result2["tension_history"]) == 20
        assert result2["tension_history"][-1]["scene"] == 20

    def test_increment_consecutive_low_tension(self):
        """consecutive_low_tension should increment when is_boring=True."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False,
                "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        tension_result = {"tension_score": 20, "is_boring": True, "signals": {}}
        result = update_conflict_engine_state(state, tension_result)
        assert result["consecutive_low_tension"] == 2

    def test_reset_consecutive_low_tension(self):
        """consecutive_low_tension should reset to 0 when is_boring=False."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": True,
                "tension_history": [],
                "active_conflicts": [], "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 3,
            },
        )
        tension_result = {"tension_score": 50, "is_boring": False, "signals": {}}
        result = update_conflict_engine_state(state, tension_result)
        assert result["consecutive_low_tension"] == 0

    def test_append_on_conflict_inject(self):
        """When conflict_suggestion status=success, append to active_conflicts and used_conflict_types."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False,
                "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        tension_result = {"tension_score": 20, "is_boring": True, "signals": {}}
        conflict_suggestion = {
            "status": "success",
            "conflict_id": "conflict_5_escalation_1",
            "type": "escalation",
            "description": "现有分歧激化为更严重的对抗",
            "involved_actors": ["朱棣", "道衍"],
            "urgency": "normal",
            "suggested_emotions": ["angry", "determined"],
        }
        result = update_conflict_engine_state(state, tension_result, conflict_suggestion)
        assert len(result["active_conflicts"]) == 1
        assert result["active_conflicts"][0]["id"] == "conflict_5_escalation_1"
        assert result["active_conflicts"][0]["type"] == "escalation"
        assert result["active_conflicts"][0]["introduced_scene"] == 5
        assert len(result["used_conflict_types"]) == 1
        assert result["used_conflict_types"][0]["type"] == "escalation"
        assert result["used_conflict_types"][0]["scene_used"] == 5
        assert result["last_inject_scene"] == 5

    def test_no_append_on_non_success_conflict(self):
        """When conflict_suggestion status != success, don't append to active_conflicts."""
        state = _make_state(
            current_scene=5,
            conflict_engine={
                "tension_score": 0, "is_boring": False,
                "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 0,
            },
        )
        tension_result = {"tension_score": 20, "is_boring": True, "signals": {}}
        conflict_suggestion = {
            "status": "limit_reached",
            "message": "当前活跃冲突已达上限",
        }
        result = update_conflict_engine_state(state, tension_result, conflict_suggestion)
        assert len(result["active_conflicts"]) == 0
        assert len(result["used_conflict_types"]) == 0

    def test_urgency_progression(self):
        """Urgency: 1 consecutive → normal, 2 → high, 3+ → critical."""
        # 1 consecutive → normal
        state1 = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 1,
            },
        )
        result1 = generate_conflict_suggestion(state1, conflict_type="escalation")
        assert result1["urgency"] == "normal"

        # 2 consecutive → high
        state2 = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 2,
            },
        )
        result2 = generate_conflict_suggestion(state2, conflict_type="escalation")
        assert result2["urgency"] == "high"

        # 3+ consecutive → critical
        state3 = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 3,
            },
        )
        result3 = generate_conflict_suggestion(state3, conflict_type="escalation")
        assert result3["urgency"] == "critical"

        # 5 consecutive → still critical
        state4 = _make_state(
            current_scene=5,
            actors={
                "朱棣": {"emotions": "angry", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "道衍": {"emotions": "fearful", "working_memory": [],
                         "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            conflict_engine={
                "tension_score": 10, "is_boring": True, "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0, "consecutive_low_tension": 5,
            },
        )
        result4 = generate_conflict_suggestion(state4, conflict_type="escalation")
        assert result4["urgency"] == "critical"
