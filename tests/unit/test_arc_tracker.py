"""Unit tests for arc_tracker.py — plot thread management and character arc tracking.

TDD tests for arc_tracker pure functions.
"""

import pytest

from app.arc_tracker import (
    ARC_TYPES,
    ARC_STAGES,
    DORMANT_THRESHOLD,
    MAX_PROGRESS_NOTES,
    MAX_RESOLVED_CONFLICTS,
    _init_arc_tracker_defaults,
    create_thread_logic,
    update_thread_logic,
    resolve_thread_logic,
    set_actor_arc_logic,
)


def _make_state(**overrides) -> dict:
    """Create a minimal state dict for testing arc_tracker functions."""
    state = {
        "current_scene": 3,
        "actors": {
            "朱棣": {
                "role": "燕王",
                "emotions": "neutral",
                "arc_progress": {
                    "arc_type": "",
                    "arc_stage": "",
                    "progress": 0,
                    "related_threads": [],
                },
            },
            "苏念": {
                "role": "宫女",
                "emotions": "anxious",
                "arc_progress": {
                    "arc_type": "",
                    "arc_stage": "",
                    "progress": 0,
                    "related_threads": [],
                },
            },
        },
        "plot_threads": [],
        "conflict_engine": {
            "active_conflicts": [],
            "resolved_conflicts": [],
        },
    }
    state.update(overrides)
    return state


class TestArcTrackerConstants:
    """Test constants are defined correctly."""

    def test_arc_types_has_four_entries(self):
        assert len(ARC_TYPES) == 4
        assert "growth" in ARC_TYPES
        assert "fall" in ARC_TYPES
        assert "transformation" in ARC_TYPES
        assert "redemption" in ARC_TYPES

    def test_arc_stages_has_four_entries(self):
        assert len(ARC_STAGES) == 4
        assert "setup" in ARC_STAGES
        assert "development" in ARC_STAGES
        assert "climax" in ARC_STAGES
        assert "resolution" in ARC_STAGES

    def test_dormant_threshold_is_8(self):
        assert DORMANT_THRESHOLD == 8

    def test_max_progress_notes_is_10(self):
        assert MAX_PROGRESS_NOTES == 10

    def test_max_resolved_conflicts_is_20(self):
        assert MAX_RESOLVED_CONFLICTS == 20

    def test_init_defaults_returns_plot_threads(self):
        result = _init_arc_tracker_defaults()
        assert "plot_threads" in result
        assert result["plot_threads"] == []


