"""Unit tests for state_manager debounce, conversation_log migration, and scene archival.

Covers:
- Debounce: _set_state() does not write immediately, flush_state_sync() forces write
- conversation_log migration: reads/writes from state, not global variable
- load_progress: backward compatibility with old conversation_log.json
- Scene archival: archive_old_scenes() and load_archived_scene()
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch, call

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with drama state containing conversation_log."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "测试戏剧",
            "current_scene": 3,
            "status": "acting",
            "conversation_log": [],
            "scenes": [],
            "actors": {},
        }
    }
    return tc


@pytest.fixture
def mock_tool_context_with_log():
    """Create a mock ToolContext with existing conversation_log entries."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "测试戏剧",
            "current_scene": 3,
            "status": "acting",
            "conversation_log": [
                {"speaker": "朱棣", "content": "你好", "type": "dialogue", "scene": 1, "timestamp": "2026-01-01T10:00:00"},
                {"speaker": "苏念", "content": "您好", "type": "dialogue", "scene": 2, "timestamp": "2026-01-01T11:00:00"},
                {"speaker": "朱棣", "content": "出发", "type": "dialogue", "scene": 3, "timestamp": "2026-01-01T12:00:00"},
            ],
            "scenes": [],
            "actors": {},
        }
    }
    return tc


# ============================================================================
# Task 1 Part A: Debounce Tests
# ============================================================================


class TestDebounce:
    """Tests for debounce state saving behavior."""

    @patch("app.state_manager._save_state_to_file")
    def test_set_state_does_not_immediately_write(self, mock_save):
        """_set_state() should NOT call _save_state_to_file immediately."""
        from app.state_manager import _set_state, _save_dirty, _save_timer

        tc = MagicMock()
        tc.state = {"drama": {}}
        state = {"theme": "test", "current_scene": 1}

        _set_state(state, tc)

        # _save_state_to_file should NOT have been called (debounced)
        mock_save.assert_not_called()

    @patch("app.state_manager._save_state_to_file")
    def test_flush_state_sync_forces_write(self, mock_save):
        """flush_state_sync() should immediately call _save_state_to_file."""
        from app.state_manager import _set_state, flush_state_sync

        tc = MagicMock()
        tc.state = {"drama": {}}
        state = {"theme": "test_drama", "current_scene": 1}

        _set_state(state, tc)
        flush_state_sync()

        # After flush, _save_state_to_file should have been called once
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == "test_drama"  # theme
        assert call_args[0][1] == state  # state dict

    @patch("app.state_manager._save_state_to_file")
    def test_multiple_set_state_single_write(self, mock_save):
        """Multiple _set_state() calls within debounce window should result in only one write."""
        from app.state_manager import _set_state, flush_state_sync

        tc = MagicMock()
        tc.state = {"drama": {}}

        # Call _set_state multiple times
        for i in range(5):
            state = {"theme": "test_drama", "current_scene": i}
            _set_state(state, tc)

        # Still no write
        mock_save.assert_not_called()

        # Flush triggers a single write with the latest state
        flush_state_sync()
        assert mock_save.call_count == 1
        call_args = mock_save.call_args
        assert call_args[0][1]["current_scene"] == 4  # latest state

    @patch("app.state_manager._save_state_to_file")
    def test_debounce_timer_is_daemon(self, mock_save):
        """Timer created by _set_state should be a daemon thread."""
        from app.state_manager import _set_state, _save_timer

        tc = MagicMock()
        tc.state = {"drama": {}}
        state = {"theme": "test_drama", "current_scene": 1}

        _set_state(state, tc)

        # Import the module-level timer variable
        import app.state_manager as sm
        assert sm._save_timer is not None
        assert sm._save_timer.daemon is True

        # Cleanup
        sm._save_timer.cancel()
        sm._save_timer = None
        sm._save_dirty = False


# ============================================================================
# Task 1 Part B: conversation_log Migration Tests
# ============================================================================


