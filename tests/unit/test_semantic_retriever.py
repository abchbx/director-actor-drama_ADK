"""Tests for semantic_retriever module — MEMORY-05 tag-based retrieval."""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch

from app.semantic_retriever import (
    TAG_WEIGHTS,
    _parse_tags_from_llm_output,
    _get_tag_weight,
    _compute_tag_score,
    _normalize_scene_range,
    _search_scene_summaries,
    _search_text_layer,
    _dedup_results,
    retrieve_relevant_scenes,
    _extract_auto_tags,
    backfill_tags,
)


# ============================================================================
# Test 1-3: _parse_tags_from_llm_output
# ============================================================================


class TestParseTagsFromLlmOutput:
    """Test _parse_tags_from_llm_output with JSON, regex fallback, and edge cases."""

    def test_json_format_tags(self):
        """Parse JSON format: input '{"summary":"...","tags":["角色:朱棣","地点:皇宫"]}' → ["角色:朱棣", "地点:皇宫"]"""
        result = _parse_tags_from_llm_output(
            '{"summary":"朱棣在皇宫","tags":["角色:朱棣","地点:皇宫"]}'
        )
        assert result == ["角色:朱棣", "地点:皇宫"]

    def test_regex_fallback(self):
        """Regex fallback when JSON fails: '角色:朱棣, 地点:皇宫' → ["角色:朱棣", "地点:皇宫"]"""
        result = _parse_tags_from_llm_output("这是一段文字，角色:朱棣，地点:皇宫。")
        assert "角色:朱棣" in result
        assert "地点:皇宫" in result

    def test_empty_unparseable_returns_empty(self):
        """Empty/unparseable input returns empty list."""
        assert _parse_tags_from_llm_output("") == []
        assert _parse_tags_from_llm_output(None) == []
        assert _parse_tags_from_llm_output("没有标签的文本") == []
        assert _parse_tags_from_llm_output("12345") == []

    def test_json_markdown_fences(self):
        """Parse JSON wrapped in ```json fences."""
        result = _parse_tags_from_llm_output(
            '```json\n{"tags": ["角色:朱棣", "情感:愤怒"]}\n```'
        )
        assert result == ["角色:朱棣", "情感:愤怒"]

    def test_plain_json_list(self):
        """Parse plain JSON list."""
        result = _parse_tags_from_llm_output('["角色:朱棣", "地点:皇宫"]')
        assert result == ["角色:朱棣", "地点:皇宫"]


# ============================================================================
# Test 4: _get_tag_weight
# ============================================================================


class TestGetTagWeight:
    """Test _get_tag_weight returns correct weights for prefix tags."""

    def test_role_weight(self):
        assert _get_tag_weight("角色:朱棣") == 3.0

    def test_conflict_weight(self):
        assert _get_tag_weight("冲突:权力争夺") == 2.0

    def test_event_weight(self):
        assert _get_tag_weight("事件:登基") == 2.0

    def test_emotion_weight(self):
        assert _get_tag_weight("情感:愤怒") == 1.5

    def test_location_weight(self):
        assert _get_tag_weight("地点:皇宫") == 1.0

    def test_no_prefix_weight(self):
        assert _get_tag_weight("权力争夺") == 1.0


# ============================================================================
# Test 5-6: _compute_tag_score
# ============================================================================


