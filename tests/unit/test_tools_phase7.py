"""Unit tests for Phase 7 tool functions: create_thread, update_thread, resolve_thread, set_actor_arc, resolve_conflict_tool."""

import pytest

from app.tools import (
    create_thread,
    update_thread,
    resolve_thread,
    set_actor_arc,
    resolve_conflict_tool,
    inject_conflict,
)


class TestCreateThreadTool:
    """Test create_thread Tool function."""

    def test_creates_thread_success(self, mock_tool_context):
        result = create_thread("林风对朱棣的复仇计划", "朱棣", mock_tool_context)
        assert result["status"] == "success"
        assert "thread_id" in result
        assert "📌" in result["message"]

    def test_creates_thread_with_multiple_actors(self, mock_tool_context):
        result = create_thread("双主角线索", "朱棣, 苏念", mock_tool_context)
        assert result["status"] == "success"
        state = mock_tool_context.state["drama"]
        assert len(state["plot_threads"]) == 1
        assert "苏念" in state["plot_threads"][0]["involved_actors"]

    def test_creates_thread_nonexistent_actor_error(self, mock_tool_context):
        result = create_thread("某线索", "不存在的角色", mock_tool_context)
        assert result["status"] == "error"

    def test_creates_thread_strips_whitespace(self, mock_tool_context):
        result = create_thread("测试线索", "  朱棣  ,  苏念  ", mock_tool_context)
        assert result["status"] == "success"
        state = mock_tool_context.state["drama"]
        assert state["plot_threads"][0]["involved_actors"] == ["朱棣", "苏念"]

    def test_state_has_plot_threads_after_create(self, mock_tool_context):
        create_thread("测试线索", "朱棣", mock_tool_context)
        state = mock_tool_context.state["drama"]
        assert len(state["plot_threads"]) == 1
        assert state["plot_threads"][0]["description"] == "测试线索"
        assert state["plot_threads"][0]["status"] == "active"


class TestUpdateThreadTool:
    """Test update_thread Tool function."""

    def test_updates_status(self, mock_tool_context):
        create_thread("测试线索", "朱棣", mock_tool_context)
        thread_id = mock_tool_context.state["drama"]["plot_threads"][0]["id"]
        result = update_thread(thread_id, status="resolving", progress_note=None, tool_context=mock_tool_context)
        assert result["status"] == "success"
        assert "已更新" in result["message"]

    def test_updates_with_progress_note(self, mock_tool_context):
        create_thread("测试线索", "朱棣", mock_tool_context)
        thread_id = mock_tool_context.state["drama"]["plot_threads"][0]["id"]
        result = update_thread(thread_id, status=None, progress_note="新进展", tool_context=mock_tool_context)
        assert result["status"] == "success"
        thread = mock_tool_context.state["drama"]["plot_threads"][0]
        assert any("新进展" in n for n in thread["progress_notes"])

    def test_nonexistent_thread_returns_error(self, mock_tool_context):
        result = update_thread("thread_99_不存在_1", status="active", progress_note=None, tool_context=mock_tool_context)
        assert result["status"] == "error"


class TestResolveThreadTool:
    """Test resolve_thread Tool function."""

    def test_resolves_thread(self, mock_tool_context):
        create_thread("复仇计划", "朱棣", mock_tool_context)
        thread_id = mock_tool_context.state["drama"]["plot_threads"][0]["id"]
        result = resolve_thread(thread_id, "和解", mock_tool_context)
        assert result["status"] == "success"
        assert "✅" in result["message"]
        assert mock_tool_context.state["drama"]["plot_threads"][0]["status"] == "resolved"

    def test_linked_conflict_hint(self, mock_tool_context):
        create_thread("复仇计划", "朱棣", mock_tool_context)
        thread_id = mock_tool_context.state["drama"]["plot_threads"][0]["id"]
        # Add a linked conflict
        mock_tool_context.state["drama"]["conflict_engine"]["active_conflicts"].append({
            "id": "conflict_3_escalation_1",
            "thread_id": thread_id,
            "type": "escalation",
        })
        result = resolve_thread(thread_id, "和解", mock_tool_context)
        assert result["status"] == "success"
        assert result.get("linked_conflict_hint") is not None

    def test_nonexistent_thread_returns_error(self, mock_tool_context):
        result = resolve_thread("thread_99_不存在_1", "无所谓", mock_tool_context)
        assert result["status"] == "error"


class TestSetActorArcTool:
    """Test set_actor_arc Tool function."""

    def test_sets_arc_type_and_progress(self, mock_tool_context):
        result = set_actor_arc("朱棣", arc_type="growth", arc_stage=None, progress=50, tool_context=mock_tool_context)
        assert result["status"] == "success"
        assert "🎭" in result["message"]

    def test_partial_update(self, mock_tool_context):
        set_actor_arc("朱棣", arc_type="fall", arc_stage=None, progress=None, tool_context=mock_tool_context)
        result = set_actor_arc("朱棣", arc_type=None, arc_stage=None, progress=75, tool_context=mock_tool_context)
        assert result["status"] == "success"
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert actor["arc_progress"]["arc_type"] == "fall"
        assert actor["arc_progress"]["progress"] == 75

    def test_invalid_arc_type_returns_error(self, mock_tool_context):
        result = set_actor_arc("朱棣", arc_type="invalid", arc_stage=None, progress=None, tool_context=mock_tool_context)
        assert result["status"] == "error"

    def test_nonexistent_actor_returns_error(self, mock_tool_context):
        result = set_actor_arc("不存在", arc_type="growth", arc_stage=None, progress=None, tool_context=mock_tool_context)
        assert result["status"] == "error"

    def test_message_includes_cn_arc_type(self, mock_tool_context):
        result = set_actor_arc("朱棣", arc_type="redemption", arc_stage="climax", progress=80, tool_context=mock_tool_context)
        assert result["status"] == "success"
        assert "救赎" in result["message"]
        assert "高潮" in result["message"]


class TestResolveConflictTool:
    """Test resolve_conflict_tool Tool function."""

    def test_resolves_active_conflict(self, mock_tool_context):
        # Add an active conflict
        mock_tool_context.state["drama"]["conflict_engine"]["active_conflicts"].append({
            "id": "conflict_3_escalation_1",
            "type": "escalation",
            "description": "矛盾升级",
            "involved_actors": ["朱棣"],
            "introduced_scene": 3,
        })
        result = resolve_conflict_tool("conflict_3_escalation_1", mock_tool_context)
        assert result["status"] == "success"
        assert "✅" in result["message"]
        # Should be moved to resolved
        ce = mock_tool_context.state["drama"]["conflict_engine"]
        assert len(ce["active_conflicts"]) == 0
        assert len(ce["resolved_conflicts"]) == 1

    def test_nonexistent_conflict_returns_error(self, mock_tool_context):
        result = resolve_conflict_tool("conflict_99_nonexistent_1", mock_tool_context)
        assert result["status"] == "error"
