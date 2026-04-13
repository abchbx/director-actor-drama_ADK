"""Unit tests for coherence_checker.py — fact tracking, consistency checking, and contradiction repair.

TDD tests for coherence_checker pure functions (COHERENCE-01/02/04).
"""

import pytest

from app.coherence_checker import (
    FACT_CATEGORIES,
    COHERENCE_CHECK_INTERVAL,
    MAX_FACTS,
    MAX_CHECK_HISTORY,
    add_fact_logic,
    validate_consistency_logic,
    validate_consistency_prompt,
    generate_repair_narration_prompt,
    repair_contradiction_logic,
    _extract_actor_names,
    _check_fact_overlap,
    _filter_relevant_facts,
    _generate_fact_id,
)


def _make_state(**overrides) -> dict:
    """Create a minimal state dict for testing coherence_checker functions."""
    state = {
        "current_scene": 5,
        "actors": {
            "朱棣": {
                "role": "燕王",
                "emotions": "neutral",
                "personality": "果断、野心勃勃、多疑",
            },
            "苏念": {
                "role": "宫女",
                "emotions": "anxious",
                "personality": "聪慧、隐忍",
            },
            "林风": {
                "role": "旧部",
                "emotions": "determined",
                "personality": "忠诚、沉稳",
            },
        },
        "established_facts": [],
        "coherence_checks": {
            "last_check_scene": 0,
            "last_result": None,
            "check_history": [],
            "total_contradictions": 0,
        },
        "scenes": [
            {
                "scene_number": 3,
                "content": "朱棣在府中与林风密议，苏念在一旁伺候",
                "actors_present": ["朱棣", "林风", "苏念"],
            },
            {
                "scene_number": 4,
                "content": "朱棣决定起兵，林风领命去筹备军需",
                "actors_present": ["朱棣", "林风"],
            },
        ],
    }
    state.update(overrides)
    return state


class TestAddFactLogic:
    """Test add_fact_logic pure function."""

    def test_creates_structured_fact_object(self):
        """Test 1: add_fact_logic 创建结构化事实对象，fact_id 格式为 fact_{scene}_{keyword}_{index}"""
        state = _make_state()
        result = add_fact_logic("朱棣已起兵", "event", "high", state)
        assert result["status"] == "success"
        assert result["fact_id"].startswith("fact_5_")
        fact = result["fact"]
        assert fact["fact"] == "朱棣已起兵"
        assert fact["category"] == "event"
        assert "朱棣" in fact["actors"]
        assert fact["scene"] == 5
        assert fact["importance"] == "high"
        assert "id" in fact
        assert "added_at" in fact

    def test_validates_category(self):
        """Test 2: add_fact_logic 验证 category 必须在 FACT_CATEGORIES 中"""
        state = _make_state()
        result = add_fact_logic("something", "invalid_category", "medium", state)
        assert result["status"] == "error"
        assert "无效" in result["message"] or "invalid" in result["message"].lower()

    def test_validates_importance(self):
        """Test 3: add_fact_logic 验证 importance 必须为 high/medium/low"""
        state = _make_state()
        result = add_fact_logic("something", "event", "critical", state)
        assert result["status"] == "error"
        assert "无效" in result["message"] or "invalid" in result["message"].lower()

    def test_max_facts_reminder(self):
        """Test 6: add_fact_logic 在事实达 MAX_FACTS(50) 时返回提醒"""
        # Create state with MAX_FACTS facts already
        facts = []
        for i in range(MAX_FACTS):
            facts.append({
                "id": f"fact_1_test_{i+1}",
                "fact": f"测试事实{i+1}",
                "category": "event",
                "actors": [],
                "scene": 1,
                "importance": "low",
                "added_at": "2026-01-01T00:00:00",
            })
        state = _make_state(established_facts=facts)
        result = add_fact_logic("新的事实", "event", "medium", state)
        assert result["status"] == "info"
        assert str(MAX_FACTS) in result["message"]

    def test_overlap_returns_info_not_blocked(self):
        """Test 7: add_fact_logic 重叠时不阻止，返回 info 状态提醒"""
        state = _make_state()
        # Add first fact
        add_fact_logic("朱棣已经起兵出发了", "event", "high", state)
        # Try to add a very similar fact
        result = add_fact_logic("朱棣已经起兵出发了", "event", "medium", state)
        # Should return info about overlap, not error
        assert result["status"] == "info"
        assert "重复" in result["message"] or "重叠" in result["message"]


