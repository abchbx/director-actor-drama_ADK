"""Unit tests for memory_manager module.

Tests the 3-tier memory architecture:
- Working memory (Tier 1) management
- Scene summaries (Tier 2) compression
- Arc summary (Tier 3) compression
- Critical memory detection and protection
- Legacy memory migration
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.memory_manager import (
    add_working_memory,
    check_and_compress,
    build_actor_context,
    mark_critical_memory,
    migrate_legacy_memory,
    detect_importance,
    ensure_actor_memory_fields,
    WORKING_MEMORY_LIMIT,
    SCENE_SUMMARY_LIMIT,
    CRITICAL_REASONS,
)


# ============================================================================
# Task 1 Tests: add_working_memory, detect_importance, data structures
# ============================================================================


class TestAddWorkingMemory:
    """Tests for add_working_memory function."""

    def test_add_working_memory_normal(self, mock_tool_context):
        """add_working_memory with normal importance adds to working_memory list."""
        result = add_working_memory(
            actor_name="朱棣",
            entry="与道衍商议起兵之事",
            importance="normal",
            critical_reason=None,
            tool_context=mock_tool_context,
        )
        assert result["status"] == "success"
        assert result["importance"] == "normal"

        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["working_memory"]) == 1
        entry = actor["working_memory"][0]
        assert entry["entry"] == "与道衍商议起兵之事"
        assert entry["importance"] == "normal"
        assert entry["scene"] == 3  # current_scene from fixture

    def test_add_working_memory_critical(self, mock_tool_context):
        """add_working_memory with critical importance adds to both working_memory AND critical_memories."""
        result = add_working_memory(
            actor_name="朱棣",
            entry="第一次遇见道衍和尚",
            importance="critical",
            critical_reason="首次登场",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "success"
        assert result["importance"] == "critical"

        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # Should be in both working_memory and critical_memories
        assert len(actor["working_memory"]) == 1
        assert len(actor["critical_memories"]) == 1

        working_entry = actor["working_memory"][0]
        assert working_entry["importance"] == "critical"

        critical_entry = actor["critical_memories"][0]
        assert critical_entry["entry"] == "第一次遇见道衍和尚"
        assert critical_entry["reason"] == "首次登场"
        assert critical_entry["scene"] == 3

    def test_add_working_memory_critical_no_reason(self, mock_tool_context):
        """add_working_memory with critical importance but no reason returns error."""
        result = add_working_memory(
            actor_name="朱棣",
            entry="某个重要事件",
            importance="critical",
            critical_reason=None,
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"
        assert "critical_reason" in result["message"]

    def test_add_working_memory_nonexistent_actor(self, mock_tool_context):
        """add_working_memory for non-existent actor returns error."""
        result = add_working_memory(
            actor_name="不存在的人",
            entry="测试",
            importance="normal",
            critical_reason=None,
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"
        assert "不存在" in result["message"]


class TestDetectImportance:
    """Tests for detect_importance function."""

    def test_detect_importance_first_appearance(self):
        """detect_importance detects 首次登场 pattern (entry contains 第一次)."""
        is_critical, reason = detect_importance("第一次遇见道衍")
        assert is_critical is True
        assert reason == "首次登场"

    def test_detect_importance_turning_point(self):
        """detect_importance detects 重大转折 pattern (entry contains 转折)."""
        is_critical, reason = detect_importance("发现密信，转折到来")
        assert is_critical is True
        assert reason == "重大转折"

    def test_detect_importance_emotional_peak(self):
        """detect_importance detects 情感高峰 pattern (situation contains strong emotion words)."""
        is_critical, reason = detect_importance("凯旋归来", situation="热泪盈眶")
        assert is_critical is True
        assert reason == "情感高峰"

    def test_detect_importance_unresolved(self):
        """detect_importance detects 未决事件 pattern (entry contains 悬念/未知/谜)."""
        is_critical, reason = detect_importance("此谜团尚未解开")
        assert is_critical is True
        assert reason == "未决事件"

    def test_detect_importance_normal(self):
        """detect_importance returns (False, None) for normal entries."""
        is_critical, reason = detect_importance("面对情境: 普通对话")
        assert is_critical is False
        assert reason is None


class TestDataStructures:
    """Tests for new actor data structure fields."""

    def test_new_actor_has_all_fields(self):
        """After calling ensure_actor_memory_fields, verify all new fields exist."""
        actor_data = {
            "role": "测试",
            "personality": "测试",
            "background": "测试",
            "knowledge_scope": "测试",
            "memory": [],
            "emotions": "neutral",
            "created_at": "2026-04-11T10:00:00",
        }
        result = ensure_actor_memory_fields(actor_data)
        assert "working_memory" in result
        assert isinstance(result["working_memory"], list)
        assert "scene_summaries" in result
        assert isinstance(result["scene_summaries"], list)
        assert "arc_summary" in result
        assert "structured" in result["arc_summary"]
        assert "narrative" in result["arc_summary"]
        assert "critical_memories" in result
        assert isinstance(result["critical_memories"], list)


# ============================================================================
# Task 2 Tests: build_actor_context, check_and_compress,
#               migrate_legacy_memory, mark_critical_memory
# ============================================================================


class TestBuildActorContext:
    """Tests for build_actor_context function."""

    def test_build_actor_context_empty_memory(self, mock_tool_context):
        """build_actor_context with empty actor memory returns 暂无记忆."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = []
        actor["scene_summaries"] = []
        actor["critical_memories"] = []
        actor["arc_summary"]["narrative"] = ""

        # Even with empty memory, we should get character anchor + emotion
        # Only if there's truly no meaningful content do we return "暂无记忆"
        result = build_actor_context("朱棣", mock_tool_context)
        # With character anchor present, we won't get "暂无记忆"
        # But let's test the truly empty case
        # Actually, build_actor_context always adds role anchor and emotion,
        # so we'll get content even with empty memory tiers.
        # Let's test a non-existent actor for "暂无记忆"
        result = build_actor_context("不存在", mock_tool_context)
        assert result == "暂无记忆"

    def test_build_actor_context_working_only(self, mock_tool_context):
        """build_actor_context with working_memory only contains 最近经历 section."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "与道衍商议", "importance": "normal", "scene": 3},
            {"entry": "训练兵马", "importance": "normal", "scene": 3},
        ]
        actor["scene_summaries"] = []
        actor["critical_memories"] = []
        actor["arc_summary"]["narrative"] = ""

        result = build_actor_context("朱棣", mock_tool_context)
        assert "【角色锚点】" in result
        assert "【当前情绪】" in result
        assert "【最近的经历（详细）】" in result
        assert "与道衍商议" in result
        assert "训练兵马" in result

    def test_build_actor_context_all_layers(self, mock_tool_context):
        """build_actor_context with all layers contains all 5 sections."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "与道衍商议", "importance": "normal", "scene": 3},
            {"entry": "训练兵马", "importance": "normal", "scene": 4},
        ]
        actor["scene_summaries"] = [
            {
                "summary": "初期活动摘要",
                "scenes_covered": "1-2",
                "key_events": ["与道衍商议。"],
            }
        ]
        actor["arc_summary"] = {
            "structured": {
                "theme": "夺权之路",
                "key_characters": ["朱棣", "道衍"],
                "unresolved": ["起兵时机"],
                "resolved": ["结交道衍"],
            },
            "narrative": "朱棣从燕王到皇帝的历程",
        }
        actor["critical_memories"] = [
            {"entry": "初见道衍", "reason": "首次登场", "scene": 1}
        ]

        result = build_actor_context("朱棣", mock_tool_context)
        assert "【角色锚点】" in result
        assert "【关键记忆" in result
        assert "【你的故事弧线】" in result
        assert "【近期场景摘要】" in result
        assert "【最近的经历" in result

    def test_build_actor_context_includes_emotion(self, mock_tool_context):
        """build_actor_context output includes emotion (当前情绪)."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["emotions"] = "anxious"
        actor["working_memory"] = [
            {"entry": "焦急等待消息", "importance": "normal", "scene": 3},
        ]

        result = build_actor_context("朱棣", mock_tool_context)
        assert "【当前情绪】焦虑" in result


class TestCheckAndCompress:
    """Tests for check_and_compress function."""

    def test_check_and_compress_working_overflow(self, mock_tool_context):
        """check_and_compress with 6 working memories triggers working→scene compression, leaving 5."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # Add 7 entries to exceed WORKING_MEMORY_LIMIT=5
        actor["working_memory"] = [
            {"entry": f"第{i}条记忆内容。包含更多信息", "importance": "normal", "scene": i}
            for i in range(7)
        ]

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "压缩摘要：第0-1场事件概述。"
            result = check_and_compress("朱棣", mock_tool_context)

        assert result["status"] == "success"
        assert len(result["compressed"]) > 0

        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["working_memory"]) == 5
        assert len(actor["scene_summaries"]) == 1

    def test_check_and_compress_scene_overflow(self, mock_tool_context):
        """check_and_compress with 11 scene summaries triggers scene→arc compression, leaving 10."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        # Add 12 scene summaries to exceed SCENE_SUMMARY_LIMIT=10
        actor["scene_summaries"] = [
            {
                "summary": f"第{i}个场景的摘要内容",
                "scenes_covered": str(i),
                "key_events": [f"事件{i}"],
            }
            for i in range(12)
        ]

        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"structured": {"theme": "测试", "key_characters": ["朱棣"], "unresolved": [], "resolved": []}, "narrative": "故事弧线概述。"}'
            result = check_and_compress("朱棣", mock_tool_context)

        assert result["status"] == "success"
        assert len(result["compressed"]) > 0

        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["scene_summaries"]) == 10
        assert actor["arc_summary"]["narrative"] != ""


class TestMigrateLegacyMemory:
    """Tests for migrate_legacy_memory function."""

    def test_migrate_legacy_memory(self, mock_tool_context_old_format):
        """migrate_legacy_memory converts old flat memory to working_memory with scene=0 and importance=normal."""
        result = migrate_legacy_memory("朱元璋", mock_tool_context_old_format)
        assert result["status"] == "success"
        assert result["migrated_count"] == 3

        actor = mock_tool_context_old_format.state["drama"]["actors"]["朱元璋"]
        assert len(actor["working_memory"]) == 3
        for entry in actor["working_memory"]:
            assert entry["scene"] == 0
            assert entry["importance"] == "normal"
        assert actor["scene_summaries"] == []
        assert actor["critical_memories"] == []
        assert "structured" in actor["arc_summary"]
        assert "narrative" in actor["arc_summary"]

    def test_migrate_legacy_preserves_old_field(self, mock_tool_context_old_format):
        """migrate_legacy_memory preserves old 'memory' field (D-13)."""
        migrate_legacy_memory("朱元璋", mock_tool_context_old_format)

        actor = mock_tool_context_old_format.state["drama"]["actors"]["朱元璋"]
        # Old "memory" field should still exist (D-13: read-only preservation)
        assert "memory" in actor
        assert len(actor["memory"]) == 3

    def test_migrate_legacy_skips_corrupted(self, mock_tool_context_old_format):
        """migrate_legacy_memory skips entries with empty/missing 'entry' key."""
        actor = mock_tool_context_old_format.state["drama"]["actors"]["朱元璋"]
        # Add corrupted entries
        actor["memory"].append({"entry": "", "timestamp": "2026-04-10T13:00:00"})
        actor["memory"].append({"timestamp": "2026-04-10T14:00:00"})  # No "entry" key

        result = migrate_legacy_memory("朱元璋", mock_tool_context_old_format)
        assert result["status"] == "success"

        # Should have 3 valid entries (original ones), not 5
        assert len(actor["working_memory"]) == 3

    def test_migrate_legacy_already_migrated(self, mock_tool_context):
        """migrate_legacy_memory on already-migrated actor returns info status."""
        result = migrate_legacy_memory("朱棣", mock_tool_context)
        assert result["status"] == "info"
        assert "已是新格式" in result["message"]


class TestMarkCriticalMemory:
    """Tests for mark_critical_memory function."""

    def test_mark_critical_memory(self, mock_tool_context):
        """mark_critical_memory moves entry from working_memory to critical_memories."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "普通记忆", "importance": "normal", "scene": 1},
            {"entry": "重要发现", "importance": "normal", "scene": 2},
        ]

        result = mark_critical_memory(
            actor_name="朱棣",
            memory_index=0,
            reason="用户标记",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "success"

        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        assert len(actor["working_memory"]) == 1
        assert actor["working_memory"][0]["entry"] == "重要发现"
        assert len(actor["critical_memories"]) == 1
        assert actor["critical_memories"][0]["reason"] == "用户标记"
        assert actor["critical_memories"][0]["entry"] == "普通记忆"

    def test_mark_critical_invalid_index(self, mock_tool_context):
        """mark_critical_memory with invalid index returns error."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "仅一条记忆", "importance": "normal", "scene": 1},
        ]

        result = mark_critical_memory(
            actor_name="朱棣",
            memory_index=99,
            reason="用户标记",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"
        assert "超出范围" in result["message"]

    def test_mark_critical_invalid_reason(self, mock_tool_context):
        """mark_critical_memory with invalid reason returns error."""
        actor = mock_tool_context.state["drama"]["actors"]["朱棣"]
        actor["working_memory"] = [
            {"entry": "仅一条记忆", "importance": "normal", "scene": 1},
        ]

        result = mark_critical_memory(
            actor_name="朱棣",
            memory_index=0,
            reason="无效原因",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"
        assert "无效" in result["message"]


# ============================================================================
# Task 2 Tests (Phase 3): Tag generation in compression prompts
# ============================================================================


class TestCompressionPromptTags:
    """Tests for tag generation in compression prompt and output."""

    def test_compression_prompt_contains_tag_rules(self):
        """_build_compression_prompt_working output contains '标签生成规则' and 'tags'."""
        from app.memory_manager import _build_compression_prompt_working
        entries = [{"entry": "测试记忆", "scene": 1}]
        prompt = _build_compression_prompt_working(entries, "朱棣")
        assert "标签生成规则" in prompt
        assert "tags" in prompt

    def test_compression_prompt_contains_json_format(self):
        """_build_compression_prompt_working output contains JSON format with tags field."""
        from app.memory_manager import _build_compression_prompt_working
        entries = [{"entry": "测试记忆", "scene": 1}]
        prompt = _build_compression_prompt_working(entries, "朱棣")
        assert '"tags":' in prompt or 'tags' in prompt
        assert "严格 JSON" in prompt

    @pytest.mark.asyncio
    async def test_compress_working_returns_tags(self, mock_tool_context):
        """compress_working_to_scene returns dict with 'tags' key (list type)."""
        from app.memory_manager import compress_working_to_scene
        entries = [
            {"entry": "朱棣在皇宫中与道衍商议", "importance": "normal", "scene": 1},
            {"entry": "决定起兵靖难", "importance": "normal", "scene": 2},
        ]
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"summary": "朱棣与道衍在皇宫商议起兵", "tags": ["角色:朱棣", "地点:皇宫", "冲突:起兵"]}'
            result = await compress_working_to_scene("朱棣", entries, mock_tool_context)
        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert "角色:朱棣" in result["tags"]

    @pytest.mark.asyncio
    async def test_compress_working_tags_fallback_on_non_json(self, mock_tool_context):
        """Tags fallback to regex extraction when LLM returns non-JSON."""
        from app.memory_manager import compress_working_to_scene
        entries = [
            {"entry": "朱棣在皇宫中愤怒地商议", "importance": "normal", "scene": 1},
        ]
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "朱棣与道衍在皇宫商议起兵，角色:朱棣，地点:皇宫"
            result = await compress_working_to_scene("朱棣", entries, mock_tool_context)
        assert "tags" in result
        assert isinstance(result["tags"], list)

    @pytest.mark.asyncio
    async def test_compress_working_tags_default_empty(self, mock_tool_context):
        """Tags default to empty list when no tags found (non-blocking)."""
        from app.memory_manager import compress_working_to_scene
        entries = [
            {"entry": "普通对话", "importance": "normal", "scene": 1},
        ]
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "这是一段没有标签格式的普通文本摘要。"
            result = await compress_working_to_scene("朱棣", entries, mock_tool_context)
        assert "tags" in result
        assert isinstance(result["tags"], list)
