"""Unit tests for Phase 5 tool functions: auto_advance, steer_drama, end_drama, trigger_storm."""

import pytest
from unittest.mock import MagicMock

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
        """trigger_storm('角色关系') returns status='success' with review guidance."""
        result = trigger_storm("角色关系", mock_tool_context)

        assert result["status"] == "success"
        assert "视角审视" in result["message"]
        assert result["focus_area"] == "角色关系"

    def test_trigger_storm_creates_storm_subdict(self, mock_tool_context_no_storm):
        """trigger_storm() does not crash when storm sub-dict doesn't exist."""
        # mock_tool_context_no_storm doesn't have 'storm' key
        result = trigger_storm("角色关系", mock_tool_context_no_storm)

        assert result["status"] == "success"
        # Should have created the storm sub-dict
        assert "storm" in mock_tool_context_no_storm.state["drama"]
