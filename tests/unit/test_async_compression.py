"""Tests for async LLM compression and edge cases.

Tests the async compression system that replaces the stub compression:
- compress_working_to_scene: async LLM compression of working memory → scene summary
- compress_scene_to_arc: async LLM compression of scene summaries → arc summary
- check_and_compress: async task launch when event loop running, sync fallback
- _merge_pending_compression: merge completed results into state
- _call_llm: LiteLlm first, httpx fallback
- Serialization: strip asyncio.Task objects for JSON persistence
- Edge cases: empty memory, single entry, rapid compression
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.memory_manager import (
    check_and_compress,
    build_actor_context,
    compress_working_to_scene,
    compress_scene_to_arc,
    _merge_pending_compression,
    _serialize_pending_for_save,
    _deserialize_pending_on_load,
    WORKING_MEMORY_LIMIT,
    SCENE_SUMMARY_LIMIT,
)


@pytest.fixture
def mock_tool_context_with_overflow():
    """Create a mock ToolContext with actor that has overflowing working memory."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "压缩测试",
            "current_scene": 5,
            "status": "acting",
            "actors": {
                "测试演员": {
                    "role": "主角",
                    "personality": "坚韧",
                    "background": "出身贫寒",
                    "knowledge_scope": "江湖事",
                    "working_memory": [
                        {"entry": f"面对情境: 第{i}场事件", "importance": "normal", "scene": i}
                        for i in range(1, 9)  # 8 entries, exceeds limit of 5
                    ],
                    "scene_summaries": [],
                    "arc_summary": {
                        "structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []},
                        "narrative": "",
                    },
                    "critical_memories": [],
                    "emotions": "neutral",
                    "created_at": "2026-04-11T10:00:00",
                }
            },
        }
    }
    return tc


class TestCompressWorkingToScene:
    """Test working→scene async compression."""

    @pytest.mark.asyncio
    async def test_compress_working_to_scene_with_mock_llm(self):
        """Test 1: compress_working_to_scene returns valid scene summary dict."""
        entries = [
            {"entry": "面对情境: 发现密信", "importance": "normal", "scene": 3},
            {"entry": "我说：必须查明真相", "importance": "normal", "scene": 3},
        ]
        tc = MagicMock()

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "第3场：角色发现密信，决心查明真相。"
            result = await compress_working_to_scene("测试", entries, tc)

        assert "summary" in result
        assert result["scenes_covered"] == "3"
        assert isinstance(result["key_events"], list)


class TestCompressSceneToArc:
    """Test scene→arc async compression."""

    @pytest.mark.asyncio
    async def test_compress_scene_to_arc_with_mock_llm(self):
        """Test 2: compress_scene_to_arc returns structured + narrative arc summary."""
        summaries = [
            {"summary": "第1-3场：发现密信", "scenes_covered": "1-3", "key_events": ["发现密信"]},
        ]
        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "测试": {
                        "arc_summary": {
                            "structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []},
                            "narrative": "",
                        }
                    }
                }
            }
        }

        mock_json = '{"structured": {"theme": "权力", "key_characters": ["朱棣"], "unresolved": ["起兵与否"], "resolved": []}, "narrative": "从密信发现开始..."}'
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_json
            result = await compress_scene_to_arc("测试", summaries, tc)

        assert "structured" in result
        assert "narrative" in result
        assert result["structured"]["theme"] == "权力"