class TestConversationLogMigration:
    """Tests for conversation_log migration from global to state."""

    @patch("app.state_manager._save_state_to_file")
    def test_add_conversation_writes_to_state(self, mock_save):
        """add_conversation() should write to state['conversation_log'], not global."""
        from app.state_manager import add_conversation

        tc = MagicMock()
        tc.state = {"drama": {"theme": "测试戏剧", "current_scene": 3, "status": "acting", "conversation_log": [], "scenes": [], "actors": {}}}
        result = add_conversation("朱棣", "你好", "dialogue", tc)

        assert result["status"] == "success"
        log = tc.state["drama"]["conversation_log"]
        assert len(log) == 1
        assert log[0]["speaker"] == "朱棣"
        assert log[0]["content"] == "你好"

    @patch("app.state_manager._save_state_to_file")
    def test_get_conversation_log_reads_from_state(self, mock_save):
        """get_conversation_log() should read from state['conversation_log']."""
        from app.state_manager import get_conversation_log

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 3,
                "status": "acting",
                "conversation_log": [
                    {"speaker": "朱棣", "content": "你好", "type": "dialogue", "scene": 1, "timestamp": "2026-01-01T10:00:00"},
                    {"speaker": "苏念", "content": "您好", "type": "dialogue", "scene": 2, "timestamp": "2026-01-01T11:00:00"},
                    {"speaker": "朱棣", "content": "出发", "type": "dialogue", "scene": 3, "timestamp": "2026-01-01T12:00:00"},
                ],
                "scenes": [],
                "actors": {},
            }
        }
        result = get_conversation_log(scene=2, tool_context=tc)

        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["entries"][0]["scene"] == 2

    @patch("app.state_manager._save_state_to_file")
    def test_get_conversation_log_all_entries(self, mock_save):
        """get_conversation_log() without scene filter returns all entries."""
        from app.state_manager import get_conversation_log

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 3,
                "status": "acting",
                "conversation_log": [
                    {"speaker": "朱棣", "content": "你好", "type": "dialogue", "scene": 1, "timestamp": "2026-01-01T10:00:00"},
                    {"speaker": "苏念", "content": "您好", "type": "dialogue", "scene": 2, "timestamp": "2026-01-01T11:00:00"},
                    {"speaker": "朱棣", "content": "出发", "type": "dialogue", "scene": 3, "timestamp": "2026-01-01T12:00:00"},
                ],
                "scenes": [],
                "actors": {},
            }
        }
        result = get_conversation_log(tool_context=tc)

        assert result["status"] == "success"
        assert result["count"] == 3

    @patch("app.state_manager._save_state_to_file")
    def test_clear_conversation_log_clears_state(self, mock_save):
        """clear_conversation_log() should clear state['conversation_log']."""
        from app.state_manager import clear_conversation_log

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 3,
                "status": "acting",
                "conversation_log": [
                    {"speaker": "朱棣", "content": "你好", "type": "dialogue", "scene": 1},
                ],
                "scenes": [],
                "actors": {},
            }
        }
        result = clear_conversation_log(tc)

        assert result["status"] == "success"
        assert tc.state["drama"]["conversation_log"] == []

    @patch("app.state_manager._save_state_to_file")
    def test_export_conversations_reads_from_state(self, mock_save):
        """export_conversations() should read from state['conversation_log']."""
        from app.state_manager import export_conversations

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 3,
                "status": "acting",
                "conversation_log": [
                    {"speaker": "朱棣", "content": "你好", "type": "dialogue", "scene": 1, "timestamp": "2026-01-01T10:00:00"},
                    {"speaker": "苏念", "content": "您好", "type": "dialogue", "scene": 2, "timestamp": "2026-01-01T11:00:00"},
                    {"speaker": "朱棣", "content": "出发", "type": "dialogue", "scene": 3, "timestamp": "2026-01-01T12:00:00"},
                ],
                "scenes": [],
                "actors": {},
            }
        }
        result = export_conversations("json", tc)

        assert result["status"] == "success"
        assert result["total_entries"] == 3

    @patch("app.state_manager._save_state_to_file")
    def test_init_drama_state_includes_conversation_log(self, mock_save):
        """init_drama_state() should initialize state['conversation_log'] = []."""
        from app.state_manager import init_drama_state

        tc = MagicMock()
        tc.state = {"drama": {}}

        result = init_drama_state("测试新剧", tc)

        assert result["status"] == "success"
        assert tc.state["drama"]["conversation_log"] == []

    @patch("app.state_manager._save_state_to_file")
    def test_load_progress_old_save_compatibility(self, mock_save):
        """load_progress() should migrate old conversation_log.json to state."""
        from app.state_manager import load_progress, DRAMAS_DIR

        # Create a temporary test structure
        with patch("app.state_manager._get_state_file") as mock_get_file, \
             patch("app.state_manager._get_drama_folder") as mock_get_folder, \
             patch("app.state_manager._ensure_drama_dirs") as mock_ensure_dirs, \
             patch("app.state_manager._get_conversations_dir") as mock_conv_dir, \
             tempfile.TemporaryDirectory() as tmpdir:

            # Setup: create state.json without conversation_log
            state_file = os.path.join(tmpdir, "state.json")
            save_data = {
                "theme": "旧戏剧",
                "current_scene": 5,
                "status": "acting",
                "scenes": [],
                "actors": {},
            }
            with open(state_file, "w") as f:
                json.dump(save_data, f)

            # Create old conversations/conversation_log.json
            conv_dir = os.path.join(tmpdir, "conversations")
            os.makedirs(conv_dir, exist_ok=True)
            conv_data = [
                {"speaker": "朱棣", "content": "旧对话", "type": "dialogue", "scene": 1}
            ]
            with open(os.path.join(conv_dir, "conversation_log.json"), "w") as f:
                json.dump(conv_data, f)

            mock_get_file.return_value = state_file
            mock_get_folder.return_value = tmpdir
            mock_ensure_dirs.return_value = {"root": tmpdir}
            mock_conv_dir.return_value = conv_dir

            tc = MagicMock()
            tc.state = {"drama": {}}

            result = load_progress("旧戏剧", tc)

            assert result["status"] == "success"
            # conversation_log should be loaded from old file
            assert len(tc.state["drama"]["conversation_log"]) == 1
            assert tc.state["drama"]["conversation_log"][0]["content"] == "旧对话"

    @patch("app.state_manager._save_state_to_file")
    def test_load_progress_new_save_no_old_file(self, mock_save):
        """load_progress() with new save (already has conversation_log) should not read old file."""
        import tempfile
        from app.state_manager import load_progress

        with patch("app.state_manager._get_state_file") as mock_get_file, \
             patch("app.state_manager._get_drama_folder") as mock_get_folder, \
             patch("app.state_manager._ensure_drama_dirs") as mock_ensure_dirs, \
             tempfile.TemporaryDirectory() as tmpdir:

            # Setup: create state.json WITH conversation_log already
            state_file = os.path.join(tmpdir, "state.json")
            save_data = {
                "theme": "新戏剧",
                "current_scene": 2,
                "status": "acting",
                "scenes": [],
                "actors": {},
                "conversation_log": [
                    {"speaker": "苏念", "content": "新对话", "type": "dialogue", "scene": 1}
                ],
            }
            with open(state_file, "w") as f:
                json.dump(save_data, f)

            mock_get_file.return_value = state_file
            mock_get_folder.return_value = tmpdir
            mock_ensure_dirs.return_value = {"root": tmpdir}

            tc = MagicMock()
            tc.state = {"drama": {}}

            result = load_progress("新戏剧", tc)

            assert result["status"] == "success"
            # Should have the existing conversation_log from state
            assert len(tc.state["drama"]["conversation_log"]) == 1
            assert tc.state["drama"]["conversation_log"][0]["content"] == "新对话"


