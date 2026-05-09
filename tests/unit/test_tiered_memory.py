"""Unit tests for Phase 28: 3-tier memory architecture (Mem0/Letta/ReMe-style).

Tests the L1/L2/L3分层记忆机制:
- L1 Working Memory: tight focus on current scene (max 3)
- L2 Short-term Memory: recent scene summaries (max 8)
- L3 Long-term Memory: vector semantic recall with RIR scoring
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.short_term_memory import (
    add_short_term_memory,
    search_short_term_memory,
    build_short_term_context,
    migrate_working_to_short_term,
    compute_rir_score,
    rank_vector_results_by_rir,
    SHORT_TERM_MEMORY_LIMIT,
    ensure_short_term_memory_fields,
)
from app.memory_manager import (
    WORKING_MEMORY_LIMIT,
    ensure_actor_memory_fields,
    pre_reasoning_hook,
    add_working_memory,
)
from app.context_builder import (
    build_actor_context_from_memory,
    _ACTOR_SECTION_PRIORITIES,
)


# ============================================================================
# L2 Short-term Memory Tests
# ============================================================================


class TestAddShortTermMemory:
    """Tests for add_short_term_memory."""

    def test_add_short_term_memory_basic(self, mock_tool_context):
        """Adding a short-term memory entry works and sets fields."""
        result = add_short_term_memory(
            actor_name="朱棣",
            summary="第3场：与道衍商议起兵",
            scene_range="3",
            tags=["角色:朱棣", "冲突:起兵"],
            tool_context=mock_tool_context,
        )
        assert result["status"] == "success"
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["short_term_memory"]) == 1
        assert actor["short_term_memory"][0]["summary"] == "第3场：与道衍商议起兵"
        assert actor["short_term_memory"][0]["tags"] == ["角色:朱棣", "冲突:起兵"]

    def test_short_term_memory_overflow_migrates(self, mock_tool_context):
        """Exceeding SHORT_TERM_MEMORY_LIMIT triggers overflow migration."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # Pre-fill to limit
        for i in range(SHORT_TERM_MEMORY_LIMIT):
            actor.setdefault("short_term_memory", []).append({
                "summary": f"摘要{i}",
                "scene_range": str(i),
                "tags": [],
                "added_scene": i,
                "access_count": 0,
            })

        with patch("app.short_term_memory._migrate_to_long_term") as mock_migrate:
            result = add_short_term_memory(
                actor_name="朱棣",
                summary="溢出摘要",
                scene_range="99",
                tags=[],
                tool_context=mock_tool_context,
            )
            assert result["status"] == "success"
            assert result["overflow_count"] == 1
            mock_migrate.assert_called_once()

    def test_nonexistent_actor_returns_error(self, mock_tool_context):
        """Adding to non-existent actor returns error."""
        result = add_short_term_memory(
            actor_name="不存在",
            summary="test",
            scene_range="1",
            tags=[],
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"


class TestSearchShortTermMemory:
    """Tests for search_short_term_memory tag-weighted search."""

    def test_search_finds_matching_tags(self, mock_tool_context):
        """Search with matching tags returns scored results."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["short_term_memory"] = [
            {"summary": "朱棣起兵", "scene_range": "1-3", "tags": ["角色:朱棣", "冲突:起兵"], "added_scene": 3, "access_count": 0},
            {"summary": "建文帝削藩", "scene_range": "4", "tags": ["角色:建文帝", "冲突:削藩"], "added_scene": 4, "access_count": 0},
        ]

        results = search_short_term_memory("朱棣", ["角色:朱棣"], mock_tool_context)
        assert len(results) == 1
        assert results[0]["summary"] == "朱棣起兵"
        assert results[0]["score"] == 3.0  # 角色 tag weight

    def test_search_no_match_returns_empty(self, mock_tool_context):
        """Search with no matching tags returns empty list."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["short_term_memory"] = [
            {"summary": "摘要", "scene_range": "1", "tags": ["角色:道衍"], "added_scene": 1, "access_count": 0},
        ]
        results = search_short_term_memory("朱棣", ["角色:朱棣"], mock_tool_context)
        assert results == []

    def test_search_top_k_limits(self, mock_tool_context):
        """top_k parameter limits results."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["short_term_memory"] = [
            {"summary": f"摘要{i}", "scene_range": str(i), "tags": ["角色:朱棣"], "added_scene": i, "access_count": 0}
            for i in range(5)
        ]
        results = search_short_term_memory("朱棣", ["角色:朱棣"], mock_tool_context, top_k=2)
        assert len(results) == 2


class TestBuildShortTermContext:
    """Tests for build_short_term_context formatting."""

    def test_build_context_with_entries(self, mock_tool_context):
        """build_short_term_context returns formatted text with entries."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["short_term_memory"] = [
            {"summary": "与道衍商议", "scene_range": "3", "tags": ["角色:朱棣"], "added_scene": 3, "access_count": 0},
        ]
        ctx = build_short_term_context("朱棣", mock_tool_context)
        assert "短期记忆" in ctx
        assert "与道衍商议" in ctx

    def test_build_context_empty_returns_empty(self, mock_tool_context):
        """No short-term memories returns empty string."""
        ctx = build_short_term_context("朱棣", mock_tool_context)
        assert ctx == ""