class TestComputeTagScore:
    """Test _compute_tag_score weighted matching logic."""

    def test_exact_match_weighted(self):
        """Exact match: query ["角色:朱棣", "情感:愤怒"] vs entry ["角色:朱棣", "地点:皇宫"] → score includes 3.0 for 角色:朱棣."""
        score = _compute_tag_score(["角色:朱棣", "情感:愤怒"], ["角色:朱棣", "地点:皇宫"])
        assert score == 3.0  # Only 角色:朱棣 matches

    def test_value_only_match_lower_weight(self):
        """Value-only match: query "朱棣" matches "角色:朱棣" with weight 1.0."""
        score = _compute_tag_score(["朱棣"], ["角色:朱棣", "地点:皇宫"])
        assert score == 1.0  # Value-only match = 1.0

    def test_no_match(self):
        """No matching tags → score 0."""
        score = _compute_tag_score(["角色:建文帝"], ["角色:朱棣"])
        assert score == 0.0

    def test_multiple_matches(self):
        """Multiple matches add up."""
        score = _compute_tag_score(
            ["角色:朱棣", "地点:皇宫"],
            ["角色:朱棣", "地点:皇宫"]
        )
        assert score == 3.0 + 1.0  # 角色:3.0 + 地点:1.0


# ============================================================================
# Test 7: _normalize_scene_range
# ============================================================================


class TestNormalizeSceneRange:
    """Test _normalize_scene_range converts various formats to integer sets."""

    def test_range_format(self):
        """'3-5' → {3, 4, 5}"""
        assert _normalize_scene_range("3-5") == {3, 4, 5}

    def test_integer_format(self):
        """integer 3 → {3}"""
        assert _normalize_scene_range(3) == {3}

    def test_string_single(self):
        """'3' → {3}"""
        assert _normalize_scene_range("3") == {3}

    def test_empty_string(self):
        """'' → empty set"""
        assert _normalize_scene_range("") == set()

    def test_comma_separated(self):
        """'3,4,5' → {3, 4, 5}"""
        assert _normalize_scene_range("3,4,5") == {3, 4, 5}


# ============================================================================
# Test 8: _search_scene_summaries
# ============================================================================


class TestSearchSceneSummaries:
    """Test _search_scene_summaries returns scored results with matched_tags."""

    def test_returns_scored_results(self):
        summaries = [
            {"summary": "朱棣起兵", "scenes_covered": "1-3", "tags": ["角色:朱棣", "事件:起兵"]},
            {"summary": "建文帝削藩", "scenes_covered": "4", "tags": ["角色:建文帝", "冲突:削藩"]},
        ]
        results = _search_scene_summaries(["角色:朱棣"], summaries)
        assert len(results) == 1
        assert results[0]["source"] == "scene_summaries"
        assert results[0]["score"] == 3.0
        assert "角色:朱棣" in results[0]["matched_tags"]

    def test_empty_tags_skipped(self):
        """Summaries without tags are skipped."""
        summaries = [
            {"summary": "无标签场景", "scenes_covered": "1", "tags": []},
            {"summary": "有标签场景", "scenes_covered": "2", "tags": ["角色:朱棣"]},
        ]
        results = _search_scene_summaries(["角色:朱棣"], summaries)
        assert len(results) == 1
        assert results[0]["text"] == "有标签场景"


# ============================================================================
# Test 9: _search_text_layer
# ============================================================================


class TestSearchTextLayer:
    """Test _search_text_layer matches query tag values against entry text."""

    def test_keyword_match(self):
        entries = [
            {"entry": "朱棣收到密信，非常愤怒", "scene": 3},
            {"entry": "道衍建议起兵", "scene": 4},
        ]
        results = _search_text_layer(["朱棣"], entries, "working_memory")
        assert len(results) == 1
        assert results[0]["score"] == 1.0
        assert results[0]["source"] == "working_memory"

    def test_no_match(self):
        entries = [
            {"entry": "道衍建议起兵", "scene": 4},
        ]
        results = _search_text_layer(["朱棣"], entries, "working_memory")
        assert len(results) == 0


# ============================================================================
# Test 10: retrieve_relevant_scenes actor_name filtering
# ============================================================================


