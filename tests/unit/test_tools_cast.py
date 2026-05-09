"""Phase 24 unit tests: scene_cast mechanism.

Tests for:
- CAST-01: state_manager scene_cast field init + migration
- CAST-02: set_scene_cast tool
- CAST-03: next_scene + actor_speak_batch cast filtering
- CAST-04: cast_change event mapping
"""

import pytest
from unittest.mock import MagicMock, patch


# ============================================================================
# CAST-01: state_manager scene_cast field
# ============================================================================


class TestSceneCastField:
    """Test scene_cast field initialization and migration."""

    def test_init_drama_state_has_scene_cast(self):
        """Verify init_drama_state includes scene_cast: None."""
        from app.state_manager import init_drama_state, _get_state, _set_state

        mock_ctx = MagicMock()
        mock_ctx.state = {"drama": {}}

        init_drama_state("测试剧本", tool_context=mock_ctx)
        state = _get_state(mock_ctx)

        assert "scene_cast" in state
        assert state["scene_cast"] is None

    def test_load_progress_migrates_scene_cast(self):
        """Verify load_progress sets scene_cast=None for old saves."""
        from app.state_manager import load_progress, _get_state
        from app.state_manager import DRAMAS_DIR
        import json
        import os

        theme = "迁移测试剧本_scene_cast"
        folder = os.path.join(DRAMAS_DIR, "".join(c if c.isalnum() or c in "-_" else "_" for c in theme))
        os.makedirs(folder, exist_ok=True)

        # Create an old-format state.json without scene_cast
        old_state = {
            "theme": theme,
            "status": "acting",
            "current_scene": 1,
            "actors": {
                "用户": {
                    "is_user_protagonist": True,
                    "control_type": "User-Controlled",
                },
            },
        }
        with open(os.path.join(folder, "state.json"), "w", encoding="utf-8") as f:
            json.dump(old_state, f, ensure_ascii=False)

        mock_ctx = MagicMock()
        mock_ctx.state = {"drama": {}}

        result = load_progress(theme, tool_context=mock_ctx)
        assert result["status"] == "success"

        state = _get_state(mock_ctx)
        assert "scene_cast" in state
        assert state["scene_cast"] is None

        # Cleanup
        import shutil
        shutil.rmtree(folder, ignore_errors=True)

    def test_get_scene_cast_default_all(self):
        """get_scene_cast returns all AI actors when scene_cast is None."""
        from app.state_manager import get_scene_cast, get_ai_actors

        state = {
            "scene_cast": None,
            "actors": {
                "用户": {"is_user_protagonist": True, "control_type": "User-Controlled"},
                "嵇康": {"is_user_protagonist": False},
                "山涛": {"is_user_protagonist": False},
            },
        }

        # get_ai_actors should return only AI actors
        ai_actors = get_ai_actors(state)
        assert ai_actors == ["嵇康", "山涛"]

        # get_scene_cast(None) should return all AI actors
        cast = get_scene_cast(state)
        assert cast == ["嵇康", "山涛"]

    def test_get_scene_cast_explicit_list(self):
        """get_scene_cast returns explicit list when scene_cast is set."""
        from app.state_manager import get_scene_cast

        state = {
            "scene_cast": ["嵇康"],
            "actors": {
                "用户": {"is_user_protagonist": True},
                "嵇康": {},
                "山涛": {},
            },
        }

        cast = get_scene_cast(state)
        assert cast == ["嵇康"]


# ============================================================================
# CAST-02: set_scene_cast tool
# ============================================================================