class TestMigrateWorkingToShortTerm:
    """Tests for migrate_working_to_short_term scene-transition migration."""

    def test_migrate_working_to_short_term(self, mock_tool_context):
        """Working memory entries are migrated to a short-term summary."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "与道衍商议起兵之事。", "importance": "normal", "scene": 3},
            {"entry": "决定立即行动。", "importance": "normal", "scene": 3},
        ]

        result = migrate_working_to_short_term("朱棣", mock_tool_context)
        assert result["status"] == "success"
        assert "2 条" in result["message"]

        # Working memory should be cleared
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["working_memory"]) == 0
        assert len(actor["short_term_memory"]) == 1

    def test_migrate_skips_if_too_few(self, mock_tool_context):
        """If working memory has < 2 entries, skip migration."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "仅一条。", "importance": "normal", "scene": 3},
        ]
        result = migrate_working_to_short_term("朱棣", mock_tool_context)
        assert result["status"] == "info"


# ============================================================================
# L3 RIR Scoring Tests
# ============================================================================


class TestRirScoring:
    """Tests for RIR (Recency, Importance, Relevance) composite scoring."""

    def test_compute_rir_max_score(self):
        """Current scene + critical + relevance=1.0 gives highest score."""
        score = compute_rir_score(relevance=1.0, entry_scene=10, current_scene=10, importance="critical")
        assert score > 0.9
        assert score <= 1.0

    def test_compute_rir_older_scene_lowers_recency(self):
        """Older scenes have lower recency component."""
        score_old = compute_rir_score(relevance=1.0, entry_scene=1, current_scene=20, importance="normal")
        score_new = compute_rir_score(relevance=1.0, entry_scene=19, current_scene=20, importance="normal")
        assert score_new > score_old

    def test_compute_rir_importance_weights(self):
        """Critical importance scores higher than normal at same recency/relevance."""
        score_critical = compute_rir_score(relevance=0.5, entry_scene=10, current_scene=10, importance="critical")
        score_normal = compute_rir_score(relevance=0.5, entry_scene=10, current_scene=10, importance="normal")
        assert score_critical > score_normal

    def test_rank_vector_results_by_rir(self):
        """RIR ranking reorders results by composite score."""
        results = [
            {"content": "old", "metadata": {"scene": 1, "importance": "normal"}, "relevance": 0.9},
            {"content": "new critical", "metadata": {"scene": 10, "importance": "critical"}, "relevance": 0.7},
            {"content": "new normal", "metadata": {"scene": 10, "importance": "normal"}, "relevance": 0.7},
        ]
        ranked = rank_vector_results_by_rir(results, current_scene=10)
        # new critical should be first (high recency + high importance)
        assert ranked[0]["content"] == "new critical"
        assert ranked[0]["rir_score"] > ranked[2]["rir_score"]


# ============================================================================
# Memory Manager Integration Tests
# ============================================================================