# ============================================================================
# Task 2: Scene Archival Tests
# ============================================================================


class TestSceneArchival:
    """Tests for scene archival with 20-scene threshold."""

    def test_archive_not_triggered_below_threshold(self):
        """archive_old_scenes() should not modify state if scenes <= 20."""
        from app.state_manager import archive_old_scenes

        scenes = [{"scene_number": i, "title": f"Scene {i}"} for i in range(1, 16)]
        state = {"theme": "test", "scenes": scenes}

        result = archive_old_scenes(state)

        assert len(result["scenes"]) == 15
        # All scenes should remain unchanged
        for s in result["scenes"]:
            assert "archived" not in s

    @patch("app.state_manager._get_drama_folder")
    def test_archive_triggered_above_threshold(self, mock_get_folder, tmp_path):
        """archive_old_scenes() should archive scenes beyond 20."""
        from app.state_manager import archive_old_scenes

        mock_get_folder.return_value = str(tmp_path)

        # Create 25 scenes
        scenes = [
            {
                "scene_number": i,
                "title": f"第{i}场",
                "time_label": f"Day {i}",
                "description": f"Description for scene {i}" * 10,
                "content": f"Content for scene {i}" * 20,
            }
            for i in range(1, 26)
        ]
        state = {"theme": "test", "scenes": scenes}

        result = archive_old_scenes(state)

        # First 5 should be archived (index metadata only)
        assert len(result["scenes"]) == 25
        for i in range(5):
            s = result["scenes"][i]
            assert s.get("archived") is True
            assert "scene_number" in s
            assert "title" in s
            assert "time_label" in s
            # Archived scenes should not have full data
            assert "content" not in s
            assert "description" not in s

        # Last 20 should be intact with full data
        for i in range(5, 25):
            s = result["scenes"][i]
            assert "archived" not in s
            assert "content" in s
            assert "description" in s

        # Archived files should exist on disk
        scenes_dir = tmp_path / "scenes"
        for i in range(1, 6):
            archive_file = scenes_dir / f"scene_{i:04d}.json"
            assert archive_file.exists()
            with open(archive_file) as f:
                archived = json.load(f)
            assert archived["scene_number"] == i
            assert "content" in archived

    @patch("app.state_manager._get_drama_folder")
    def test_load_archived_scene(self, mock_get_folder, tmp_path):
        """load_archived_scene() should read archived scene data from disk."""
        from app.state_manager import load_archived_scene

        mock_get_folder.return_value = str(tmp_path)
        scenes_dir = tmp_path / "scenes"
        scenes_dir.mkdir()

        # Write a test archive file
        scene_data = {"scene_number": 3, "title": "Test", "content": "Full content"}
        archive_file = scenes_dir / "scene_0003.json"
        with open(archive_file, "w") as f:
            json.dump(scene_data, f)

        result = load_archived_scene("test", 3)
        assert result is not None
        assert result["scene_number"] == 3
        assert result["content"] == "Full content"

    @patch("app.state_manager._get_drama_folder")
    def test_load_archived_scene_not_found(self, mock_get_folder, tmp_path):
        """load_archived_scene() should return None for non-existent scene."""
        from app.state_manager import load_archived_scene

        mock_get_folder.return_value = str(tmp_path)

        result = load_archived_scene("test", 999)
        assert result is None


