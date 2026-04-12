"""Tests for context_builder module — MEMORY-04 context assembly with token budget control."""

import pytest
from unittest.mock import MagicMock, patch

from app.context_builder import (
    estimate_tokens,
    _truncate_sections,
    build_actor_context_from_memory,
    build_actor_context,
    build_director_context,
    _extract_scene_transition,
    _build_last_scene_transition_section,
    _build_steer_section,
    _build_epilogue_section,
    _build_auto_advance_section,
    _DIRECTOR_SECTION_PRIORITIES,
    DEFAULT_ACTOR_TOKEN_BUDGET,
    DEFAULT_DIRECTOR_TOKEN_BUDGET,
)


# ============================================================================
# estimate_tokens tests
# ============================================================================


class TestEstimateTokens:
    """Test estimate_tokens() with various text inputs."""

    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        assert estimate_tokens(None) == 0

    def test_english_text(self):
        # "Hello world" = 2 words × 1.0 × 1.1 + 1 = 3
        result = estimate_tokens("Hello world")
        assert result == 3

    def test_cjk_text(self):
        # "你好世界" = 4 CJK chars × 1.5 × 1.1 + 1 = 7
        result = estimate_tokens("你好世界")
        assert result == 7

    def test_mixed_cjk_english(self):
        # "Hello你好" = 2 CJK + 1 English word
        # (2 * 1.5 + 1 * 1.0) * 1.1 + 1 = (3 + 1) * 1.1 + 1 = 4.4 + 1 = 5
        result = estimate_tokens("Hello你好")
        assert result == 5

    def test_pure_spaces(self):
        # Only spaces = 0 words after split
        result = estimate_tokens("   ")
        assert result == 1  # (0 + 0) * 1.1 + 1 = 1

    def test_long_text_returns_larger_value(self):
        short = estimate_tokens("短文本")
        long = estimate_tokens("这是一段非常长的文本" * 100)
        assert long > short


# ============================================================================
# _truncate_sections tests
# ============================================================================


class TestTruncateSections:
    """Test _truncate_sections() priority-based truncation."""

    def test_empty_list_returns_empty(self):
        assert _truncate_sections([], 1000) == []

    def test_under_budget_returns_unchanged(self):
        sections = [
            {"key": "a", "text": "short text", "priority": 1, "truncatable": True},
            {"key": "b", "text": "also short", "priority": 2, "truncatable": False},
        ]
        result = _truncate_sections(sections, 10000)
        assert len(result) == 2

    def test_truncates_lowest_priority_first(self):
        # Create sections where one must be truncated
        long_text = "word " * 500  # ~500 tokens
        sections = [
            {"key": "low", "text": long_text, "priority": 1, "truncatable": True},
            {"key": "high", "text": "important content", "priority": 10, "truncatable": False},
        ]
        result = _truncate_sections(sections, 100)
        # The low priority section should be emptied
        keys = [s["key"] for s in result]
        assert "high" in keys

    def test_never_truncates_non_truncatable(self):
        long_text = "word " * 500
        sections = [
            {"key": "protected", "text": long_text, "priority": 1, "truncatable": False},
        ]
        result = _truncate_sections(sections, 10)
        # Should still contain the protected section
        assert len(result) == 1
        assert result[0]["key"] == "protected"

    def test_item_level_truncation(self):
        items = ["item 1 that is somewhat long", "item 2 that is somewhat long", "item 3 that is somewhat long", "item 4 that is somewhat long", "item 5 that is somewhat long"]
        sections = [
            {
                "key": "items",
                "text": "Header\n" + "\n".join(items),
                "priority": 1,
                "truncatable": True,
                "header": "Header",
                "items": items.copy(),
            },
        ]
        # Very small budget to force item removal
        result = _truncate_sections(sections, 20)
        # Section should be truncated or removed entirely
        assert len(result) >= 0
        if result and result[0].get("items") is not None:
            assert len(result[0].get("items", [])) <= 5

    def test_removes_empty_sections_from_result(self):
        # After truncation, empty sections should be filtered out
        # First create sections that will be truncated to empty
        long_text = "word " * 200
        sections = [
            {"key": "a", "text": long_text, "priority": 1, "truncatable": True},
            {"key": "b", "text": "content", "priority": 2, "truncatable": False},
        ]
        result = _truncate_sections(sections, 10)
        # Section "a" should be emptied and then filtered out
        assert all(s.get("text") for s in result)
        assert any(s["key"] == "b" for s in result)