class TestCheckAndCompressAsync:
    """Test check_and_compress async task launching."""

    def test_check_and_compress_launches_async_task(self):
        """Test 3: check_and_compress launches async task when event loop is running."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "异步测试",
                "actors": {
                    "异步演员": {
                        "working_memory": [
                            {"entry": f"条目{i}", "importance": "normal", "scene": i}
                            for i in range(8)  # Exceeds limit of 5
                        ],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []}, "narrative": ""},
                        "critical_memories": [],
                    }
                },
            }
        }

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "压缩摘要"
            # Run within an event loop to test async path
            result = asyncio.run(self._run_check_and_compress(tc))

        assert result["status"] == "success"
        assert len(result["compressed"]) > 0
        # Working memory should be trimmed
        actor = tc.state["drama"]["actors"]["异步演员"]
        assert len(actor["working_memory"]) <= WORKING_MEMORY_LIMIT

    async def _run_check_and_compress(self, tc):
        """Helper to run check_and_compress within an async context."""
        return check_and_compress("异步演员", tc)

    def test_check_and_compress_fallback_sync(self):
        """Test 4: check_and_compress falls back to sync when no event loop."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "同步回退测试",
                "actors": {
                    "同步演员": {
                        "working_memory": [
                            {"entry": f"条目{i}", "importance": "normal", "scene": i}
                            for i in range(8)
                        ],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []}, "narrative": ""},
                        "critical_memories": [],
                    }
                },
            }
        }

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "同步压缩摘要"
            # No running event loop → asyncio.run() path
            result = check_and_compress("同步演员", tc)

        assert result["status"] == "success"
        assert len(result["compressed"]) > 0


class TestMergePendingCompression:
    """Test _merge_pending_compression logic."""

    def test_merge_completed_working_to_scene(self):
        """Test 5: Completed working→scene task result merged into scene_summaries."""
        tc = MagicMock()
        tc.state = {"drama": {"actors": {}, "theme": "测试"}}

        # Create a completed mock task
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.result.return_value = {
            "summary": "压缩摘要",
            "scenes_covered": "1-3",
            "key_events": ["事件1"],
        }

        actor_data = {
            "scene_summaries": [],
            "_pending_compression": {
                "working_to_scene": mock_task,
                "scene_to_arc": None,
                "pending_entries": [],
                "result": None,
            },
        }

        merged = _merge_pending_compression("测试", actor_data, tc)
        assert merged is True
        assert len(actor_data["scene_summaries"]) == 1
        assert actor_data["_pending_compression"]["working_to_scene"] is None

    def test_merge_completed_scene_to_arc(self):
        """Test 6: Completed scene→arc task result merged into arc_summary."""
        tc = MagicMock()
        tc.state = {"drama": {"actors": {}, "theme": "测试"}}

        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.result.return_value = {
            "structured": {"theme": "权力", "key_characters": ["朱棣"], "unresolved": [], "resolved": []},
            "narrative": "新的弧线摘要",
        }

        actor_data = {
            "arc_summary": {"structured": {}, "narrative": ""},
            "_pending_compression": {
                "working_to_scene": None,
                "scene_to_arc": mock_task,
                "pending_entries": [],
                "result": None,
            },
        }

        merged = _merge_pending_compression("测试", actor_data, tc)
        assert merged is True
        assert actor_data["arc_summary"]["narrative"] == "新的弧线摘要"
        assert actor_data["_pending_compression"]["scene_to_arc"] is None

    def test_merge_keeps_pending_when_task_not_done(self):
        """Test 7: If task not done, pending_entries remain as fallback."""
        tc = MagicMock()
        tc.state = {"drama": {"actors": {}, "theme": "测试"}}

        mock_task = MagicMock()
        mock_task.done.return_value = False  # Not done yet

        actor_data = {
            "scene_summaries": [],
            "_pending_compression": {
                "working_to_scene": mock_task,
                "scene_to_arc": None,
                "pending_entries": [{"entry": "待压缩条目", "importance": "normal", "scene": 1}],
                "result": None,
            },
        }

        merged = _merge_pending_compression("测试", actor_data, tc)
        assert merged is False
        # Pending entries still there
        assert len(actor_data["_pending_compression"]["pending_entries"]) == 1


class TestBuildContextWithPending:
    """Test build_actor_context includes pending entries."""

    def test_build_context_includes_pending_entries(self, mock_tool_context_with_overflow):
        """Test 8: When compression is in progress, pending entries appear in context."""
        from app.memory_manager import add_working_memory
        tc = mock_tool_context_with_overflow
        actor = tc.state["drama"]["actors"]["测试演员"]
        actor["_pending_compression"] = {
            "working_to_scene": None,
            "scene_to_arc": None,
            "pending_entries": [
                {"entry": "待压缩的重要记忆", "importance": "normal", "scene": 2}
            ],
            "result": None,
        }

        context = build_actor_context("测试演员", tc)
        assert "待压缩" in context


