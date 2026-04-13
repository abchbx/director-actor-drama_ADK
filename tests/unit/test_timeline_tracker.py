"""Unit tests for timeline_tracker.py — timeline tracking pure functions.

TDD tests for timeline_tracker pure functions (COHERENCE-05).
"""

from app.timeline_tracker import (
    TIME_PERIODS,
    MAX_TIME_PERIODS,
    advance_time_logic,
    detect_timeline_jump_logic,
    parse_time_description,
    _chinese_num_to_int,
    _extract_period,
    _build_time脉络,
)


def _make_state(**overrides) -> dict:
    """Create a minimal state dict for testing timeline_tracker functions."""
    state = {
        "current_scene": 5,
        "actors": {
            "朱棣": {
                "role": "燕王",
                "emotions": "neutral",
            },
        },
        "established_facts": [],
        "coherence_checks": {
            "last_check_scene": 0,
            "last_result": None,
            "check_history": [],
            "total_contradictions": 0,
        },
        "scenes": [],
        "timeline": {
            "current_time": "第一天",
            "days_elapsed": 1,
            "current_period": None,
            "time_periods": [],
            "last_jump_check": None,
        },
    }
    state.update(overrides)
    return state


class TestAdvanceTimeLogic:
    """Test advance_time_logic pure function."""

    def test_full_day_period_params_updates_state(self):
        """Test 1: advance_time_logic with full day+period params updates current_time, days_elapsed, current_period, and appends to time_periods"""
        state = _make_state()
        result = advance_time_logic(state, "第三天黄昏", day=3, period="黄昏")
        assert result["status"] == "success"
        assert state["timeline"]["current_time"] == "第三天黄昏"
        assert state["timeline"]["days_elapsed"] == 3
        assert state["timeline"]["current_period"] == "黄昏"
        assert len(state["timeline"]["time_periods"]) == 1
        entry = state["timeline"]["time_periods"][0]
        assert entry["day"] == 3
        assert entry["period"] == "黄昏"
        assert entry["label"] == "第三天黄昏"
        assert entry["flashback"] is False

    def test_only_time_description_calls_parse(self):
        """Test 2: advance_time_logic with only time_description calls parse_time_description to extract day and period"""
        state = _make_state()
        result = advance_time_logic(state, "第三天黄昏")
        assert result["status"] == "success"
        assert state["timeline"]["days_elapsed"] == 3
        assert state["timeline"]["current_period"] == "黄昏"

    def test_parse_failure_still_updates_current_time(self):
        """Test 3: advance_time_logic when parse fails still updates current_time but returns status 'info' with warning"""
        state = _make_state()
        result = advance_time_logic(state, "某个无法解析的时间")
        assert result["status"] == "info"
        assert state["timeline"]["current_time"] == "某个无法解析的时间"
        assert "无法解析" in result["message"] or "⚠️" in result["message"]

    def test_flashback_marks_entry(self):
        """Test 4: advance_time_logic with flashback=True marks the time_periods entry with flashback: True"""
        state = _make_state()
        result = advance_time_logic(state, "第一天清晨", day=1, period="清晨", flashback=True)
        assert result["status"] == "success"
        entry = state["timeline"]["time_periods"][0]
        assert entry["flashback"] is True

    def test_merges_time_periods_when_exceeding_max(self):
        """Test 5: advance_time_logic merges time_periods when exceeding MAX_TIME_PERIODS=20"""
        # Create state with MAX_TIME_PERIODS entries
        periods = []
        for i in range(MAX_TIME_PERIODS):
            periods.append(
                {
                    "label": f"第{i+1}天清晨",
                    "day": i + 1,
                    "period": "清晨",
                    "scene_range": [i + 1, i + 1],
                    "flashback": False,
                }
            )
        state = _make_state()
        state["timeline"]["time_periods"] = periods
        # Add one more to trigger merge
        result = advance_time_logic(state, "第二十一天黄昏", day=21, period="黄昏")
        assert result["status"] == "success"
        # After merge, time_periods should be <= MAX_TIME_PERIODS
        assert len(state["timeline"]["time_periods"]) <= MAX_TIME_PERIODS

    def test_invalid_period_returns_error(self):
        """Test: advance_time_logic with invalid period returns error"""
        state = _make_state()
        result = advance_time_logic(state, "第三天午夜", day=3, period="午夜")
        assert result["status"] == "error"

    def test_auto_runs_jump_detection(self):
        """Test: advance_time_logic auto-runs detect_timeline_jump_logic"""
        state = _make_state()
        advance_time_logic(state, "第三天黄昏", day=3, period="黄昏")
        assert state["timeline"]["last_jump_check"] is not None


