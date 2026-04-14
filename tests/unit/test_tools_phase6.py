"""Unit tests for Phase 6 tool functions: evaluate_tension, inject_conflict,
and state_manager conflict_engine initialization/compatibility."""

import pytest
from unittest.mock import MagicMock, patch

from app.tools import evaluate_tension, inject_conflict
from app.state_manager import init_drama_state, load_progress, _get_state, _set_state


class TestEvaluateTensionTool:
    """Tests for evaluate_tension() tool function."""

    def test_neutral_state_returns_low_tension(self, mock_tool_context):
        """evaluate_tension with neutral state returns tension_score < 30, is_boring=True."""
        # mock_tool_context has a single actor with neutral emotion and no conflicts
        result = evaluate_tension(mock_tool_context)

        assert result["status"] == "success"
        assert result["tension_score"] < 30
        assert result["is_boring"] is True
        assert "tension_score" in result
        assert "is_boring" in result
        assert "suggested_action" in result
        assert "signals" in result

    def test_updates_state_tension_score_and_is_boring(self, mock_tool_context):
        """evaluate_tension updates state['conflict_engine']['tension_score'] and ['is_boring']."""
        # Ensure conflict_engine doesn't exist initially
        mock_tool_context.state["drama"].pop("conflict_engine", None)

        result = evaluate_tension(mock_tool_context)

        ce = mock_tool_context.state["drama"]["conflict_engine"]
        assert ce["tension_score"] == result["tension_score"]
        assert ce["is_boring"] == result["is_boring"]

    def test_updates_tension_history(self, mock_tool_context):
        """evaluate_tension appends to tension_history."""
        mock_tool_context.state["drama"].pop("conflict_engine", None)

        result = evaluate_tension(mock_tool_context)

        ce = mock_tool_context.state["drama"]["conflict_engine"]
        assert len(ce["tension_history"]) == 1
        assert ce["tension_history"][0]["scene"] == mock_tool_context.state["drama"]["current_scene"]
        assert ce["tension_history"][0]["score"] == result["tension_score"]


class TestInjectConflictTool:
    """Tests for inject_conflict() tool function."""

    def test_auto_selects_conflict_type(self, mock_tool_context):
        """inject_conflict without conflict_type auto-selects a type."""
        result = inject_conflict(None, mock_tool_context)

        assert result["status"] == "success"
        assert "type" in result
        assert "type_cn" in result
        assert "description" in result
        assert "prompt_hint" in result
        assert "involved_actors" in result
        assert "urgency" in result

    def test_explicit_conflict_type(self, mock_tool_context):
        """inject_conflict with explicit conflict_type uses that type."""
        result = inject_conflict("betrayal", mock_tool_context)

        assert result["status"] == "success"
        assert result["type"] == "betrayal"
        assert "信任背叛" in result["type_cn"]

    def test_invalid_conflict_type_returns_error(self, mock_tool_context):
        """inject_conflict with invalid conflict_type returns error."""
        result = inject_conflict("invalid_type", mock_tool_context)

        assert result["status"] == "error"
        assert "无效的冲突类型" in result["message"]

    def test_updates_used_conflict_types_and_active_conflicts(self, mock_tool_context):
        """inject_conflict updates used_conflict_types and active_conflicts in state."""
        mock_tool_context.state["drama"].pop("conflict_engine", None)

        result = inject_conflict("escalation", mock_tool_context)

        assert result["status"] == "success"
        ce = mock_tool_context.state["drama"]["conflict_engine"]
        assert len(ce["used_conflict_types"]) == 1
        assert ce["used_conflict_types"][0]["type"] == "escalation"
        assert len(ce["active_conflicts"]) == 1
        assert ce["active_conflicts"][0]["type"] == "escalation"

    def test_all_types_exhausted(self, mock_tool_context):
        """inject_conflict when all types exhausted returns all_exhausted status."""
        # Mark all types as used within the dedup window
        from app.conflict_engine import CONFLICT_TEMPLATES
        current_scene = mock_tool_context.state["drama"]["current_scene"]

        mock_tool_context.state["drama"]["conflict_engine"] = {
            "tension_score": 0,
            "is_boring": True,
            "tension_history": [],
            "active_conflicts": [],
            "used_conflict_types": [
                {"type": t, "scene_used": current_scene}
                for t in CONFLICT_TEMPLATES.keys()
            ],
            "last_inject_scene": 0,
            "consecutive_low_tension": 1,
        }

        result = inject_conflict(None, mock_tool_context)

        assert result["status"] == "all_exhausted"


class TestConflictEngineInit:
    """Tests for conflict_engine initialization in state_manager."""

    def test_init_drama_state_creates_conflict_engine(self, mock_tool_context):
        """init_drama_state creates conflict_engine sub-dict with all 7 default fields."""
        init_drama_state("张力测试剧", mock_tool_context)

        state = _get_state(mock_tool_context)
        assert "conflict_engine" in state
        ce = state["conflict_engine"]
        expected_keys = {
            "tension_score", "is_boring", "tension_history",
            "active_conflicts", "used_conflict_types",
            "last_inject_scene", "consecutive_low_tension",
            "resolved_conflicts",  # Phase 7
        }
        assert set(ce.keys()) == expected_keys
        assert ce["tension_score"] == 0
        assert ce["is_boring"] is False
        assert ce["tension_history"] == []
        assert ce["active_conflicts"] == []
        assert ce["used_conflict_types"] == []
        assert ce["last_inject_scene"] == 0
        assert ce["consecutive_low_tension"] == 0

    def test_load_progress_compatibility(self, mock_tool_context_old_format):
        """load_progress with old save (no conflict_engine) auto-initializes defaults."""
        # First, save state with old format (no conflict_engine)
        # We need to set up a save file for load_progress
        import json
        import os
        from app.state_manager import DRAMAS_DIR, _sanitize_name, _ensure_drama_dirs

        theme = "旧格式戏剧"
        dirs = _ensure_drama_dirs(theme)
        state_file = os.path.join(dirs["root"], "state.json")

        # Write old format state (no conflict_engine)
        old_state = {
            "theme": theme,
            "status": "acting",
            "current_scene": 5,
            "scenes": [],
            "actors": {
                "朱元璋": {
                    "role": "皇帝",
                    "personality": "威严果断",
                    "background": "大明开国皇帝",
                    "knowledge_scope": "天下大事",
                    "memory": [],
                    "working_memory": [],
                    "scene_summaries": [],
                    "arc_summary": {"structured": {}, "narrative": ""},
                    "critical_memories": [],
                    "emotions": "angry",
                }
            },
            "narration_log": [],
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(old_state, f, ensure_ascii=False, indent=2)

        # Load the old format state
        result = load_progress(theme, mock_tool_context_old_format)

        assert result["status"] == "success"
        state = _get_state(mock_tool_context_old_format)
        assert "conflict_engine" in state
        ce = state["conflict_engine"]
        assert ce["tension_score"] == 0
        assert ce["is_boring"] is False
        assert ce["tension_history"] == []
        assert ce["active_conflicts"] == []
        assert ce["used_conflict_types"] == []
        assert ce["last_inject_scene"] == 0
        assert ce["consecutive_low_tension"] == 0