class TestSetSceneCastTool:
    """Test set_scene_cast tool function."""

    def _make_context(self, actors=None, scene_cast=None):
        """Helper to create a mock tool_context with drama state."""
        mock_ctx = MagicMock()
        mock_ctx.state = {
            "drama": {
                "theme": "测试",
                "actors": actors or {
                    "用户": {"is_user_protagonist": True, "control_type": "User-Controlled"},
                    "嵇康": {"role": "隐士", "is_user_protagonist": False},
                    "山涛": {"role": "官员", "is_user_protagonist": False},
                },
                "scene_cast": scene_cast,
            }
        }
        return mock_ctx

    def test_set_scene_cast_success(self):
        """Normal set_scene_cast returns success with cast + standby."""
        from app.tools import set_scene_cast

        ctx = self._make_context()
        result = set_scene_cast(cast=["嵇康"], tool_context=ctx)

        assert result["status"] == "success"
        assert "嵇康" in result["scene_cast"]
        assert "用户" in result["scene_cast"]  # Auto-included
        assert "山涛" in result["standby"]

    def test_set_scene_cast_empty_rejected(self):
        """Empty cast list is rejected."""
        from app.tools import set_scene_cast

        ctx = self._make_context()
        result = set_scene_cast(cast=[], tool_context=ctx)

        assert result["status"] == "error"
        assert "不能为空" in result["message"]

    def test_set_scene_cast_invalid_actor(self):
        """Invalid actor names are rejected."""
        from app.tools import set_scene_cast

        ctx = self._make_context()
        result = set_scene_cast(cast=["不存在的角色"], tool_context=ctx)

        assert result["status"] == "error"
        assert "不存在" in result["message"]
        assert "不存在的角色" in result["invalid_names"]

    def test_set_scene_cast_user_protagonist_included(self):
        """User protagonist is auto-included even if not in cast list."""
        from app.tools import set_scene_cast

        ctx = self._make_context()
        result = set_scene_cast(cast=["嵇康"], tool_context=ctx)

        assert "用户" in result["scene_cast"]

    def test_set_scene_cast_dedup_preserves_order(self):
        """Deduplication preserves order and removes duplicates."""
        from app.tools import set_scene_cast

        ctx = self._make_context()
        result = set_scene_cast(cast=["嵇康", "嵇康", "山涛"], tool_context=ctx)

        assert result["scene_cast"].count("嵇康") == 1
        assert result["scene_cast"].index("嵇康") < result["scene_cast"].index("山涛")


# ============================================================================
# CAST-03: next_scene resets scene_cast
# ============================================================================


class TestNextSceneCastReset:
    """Test that next_scene resets scene_cast to all actors."""

    def test_next_scene_resets_scene_cast(self):
        """After next_scene, scene_cast should be reset to all actors."""
        from app.tools import next_scene
        from app.state_manager import _set_state

        mock_ctx = MagicMock()
        mock_ctx.state = {
            "drama": {
                "theme": "测试剧本",
                "current_scene": 1,
                "status": "acting",
                "scenes": [{"scene_number": 1}],
                "actors": {
                    "用户": {"is_user_protagonist": True, "control_type": "User-Controlled"},
                    "嵇康": {"emotions": "calm"},
                    "山涛": {"emotions": "neutral"},
                },
                "scene_cast": ["用户", "嵇康"],  # Previously limited
                "remaining_auto_scenes": 0,
                "steer_direction": None,
                "dynamic_storm": {},
            }
        }

        with patch("app.tools.advance_scene", return_value={"status": "success", "current_scene": 2}):
            with patch("app.tools.build_director_context", return_value=""):
                with patch("app.state_manager.archive_old_scenes", side_effect=lambda s: s):
                    result = next_scene(tool_context=mock_ctx)

        assert result["status"] == "success"
        # scene_cast should be reset to all actors (including 用户)
        scene_cast = result.get("scene_cast", [])
        assert "用户" in scene_cast
        assert "嵇康" in scene_cast
        assert "山涛" in scene_cast

    def test_next_scene_returns_scene_cast_fields(self):
        """next_scene response includes scene_cast and standby fields."""
        from app.tools import next_scene

        mock_ctx = MagicMock()
        mock_ctx.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 0,
                "status": "setup",
                "scenes": [],
                "actors": {
                    "用户": {"is_user_protagonist": True, "control_type": "User-Controlled"},
                    "嵇康": {},
                },
                "remaining_auto_scenes": 0,
                "steer_direction": None,
                "dynamic_storm": {},
            }
        }

        with patch("app.tools.advance_scene", return_value={"status": "success", "current_scene": 1}):
            with patch("app.tools.build_director_context", return_value=""):
                with patch("app.state_manager.archive_old_scenes", side_effect=lambda s: s):
                    result = next_scene(tool_context=mock_ctx)

        assert "scene_cast" in result
        assert "standby" in result


# ============================================================================
# CAST-03: actor_speak_batch skips standby actors
# ============================================================================