class TestCreateThreadLogic:
    """Test create_thread_logic pure function."""

    def test_creates_thread_with_auto_id(self):
        state = _make_state()
        result = create_thread_logic("林风对朱棣的复仇计划", ["朱棣"], state)
        assert result["status"] == "success"
        assert "thread_id" in result
        assert result["thread_id"].startswith("thread_3_")
        assert result["thread"]["status"] == "active"
        assert result["thread"]["introduced_scene"] == 3
        assert result["thread"]["last_updated_scene"] == 3
        assert result["thread"]["progress_notes"] == []

    def test_id_format_includes_keyword(self):
        state = _make_state()
        result = create_thread_logic("苏念与朱棣的秘密关系", ["朱棣", "苏念"], state)
        assert "苏念" in result["thread_id"] or "秘密" in result["thread_id"]

    def test_id_increments_for_same_scene_keyword(self):
        state = _make_state()
        r1 = create_thread_logic("复仇线索一", ["朱棣"], state)
        r2 = create_thread_logic("复仇线索二", ["朱棣"], state)
        assert r1["thread_id"] != r2["thread_id"]
        # Second should have higher index
        idx1 = r1["thread_id"].rsplit("_", 1)[-1]
        idx2 = r2["thread_id"].rsplit("_", 1)[-1]
        assert int(idx2) > int(idx1)

    def test_invalid_actor_returns_error(self):
        state = _make_state()
        result = create_thread_logic("某线索", ["不存在的角色"], state)
        assert result["status"] == "error"
        assert "不存在" in result["message"]

    def test_thread_added_to_plot_threads(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        assert len(state["plot_threads"]) == 1
        assert state["plot_threads"][0]["description"] == "测试线索"

    def test_involved_actors_stored(self):
        state = _make_state()
        result = create_thread_logic("双主角线索", ["朱棣", "苏念"], state)
        assert result["thread"]["involved_actors"] == ["朱棣", "苏念"]


class TestUpdateThreadLogic:
    """Test update_thread_logic pure function."""

    def test_updates_status(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = update_thread_logic(thread_id, status="resolving", progress_note=None, state=state)
        assert result["status"] == "success"
        assert state["plot_threads"][0]["status"] == "resolving"

    def test_appends_progress_note(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = update_thread_logic(thread_id, status=None, progress_note="林风发现朱棣的秘密", state=state)
        assert result["status"] == "success"
        assert len(state["plot_threads"][0]["progress_notes"]) == 1
        assert "林风发现朱棣的秘密" in state["plot_threads"][0]["progress_notes"][0]
        assert "第3场" in state["plot_threads"][0]["progress_notes"][0]

    def test_updates_last_updated_scene(self):
        state = _make_state(current_scene=10)
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        update_thread_logic(thread_id, status=None, progress_note="更新", state=state)
        assert state["plot_threads"][0]["last_updated_scene"] == 10

    def test_nonexistent_thread_returns_error(self):
        state = _make_state()
        result = update_thread_logic("thread_99_不存在_1", status="active", progress_note=None, state=state)
        assert result["status"] == "error"

    def test_invalid_status_returns_error(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = update_thread_logic(thread_id, status="invalid", progress_note=None, state=state)
        assert result["status"] == "error"

    def test_progress_notes_fifo_trim(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        # Add 11 notes
        for i in range(11):
            update_thread_logic(thread_id, status=None, progress_note=f"笔记{i}", state=state)
        assert len(state["plot_threads"][0]["progress_notes"]) == MAX_PROGRESS_NOTES
        # The oldest should be gone — first remaining should be note 1 (note 0 was trimmed)
        assert "笔记1" in state["plot_threads"][0]["progress_notes"][0]

    def test_both_status_and_note_together(self):
        state = _make_state()
        create_thread_logic("测试线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = update_thread_logic(thread_id, status="dormant", progress_note="暂停推进", state=state)
        assert result["status"] == "success"
        assert state["plot_threads"][0]["status"] == "dormant"
        assert len(state["plot_threads"][0]["progress_notes"]) == 1


class TestResolveThreadLogic:
    """Test resolve_thread_logic pure function."""

    def test_resolves_thread(self):
        state = _make_state()
        create_thread_logic("复仇计划", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = resolve_thread_logic(thread_id, "朱棣放弃了复仇", state)
        assert result["status"] == "success"
        assert state["plot_threads"][0]["status"] == "resolved"
        assert result["resolution"] == "朱棣放弃了复仇"

    def test_resolution_note_appended(self):
        state = _make_state()
        create_thread_logic("复仇计划", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        resolve_thread_logic(thread_id, "大结局", state)
        notes = state["plot_threads"][0]["progress_notes"]
        assert any("[解决]" in n for n in notes)

    def test_nonexistent_thread_returns_error(self):
        state = _make_state()
        result = resolve_thread_logic("thread_99_不存在_1", "无所谓", state)
        assert result["status"] == "error"

    def test_already_resolved_returns_error(self):
        state = _make_state()
        create_thread_logic("复仇计划", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        resolve_thread_logic(thread_id, "已解决", state)
        # Try resolving again
        result = resolve_thread_logic(thread_id, "再次解决", state)
        assert result["status"] == "error"

    def test_linked_conflict_hint(self):
        state = _make_state()
        create_thread_logic("复仇计划", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        # Add a linked conflict
        state["conflict_engine"]["active_conflicts"].append({
            "id": "conflict_3_escalation_1",
            "thread_id": thread_id,
            "type": "escalation",
            "description": "矛盾升级",
            "involved_actors": ["朱棣"],
        })
        result = resolve_thread_logic(thread_id, "和解", state)
        assert result["status"] == "success"
        assert "linked_conflict_hint" in result
        assert "conflict_3_escalation_1" in result["linked_conflict_hint"]

    def test_no_hint_when_no_linked_conflict(self):
        state = _make_state()
        create_thread_logic("独立线索", ["朱棣"], state)
        thread_id = state["plot_threads"][0]["id"]
        result = resolve_thread_logic(thread_id, "自然结束", state)
        assert result["status"] == "success"
        assert "linked_conflict_hint" not in result


class TestSetActorArcLogic:
    """Test set_actor_arc_logic pure function."""

    def test_sets_arc_type_and_progress(self):
        state = _make_state()
        result = set_actor_arc_logic("朱棣", arc_type="growth", arc_stage=None, progress=50, related_threads=None, state=state)
        assert result["status"] == "success"
        assert result["arc_progress"]["arc_type"] == "growth"
        assert result["arc_progress"]["progress"] == 50

    def test_partial_update_only_progress(self):
        state = _make_state()
        # First set arc_type
        set_actor_arc_logic("朱棣", arc_type="fall", arc_stage=None, progress=None, related_threads=None, state=state)
        # Then only update progress
        result = set_actor_arc_logic("朱棣", arc_type=None, arc_stage=None, progress=75, related_threads=None, state=state)
        assert result["status"] == "success"
        assert result["arc_progress"]["arc_type"] == "fall"  # Unchanged
        assert result["arc_progress"]["progress"] == 75

    def test_invalid_arc_type_returns_error(self):
        state = _make_state()
        result = set_actor_arc_logic("朱棣", arc_type="invalid", arc_stage=None, progress=None, related_threads=None, state=state)
        assert result["status"] == "error"

    def test_invalid_arc_stage_returns_error(self):
        state = _make_state()
        result = set_actor_arc_logic("朱棣", arc_type=None, arc_stage="invalid", progress=None, related_threads=None, state=state)
        assert result["status"] == "error"

    def test_progress_out_of_range_returns_error(self):
        state = _make_state()
        result = set_actor_arc_logic("朱棣", arc_type=None, arc_stage=None, progress=150, related_threads=None, state=state)
        assert result["status"] == "error"
        result = set_actor_arc_logic("朱棣", arc_type=None, arc_stage=None, progress=-1, related_threads=None, state=state)
        assert result["status"] == "error"

    def test_nonexistent_actor_returns_error(self):
        state = _make_state()
        result = set_actor_arc_logic("不存在", arc_type="growth", arc_stage=None, progress=None, related_threads=None, state=state)
        assert result["status"] == "error"

    def test_initializes_arc_progress_if_missing(self):
        state = _make_state()
        # Remove arc_progress
        del state["actors"]["朱棣"]["arc_progress"]
        result = set_actor_arc_logic("朱棣", arc_type="redemption", arc_stage="climax", progress=80, related_threads=None, state=state)
        assert result["status"] == "success"
        assert result["arc_progress"]["arc_type"] == "redemption"
        assert result["arc_progress"]["arc_stage"] == "climax"
        assert result["arc_progress"]["progress"] == 80

    def test_related_threads_update(self):
        state = _make_state()
        result = set_actor_arc_logic("朱棣", arc_type=None, arc_stage=None, progress=None, related_threads=["thread_3_复仇_1"], state=state)
        assert result["status"] == "success"
        assert result["arc_progress"]["related_threads"] == ["thread_3_复仇_1"]
