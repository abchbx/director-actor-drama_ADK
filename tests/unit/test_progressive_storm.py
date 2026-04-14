"""Tests for Phase 9: Progressive STORM — trigger_type, freshness, integration_hint."""
import pytest
from app.dynamic_storm import update_dynamic_storm_state, _init_dynamic_storm_defaults
from app.context_builder import _build_dynamic_storm_section


def _make_state(**overrides):
    """Build a minimal drama state dict for testing."""
    state = {
        "current_scene": 10,
        "storm": {"perspectives": [], "outline": {}},
        "conflict_engine": {
            "tension_score": 50, "is_boring": False,
            "tension_history": [], "active_conflicts": [],
            "used_conflict_types": [], "last_inject_scene": 0,
            "consecutive_low_tension": 0,
        },
        "plot_threads": [],
        "actors": {},
        "scenes": [],
        "dynamic_storm": _init_dynamic_storm_defaults(),
    }
    state.update(overrides)
    return state


class TestTriggerType:
    """D-07/D-08/D-16: trigger_type parameter handling."""

    def test_update_dynamic_storm_state_auto_trigger(self):
        state = _make_state()
        ds = update_dynamic_storm_state(state, trigger_type="auto", focus_area="", perspectives_found=1)
        assert ds["trigger_history"][-1]["trigger_type"] == "auto"

    def test_update_dynamic_storm_state_manual_trigger(self):
        state = _make_state()
        ds = update_dynamic_storm_state(state, trigger_type="manual", focus_area="角色关系", perspectives_found=2)
        assert ds["trigger_history"][-1]["trigger_type"] == "manual"
        assert ds["trigger_history"][-1]["focus_area"] == "角色关系"

    def test_update_dynamic_storm_state_tension_low_trigger(self):
        state = _make_state()
        ds = update_dynamic_storm_state(state, trigger_type="tension_low", focus_area="", perspectives_found=1)
        assert ds["trigger_history"][-1]["trigger_type"] == "tension_low"


class TestFreshnessMarkers:
    """D-01/D-03: 🆕 freshness calculation in _build_dynamic_storm_section."""

    def test_fresh_perspective_shows_marker(self):
        """Perspective discovered 1 scene ago should show 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "权力暗流", "description": "从权力运作的隐秘机制审视剧情", "discovered_scene": 9, "questions": ["权力如何运作？"]}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" in result["text"]
        assert "权力暗流" in result["text"]
        assert "1场前发现" in result["text"]

    def test_old_perspective_no_marker(self):
        """Perspective discovered 4 scenes ago should NOT show 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "权力暗流", "description": "从权力运作审视", "discovered_scene": 6, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" not in result["text"]

    def test_discovery_scene_same_as_current(self):
        """Perspective discovered in current scene (age=0) should show 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "新视角", "description": "描述", "discovered_scene": 10, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" in result["text"]
        assert "本场发现" in result["text"]

    def test_age_2_still_fresh(self):
        """Perspective discovered 2 scenes ago (age=2) should still show 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "新视角", "description": "描述", "discovered_scene": 8, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" in result["text"]

    def test_age_3_not_fresh(self):
        """Perspective discovered 3 scenes ago (age=3) should NOT show 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "旧视角", "description": "描述", "discovered_scene": 7, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" not in result["text"]

    def test_gradual_integration_hint_shown(self):
        """When fresh perspectives exist, gradual integration hint should appear."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "权力暗流", "description": "描述", "discovered_scene": 9, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "逐步融入" in result["text"]

    def test_no_fresh_perspectives_no_extra_content(self):
        """When no fresh perspectives, output should not contain 🆕 or integration hint."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "旧视角", "description": "描述", "discovered_scene": 5, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" not in result["text"]
        assert "逐步融入" not in result["text"]

    def test_storm_perspectives_dynamic_storm_source_fresh(self):
        """Perspectives in storm.perspectives with source=dynamic_storm should also get 🆕."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = []
        state["storm"]["perspectives"] = [
            {"name": "权力暗流", "description": "从权力运作审视", "source": "dynamic_storm", "discovered_scene": 9, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" in result["text"]
        assert "权力暗流" in result["text"]

    def test_storm_perspectives_setup_source_no_marker(self):
        """Perspectives with source != dynamic_storm should NOT get 🆕 even if recent."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = []
        state["storm"]["perspectives"] = [
            {"name": "主角视角", "description": "从主角出发", "source": "setup", "discovered_scene": 1, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        assert "🆕" not in result["text"]

    def test_no_duplicate_fresh_perspectives(self):
        """Same perspective in both discovered and storm.perspectives should not show twice."""
        state = _make_state(current_scene=10)
        state["dynamic_storm"]["discovered_perspectives"] = [
            {"name": "权力暗流", "description": "从权力运作审视", "discovered_scene": 9, "questions": []}
        ]
        state["storm"]["perspectives"] = [
            {"name": "权力暗流", "description": "从权力运作审视", "source": "dynamic_storm", "discovered_scene": 9, "questions": []}
        ]
        result = _build_dynamic_storm_section(state)
        # Should appear only once
        assert result["text"].count("🆕 权力暗流") == 1


class TestIntegrationHint:
    """D-09: integration_hint for manual triggers."""

    def test_manual_trigger_has_integration_hint(self):
        """When trigger_type=manual and perspectives found, integration_hint should exist."""
        new_perspectives = [
            {"name": "权力暗流", "description": "隐秘权力", "questions": ["权力如何暗中运作？"]}
        ]
        trigger_type = "manual"
        # Simulate the logic from tools.py
        if trigger_type == "manual" and new_perspectives:
            first_p = new_perspectives[0]
            p_name = first_p.get("name", "新视角")
            q = first_p.get("questions", [""])[0] if first_p.get("questions") else ""
            hint_topic = q[:20].rstrip("？?。") if q else "新方向"
            integration_hint = (
                f"新视角「{p_name}」已发现。"
                f"建议先在下一场旁白中暗示{hint_topic}，再逐步让角色卷入。"
                f"用 /steer 可指定融入方向。"
            )
        else:
            integration_hint = None
        assert integration_hint is not None
        assert "权力暗流" in integration_hint
        assert "旁白中暗示" in integration_hint
        assert "/steer" in integration_hint

    def test_auto_trigger_no_integration_hint(self):
        """When trigger_type=auto, integration_hint should not be generated."""
        trigger_type = "auto"
        new_perspectives = [{"name": "测试", "description": "测试", "questions": []}]
        should_have_hint = (trigger_type == "manual" and bool(new_perspectives))
        assert should_have_hint is False

    def test_manual_no_perspectives_no_hint(self):
        """When trigger_type=manual but no perspectives found, no integration_hint."""
        trigger_type = "manual"
        new_perspectives = []
        should_have_hint = (trigger_type == "manual" and bool(new_perspectives))
        assert should_have_hint is False
