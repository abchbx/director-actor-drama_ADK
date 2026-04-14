"""TDD unit tests for app/dynamic_storm.py.

Tests all pure functions in the Dynamic STORM module:
- discover_perspectives_prompt()
- check_keyword_overlap()
- suggest_conflict_types()
- parse_llm_perspectives()
- _init_dynamic_storm_defaults()
- update_dynamic_storm_state()
"""

import pytest

from app.dynamic_storm import (
    CONFLICT_KEYWORD_MAP,
    MAX_TRIGGER_HISTORY,
    OVERLAP_THRESHOLD,
    STORM_INTERVAL,
    VIRTUAL_WORDS,
    _init_dynamic_storm_defaults,
    check_keyword_overlap,
    discover_perspectives_prompt,
    parse_llm_perspectives,
    suggest_conflict_types,
    update_dynamic_storm_state,
)


# ============================================================================
# Helper / 辅助函数
# ============================================================================


def _make_state(**overrides):
    """Build a test state dict with sensible defaults."""
    state = {
        "current_scene": 5,
        "storm": {
            "perspectives": [
                {"name": "主角视角", "description": "从主角立场看", "questions": ["主角想要什么?"]},
                {"name": "反派视角", "description": "从反派立场看", "questions": ["反派的动机?"]},
            ],
            "outline": {"title": "测试剧", "premise": "测试前提"},
        },
        "conflict_engine": {
            "tension_score": 25,
            "is_boring": True,
            "consecutive_low_tension": 3,
            "active_conflicts": [{"id": "c1", "type": "escalation", "description": "矛盾升级"}],
        },
        "plot_threads": [
            {"id": "t1", "description": "旧线索", "status": "dormant", "involved_actors": ["A"], "introduced_scene": 1, "last_updated_scene": 1},
        ],
        "actors": {
            "主角": {"emotions": "sad", "arc_progress": {"arc_type": "growth", "progress": 50}},
        },
        "scenes": [
            {"scene": 3, "title": "第三场", "summary": "发生了某事"},
            {"scene": 4, "title": "第四场", "summary": "又有事"},
            {"scene": 5, "title": "第五场", "summary": "继续发展"},
        ],
        "dynamic_storm": {"scenes_since_last_storm": 0, "trigger_history": [], "discovered_perspectives": []},
    }
    state.update(overrides)
    return state


# ============================================================================
# TestDiscoverPerspectivesPrompt
# ============================================================================


class TestDiscoverPerspectivesPrompt:
    """Tests for discover_perspectives_prompt()."""

    def test_prompt_contains_required_sections(self):
        """Prompt should contain 已有视角, 张力, 冲突, 休眠, 角色弧线, 近期场景."""
        state = _make_state()
        prompt = discover_perspectives_prompt(state)
        assert "已有视角" in prompt
        assert "张力" in prompt
        assert "冲突" in prompt
        assert "休眠" in prompt
        assert "弧线" in prompt
        assert "近期场景" in prompt

    def test_prompt_contains_perspective_names(self):
        """Prompt should list existing perspective names."""
        state = _make_state()
        prompt = discover_perspectives_prompt(state)
        assert "主角视角" in prompt
        assert "反派视角" in prompt

    def test_prompt_with_focus_area(self):
        """Prompt should include focus area when provided."""
        state = _make_state()
        prompt = discover_perspectives_prompt(state, focus_area="权力斗争")
        assert "权力斗争" in prompt

    def test_prompt_contains_json_format_instruction(self):
        """Prompt should instruct LLM to return JSON array."""
        state = _make_state()
        prompt = discover_perspectives_prompt(state)
        assert "JSON" in prompt or "json" in prompt
        assert '"name"' in prompt

    def test_prompt_empty_state_no_crash(self):
        """Prompt should not crash with empty state."""
        state = {}
        prompt = discover_perspectives_prompt(state)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_world_setting(self):
        """Prompt should include outline/world setting."""
        state = _make_state()
        prompt = discover_perspectives_prompt(state)
        assert "测试剧" in prompt
        assert "测试前提" in prompt


# ============================================================================
# TestCheckKeywordOverlap
# ============================================================================