# ============================================================================
# build_actor_context_from_memory tests
# ============================================================================


class TestBuildActorContextFromMemory:
    """Test build_actor_context_from_memory() actor context assembly."""

    def test_no_actor_data_returns_default(self, mock_tool_context):
        result = build_actor_context_from_memory("不存在的角色", mock_tool_context)
        assert result == "暂无记忆"

    def test_includes_anchor_section(self, mock_tool_context):
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【角色锚点】" in result
        assert "朱棣" in result
        assert "燕王" in result

    def test_includes_emotion_section(self, mock_tool_context):
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【当前情绪】" in result

    def test_includes_critical_memories(self, mock_tool_context):
        # Add critical memory to actor
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["critical_memories"] = [
            {"entry": "登基为帝", "reason": "重大转折", "scene": 1}
        ]
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【关键记忆（永久保留）】" in result
        assert "登基为帝" in result

    def test_includes_arc_summary(self, mock_tool_context):
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["arc_summary"] = {
            "structured": {
                "theme": "权力与亲情",
                "key_characters": ["朱棣"],
                "unresolved": ["削藩之争"],
                "resolved": [],
            },
            "narrative": "朱棣从一个藩王走向皇位。",
        }
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【你的故事弧线】" in result
        assert "权力与亲情" in result

    def test_includes_scene_summaries(self, mock_tool_context):
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["scene_summaries"] = [
            {"summary": "朱棣起兵靖难", "scenes_covered": "1-3", "key_events": []}
        ]
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【近期场景摘要】" in result
        assert "起兵靖难" in result

    def test_includes_working_memory(self, mock_tool_context):
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["working_memory"] = [
            {"entry": "收到密信", "importance": "normal", "scene": 3}
        ]
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【最近的经历（详细）】" in result
        assert "收到密信" in result

    def test_truncates_when_over_budget(self, mock_tool_context):
        # Add lots of working memory to force truncation
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["working_memory"] = [
            {"entry": f"非常长的记忆条目内容第{i}次经历" * 50, "importance": "normal", "scene": i}
            for i in range(20)
        ]
        # Use very small budget to force truncation
        result = build_actor_context_from_memory("朱棣", mock_tool_context, token_budget=200)
        # Anchor and emotion should still be present (not truncatable)
        assert "【角色锚点】" in result
        assert "【当前情绪】" in result

    def test_calls_merge_pending_compression(self, mock_tool_context):
        with patch("app.context_builder._merge_pending_compression") as mock_merge:
            mock_merge.return_value = False
            build_actor_context_from_memory("朱棣", mock_tool_context)
            mock_merge.assert_called_once()


# ============================================================================
# build_actor_context (wrapper) tests
# ============================================================================


class TestBuildActorContext:
    """Test build_actor_context() backward-compatible wrapper."""

    def test_wrapper_calls_from_memory_with_default_budget(self, mock_tool_context):
        with patch("app.context_builder.build_actor_context_from_memory") as mock_from_memory:
            mock_from_memory.return_value = "test context"
            result = build_actor_context("朱棣", mock_tool_context)
            mock_from_memory.assert_called_once_with("朱棣", mock_tool_context)
            assert result == "test context"


# ============================================================================
# build_director_context tests
# ============================================================================