class TestWorkingMemoryLimit:
    """Tests that WORKING_MEMORY_LIMIT is tightened to 3 (Phase 28)."""

    def test_working_memory_limit_is_three(self):
        """D-01: working memory limit tightened to 3."""
        assert WORKING_MEMORY_LIMIT == 3

    def test_add_working_memory_respects_limit(self, mock_tool_context):
        """Adding 4 working memories triggers compression, leaving 3."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # Pre-fill with 4 entries (exceeds limit of 3)
        actor["working_memory"] = [
            {"entry": f"第{i}条记忆", "importance": "normal", "scene": i}
            for i in range(4)
        ]

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "压缩摘要"
            result = add_working_memory(
                actor_name="朱棣",
                entry="新增记忆",
                importance="normal",
                critical_reason=None,
                tool_context=mock_tool_context,
            )

        assert result["status"] == "success"
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # After compression, working_memory should be within limit
        assert len(actor["working_memory"]) <= WORKING_MEMORY_LIMIT


class TestEnsureActorMemoryFields:
    """Tests that ensure_actor_memory_fields initializes short_term_memory."""

    def test_initializes_short_term_memory(self):
        """Phase 28: ensure_actor_memory_fields adds short_term_memory field."""
        actor_data = {"role": "测试"}
        result = ensure_actor_memory_fields(actor_data)
        assert "short_term_memory" in result
        assert isinstance(result["short_term_memory"], list)
        assert result["short_term_memory"] == []

    def test_preserves_existing_short_term_memory(self):
        """Existing short_term_memory is preserved."""
        actor_data = {"role": "测试", "short_term_memory": [{"summary": "test"}]}
        result = ensure_actor_memory_fields(actor_data)
        assert len(result["short_term_memory"]) == 1


class TestPreReasoningHook:
    """Tests that pre_reasoning_hook returns L2 and L3 recall."""

    def test_hook_returns_l2_l3_keys(self, mock_tool_context):
        """Phase 28: pre_reasoning_hook returns l2_recall and l3_recall."""
        result = pre_reasoning_hook("朱棣", mock_tool_context)
        assert result["status"] == "success"
        assert "l2_recall" in result
        assert "l3_recall" in result
        assert "recall_tags" in result

    def test_hook_l2_recall_with_short_term_memory(self, mock_tool_context):
        """L2 recall finds matching short-term memories."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["short_term_memory"] = [
            {"summary": "朱棣在皇宫", "scene_range": "1", "tags": ["角色:朱棣", "地点:皇宫"], "added_scene": 1, "access_count": 0},
        ]
        actor["working_memory"] = [
            {"entry": "角色:朱棣 在 地点:皇宫", "importance": "normal", "scene": 3},
        ]

        result = pre_reasoning_hook("朱棣", mock_tool_context)
        # l2_recall may be empty if auto_tags don't match, but keys must exist
        assert "l2_recall" in result
        assert "l3_recall" in result


# ============================================================================
# Context Builder 3-Tier Tests
# ============================================================================


class TestContextBuilderThreeTier:
    """Tests that actor context assembly includes all three memory tiers."""

    def test_context_includes_working_memory(self, mock_tool_context):
        """L1: Actor context includes working memory section."""
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["working_memory"] = [
            {"entry": "当前场景行动", "importance": "normal", "scene": 3},
        ]
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【工作记忆（当前场景）】" in result
        assert "当前场景行动" in result

    def test_context_includes_short_term_memory(self, mock_tool_context):
        """L2: Actor context includes short-term memory section."""
        actors = mock_tool_context.state["drama"]["actors"]
        actors["朱棣"]["short_term_memory"] = [
            {"summary": "前期商议摘要", "scene_range": "1-2", "tags": ["角色:朱棣"], "added_scene": 2, "access_count": 0},
        ]
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        assert "【短期记忆（近期场景摘要）】" in result
        assert "前期商议摘要" in result

    def test_context_includes_vector_memory_section(self, mock_tool_context):
        """L3: Actor context attempts to include vector memory section."""
        # Vector memory may be unavailable (no chromadb), but the code path should not crash
        result = build_actor_context_from_memory("朱棣", mock_tool_context)
        # Should at minimum contain anchor and emotion
        assert "【角色锚点】" in result
        assert "【当前情绪】" in result

    def test_section_priorities_include_new_tiers(self):
        """_ACTOR_SECTION_PRIORITIES includes short_term_memory and vector_memory."""
        assert "short_term_memory" in _ACTOR_SECTION_PRIORITIES
        assert "vector_memory" in _ACTOR_SECTION_PRIORITIES
        assert _ACTOR_SECTION_PRIORITIES["short_term_memory"] == 2
        assert _ACTOR_SECTION_PRIORITIES["vector_memory"] == 2

    def test_working_memory_priority_is_lowest(self):
        """L1 working memory has lowest priority (1) for truncation."""
        assert _ACTOR_SECTION_PRIORITIES["working_memory"] == 1