class TestCheckFactOverlap:
    """Test _check_fact_overlap helper function."""

    def test_detects_80_percent_overlap(self):
        """Test 4: _check_fact_overlap 检测前 20 字 80% 重叠"""
        existing = [{"fact": "朱棣已经在北方起兵发动叛乱"}]
        result = _check_fact_overlap("朱棣已经在北方起兵发动叛乱", existing)
        assert result["is_duplicate"] is True
        assert result["overlapping_with"] is not None

    def test_no_overlap_for_different_facts(self):
        """Test that different facts don't trigger overlap."""
        existing = [{"fact": "林风忠诚守护着朱棣的秘密"}]
        result = _check_fact_overlap("苏念在宫中发现了密信", existing)
        assert result["is_duplicate"] is False


class TestExtractActorNames:
    """Test _extract_actor_names helper function."""

    def test_extracts_known_actors(self):
        """Test 5: _extract_actor_names 从事实文本提取已知角色名"""
        known_actors = ["朱棣", "苏念", "林风"]
        result = _extract_actor_names("朱棣已起兵，林风随行", known_actors)
        assert "朱棣" in result
        assert "林风" in result
        assert "苏念" not in result

    def test_no_actors_in_text(self):
        """Test that no actors are returned when none match."""
        known_actors = ["朱棣", "苏念"]
        result = _extract_actor_names("天下大乱，群雄并起", known_actors)
        assert result == []


class TestFilterRelevantFacts:
    """Test _filter_relevant_facts helper function."""

    def test_filters_by_importance_and_actors(self):
        """Test 8: _filter_relevant_facts 按 importance/actors/category 筛选相关事实"""
        facts = [
            {
                "id": "fact_1_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "actors": ["朱棣"],
                "scene": 1,
                "importance": "high",
                "added_at": "2026-01-01T00:00:00",
            },
            {
                "id": "fact_2_规则_1",
                "fact": "魔法在满月时最强",
                "category": "rule",
                "actors": [],
                "scene": 2,
                "importance": "medium",
                "added_at": "2026-01-01T00:00:00",
            },
            {
                "id": "fact_3_细节_1",
                "fact": "苏念微微笑了笑",
                "category": "event",
                "actors": ["苏念"],
                "scene": 3,
                "importance": "low",
                "added_at": "2026-01-01T00:00:00",
            },
        ]
        state = _make_state(established_facts=facts)
        result = _filter_relevant_facts(state)
        # Should include high importance fact with actor overlap
        fact_ids = [f["id"] for f in result]
        assert "fact_1_起兵_1" in fact_ids
        # Should include rule category regardless of actors
        assert "fact_2_规则_1" in fact_ids
        # Should NOT include low importance fact
        assert "fact_3_细节_1" not in fact_ids

    def test_rule_category_always_included(self):
        """Test 14: _filter_relevant_facts category="rule" 的事实始终包含"""
        facts = [
            {
                "id": "fact_1_魔法_1",
                "fact": "魔法在满月时最强",
                "category": "rule",
                "actors": [],
                "scene": 1,
                "importance": "medium",
                "added_at": "2026-01-01T00:00:00",
            },
        ]
        # Use scenes with no overlapping actors
        state = _make_state(
            established_facts=facts,
            scenes=[
                {
                    "scene_number": 4,
                    "content": "一个无关的人在远方行走",
                    "actors_present": ["路人甲"],
                },
            ],
        )
        result = _filter_relevant_facts(state)
        fact_ids = [f["id"] for f in result]
        assert "fact_1_魔法_1" in fact_ids


class TestValidateConsistencyPrompt:
    """Test validate_consistency_prompt function."""

    def test_builds_correct_prompt(self):
        """Test 9: validate_consistency_prompt 构建包含事实列表+场景内容+输出格式的 prompt"""
        facts = [
            {
                "id": "fact_5_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "actors": ["朱棣"],
                "importance": "high",
            },
        ]
        recent_scenes = [
            {
                "scene_number": 4,
                "content": "朱棣仍在犹豫是否出兵",
            },
        ]
        prompt = validate_consistency_prompt(facts, recent_scenes)
        # Should contain core instruction
        assert "矛盾" in prompt
        # Should contain fact
        assert "朱棣已起兵" in prompt
        # Should contain scene content
        assert "犹豫" in prompt
        # Should contain output format
        assert "JSON" in prompt or "json" in prompt
        assert "contradictions" in prompt
        assert "has_contradiction" in prompt