class TestCheckKeywordOverlap:
    """Tests for check_keyword_overlap()."""

    def test_identical_names_high_overlap(self):
        """Identical names should return overlap_ratio >= 0.6."""
        result = check_keyword_overlap("权力博弈", ["权力博弈"])
        assert result["overlap_ratio"] >= OVERLAP_THRESHOLD

    def test_completely_different_names_low_overlap(self):
        """Completely different names should return overlap_ratio < 0.6."""
        result = check_keyword_overlap("命运交织", ["权力博弈"])
        assert result["overlap_ratio"] < OVERLAP_THRESHOLD

    def test_partial_overlap(self):
        """Partially overlapping names should return correct ratio."""
        result = check_keyword_overlap("权力暗流", ["权力博弈"])
        assert result["overlap_ratio"] > 0
        # "权力" is a shared keyword
        assert "权力博弈" in result["overlapping_with"]

    def test_virtual_words_stripped(self):
        """Virtual words should be filtered out."""
        result = check_keyword_overlap("社会视角", ["社会视角"])
        # After stripping 虚词 "视角", "社会" remains
        # The overlap check should still work on non-virtual segments
        assert isinstance(result["overlap_ratio"], float)

    def test_empty_existing_names(self):
        """Empty existing names list should return zero overlap."""
        result = check_keyword_overlap("权力博弈", [])
        assert result["overlap_ratio"] == 0.0
        assert result["overlap_warning"] is None
        assert result["overlapping_with"] == []

    def test_overlap_warning_triggered(self):
        """Overlap warning should be set when ratio exceeds threshold."""
        result = check_keyword_overlap("权力博弈与暗流", ["权力博弈"])
        if result["overlap_ratio"] > OVERLAP_THRESHOLD:
            assert result["overlap_warning"] is not None

    def test_return_structure(self):
        """Should return dict with overlap_ratio, overlap_warning, overlapping_with."""
        result = check_keyword_overlap("测试", ["测试"])
        assert "overlap_ratio" in result
        assert "overlap_warning" in result
        assert "overlapping_with" in result


# ============================================================================
# TestSuggestConflictTypes
# ============================================================================


class TestSuggestConflictTypes:
    """Tests for suggest_conflict_types()."""

    def test_secret_keyword(self):
        """'隐藏的秘密' should return ['secret_revealed']."""
        result = suggest_conflict_types("隐藏的秘密")
        assert "secret_revealed" in result

    def test_escalation_keyword(self):
        """'矛盾升级' should return ['escalation']."""
        result = suggest_conflict_types("矛盾升级")
        assert "escalation" in result

    def test_no_match_returns_empty(self):
        """Unrelated description should return empty list."""
        result = suggest_conflict_types("无关描述")
        assert result == []

    def test_multiple_matches(self):
        """Description with multiple keyword matches should return deduplicated types."""
        result = suggest_conflict_types("隐藏的秘密导致矛盾升级")
        assert "secret_revealed" in result
        assert "escalation" in result

    def test_dedup_preserves_order(self):
        """Same conflict type from multiple keywords should appear once."""
        # Both "矛盾" and "升级" map to "escalation"
        result = suggest_conflict_types("矛盾升级对抗")
        escalation_count = result.count("escalation")
        assert escalation_count == 1


# ============================================================================
# TestParseLlmPerspectives
# ============================================================================


class TestParseLlmPerspectives:
    """Tests for parse_llm_perspectives()."""

    def test_valid_json_array(self):
        """Valid JSON array should parse correctly."""
        response = '[{"name": "权力博弈", "description": "从权力运作角度", "questions": ["谁在操控?"]}]'
        result = parse_llm_perspectives(response)
        assert len(result) == 1
        assert result[0]["name"] == "权力博弈"
        assert result[0]["description"] == "从权力运作角度"
        assert result[0]["questions"] == ["谁在操控?"]

    def test_json_code_block(self):
        """```json blocks should be handled."""
        response = '```json\n[{"name": "社会暗面", "description": "社会的阴暗面", "questions": []}]\n```'
        result = parse_llm_perspectives(response)
        assert len(result) == 1
        assert result[0]["name"] == "社会暗面"

    def test_invalid_json_returns_empty(self):
        """Invalid JSON should return empty list."""
        result = parse_llm_perspectives("这不是JSON")
        assert result == []

    def test_missing_fields_get_defaults(self):
        """Perspectives with missing questions should default to empty list."""
        response = '[{"name": "测试视角", "description": "测试描述"}]'
        result = parse_llm_perspectives(response)
        assert len(result) == 1
        assert result[0]["questions"] == []

    def test_empty_name_skipped(self):
        """Perspectives with empty name should be skipped."""
        response = '[{"name": "", "description": "无名称"}]'
        result = parse_llm_perspectives(response)
        assert len(result) == 0

    def test_empty_description_skipped(self):
        """Perspectives with empty description should be skipped."""
        response = '[{"name": "有名称", "description": ""}]'
        result = parse_llm_perspectives(response)
        assert len(result) == 0

    def test_non_dict_items_skipped(self):
        """Non-dict items in the array should be skipped."""
        response = '["string", 123, {"name": "有效", "description": "有效描述"}]'
        result = parse_llm_perspectives(response)
        assert len(result) == 1
        assert result[0]["name"] == "有效"

    def test_non_array_returns_empty(self):
        """Non-array JSON should return empty list."""
        result = parse_llm_perspectives('{"name": "test"}')
        assert result == []


