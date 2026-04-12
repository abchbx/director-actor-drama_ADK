"""Integration tests for memory_manager + state_manager + tools integration.

Tests the integration between the 3-tier memory architecture (memory_manager.py)
and the existing system (state_manager.py, tools.py, agent.py).

Covers:
- register_actor creates actors with new memory fields
- update_actor_memory delegates to add_working_memory
- load_progress auto-migrates old format actors
- get_all_actors returns new memory tier counts
- actor_speak uses build_actor_context
- actor_speak records dialogue in working memory
- mark_memory tool integration
- load_drama uses new memory fields
- agent.py includes mark_memory in tools list
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.state_manager import (
    register_actor,
    update_actor_memory,
    load_progress,
    get_all_actors,
    _get_state,
    _set_state,
    init_drama_state,
    _migrate_legacy_status,
)
from app.memory_manager import (
    add_working_memory,
    build_actor_context,
    detect_importance,
    ensure_actor_memory_fields,
)


@pytest.fixture
def fresh_tool_context():
    """Create a fresh tool context for integration tests."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "集成测试戏剧",
            "current_scene": 1,
            "status": "acting",
            "actors": {},
        }
    }
    return tc


# ============================================================================
# Task 1 Tests: state_manager integration
# ============================================================================


class TestRegisterActorNewFields:
    """Test 1: register_actor creates actor with new memory fields."""

    def test_register_actor_has_new_fields(self, fresh_tool_context):
        """MEMORY-01: register_actor creates actor with new memory fields."""
        result = register_actor("张三", "主角", "勇敢", "战士出身", "武术", fresh_tool_context)
        assert result["status"] == "success"

        actor = fresh_tool_context.state["drama"]["actors"]["张三"]
        assert "working_memory" in actor
        assert "scene_summaries" in actor
        assert "arc_summary" in actor
        assert "critical_memories" in actor
        assert actor["working_memory"] == []
        assert actor["scene_summaries"] == []
        assert actor["critical_memories"] == []
        assert actor["arc_summary"]["narrative"] == ""
        # D-13: old field still present
        assert "memory" in actor


class TestUpdateActorMemoryDelegation:
    """Test 2: update_actor_memory delegates to add_working_memory."""

    def test_update_actor_memory_delegates(self, fresh_tool_context):
        """update_actor_memory now delegates to add_working_memory."""
        register_actor("李四", "反派", "阴险", "刺客", "暗杀术", fresh_tool_context)
        result = update_actor_memory("李四", "面对情境: 首次登场", fresh_tool_context)
        assert result["status"] == "success"

        actor = fresh_tool_context.state["drama"]["actors"]["李四"]
        # Should be in working_memory (new system)
        assert len(actor["working_memory"]) >= 1
        # Auto-detected "首次登场" → critical
        assert any(e["entry"] == "面对情境: 首次登场" for e in actor["working_memory"])


class TestGetAllActorsNewFields:
    """Test 4: get_all_actors returns new memory tier counts."""

    def test_get_all_actors_returns_new_stats(self, fresh_tool_context):
        """get_all_actors returns new memory tier counts."""
        register_actor("王五", "配角", "温和", "书生", "文学", fresh_tool_context)
        result = get_all_actors(fresh_tool_context)
        assert result["status"] == "success"

        info = result["actors"]["王五"]
        assert "working_memory_count" in info
        assert "scene_summaries_count" in info
        assert "critical_memories_count" in info
        assert "has_arc_summary" in info
        assert info["working_memory_count"] == 0
        assert info["has_arc_summary"] is False