class TestRetrieveRelevantScenesActorFilter:
    """Test retrieve_relevant_scenes with actor_name limits to that actor's memories."""

    def _make_context(self):
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 5,
                "status": "acting",
                "actors": {
                    "朱棣": {
                        "working_memory": [],
                        "scene_summaries": [
                            {"summary": "朱棣起兵", "scenes_covered": "1-3", "tags": ["角色:朱棣"]},
                        ],
                        "critical_memories": [],
                        "arc_summary": {"structured": {}, "narrative": ""},
                    },
                    "道衍": {
                        "working_memory": [],
                        "scene_summaries": [
                            {"summary": "道衍献策", "scenes_covered": "1-3", "tags": ["角色:道衍"]},
                        ],
                        "critical_memories": [],
                        "arc_summary": {"structured": {}, "narrative": ""},
                    },
                },
            }
        }
        return tc

    def test_actor_name_limits_search(self):
        """With actor_name, only that actor's memories are searched."""
        tc = self._make_context()
        results = retrieve_relevant_scenes(["角色:朱棣"], 5, tc, actor_name="朱棣")
        assert len(results) == 1
        assert results[0]["text"] == "朱棣起兵"

    def test_no_actor_name_searches_all(self):
        """Without actor_name, all actors are searched globally."""
        tc = self._make_context()
        results = retrieve_relevant_scenes(["角色:道衍"], 5, tc)
        assert len(results) >= 1
        # Should find 道衍's scene
        assert any(r["text"] == "道衍献策" for r in results)


# ============================================================================
# Test 11: retrieve_relevant_scenes dedup
# ============================================================================


class TestRetrieveRelevantScenesDedup:
    """Test retrieve_relevant_scenes deduplicates by scene range."""

    def test_dedup_keeps_highest_score(self):
        """Same scene entries keep only highest score."""
        results = [
            {"source": "scene_summaries", "scenes_covered": "1-3", "text": "高分", "matched_tags": [], "score": 3.0},
            {"source": "working_memory", "scenes_covered": "2", "text": "低分", "matched_tags": [], "score": 1.0},
        ]
        deduped = _dedup_results(results)
        assert len(deduped) == 1
        assert deduped[0]["text"] == "高分"


# ============================================================================
# Test 12: retrieve_relevant_scenes top-K
# ============================================================================


class TestRetrieveRelevantScenesTopK:
    """Test retrieve_relevant_scenes returns top-K results sorted by score."""

    def _make_context_with_many_results(self):
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 5,
                "status": "acting",
                "actors": {
                    "朱棣": {
                        "working_memory": [],
                        "scene_summaries": [
                            {"summary": "场景1", "scenes_covered": "1", "tags": ["角色:朱棣"]},
                            {"summary": "场景2", "scenes_covered": "2", "tags": ["角色:朱棣", "冲突:起兵"]},
                            {"summary": "场景3", "scenes_covered": "3", "tags": ["角色:朱棣"]},
                            {"summary": "场景4", "scenes_covered": "4", "tags": ["角色:朱棣"]},
                        ],
                        "critical_memories": [],
                        "arc_summary": {"structured": {}, "narrative": ""},
                    },
                },
            }
        }
        return tc

    def test_top_k_limit(self):
        """Returns at most top_k results."""
        tc = self._make_context_with_many_results()
        results = retrieve_relevant_scenes(["角色:朱棣"], 5, tc, top_k=2)
        assert len(results) <= 2

    def test_sorted_by_score_descending(self):
        """Results sorted by score descending."""
        tc = self._make_context_with_many_results()
        results = retrieve_relevant_scenes(["角色:朱棣", "冲突:起兵"], 5, tc, top_k=4)
        for i in range(len(results) - 1):
            assert results[i]["score"] >= results[i + 1]["score"]


# ============================================================================
# Test 13: _extract_auto_tags
# ============================================================================