# ============================================================================
# TestInitDefaults
# ============================================================================


class TestInitDefaults:
    """Tests for _init_dynamic_storm_defaults()."""

    def test_returns_correct_structure(self):
        """Should return dict with all required fields (D-27)."""
        defaults = _init_dynamic_storm_defaults()
        assert "scenes_since_last_storm" in defaults
        assert "trigger_history" in defaults
        assert "discovered_perspectives" in defaults
        assert defaults["scenes_since_last_storm"] == 0
        assert defaults["trigger_history"] == []
        assert defaults["discovered_perspectives"] == []


# ============================================================================
# TestUpdateDynamicStormState
# ============================================================================


class TestUpdateDynamicStormState:
    """Tests for update_dynamic_storm_state()."""

    def test_trigger_resets_counter(self):
        """Trigger should reset scenes_since_last_storm to 0."""
        state = _make_state(dynamic_storm={"scenes_since_last_storm": 7, "trigger_history": [], "discovered_perspectives": []})
        result = update_dynamic_storm_state(state, trigger_type="auto", focus_area="权力", perspectives_found=2)
        assert result["scenes_since_last_storm"] == 0

    def test_trigger_appends_history(self):
        """Trigger should append entry to trigger_history."""
        state = _make_state(dynamic_storm={"scenes_since_last_storm": 0, "trigger_history": [], "discovered_perspectives": []})
        result = update_dynamic_storm_state(state, trigger_type="auto", focus_area="测试聚焦", perspectives_found=1)
        assert len(result["trigger_history"]) == 1
        assert result["trigger_history"][0]["trigger_type"] == "auto"
        assert result["trigger_history"][0]["focus_area"] == "测试聚焦"
        assert result["trigger_history"][0]["perspectives_found"] == 1

    def test_history_trimmed_to_max(self):
        """trigger_history should be trimmed to MAX_TRIGGER_HISTORY."""
        history = [{"scene": i, "trigger_type": "auto", "focus_area": "", "perspectives_found": 0} for i in range(15)]
        state = _make_state(dynamic_storm={"scenes_since_last_storm": 0, "trigger_history": history, "discovered_perspectives": []})
        result = update_dynamic_storm_state(state, trigger_type="auto", focus_area="", perspectives_found=0)
        assert len(result["trigger_history"]) == MAX_TRIGGER_HISTORY

    def test_new_perspectives_extend_discovered(self):
        """new_perspectives should extend discovered_perspectives list."""
        state = _make_state(dynamic_storm={"scenes_since_last_storm": 0, "trigger_history": [], "discovered_perspectives": []})
        new_p = [{"name": "新视角", "description": "新描述", "questions": []}]
        result = update_dynamic_storm_state(state, trigger_type="auto", perspectives_found=1, new_perspectives=new_p)
        assert len(result["discovered_perspectives"]) == 1
        assert result["discovered_perspectives"][0]["name"] == "新视角"

    def test_missing_dynamic_storm_auto_inits(self):
        """Missing dynamic_storm should auto-initialize."""
        state = _make_state()
        del state["dynamic_storm"]
        result = update_dynamic_storm_state(state, trigger_type="manual", focus_area="测试")
        assert "scenes_since_last_storm" in result
        assert "trigger_history" in result
        assert len(result["trigger_history"]) == 1

    def test_no_trigger_no_counter_reset(self):
        """Empty trigger_type should not reset counter or append history."""
        state = _make_state(dynamic_storm={"scenes_since_last_storm": 5, "trigger_history": [], "discovered_perspectives": []})
        result = update_dynamic_storm_state(state, trigger_type="")
        assert result["scenes_since_last_storm"] == 5
        assert len(result["trigger_history"]) == 0

    def test_constants_values(self):
        """Constants should have expected values."""
        assert STORM_INTERVAL == 8
        assert MAX_TRIGGER_HISTORY == 10
        assert OVERLAP_THRESHOLD == 0.6
        assert len(VIRTUAL_WORDS) > 0
        assert len(CONFLICT_KEYWORD_MAP) > 0
