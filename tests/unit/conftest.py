"""Shared test fixtures for memory_manager unit tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext with drama state containing a test actor."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "测试戏剧",
            "current_scene": 3,
            "status": "acting",
            "remaining_auto_scenes": 0,
            "steer_direction": None,
            "storm": {"last_review": {}},
            "conflict_engine": {
                "tension_score": 0,
                "is_boring": False,
                "tension_history": [],
                "active_conflicts": [],
                "used_conflict_types": [],
                "last_inject_scene": 0,
                "consecutive_low_tension": 0,
                "resolved_conflicts": [],
            },
            "plot_threads": [],
            "established_facts": [],
            "coherence_checks": {
                "last_check_scene": 0,
                "last_result": None,
                "check_history": [],
                "total_contradictions": 0,
            },
            "actors": {
                "朱棣": {
                    "role": "燕王",
                    "personality": "沉稳冷静，说话简短有力",
                    "background": "明太祖第四子，封燕王，镇守北平",
                    "knowledge_scope": "熟悉军事和朝堂",
                    "memory": [],  # old field
                    "working_memory": [],
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
                    "arc_progress": {
                        "arc_type": "",
                        "arc_stage": "",
                        "progress": 0,
                        "related_threads": [],
                    },
                    "created_at": "2026-04-11T10:00:00",
                },
                "苏念": {
                    "role": "宫女",
                    "personality": "温柔聪慧，善于察言观色",
                    "background": "后宫宫女，暗中传递消息",
                    "knowledge_scope": "宫廷内幕",
                    "memory": [],
                    "working_memory": [],
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
                    "emotions": "anxious",
                    "arc_progress": {
                        "arc_type": "",
                        "arc_stage": "",
                        "progress": 0,
                        "related_threads": [],
                    },
                    "created_at": "2026-04-11T10:00:00",
                },
            },
        }
    }
    return tc


@pytest.fixture
def mock_tool_context_no_storm():
    """Create a mock ToolContext without the storm sub-dict, for testing trigger_storm initialization."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "测试戏剧",
            "current_scene": 3,
            "status": "acting",
            "remaining_auto_scenes": 0,
            "steer_direction": None,
            # Note: no "storm" key
            "actors": {
                "朱棣": {
                    "role": "燕王",
                    "personality": "沉稳冷静",
                    "background": "明太祖第四子",
                    "knowledge_scope": "军事",
                    "working_memory": [],
                    "scene_summaries": [],
                    "arc_summary": {"structured": {}, "narrative": ""},
                    "critical_memories": [],
                    "emotions": "neutral",
                }
            },
        }
    }
    return tc


@pytest.fixture
def mock_tool_context_old_format():
    """Create a mock ToolContext with OLD format actor (no new fields)."""
    tc = MagicMock()
    tc.state = {
        "drama": {
            "theme": "旧格式戏剧",
            "current_scene": 5,
            "status": "acting",
            "actors": {
                "朱元璋": {
                    "role": "皇帝",
                    "personality": "威严果断",
                    "background": "大明开国皇帝",
                    "knowledge_scope": "天下大事",
                    "memory": [
                        {"entry": "面对情境: 第一场描述", "timestamp": "2026-04-10T10:00:00"},
                        {"entry": "面对情境: 第二场描述", "timestamp": "2026-04-10T11:00:00"},
                        {"entry": "面对情境: 第三场描述", "timestamp": "2026-04-10T12:00:00"},
                    ],
                    "emotions": "angry",
                    "created_at": "2026-04-10T09:00:00",
                }
            },
        }
    }
    return tc