class TestParseTimeDescription:
    """Test parse_time_description function."""

    def test_day_and_period_extraction(self):
        """Test 6: parse_time_description('第三天黄昏') returns {day: 3, period: '黄昏'}"""
        result = parse_time_description("第三天黄昏")
        assert result["day"] == 3
        assert result["period"] == "黄昏"

    def test_day_only_no_period(self):
        """Test 7: parse_time_description('第一天') returns {day: 1, period: None}"""
        result = parse_time_description("第一天")
        assert result["day"] == 1
        assert result["period"] is None

    def test_large_day_number_with_period(self):
        """Test 8: parse_time_description('第九十九天深夜') returns {day: 99, period: '深夜'}"""
        result = parse_time_description("第九十九天深夜")
        assert result["day"] == 99
        assert result["period"] == "深夜"

    def test_unrecognized_text_returns_none(self):
        """Test 9: parse_time_description with unrecognized text returns {day: None, period: None}"""
        result = parse_time_description("某个时间点")
        assert result["day"] is None
        assert result["period"] is None

    def test_period_only_no_day(self):
        """Test: parse_time_description with only period, no day number"""
        result = parse_time_description("黄昏时分")
        assert result["day"] is None
        assert result["period"] == "黄昏"

    def test_various_day_numbers(self):
        """Test: parse_time_description handles various day numbers"""
        assert parse_time_description("第十天上午")["day"] == 10
        assert parse_time_description("第二十一天中午")["day"] == 21
        assert parse_time_description("第五天夜晚")["day"] == 5


class TestChineseNumToInt:
    """Test _chinese_num_to_int helper function."""

    def test_single_digits(self):
        """Test 10a: _chinese_num_to_int converts 一 through 九 correctly"""
        assert _chinese_num_to_int("一") == 1
        assert _chinese_num_to_int("二") == 2
        assert _chinese_num_to_int("三") == 3
        assert _chinese_num_to_int("四") == 4
        assert _chinese_num_to_int("五") == 5
        assert _chinese_num_to_int("六") == 6
        assert _chinese_num_to_int("七") == 7
        assert _chinese_num_to_int("八") == 8
        assert _chinese_num_to_int("九") == 9

    def test_ten(self):
        """Test 10b: _chinese_num_to_int converts 十 correctly"""
        assert _chinese_num_to_int("十") == 10

    def test_teens(self):
        """Test 10c: _chinese_num_to_int converts 十一, 十二, etc."""
        assert _chinese_num_to_int("十一") == 11
        assert _chinese_num_to_int("十二") == 12
        assert _chinese_num_to_int("十九") == 19

    def test_twenties(self):
        """Test 10d: _chinese_num_to_int converts 二十, 二十三, etc."""
        assert _chinese_num_to_int("二十") == 20
        assert _chinese_num_to_int("二十三") == 23
        assert _chinese_num_to_int("二十八") == 28

    def test_ninety_nine(self):
        """Test 10e: _chinese_num_to_int converts 九十九"""
        assert _chinese_num_to_int("九十九") == 99

    def test_unrecognized_returns_none(self):
        """Test: _chinese_num_to_int returns None for unrecognized input"""
        assert _chinese_num_to_int("零") is None
        assert _chinese_num_to_int("百") is None
        assert _chinese_num_to_int("") is None
        assert _chinese_num_to_int("abc") is None