class TestValidateConsistencyLogic:
    """Test validate_consistency_logic pure function."""

    def test_returns_relevant_facts_and_scenes(self):
        """Test 10: validate_consistency_logic 返回待检查事实列表和 scenes_analyzed"""
        facts = [
            {
                "id": "fact_1_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "actors": ["朱棣"],
                "scene": 1,
                "importance": "high",
                "added_at": "2026-01-01T00:00:00",
            },
        ]
        state = _make_state(established_facts=facts)
        result = validate_consistency_logic(state)
        assert result["status"] == "success"
        assert result["facts_checked"] >= 1
        assert "scenes_analyzed" in result

    def test_no_relevant_facts_returns_success(self):
        """Test that no relevant facts returns clean result."""
        state = _make_state(established_facts=[])
        result = validate_consistency_logic(state)
        assert result["status"] == "success"
        assert result["facts_checked"] == 0


class TestGenerateRepairNarrationPrompt:
    """Test generate_repair_narration_prompt function."""

    def test_supplement_repair_prompt(self):
        """Test 11: generate_repair_narration_prompt 构建补充式修复旁白 prompt"""
        contradiction = {
            "fact_id": "fact_5_起兵_1",
            "fact_text": "朱棣已起兵",
            "scene_text": "朱棣仍在犹豫是否出兵",
            "explanation": "矛盾：已起兵 vs 仍在犹豫",
        }
        prompt = generate_repair_narration_prompt(contradiction, "supplement")
        assert "之前未曾提及" in prompt
        assert "朱棣已起兵" in prompt

    def test_correction_repair_prompt(self):
        """Test 11b: generate_repair_narration_prompt 构建修正式修复旁白 prompt"""
        contradiction = {
            "fact_id": "fact_5_起兵_1",
            "fact_text": "朱棣已起兵",
            "scene_text": "朱棣仍在犹豫是否出兵",
            "explanation": "矛盾：已起兵 vs 仍在犹豫",
        }
        prompt = generate_repair_narration_prompt(contradiction, "correction")
        assert "其实" in prompt or "原来" in prompt


class TestRepairContradictionLogic:
    """Test repair_contradiction_logic pure function."""

    def test_appends_repair_note_without_modifying_original(self):
        """Test 12: repair_contradiction_logic 追加 repair_note 不修改原始事实"""
        facts = [
            {
                "id": "fact_5_起兵_1",
                "fact": "朱棣已起兵",
                "category": "event",
                "actors": ["朱棣"],
                "scene": 5,
                "importance": "high",
                "added_at": "2026-01-01T00:00:00",
            },
        ]
        state = _make_state(established_facts=facts)
        original_fact_text = state["established_facts"][0]["fact"]

        result = repair_contradiction_logic(
            "fact_5_起兵_1", "supplement", "朱棣的犹豫只是表面的", state
        )
        assert result["status"] == "success"
        assert result["fact_id"] == "fact_5_起兵_1"
        # Original fact text should NOT be modified
        assert state["established_facts"][0]["fact"] == original_fact_text
        # But repair_note should be appended
        assert "repair_type" in state["established_facts"][0]
        assert state["established_facts"][0]["repair_type"] == "supplement"

    def test_validates_fact_id_exists(self):
        """Test 13: repair_contradiction_logic 验证 fact_id 存在性"""
        state = _make_state(established_facts=[])
        result = repair_contradiction_logic(
            "fact_99_nonexistent_1", "supplement", "修复说明", state
        )
        assert result["status"] == "error"
        assert "不存在" in result["message"]


class TestGenerateFactId:
    """Test _generate_fact_id helper function."""

    def test_chinese_keyword_extraction(self):
        """Test 15: fact_id 关键词提取——中文 2-4 字匹配"""
        state = _make_state()
        fact_id = _generate_fact_id("朱棣已起兵", 5, state["established_facts"])
        assert fact_id.startswith("fact_5_")
        # Keyword should be Chinese characters from the fact text
        parts = fact_id.split("_")
        assert len(parts) >= 3

    def test_fallback_to_fact_when_no_chinese(self):
        """Test 15b: 无中文时 fallback 'fact'"""
        state = _make_state()
        fact_id = _generate_fact_id("something happened", 5, state["established_facts"])
        assert "fact_5_fact" in fact_id