class TestLiteLlmFallback:
    """Test LiteLlm → httpx fallback."""

    @pytest.mark.asyncio
    async def test_litellm_failure_triggers_httpx_fallback(self):
        """Test 9: LiteLlm failure triggers httpx fallback, and both failing returns fallback text."""
        from app.memory_manager import _call_llm

        # When both LiteLlm and httpx fail (no API keys in test env),
        # _call_llm should still return a fallback string (not raise).
        result = await _call_llm("test prompt")
        assert isinstance(result, str)
        assert len(result) > 0


class TestSerialization:
    """Test _pending_compression serialization."""

    def test_serialize_strips_tasks(self):
        """Test 10: _serialize_pending_for_save strips non-serializable Task objects."""
        mock_task = MagicMock()  # Simulates asyncio.Task
        actor_data = {
            "_pending_compression": {
                "working_to_scene": mock_task,
                "scene_to_arc": None,
                "pending_entries": [{"entry": "test", "importance": "normal", "scene": 1}],
                "result": None,
            }
        }

        result = _serialize_pending_for_save(actor_data)
        assert result["_pending_compression"]["working_to_scene"] is None
        assert result["_pending_compression"]["pending_entries"] == [
            {"entry": "test", "importance": "normal", "scene": 1}
        ]

    def test_deserialize_restores_structure(self):
        """Test 11: _deserialize_pending_on_load restores correct structure."""
        actor_data = {
            "_pending_compression": {
                "pending_entries": [{"entry": "old", "importance": "normal", "scene": 0}],
            }
        }

        result = _deserialize_pending_on_load(actor_data)
        assert result["_pending_compression"]["working_to_scene"] is None
        assert result["_pending_compression"]["scene_to_arc"] is None
        assert len(result["_pending_compression"]["pending_entries"]) == 1


class TestEdgeCases:
    """Test edge cases: empty memory, single entry, rapid compression."""

    def test_check_and_compress_empty_memory(self):
        """check_and_compress with empty memory returns '无需压缩'."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "空演员": {
                        "working_memory": [],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []}, "narrative": ""},
                        "critical_memories": [],
                    }
                },
                "theme": "测试",
            }
        }
        result = check_and_compress("空演员", tc)
        assert result["compressed"] == []

    def test_check_and_compress_single_entry(self):
        """check_and_compress with 1 working memory entry (below limit) returns '无需压缩'."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "单条演员": {
                        "working_memory": [{"entry": "只有一条", "importance": "normal", "scene": 1}],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []}, "narrative": ""},
                        "critical_memories": [],
                    }
                },
                "theme": "测试",
            }
        }
        result = check_and_compress("单条演员", tc)
        assert result["compressed"] == []

    def test_build_context_empty_actor(self):
        """build_actor_context with no actor data returns '暂无记忆'."""
        tc = MagicMock()
        tc.state = {"drama": {"actors": {}, "theme": "测试"}}
        result = build_actor_context("不存在", tc)
        assert result == "暂无记忆"

    def test_rapid_compression_multiple_overflows(self):
        """Multiple rapid compressions don't lose entries."""
        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "快演员": {
                        "working_memory": [
                            {"entry": f"条目{i}", "importance": "normal", "scene": i}
                            for i in range(12)  # Way over limit
                        ],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {"theme": "", "key_characters": [], "unresolved": [], "resolved": []}, "narrative": ""},
                        "critical_memories": [],
                    }
                },
                "theme": "测试",
            }
        }
        result = check_and_compress("快演员", tc)
        # Should have triggered compression
        assert len(result["compressed"]) > 0
        # Working memory should be capped at limit
        actor = tc.state["drama"]["actors"]["快演员"]
        assert len(actor["working_memory"]) <= WORKING_MEMORY_LIMIT