class TestExtractPeriod:
    """Test _extract_period helper function."""

    def test_extracts_each_time_period(self):
        """Test 11: _extract_period extracts TIME_PERIODS keywords from text"""
        for period in TIME_PERIODS:
            result = _extract_period(f"第{period}的时候")
            assert result == period, f"Failed to extract '{period}'"

    def test_no_period_returns_none(self):
        """Test: _extract_period returns None when no TIME_PERIODS keyword found"""
        assert _extract_period("没有时段关键词") is None

    def test_extracts_from_full_description(self):
        """Test: _extract_period extracts from a full time description"""
        assert _extract_period("第三天黄昏") == "黄昏"
        assert _extract_period("第一天清晨") == "清晨"


class TestBuildTime脉络:
    """Test _build_time脉络 helper function."""

    def test_merges_adjacent_same_day_entries(self):
        """Test 12: _build_time脉络 merges adjacent same-day entries into range format"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第一天夜晚",
                "day": 1,
                "period": "夜晚",
                "scene_range": [2, 2],
                "flashback": False,
            },
        ]
        result = _build_time脉络(state)
        assert "第1场～第2场" in result
        assert "第一天" in result
        assert "清晨" in result
        assert "夜晚" in result

    def test_different_days_on_separate_lines(self):
        """Test: _build_time脉络 puts different-day entries on separate lines"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第三天黄昏",
                "day": 3,
                "period": "黄昏",
                "scene_range": [2, 2],
                "flashback": False,
            },
        ]
        result = _build_time脉络(state)
        lines = [line for line in result.strip().split("\n") if line.strip()]
        assert len(lines) >= 2

    def test_flashback_prefix(self):
        """Test: _build_time脉络 prefixes flashback entries with （闪回）"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": True,
            },
        ]
        result = _build_time脉络(state)
        assert "闪回" in result

    def test_empty_time_periods(self):
        """Test: _build_time脉络 returns empty string for empty time_periods"""
        state = _make_state()
        state["timeline"]["time_periods"] = []
        result = _build_time脉络(state)
        assert result == ""


class TestDetectTimelineJumpLogic:
    """Test detect_timeline_jump_logic pure function."""

    def test_no_time_periods_returns_empty(self):
        """Test 1: detect_timeline_jump_logic with no time_periods returns empty jumps list"""
        state = _make_state()
        state["timeline"]["time_periods"] = []
        result = detect_timeline_jump_logic(state)
        assert result["status"] == "success"
        assert result["jumps"] == []
        assert result["max_gap"] == 0

    def test_single_time_period_no_jumps(self):
        """Test 2: detect_timeline_jump_logic with single time_period returns no jumps"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            }
        ]
        result = detect_timeline_jump_logic(state)
        assert result["jumps"] == []
        assert result["max_gap"] == 0

    def test_same_day_period_change_normal(self):
        """Test 3: Same-day period change (day_gap=0) returns severity 'normal' — not in jumps"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第一天夜晚",
                "day": 1,
                "period": "夜晚",
                "scene_range": [2, 2],
                "flashback": False,
            },
        ]
        result = detect_timeline_jump_logic(state)
        # Normal jumps should not be in the jumps list (only minor/significant)
        normal_jumps = [j for j in result["jumps"] if j["severity"] == "normal"]
        assert len(normal_jumps) == 0

    def test_minor_jump_1_to_2_days(self):
        """Test 4: 1-2 day gap returns severity 'minor' with suggestion"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第三天黄昏",
                "day": 3,
                "period": "黄昏",
                "scene_range": [2, 2],
                "flashback": False,
            },
        ]
        result = detect_timeline_jump_logic(state)
        assert len(result["jumps"]) >= 1
        jump = result["jumps"][0]
        assert jump["severity"] == "minor"
        assert jump["day_gap"] == 2
        assert "建议" in jump["suggestion"]

    def test_significant_jump_3_plus_days(self):
        """Test 5: 3+ day gap returns severity 'significant' with suggestion"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第五天清晨",
                "day": 5,
                "period": "清晨",
                "scene_range": [2, 2],
                "flashback": False,
            },
        ]
        result = detect_timeline_jump_logic(state)
        assert len(result["jumps"]) >= 1
        jump = result["jumps"][0]
        assert jump["severity"] == "significant"
        assert jump["day_gap"] == 4
        assert "建议" in jump["suggestion"]

    def test_multiple_jumps_detected(self):
        """Test 6: Multiple jumps detected across multiple adjacent time_periods"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第三天黄昏",
                "day": 3,
                "period": "黄昏",
                "scene_range": [2, 2],
                "flashback": False,
            },
            {
                "label": "第十天清晨",
                "day": 10,
                "period": "清晨",
                "scene_range": [3, 3],
                "flashback": False,
            },
        ]
        result = detect_timeline_jump_logic(state)
        assert len(result["jumps"]) == 2
        assert result["max_gap"] == 7

    def test_flashback_entries_skipped(self):
        """Test 7: Flashback entries are skipped in jump detection"""
        state = _make_state()
        state["timeline"]["time_periods"] = [
            {
                "label": "第一天清晨",
                "day": 1,
                "period": "清晨",
                "scene_range": [1, 1],
                "flashback": False,
            },
            {
                "label": "第十天清晨",
                "day": 10,
                "period": "清晨",
                "scene_range": [2, 2],
                "flashback": True,  # Flashback — should be skipped
            },
            {
                "label": "第二天上午",
                "day": 2,
                "period": "上午",
                "scene_range": [3, 3],
                "flashback": False,
            },
        ]
        result = detect_timeline_jump_logic(state)
        # The flashback pair (day 1→10) should be skipped
        # The pair involving flashback (day 10→2) should also be skipped
        # So no significant/minor jumps should be detected
        for jump in result["jumps"]:
            assert jump["severity"] != "significant" or jump["day_gap"] < 3


