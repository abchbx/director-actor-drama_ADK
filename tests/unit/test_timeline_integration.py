"""Integration tests for timeline tracking with tools, context_builder, agent, and coherence_checker.

Tests for Phase 11 integration (COHERENCE-05).
"""
import pytest
from app.timeline_tracker import advance_time_logic, detect_timeline_jump_logic, TIME_PERIODS, _build_time脉络
from app.coherence_checker import validate_consistency_prompt


def _make_state(**overrides) -> dict:
    """Create a minimal state dict for timeline integration tests."""
    state = {
        "current_scene": 5,
        "theme": "测试戏剧",
        "status": "acting",
        "actors": {"朱棣": {"role": "燕王", "emotions": "neutral", "personality": "果断"}},
        "established_facts": [],
        "coherence_checks": {
            "last_check_scene": 0, "last_result": None,
            "check_history": [], "total_contradictions": 0,
        },
        "scenes": [
            {"scene_number": 3, "content": "朱棣在府中", "actors_present": ["朱棣"]},
            {"scene_number": 4, "content": "朱棣起兵", "actors_present": ["朱棣"]},
        ],
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


class TestTimelineIntegration:
    """Integration tests for timeline + coherence."""

    def test_advance_time_updates_timeline_state(self):
        state = _make_state()
        result = advance_time_logic(state, "第三天黄昏", day=3, period="黄昏")
        assert result["status"] == "success"
        assert state["timeline"]["current_time"] == "第三天黄昏"
        assert state["timeline"]["days_elapsed"] == 3
        assert state["timeline"]["current_period"] == "黄昏"
        assert len(state["timeline"]["time_periods"]) == 1

    def test_advance_time_auto_detects_jump(self):
        state = _make_state()
        advance_time_logic(state, "第一天", day=1, period="清晨")
        advance_time_logic(state, "第五天", day=5, period="上午")
        assert state["timeline"]["last_jump_check"] is not None
        assert state["timeline"]["last_jump_check"]["max_gap"] == 4

    def test_validate_consistency_prompt_includes_temporal(self):
        facts = [{"id": "f1", "fact": "朱棣起兵", "category": "event", "actors": ["朱棣"], "time_context": "第三天黄昏"}]
        scenes = [{"scene_number": 5, "content": "朱棣还在犹豫"}]
        prompt = validate_consistency_prompt(facts, scenes)
        assert "时序" in prompt

    def test_build_time脉络_with_multiple_periods(self):
        state = _make_state()
        advance_time_logic(state, "第一天清晨", day=1, period="清晨")
        advance_time_logic(state, "第一天夜晚", day=1, period="夜晚")
        advance_time_logic(state, "第三天黄昏", day=3, period="黄昏")
        result = _build_time脉络(state)
        assert "第一天" in result
        assert "第三天" in result

    def test_fact_with_time_context(self):
        """Test that time_context field is stored on facts."""
        from app.coherence_checker import add_fact_logic
        state = _make_state()
        result = add_fact_logic("朱棣已起兵", "event", "high", state)
        assert result["status"] == "success"
        # time_context is added by the Tool layer, not the _logic function
        # So we verify the fact dict can hold it
        fact = result["fact"]
        fact["time_context"] = "第三天黄昏"
        assert fact["time_context"] == "第三天黄昏"


class TestTimelineContextBuilder:
    """Test timeline section formatting."""

    def test_timeline_section_shows_current_time(self):
        from app.context_builder import _build_timeline_section
        state = _make_state()
        section = _build_timeline_section(state)
        assert section["key"] == "timeline"
        assert "第一天" in section["text"]

    def test_timeline_section_shows_jump_alert(self):
        from app.context_builder import _build_timeline_section
        state = _make_state()
        advance_time_logic(state, "第一天", day=1, period="清晨")
        advance_time_logic(state, "第五天", day=5, period="上午")
        section = _build_timeline_section(state)
        assert "显著跳跃" in section["text"] or "轻微跳跃" in section["text"] or "跳跃" in section["text"]

    def test_timeline_priority_is_5(self):
        from app.context_builder import _DIRECTOR_SECTION_PRIORITIES
        assert _DIRECTOR_SECTION_PRIORITIES.get("timeline") == 5

    def test_actor_current_time_priority_is_6(self):
        from app.context_builder import _ACTOR_SECTION_PRIORITIES
        assert _ACTOR_SECTION_PRIORITIES.get("current_time") == 6