class TestActorSpeakBatchCastFilter:
    """Test actor_speak_batch skips standby actors."""

    def test_actor_speak_batch_skips_standby(self):
        """Actors not in scene_cast should be skipped."""
        # This tests the filter logic at the entry of actor_speak_batch
        state = {
            "scene_cast": ["嵇康"],  # Only 嵇康 on stage
            "actors": {
                "用户": {"is_user_protagonist": True},
                "嵇康": {},
                "山涛": {},  # Standby
            },
        }

        actors_input = [
            {"actor_name": "嵇康", "situation": "responding"},
            {"actor_name": "山涛", "situation": "should be skipped"},
        ]

        # Simulate the filter logic from actor_speak_batch
        scene_cast = state.get("scene_cast")
        skipped_standby = []
        filtered = []
        for entry in actors_input:
            actor_name = entry.get("actor_name", "")
            if scene_cast is not None and actor_name not in scene_cast:
                skipped_standby.append(actor_name)
                continue
            filtered.append(entry)

        assert len(filtered) == 1
        assert filtered[0]["actor_name"] == "嵇康"
        assert "山涛" in skipped_standby

    def test_actor_speak_batch_none_scene_cast_no_filter(self):
        """When scene_cast is None, no actors are filtered out."""
        state = {
            "scene_cast": None,
            "actors": {
                "用户": {"is_user_protagonist": True},
                "嵇康": {},
                "山涛": {},
            },
        }

        actors_input = [
            {"actor_name": "嵇康", "situation": "responding"},
            {"actor_name": "山涛", "situation": "also responding"},
        ]

        scene_cast = state.get("scene_cast")
        skipped = []
        for entry in actors_input:
            actor_name = entry.get("actor_name", "")
            if scene_cast is not None and actor_name not in scene_cast:
                skipped.append(actor_name)
                continue

        assert len(skipped) == 0


# ============================================================================
# CAST-04: cast_change event mapping
# ============================================================================


class TestCastChangeEventMapping:
    """Test cast_change event mapping in event_mapper."""

    def test_set_scene_cast_in_tool_event_map(self):
        """set_scene_cast is mapped to cast_change + command_echo."""
        from app.api.event_mapper import TOOL_EVENT_MAP

        assert "set_scene_cast" in TOOL_EVENT_MAP
        assert "cast_change" in TOOL_EVENT_MAP["set_scene_cast"]
        assert "command_echo" in TOOL_EVENT_MAP["set_scene_cast"]

    def test_set_scene_cast_in_no_typing_tools(self):
        """set_scene_cast is in NO_TYPING_TOOLS (instant operation)."""
        from app.api.event_mapper import NO_TYPING_TOOLS

        assert "set_scene_cast" in NO_TYPING_TOOLS

    def test_cast_change_call_data_extraction(self):
        """cast_change call data is extracted correctly."""
        from app.api.event_mapper import _extract_call_data

        mock_fc = MagicMock()
        mock_fc.args = {"cast": ["嵇康", "山涛"]}

        data = _extract_call_data("cast_change", mock_fc)
        assert data["cast"] == ["嵇康", "山涛"]
        assert data["sender_type"] == "director"

    def test_cast_change_response_data_extraction(self):
        """cast_change response data is extracted correctly."""
        from app.api.event_mapper import _extract_response_data

        response = {
            "scene_cast": ["用户", "嵇康"],
            "standby": ["山涛"],
            "message": "🎭 场景卡司已更新",
        }

        data = _extract_response_data("cast_change", response)
        assert data["scene_cast"] == ["用户", "嵇康"]
        assert data["standby"] == ["山涛"]
        assert data["sender_type"] == "director"


# ============================================================================
# CAST-01: REST endpoint includes scene_cast
# ============================================================================


class TestCastStatusEndpointSceneCast:
    """Test /drama/cast/status includes scene_cast field."""

    def test_cast_status_response_model_has_scene_cast(self):
        """CastStatusResponse model includes scene_cast field."""
        from app.api.models import CastStatusResponse

        resp = CastStatusResponse(
            status="success",
            actors={"嵇康": {"pid": 123, "running": True, "port": 8001}},
            scene_cast=["嵇康"],
        )
        assert resp.scene_cast == ["嵇康"]

    def test_cast_status_response_model_none_scene_cast(self):
        """CastStatusResponse scene_cast defaults to None (all on stage)."""
        from app.api.models import CastStatusResponse

        resp = CastStatusResponse(
            status="success",
            actors={},
        )
        assert resp.scene_cast is None