class TestInitDramaStateTimeline:
    """Test init_drama_state initializes timeline fields."""

    def test_initializes_timeline_field(self):
        """Test 8: init_drama_state includes timeline field with all default values"""
        from unittest.mock import MagicMock

        from app.state_manager import init_drama_state

        tc = MagicMock()
        tc.state = {"drama": {}}
        init_drama_state("测试主题", tool_context=tc)
        state = tc.state.get("drama", {})
        tl = state.get("timeline", {})
        assert tl.get("current_time") == "第一天"
        assert tl.get("days_elapsed") == 1
        assert tl.get("current_period") is None
        assert tl.get("time_periods") == []
        assert tl.get("last_jump_check") is None


class TestLoadProgressTimeline:
    """Test load_progress backward compatibility for timeline fields."""

    def test_setdefault_timeline(self):
        """Test 9: load_progress sets default timeline for old saves missing the field"""
        import json
        import os
        from unittest.mock import MagicMock

        from app.state_manager import _ensure_drama_dirs, load_progress

        theme = "__test_timeline_load__"
        dirs = _ensure_drama_dirs(theme)

        # Create a save file WITHOUT timeline (simulating old save)
        old_state = {
            "theme": theme,
            "status": "acting",
            "current_scene": 5,
            "scenes": [],
            "actors": {},
            "narration_log": [],
            "established_facts": [],
            "coherence_checks": {
                "last_check_scene": 0,
                "last_result": None,
                "check_history": [],
                "total_contradictions": 0,
            },
        }
        state_file = os.path.join(dirs["root"], "state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(old_state, f, ensure_ascii=False)

        tc = MagicMock()
        tc.state = {"drama": {}}
        load_progress(theme, tool_context=tc)
        state = tc.state.get("drama", {})
        tl = state.get("timeline", {})
        assert tl.get("current_time") == "第一天"
        assert tl.get("days_elapsed") == 1
        assert tl.get("current_period") is None
        assert tl.get("time_periods") == []
        assert tl.get("last_jump_check") is None