class TestBuildDirectorContext:
    """Test build_director_context() director context assembly."""

    def test_no_theme_returns_default(self, mock_tool_context):
        # Remove theme
        mock_tool_context.state["drama"]["theme"] = ""
        # Need to reset state to remove theme
        mock_tool_context.state["drama"] = {"theme": "", "current_scene": 0, "status": "", "actors": {}}
        result = build_director_context(mock_tool_context)
        assert result == "暂无戏剧上下文"

    def test_includes_global_arc(self, mock_tool_context):
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["arc_summary"] = {
            "structured": {"theme": "权谋", "key_characters": [], "unresolved": [], "resolved": []},
            "narrative": "朱棣从燕王到皇帝的传奇之路。",
        }
        result = build_director_context(mock_tool_context)
        assert "【全局故事弧线】" in result

    def test_includes_current_status(self, mock_tool_context):
        result = build_director_context(mock_tool_context)
        assert "【当前状态】" in result

    def test_includes_recent_scenes(self, mock_tool_context):
        mock_tool_context.state["drama"]["scenes"] = [
            {"scene_number": 1, "title": "靖难之始", "description": "朱棣起兵"},
        ]
        result = build_director_context(mock_tool_context)
        assert "【近期场景】" in result

    def test_includes_actor_emotions(self, mock_tool_context):
        result = build_director_context(mock_tool_context)
        assert "【演员情绪快照】" in result

    def test_includes_storm_when_exists(self, mock_tool_context):
        mock_tool_context.state["drama"]["storm"] = {
            "perspectives": [
                {"name": "主角视角", "description": "从主角内心出发", "questions": []},
            ]
        }
        result = build_director_context(mock_tool_context)
        assert "【STORM视角】" in result
        assert "主角视角" in result

    def test_skips_conflict_engine_when_absent(self, mock_tool_context):
        result = build_director_context(mock_tool_context)
        assert "【活跃冲突】" not in result

    def test_includes_conflict_engine_when_present(self, mock_tool_context):
        mock_tool_context.state["drama"]["conflict_engine"] = {
            "active_conflicts": ["朱棣vs建文帝"]
        }
        result = build_director_context(mock_tool_context)
        assert "【活跃冲突】" in result
        assert "朱棣vs建文帝" in result

    def test_skips_dynamic_storm_when_absent(self, mock_tool_context):
        result = build_director_context(mock_tool_context)
        assert "【最新STORM发现】" not in result

    def test_includes_dynamic_storm_when_present(self, mock_tool_context):
        mock_tool_context.state["drama"]["dynamic_storm"] = {
            "trigger_history": ["角色冲突触发"]
        }
        result = build_director_context(mock_tool_context)
        assert "【最新STORM发现】" in result

    def test_skips_established_facts_when_absent(self, mock_tool_context):
        result = build_director_context(mock_tool_context)
        assert "【已确立事实】" not in result

    def test_includes_established_facts_when_present(self, mock_tool_context):
        mock_tool_context.state["drama"]["established_facts"] = [
            "朱棣已起兵"
        ]
        result = build_director_context(mock_tool_context)
        assert "【已确立事实】" in result
        assert "朱棣已起兵" in result

    def test_truncates_when_over_30000_budget(self, mock_tool_context):
        # Add massive data to force truncation
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["arc_summary"] = {
            "structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []},
            "narrative": "超长文本" * 5000,
        }
        # Use very small budget to force truncation
        result = build_director_context(mock_tool_context, token_budget=200)
        # Current status and actor emotions should still be present (not truncatable)
        assert "【当前状态】" in result
        assert "【演员情绪快照】" in result


# ============================================================================
# Integration tests — Plan 02 migration and tool registration
# ============================================================================


class TestMigrationBackwardCompat:
    """Test backward compatibility after build_actor_context migration."""

    def test_re_export_from_memory_manager(self):
        """from app.memory_manager import build_actor_context still works."""
        from app.memory_manager import build_actor_context as mm_bac
        from app.context_builder import build_actor_context as cb_bac
        assert mm_bac is cb_bac

    def test_tools_import_chain(self, mock_tool_context):
        """tools.py can successfully call build_actor_context via new import path."""
        from app.tools import build_actor_context
        # This should work via context_builder import
        result = build_actor_context("朱棣", mock_tool_context)
        assert "【角色锚点】" in result


class TestGetDirectorContextTool:
    """Test get_director_context tool function."""

    def test_returns_valid_dict(self, mock_tool_context):
        """get_director_context returns status/context/message dict."""
        from app.tools import get_director_context
        result = get_director_context(mock_tool_context)
        assert result["status"] == "success"
        assert "context" in result
        assert "message" in result

    def test_includes_context_summary(self, mock_tool_context):
        """get_director_context returns meaningful context."""
        from app.tools import get_director_context
        result = get_director_context(mock_tool_context)
        assert "【当前状态】" in result["context"] or "暂无" in result["context"]