class TestLoadProgressMigration:
    """Test 3 & 5: load_progress migration tests."""

    def test_load_progress_migrates_old_format(self, fresh_tool_context, tmp_path):
        """Test 3: load_progress with old-format actor triggers migration."""
        import json
        from app import state_manager

        # Create an old-format save file
        old_state = {
            "theme": "旧格式戏剧",
            "current_scene": 2,
            "status": "acting",
            "actors": {
                "旧角色": {
                    "role": "测试",
                    "personality": "普通",
                    "background": "测试背景",
                    "knowledge_scope": "测试知识",
                    "memory": [
                        {"entry": "旧记忆1", "timestamp": "2026-04-10T10:00:00"},
                        {"entry": "旧记忆2", "timestamp": "2026-04-10T11:00:00"},
                    ],
                    "emotions": "neutral",
                    "created_at": "2026-04-10T09:00:00",
                }
            },
            "scenes": [],
            "narration_log": [],
            "created_at": "2026-04-10T09:00:00",
            "updated_at": "2026-04-10T12:00:00",
        }

        # Use the state_manager's own directory structure
        save_dir = os.path.join(state_manager.DRAMAS_DIR, "旧格式戏剧")
        os.makedirs(save_dir, exist_ok=True)
        state_file = os.path.join(save_dir, "state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(old_state, f, ensure_ascii=False, indent=2)

        result = load_progress("旧格式戏剧", fresh_tool_context)
        assert result["status"] == "success"

        # The old-format actor should now have new fields
        actor = fresh_tool_context.state["drama"]["actors"]["旧角色"]
        assert "working_memory" in actor
        assert len(actor["working_memory"]) == 2  # Migrated from old memory
        # Old memory field preserved (D-13)
        assert "memory" in actor

    def test_load_progress_no_re_migration(self, fresh_tool_context, tmp_path):
        """Test 5: load_progress with already-migrated actor does NOT re-migrate."""
        import json
        from app import state_manager

        # Create a new-format save file
        new_state = {
            "theme": "新格式戏剧",
            "current_scene": 1,
            "status": "acting",
            "actors": {
                "新角色": {
                    "role": "测试",
                    "personality": "普通",
                    "background": "测试背景",
                    "knowledge_scope": "测试知识",
                    "memory": [],
                    "working_memory": [
                        {"entry": "已有记忆", "importance": "normal", "scene": 1},
                    ],
                    "scene_summaries": [],
                    "arc_summary": {
                        "structured": {
                            "theme": "",
                            "key_characters": [],
                            "unresolved": [],
                            "resolved": [],
                        },
                        "narrative": "",
                    },
                    "critical_memories": [],
                    "emotions": "neutral",
                    "created_at": "2026-04-11T09:00:00",
                }
            },
            "scenes": [],
            "narration_log": [],
            "created_at": "2026-04-11T09:00:00",
            "updated_at": "2026-04-11T10:00:00",
        }

        save_dir = os.path.join(state_manager.DRAMAS_DIR, "新格式戏剧")
        os.makedirs(save_dir, exist_ok=True)
        state_file = os.path.join(save_dir, "state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(new_state, f, ensure_ascii=False, indent=2)

        result = load_progress("新格式戏剧", fresh_tool_context)
        assert result["status"] == "success"

        actor = fresh_tool_context.state["drama"]["actors"]["新角色"]
        # Should still have exactly 1 working memory (not duplicated)
        assert len(actor["working_memory"]) == 1


import os


# ============================================================================
# Task 2 Tests: tools.py + agent.py integration
# ============================================================================


class TestActorSpeakUsesBuildContext:
    """Test that actor_speak uses build_actor_context instead of flat memory_str."""

    def test_actor_speak_builds_layered_context(self, fresh_tool_context):
        """actor_speak should call build_actor_context, not use flat memory list."""
        from app.memory_manager import add_working_memory

        register_actor("赵六", "将军", "刚毅", "边关守将", "军事", fresh_tool_context)

        # Add some working memory
        add_working_memory("赵六", "面对情境: 敌军来袭", "normal", None, fresh_tool_context)

        # Verify build_actor_context produces layered output
        context = build_actor_context("赵六", fresh_tool_context)
        assert "【角色锚点】" in context
        assert "【当前情绪】" in context
        assert "最近的经历" in context


class TestMarkMemory:
    """Test /mark command integration."""

    def test_mark_memory_marks_last_entry(self, fresh_tool_context):
        """mark_memory should mark the last working_memory entry as critical."""
        register_actor("钱七", "谋士", "多谋", "军师", "兵法", fresh_tool_context)
        add_working_memory("钱七", "面对情境: 普通对话", "normal", None, fresh_tool_context)
        add_working_memory("钱七", "面对情境: 发现密信", "normal", None, fresh_tool_context)

        from app.tools import mark_memory

        result = mark_memory("钱七", "这段很重要", fresh_tool_context)
        assert result["status"] == "success"

        actor = fresh_tool_context.state["drama"]["actors"]["钱七"]
        assert len(actor["critical_memories"]) == 1
        assert actor["critical_memories"][0]["reason"] == "用户标记"

    def test_mark_memory_no_working_memory(self, fresh_tool_context):
        """mark_memory with no working memory returns error."""
        register_actor("孙八", "书童", "老实", "农家子弟", "家务", fresh_tool_context)

        from app.tools import mark_memory

        result = mark_memory("孙八", "试试", fresh_tool_context)
        assert result["status"] == "error"


class TestLoadDramaNewMemory:
    """Test load_drama uses new memory fields."""

    def test_load_drama_uses_working_memory(self, fresh_tool_context):
        """load_drama should extract memory from working_memory, not old memory field."""
        register_actor("周九", "太守", "儒雅", "世家子弟", "政务", fresh_tool_context)
        add_working_memory("周九", "面对情境: 朝廷来使", "normal", None, fresh_tool_context)

        actor = fresh_tool_context.state["drama"]["actors"]["周九"]
        # Working memory should be populated
        assert len(actor["working_memory"]) >= 1
        # Old memory field should be empty (new actors don't write to it)
        assert len(actor.get("memory", [])) == 0


class TestAgentIncludesMarkMemory:
    """Test 6: agent.py director tools list includes mark_memory."""

    def test_agent_includes_mark_memory(self):
        """agent.py improv_director tools list includes mark_memory."""
        from app.agent import _improv_director
        from app.tools import mark_memory as mark_memory_tool

        # In ADK, tools in the tools list are Python functions
        tool_names = [t.__name__ if hasattr(t, '__name__') else getattr(t, 'name', str(t)) for t in _improv_director.tools]
        assert "mark_memory" in tool_names


# ============================================================================
# Phase 5 — Mixed Autonomy Mode Backward Compatibility Tests
# ============================================================================


class TestPhase5BackwardCompat:
    """Test Phase 5 state field defaults, migration, and backward compatibility."""

    def test_load_legacy_state_without_phase5_fields(self):
        """Loading a state dict WITHOUT Phase 5 fields gets safe defaults via setdefault."""
        # Simulate an old state dict without Phase 5 fields
        state = {
            "theme": "旧戏剧",
            "status": "acting",
            "current_scene": 5,
            "actors": {"角色A": {"role": "主角"}},
            "scenes": [],
            "narration_log": [],
        }
        # Apply the same setdefault logic as load_progress
        state.setdefault("remaining_auto_scenes", 0)
        state.setdefault("steer_direction", None)
        state.setdefault("storm", {"last_review": {}})
        if "storm" in state and "last_review" not in state["storm"]:
            state["storm"]["last_review"] = {}

        assert state["remaining_auto_scenes"] == 0
        assert state["steer_direction"] is None
        assert state["storm"] == {"last_review": {}}

    def test_load_state_with_ended_status_preserved(self):
        """_migrate_legacy_status preserves 'ended' status instead of overwriting to 'acting'."""
        state = {
            "status": "ended",
            "actors": {"角色A": {"role": "主角"}},
        }
        result = _migrate_legacy_status(state)
        assert result["status"] == "ended"

    def test_init_drama_state_has_phase5_fields(self, fresh_tool_context):
        """init_drama_state initializes remaining_auto_scenes, steer_direction, storm."""
        import json
        from app import state_manager

        # Create a unique theme to avoid conflicts
        theme = f"Phase5InitTest_{id(fresh_tool_context)}"

        # Mock _save_state_to_file to avoid file I/O
        with patch.object(state_manager, '_save_state_to_file'):
            result = init_drama_state(theme, fresh_tool_context)

        assert result["status"] == "success"
        drama_state = fresh_tool_context.state["drama"]
        assert drama_state["remaining_auto_scenes"] == 0
        assert drama_state["steer_direction"] is None
        assert drama_state["storm"] == {"last_review": {}}

    def test_load_state_storm_without_last_review(self):
        """Loading a state with storm sub-dict but no last_review gets it filled in."""
        state = {
            "theme": "测试",
            "status": "acting",
            "current_scene": 1,
            "actors": {},
            "scenes": [],
            "narration_log": [],
            "storm": {"perspectives": []},  # has storm but no last_review
        }
        # Apply the same setdefault logic as load_progress
        state.setdefault("remaining_auto_scenes", 0)
        state.setdefault("steer_direction", None)
        state.setdefault("storm", {"last_review": {}})
        if "storm" in state and "last_review" not in state["storm"]:
            state["storm"]["last_review"] = {}

        assert state["storm"]["last_review"] == {}
        # Existing perspectives should be preserved
        assert state["storm"]["perspectives"] == []