class TestExtractAutoTags:
    """Test _extract_auto_tags extracts tags from working_memory and current scene."""

    def test_extracts_from_working_memory(self):
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 3,
                "status": "acting",
                "scenes": [],
                "actors": {},
            }
        }
        actor_data = {
            "role": "燕王",
            "name": "朱棣",
            "working_memory": [
                {"entry": "与角色:道衍商议", "importance": "normal", "scene": 3},
            ],
            "scene_summaries": [
                {"summary": "...", "scenes_covered": "1", "tags": ["角色:朱棣", "冲突:起兵"]},
            ],
        }
        tags = _extract_auto_tags(actor_data, tc)
        assert len(tags) > 0
        # Should include tags from scene_summaries
        assert any("朱棣" in t or "起兵" in t for t in tags)

    def test_returns_up_to_8_tags(self):
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 3,
                "status": "acting",
                "scenes": [],
                "actors": {},
            }
        }
        actor_data = {
            "role": "燕王",
            "name": "朱棣",
            "working_memory": [
                {"entry": f"角色:人物{i}", "importance": "normal", "scene": i}
                for i in range(10)
            ],
            "scene_summaries": [],
        }
        tags = _extract_auto_tags(actor_data, tc)
        assert len(tags) <= 8


# ============================================================================
# Test 14: backfill_tags
# ============================================================================


class TestBackfillTags:
    """Test backfill_tags marks state and skips if already done."""

    @pytest.mark.asyncio
    async def test_marks_backfilled(self):
        """backfill_tags sets tags_backfilled=True after completion."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 3,
                "status": "acting",
                "tags_backfilled": False,
                "actors": {
                    "朱棣": {
                        "scene_summaries": [
                            {"summary": "朱棣起兵", "scenes_covered": "1", "tags": []},
                        ],
                    },
                },
            }
        }
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm, \
             patch("app.semantic_retriever._set_state"):
            mock_llm.return_value = '{"scenes": [{"summary_index": 0, "tags": ["角色:朱棣", "事件:起兵"]}]}'
            result = await backfill_tags(tc)
        # The key thing: tags_backfilled should be set
        assert tc.state["drama"].get("tags_backfilled") is True

    @pytest.mark.asyncio
    async def test_skips_if_already_backfilled(self):
        """backfill_tags skips if tags_backfilled=True."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试",
                "current_scene": 3,
                "status": "acting",
                "tags_backfilled": True,
                "actors": {},
            }
        }
        result = await backfill_tags(tc)
        assert result["status"] == "info"
        assert "跳过" in result["message"]


# ============================================================================
# Test 15: Retrieval latency
# ============================================================================


class TestRetrievalLatency:
    """Test retrieval latency < 100ms for 200 entries × 10 tags."""

    def test_latency_under_100ms(self):
        """Retrieval with 200 entries × 10 tags should complete under 100ms."""
        tc = MagicMock()
        # Build 200 scene summaries with 10 tags each
        actors = {}
        for i in range(20):  # 20 actors
            summaries = []
            for j in range(10):  # 10 summaries each = 200 total
                summaries.append({
                    "summary": f"场景{i*10+j}摘要内容，包含角色互动和冲突",
                    "scenes_covered": str(i * 10 + j + 1),
                    "tags": [
                        f"角色:角色{i}A", f"角色:角色{i}B",
                        f"地点:地点{i}", f"情感:情感{i}",
                        f"冲突:冲突{i}", f"事件:事件{i}",
                        f"其他:其他{i}", f"角色:角色{(i+1)%20}A",
                        f"地点:地点{(i+1)%20}", f"冲突:冲突{(i+1)%20}",
                    ],
                })
            actors[f"角色{i}"] = {
                "working_memory": [],
                "scene_summaries": summaries,
                "critical_memories": [],
                "arc_summary": {"structured": {}, "narrative": ""},
            }
        tc.state = {"drama": {"current_scene": 100, "actors": actors}}

        start = time.time()
        results = retrieve_relevant_scenes(
            ["角色:角色5A", "冲突:冲突3"], 100, tc, top_k=5
        )
        elapsed = time.time() - start

        assert elapsed < 0.1  # 100ms
        assert len(results) > 0