# ============================================================================
# Task 1 Part A (13-03): State Migration Tests — _current_drama_folder removal
# ============================================================================


class TestCurrentDramaFolderRemoval:
    """Tests for _current_drama_folder global variable removal (STATE-01/D-09/D-10/D-11)."""

    def test_no_global_drama_folder(self):
        """_current_drama_folder should not exist as module attribute."""
        import app.state_manager as sm
        assert not hasattr(sm, "_current_drama_folder")

    def test_get_current_theme_requires_tool_context(self):
        """_get_current_theme(None) should raise ValueError."""
        from app.state_manager import _get_current_theme
        with pytest.raises(ValueError, match="tool_context is required"):
            _get_current_theme(None)

    def test_get_current_theme_with_tool_context(self):
        """_get_current_theme(mock_tool_context) should return theme."""
        from app.state_manager import _get_current_theme
        tc = MagicMock()
        tc.state = {"drama": {"theme": "测试戏剧"}}
        result = _get_current_theme(tc)
        assert result == "测试戏剧"

    @patch("app.state_manager._save_state_to_file")
    def test_init_drama_state_no_global_assignment(self, mock_save):
        """After init_drama_state, no _current_drama_folder attribute on module."""
        import app.state_manager as sm
        from app.state_manager import init_drama_state

        tc = MagicMock()
        tc.state = {"drama": {}}

        init_drama_state("测试新剧", tc)

        assert not hasattr(sm, "_current_drama_folder")

    @patch("app.state_manager._save_state_to_file")
    def test_load_progress_no_global_assignment(self, mock_save):
        """After load_progress, no _current_drama_folder attribute on module."""
        import app.state_manager as sm
        from app.state_manager import load_progress

        with patch("app.state_manager._get_state_file") as mock_get_file, \
             patch("app.state_manager._get_drama_folder") as mock_get_folder, \
             patch("app.state_manager._ensure_drama_dirs") as mock_ensure_dirs, \
             tempfile.TemporaryDirectory() as tmpdir:

            state_file = os.path.join(tmpdir, "state.json")
            save_data = {
                "theme": "测试戏剧",
                "current_scene": 1,
                "status": "acting",
                "scenes": [],
                "actors": {},
            }
            with open(state_file, "w") as f:
                json.dump(save_data, f)

            mock_get_file.return_value = state_file
            mock_get_folder.return_value = tmpdir
            mock_ensure_dirs.return_value = {"root": tmpdir}

            tc = MagicMock()
            tc.state = {"drama": {}}

            load_progress("测试戏剧", tc)

            assert not hasattr(sm, "_current_drama_folder")