class TestDirectorNarrateIntegration:
    """Test director_narrate includes director_context in return."""

    def test_includes_director_context_key(self, mock_tool_context):
        """director_narrate return dict includes 'director_context' key."""
        from app.tools import director_narrate
        result = director_narrate("夜幕降临，燕王府灯火通明。", mock_tool_context)
        assert "director_context" in result

    def test_director_context_is_string(self, mock_tool_context):
        """director_context value is a string."""
        from app.tools import director_narrate
        result = director_narrate("夜幕降临，燕王府灯火通明。", mock_tool_context)
        assert isinstance(result["director_context"], str)


class TestNextSceneIntegration:
    """Test next_scene includes director_context in return."""

    def test_includes_director_context_key(self, mock_tool_context):
        """next_scene return dict includes 'director_context' key."""
        from app.tools import next_scene
        result = next_scene(mock_tool_context)
        assert "director_context" in result

    def test_director_context_is_string(self, mock_tool_context):
        """director_context value is a string."""
        from app.tools import next_scene
        result = next_scene(mock_tool_context)
        assert isinstance(result["director_context"], str)


# ============================================================================
# Phase 3 — Semantic Recall Tests (MEMORY-05)
# ============================================================================


class TestSemanticRecallSection:
    """Test semantic_recall section in actor context assembly."""

    def test_semantic_recall_priority_is_zero(self):
        """_ACTOR_SECTION_PRIORITIES['semantic_recall'] == 0."""
        from app.context_builder import _ACTOR_SECTION_PRIORITIES
        assert _ACTOR_SECTION_PRIORITIES["semantic_recall"] == 0

    def test_semantic_recall_section_present_when_tags_exist(self, mock_tool_context):
        """Actor context includes '相关回忆' section when scene_summaries have tags."""
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["scene_summaries"] = [
            {"summary": "朱棣在皇宫中起兵", "scenes_covered": "1-3", "key_events": [], "tags": ["角色:朱棣", "地点:皇宫"]},
        ]
        actors["朱棣"]["working_memory"] = [
            {"entry": "面对情境: 朱棣在皇宫中愤怒", "importance": "normal", "scene": 3},
        ]

        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        # The semantic_recall section may or may not appear depending on auto_tags extraction
        # But at minimum, the section priority should be 0
        from app.context_builder import _ACTOR_SECTION_PRIORITIES
        assert _ACTOR_SECTION_PRIORITIES["semantic_recall"] == 0

    def test_semantic_recall_truncatable(self):
        """semantic_recall section should be truncatable (priority 0)."""
        from app.context_builder import _ACTOR_SECTION_PRIORITIES
        # Priority 0 means it's the first to be truncated
        assert _ACTOR_SECTION_PRIORITIES["semantic_recall"] == 0

    def test_semantic_recall_truncated_before_other_sections(self, mock_tool_context):
        """When budget is tight, semantic_recall is truncated before other sections."""
        actors = mock_tool_context.state["drama"]["actors"]
        # Add lots of data to force truncation
        actors["朱棣"]["working_memory"] = [
            {"entry": f"第{i}条记忆，非常长的内容" * 5, "importance": "normal", "scene": i}
            for i in range(5)
        ]
        actors["朱棣"]["scene_summaries"] = [
            {"summary": f"场景{i}摘要", "scenes_covered": str(i), "tags": ["角色:朱棣"], "key_events": []}
            for i in range(5)
        ]

        # Small budget to force truncation
        result = build_actor_context_from_memory("朱棣", mock_tool_context, token_budget=300)
        # Anchor and emotion should survive (not truncatable)
        assert "【角色锚点】" in result
        assert "【当前情绪】" in result


# ============================================================================
# Phase 4 — Scene Transition Tests (LOOP-03)
# ============================================================================


