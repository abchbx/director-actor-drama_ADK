"""Unit tests for Phase 10 tool functions: add_fact, validate_consistency, repair_contradiction."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.tools import add_fact, validate_consistency, repair_contradiction


class TestAddFactTool:
    """Test add_fact Tool function."""

    def test_add_fact_calls_logic_and_writes_state(self, mock_tool_context):
        """Test 1: add_fact Tool 调用 add_fact_logic 并写入 state"""
        result = add_fact("朱棣已起兵", category="event", importance="high", tool_context=mock_tool_context)
        assert result["status"] == "success"
        assert "fact_id" in result
        assert "📌" in result["message"]
        # Verify state was written
        state = mock_tool_context.state["drama"]
        assert len(state["established_facts"]) == 1
        assert state["established_facts"][0]["fact"] == "朱棣已起兵"

    def test_add_fact_default_category_and_importance(self, mock_tool_context):
        """Test 2: add_fact Tool defaults category=event, importance=medium"""
        result = add_fact("故事发生在明朝", tool_context=mock_tool_context)
        assert result["status"] == "success"
        state = mock_tool_context.state["drama"]
        fact = state["established_facts"][0]
        assert fact["category"] == "event"
        assert fact["importance"] == "medium"


class TestValidateConsistencyTool:
    """Test validate_consistency Tool function."""

    @pytest.mark.asyncio
    async def test_validate_consistency_calls_logic_and_llm(self, mock_tool_context):
        """Test 3: validate_consistency Tool 调用 validate_consistency_logic + LLM 并更新 coherence_checks"""
        # Set up state with relevant facts
        mock_tool_context.state["drama"]["established_facts"] = [
            {
                "id": "fact_1_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "importance": "high",
                "actors": ["朱棣"],
                "scene": 1,
            }
        ]
        mock_tool_context.state["drama"]["scenes"] = [
            {"scene_number": 2, "content": "朱棣仍在犹豫是否出兵", "actors_present": ["朱棣"]}
        ]
        mock_tool_context.state["drama"]["current_scene"] = 3

        # Mock _call_llm
        llm_response = '{"contradictions": [{"fact_id": "fact_1_起兵_1", "fact_text": "朱棣已起兵", "scene_text": "朱棣仍在犹豫", "explanation": "矛盾"}], "has_contradiction": true}'
        with patch("app.memory_manager._call_llm", new_callable=AsyncMock, return_value=llm_response):
            result = await validate_consistency(tool_context=mock_tool_context)

        assert result["status"] == "success"
        assert "⚠️" in result["message"]
        assert len(result["contradictions"]) == 1
        # Check coherence_checks was updated
        cc = mock_tool_context.state["drama"]["coherence_checks"]
        assert cc["last_check_scene"] == 3
        assert cc["last_result"] == 1
        assert cc["total_contradictions"] == 1

    @pytest.mark.asyncio
    async def test_validate_consistency_no_relevant_facts(self, mock_tool_context):
        """Test 4: validate_consistency Tool 无相关事实时返回无需检查"""
        # No facts that pass the filter (current_scene = 3, facts have scene >= current)
        mock_tool_context.state["drama"]["established_facts"] = []
        result = await validate_consistency(tool_context=mock_tool_context)
        assert result["status"] == "success"
        assert result["contradictions"] == []
        assert "无需检查" in result["message"] or "通过" in result["message"]


class TestRepairContradictionTool:
    """Test repair_contradiction Tool function."""

    def test_repair_contradiction_calls_logic_and_writes_state(self, mock_tool_context):
        """Test 5: repair_contradiction Tool 调用 repair_contradiction_logic 并更新 state"""
        # Add a fact to repair
        mock_tool_context.state["drama"]["established_facts"] = [
            {
                "id": "fact_1_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "importance": "high",
                "actors": ["朱棣"],
                "scene": 1,
            }
        ]
        result = repair_contradiction(
            fact_id="fact_1_起兵_1",
            repair_type="correction",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "success"
        assert result["fact_id"] == "fact_1_起兵_1"
        assert result["repair_type"] == "correction"
        assert "✅" in result["message"]
        # Verify state was written (repair_type appended to fact)
        state = mock_tool_context.state["drama"]
        fact = state["established_facts"][0]
        assert fact.get("repair_type") == "correction"

    def test_repair_contradiction_validates_repair_type(self, mock_tool_context):
        """Test 6: repair_contradiction Tool 验证 repair_type 为 supplement/correction"""
        mock_tool_context.state["drama"]["established_facts"] = [
            {
                "id": "fact_1_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "importance": "high",
                "actors": ["朱棣"],
                "scene": 1,
            }
        ]
        result = repair_contradiction(
            fact_id="fact_1_起兵_1",
            repair_type="invalid_type",
            tool_context=mock_tool_context,
        )
        assert result["status"] == "error"
