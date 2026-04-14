"""Unit tests for Phase 5 tool functions: auto_advance, steer_drama, end_drama, trigger_storm."""

import pytest
from unittest.mock import MagicMock, patch

from app.tools import auto_advance, steer_drama, end_drama, trigger_storm, next_scene


class TestAutoAdvance:
    """Tests for auto_advance() tool function."""

    def test_auto_advance_success(self, mock_tool_context):
        """auto_advance(3) returns status='success', sets remaining_auto_scenes=3."""
        result = auto_advance(3, mock_tool_context)

        assert result["status"] == "success"
        assert "3 场" in result["message"]
        assert result["remaining_auto_scenes"] == 3
        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 3

    def test_auto_advance_soft_cap(self, mock_tool_context):
        """auto_advance(15) returns status='info', does NOT set remaining_auto_scenes."""
        # Reset to 0 first
        mock_tool_context.state["drama"]["remaining_auto_scenes"] = 0

        result = auto_advance(15, mock_tool_context)

        assert result["status"] == "info"
        assert "超过建议上限" in result["message"]
        # Should NOT have changed the counter
        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 0

    def test_auto_advance_boundary_10(self, mock_tool_context):
        """auto_advance(10) returns status='success' (boundary, 10 is allowed)."""
        result = auto_advance(10, mock_tool_context)

        assert result["status"] == "success"
        assert "10 场" in result["message"]
        assert result["remaining_auto_scenes"] == 10
        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 10


class TestSteerDrama:
    """Tests for steer_drama() tool function."""

    def test_steer_drama_success(self, mock_tool_context):
        """steer_drama('让朱棣更偏执') sets steer_direction and returns confirmation."""
        result = steer_drama("让朱棣更偏执", mock_tool_context)

        assert result["status"] == "success"
        assert "方向已设置" in result["message"]
        assert result["steer_direction"] == "让朱棣更偏执"
        assert mock_tool_context.state["drama"]["steer_direction"] == "让朱棣更偏执"


class TestEndDrama:
    """Tests for end_drama() tool function."""

    def test_end_drama_success(self, mock_tool_context):
        """end_drama() sets status='ended', returns epilogue_template."""
        result = end_drama(mock_tool_context)

        assert result["status"] == "success"
        assert "终幕已触发" in result["message"]
        assert result["drama_status"] == "ended"
        assert "epilogue_template" in result
        assert mock_tool_context.state["drama"]["status"] == "ended"

    def test_end_drama_clears_steer(self, mock_tool_context):
        """end_drama() clears steer_direction (A5 mitigation)."""
        # Set steer first
        mock_tool_context.state["drama"]["steer_direction"] = "让朱棣更偏执"

        result = end_drama(mock_tool_context)

        assert result["status"] == "success"
        assert mock_tool_context.state["drama"]["steer_direction"] is None
        # Also reset auto-advance counter
        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 0


class TestTriggerStorm:
    """Tests for trigger_storm() tool function."""

    def test_trigger_storm_success(self, mock_tool_context):
        """trigger_storm('角色关系') returns status='success' (Phase 8: now wraps dynamic_storm)."""
        result = trigger_storm("角色关系", mock_tool_context)

        assert result["status"] == "success"
        # Phase 8: trigger_storm is now a backward-compat alias for dynamic_storm
        # Message format has changed from "视角审视" to "Dynamic STORM"
        assert result["focus_area"] == "角色关系"

    def test_trigger_storm_creates_storm_subdict(self, mock_tool_context_no_storm):
        """trigger_storm() does not crash when storm sub-dict doesn't exist."""
        # mock_tool_context_no_storm doesn't have 'storm' key
        result = trigger_storm("角色关系", mock_tool_context_no_storm)

        assert result["status"] == "success"
        # Should have created the storm sub-dict
        assert "storm" in mock_tool_context_no_storm.state["drama"]


class TestNextSceneEnhancements:
    """Tests for next_scene() Phase 5 enhancements."""

    def test_next_scene_decrement_auto(self, mock_tool_context):
        """next_scene() decrements remaining_auto_scenes when > 0."""
        mock_tool_context.state["drama"]["remaining_auto_scenes"] = 3

        with patch("app.tools.advance_scene") as mock_advance, \
             patch("app.tools._extract_scene_transition") as mock_transition, \
             patch("app.tools.build_director_context") as mock_ctx:
            mock_advance.return_value = {"status": "success"}
            mock_transition.return_value = {
                "is_first_scene": False,
                "last_ending": "",
                "actor_emotions": {},
                "unresolved": [],
            }
            mock_ctx.return_value = ""

            result = next_scene(mock_tool_context)

        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 2
        assert result["auto_remaining"] == 2
        assert "自动推进中" in result["message"]
        assert "剩余 2 场" in result["message"]

    def test_next_scene_decrement_to_zero(self, mock_tool_context):
        """next_scene() decrements to 0 and shows 'manual mode' message."""
        mock_tool_context.state["drama"]["remaining_auto_scenes"] = 1

        with patch("app.tools.advance_scene") as mock_advance, \
             patch("app.tools._extract_scene_transition") as mock_transition, \
             patch("app.tools.build_director_context") as mock_ctx:
            mock_advance.return_value = {"status": "success"}
            mock_transition.return_value = {
                "is_first_scene": False,
                "last_ending": "",
                "actor_emotions": {},
                "unresolved": [],
            }
            mock_ctx.return_value = ""

            result = next_scene(mock_tool_context)

        assert mock_tool_context.state["drama"]["remaining_auto_scenes"] == 0
        assert result["auto_remaining"] == 0
        assert "回到手动模式" in result["message"]

    def test_next_scene_clears_steer(self, mock_tool_context):
        """next_scene() clears steer_direction after reading it (D-09)."""
        mock_tool_context.state["drama"]["steer_direction"] = "让朱棣更偏执"
        mock_tool_context.state["drama"]["remaining_auto_scenes"] = 0

        with patch("app.tools.advance_scene") as mock_advance, \
             patch("app.tools._extract_scene_transition") as mock_transition, \
             patch("app.tools.build_director_context") as mock_ctx:
            mock_advance.return_value = {"status": "success"}
            mock_transition.return_value = {
                "is_first_scene": False,
                "last_ending": "",
                "actor_emotions": {},
                "unresolved": [],
            }
            mock_ctx.return_value = ""

            result = next_scene(mock_tool_context)

        assert mock_tool_context.state["drama"]["steer_direction"] is None
        # Return dict should still have the steer value that was read
        assert result["steer_direction"] == "让朱棣更偏执"

    def test_next_scene_no_auto_no_steer(self, mock_tool_context):
        """next_scene() with no auto or steer returns clean result."""
        mock_tool_context.state["drama"]["remaining_auto_scenes"] = 0
        mock_tool_context.state["drama"]["steer_direction"] = None

        with patch("app.tools.advance_scene") as mock_advance, \
             patch("app.tools._extract_scene_transition") as mock_transition, \
             patch("app.tools.build_director_context") as mock_ctx:
            mock_advance.return_value = {"status": "success"}
            mock_transition.return_value = {
                "is_first_scene": False,
                "last_ending": "",
                "actor_emotions": {},
                "unresolved": [],
            }
            mock_ctx.return_value = ""

            result = next_scene(mock_tool_context)

        assert result["auto_remaining"] == 0
        assert result["steer_direction"] is None
        # No auto/steer info in message
        assert "自动推进" not in result["message"]