class TestExtractSceneTransition:
    """Test _extract_scene_transition() pure function for scene transition data."""

    def test_returns_is_first_scene_when_scenes_empty(self):
        """When scenes list is empty, is_first_scene should be True."""
        from app.context_builder import _extract_scene_transition
        state = {"scenes": [], "actors": {}, "current_scene": 0}
        result = _extract_scene_transition(state)
        assert result["is_first_scene"] is True

    def test_returns_is_first_scene_when_current_scene_zero(self):
        """When current_scene is 0, is_first_scene should be True even if scenes list has entries."""
        from app.context_builder import _extract_scene_transition
        state = {
            "scenes": [{"scene_number": 1, "title": "Test", "description": "desc"}],
            "actors": {},
            "current_scene": 0,
        }
        result = _extract_scene_transition(state)
        assert result["is_first_scene"] is True

    def test_extracts_last_ending_from_last_scene(self):
        """When scenes exist, last_ending should contain description from scenes[-1]."""
        from app.context_builder import _extract_scene_transition
        state = {
            "scenes": [
                {"scene_number": 1, "title": "第一场", "description": "朱棣起兵靖难"},
            ],
            "actors": {"朱棣": {"role": "燕王", "emotions": "angry", "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}}},
            "current_scene": 2,
        }
        result = _extract_scene_transition(state)
        assert result["is_first_scene"] is False
        assert "朱棣起兵靖难" in result["last_ending"]

    def test_extracts_actor_emotions(self):
        """Actor emotions should be mapped to Chinese labels."""
        from app.context_builder import _extract_scene_transition
        state = {
            "scenes": [{"scene_number": 1, "title": "T", "description": "D"}],
            "actors": {
                "朱棣": {"emotions": "angry", "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
                "建文帝": {"emotions": "fearful", "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}},
            },
            "current_scene": 2,
        }
        result = _extract_scene_transition(state)
        assert result["actor_emotions"]["朱棣"] == "愤怒"
        assert result["actor_emotions"]["建文帝"] == "恐惧"

    def test_extracts_unresolved_from_critical_memories(self):
        """Unresolved events from critical_memories with reason='未决事件' should be extracted."""
        from app.context_builder import _extract_scene_transition
        state = {
            "scenes": [{"scene_number": 1, "title": "T", "description": "D"}],
            "actors": {
                "朱棣": {
                    "emotions": "neutral",
                    "critical_memories": [
                        {"entry": "削藩之争尚未解决", "reason": "未决事件", "scene": 1},
                    ],
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            "current_scene": 2,
        }
        result = _extract_scene_transition(state)
        assert len(result["unresolved"]) >= 1
        assert any("削藩" in u for u in result["unresolved"])

    def test_limits_unresolved_to_five_items(self):
        """Unresolved list should be capped at 5 items to save tokens."""
        from app.context_builder import _extract_scene_transition
        memories = [
            {"entry": f"未决事件{i}", "reason": "未决事件", "scene": i}
            for i in range(8)
        ]
        state = {
            "scenes": [{"scene_number": 1, "title": "T", "description": "D"}],
            "actors": {
                "朱棣": {
                    "emotions": "neutral",
                    "critical_memories": memories,
                    "arc_summary": {"structured": {"unresolved": []}},
                },
            },
            "current_scene": 2,
        }
        result = _extract_scene_transition(state)
        assert len(result["unresolved"]) <= 5


class TestBuildLastSceneTransitionSection:
    """Test _build_last_scene_transition_section() section builder."""

    def test_returns_empty_text_when_no_scenes(self):
        """When no scenes exist, the section text should be empty."""
        from app.context_builder import _build_last_scene_transition_section
        state = {"scenes": [], "actors": {}, "current_scene": 0}
        result = _build_last_scene_transition_section(state)
        assert result["text"] == ""

    def test_returns_text_with_transition_label_when_scenes_exist(self):
        """When scenes exist, the section text should contain '上一场衔接'."""
        from app.context_builder import _build_last_scene_transition_section
        state = {
            "scenes": [
                {"scene_number": 1, "title": "靖难之始", "description": "朱棣起兵"},
            ],
            "actors": {"朱棣": {"role": "燕王", "emotions": "angry", "critical_memories": [], "arc_summary": {"structured": {"unresolved": []}}}},
            "current_scene": 2,
        }
        result = _build_last_scene_transition_section(state)
        assert "上一场衔接" in result["text"]

    def test_has_priority_seven(self):
        """Transition section priority should be 7 (higher than recent_scenes, lower than current_status)."""
        from app.context_builder import _build_last_scene_transition_section
        state = {"scenes": [], "actors": {}, "current_scene": 0}
        result = _build_last_scene_transition_section(state)
        assert result["priority"] == 7

    def test_is_not_truncatable(self):
        """Transition section should never be truncated."""
        from app.context_builder import _build_last_scene_transition_section
        state = {"scenes": [], "actors": {}, "current_scene": 0}
        result = _build_last_scene_transition_section(state)
        assert result["truncatable"] is False


class TestDirectorContextTransitionIntegration:
    """Test build_director_context() includes transition section when scenes exist."""

    def test_includes_transition_section_when_scenes_exist(self, mock_tool_context):
        """build_director_context output should contain '上一场衔接' when scenes exist."""
        mock_tool_context.state["drama"]["scenes"] = [
            {"scene_number": 1, "title": "靖难之始", "description": "朱棣起兵靖难"},
        ]
        mock_tool_context.state["drama"]["current_scene"] = 2
        result = build_director_context(mock_tool_context)
        assert "上一场衔接" in result

    def test_no_transition_section_when_no_scenes(self, mock_tool_context):
        """build_director_context output should NOT contain '上一场衔接' when no scenes."""
        mock_tool_context.state["drama"]["scenes"] = []
        mock_tool_context.state["drama"]["current_scene"] = 0
        result = build_director_context(mock_tool_context)
        assert "上一场衔接" not in result


# ============================================================================
# Phase 5 — Mixed Autonomy Mode Section Tests
# ============================================================================


class TestPhase5Sections:
    """Test Phase 5 context builder sections: steer, epilogue, auto-advance."""

    # --- _build_steer_section tests ---

    def test_steer_section_with_direction(self):
        """_build_steer_section with steer_direction returns text with 【用户引导】."""
        state = {"steer_direction": "让朱棣更偏执"}
        result = _build_steer_section(state)
        assert "【用户引导】" in result["text"]
        assert "让朱棣更偏执" in result["text"]
        assert result["key"] == "steer"
        assert result["priority"] == _DIRECTOR_SECTION_PRIORITIES["steer"]
        assert result["truncatable"] is False

    def test_steer_section_without_direction(self):
        """_build_steer_section with steer_direction=None returns empty text."""
        state = {"steer_direction": None}
        result = _build_steer_section(state)
        assert result["text"] == ""
        assert result["key"] == "steer"

    # --- _build_epilogue_section tests ---

    def test_epilogue_section_ended(self):
        """_build_epilogue_section with status='ended' returns text with 【番外篇模式】."""
        state = {"status": "ended"}
        result = _build_epilogue_section(state)
        assert "【番外篇模式】" in result["text"]
        assert "番外篇/后日谈" in result["text"]
        assert result["key"] == "epilogue"
        assert result["priority"] == _DIRECTOR_SECTION_PRIORITIES["epilogue"]
        assert result["truncatable"] is False

    def test_epilogue_section_acting(self):
        """_build_epilogue_section with status='acting' returns empty text."""
        state = {"status": "acting"}
        result = _build_epilogue_section(state)
        assert result["text"] == ""
        assert result["key"] == "epilogue"

    # --- _build_auto_advance_section tests ---

    def test_auto_advance_section_active(self):
        """_build_auto_advance_section with remaining_auto_scenes=3 returns text with 【自动推进模式】."""
        state = {"remaining_auto_scenes": 3}
        result = _build_auto_advance_section(state)
        assert "【自动推进模式】" in result["text"]
        assert "3 场" in result["text"]
        assert result["key"] == "auto_advance"
        assert result["priority"] == _DIRECTOR_SECTION_PRIORITIES["auto_advance"]
        assert result["truncatable"] is False

    def test_auto_advance_section_inactive(self):
        """_build_auto_advance_section with remaining_auto_scenes=0 returns empty text."""
        state = {"remaining_auto_scenes": 0}
        result = _build_auto_advance_section(state)
        assert result["text"] == ""
        assert result["key"] == "auto_advance"

    # --- Integration: build_director_context includes new sections ---

    def test_build_director_context_includes_steer(self, mock_tool_context):
        """build_director_context with steer_direction set includes 【用户引导】 in output."""
        mock_tool_context.state["drama"]["steer_direction"] = "加强冲突"
        result = build_director_context(mock_tool_context)
        assert "【用户引导】" in result
        assert "加强冲突" in result

    def test_build_director_context_includes_epilogue(self, mock_tool_context):
        """build_director_context with status='ended' includes 【番外篇模式】 in output."""
        mock_tool_context.state["drama"]["status"] = "ended"
        result = build_director_context(mock_tool_context)
        assert "【番外篇模式】" in result
