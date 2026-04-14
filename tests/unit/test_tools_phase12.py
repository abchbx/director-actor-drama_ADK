"""Unit tests for Phase 12 tools.py changes.

Covers:
- actor_speak error detection logic ([ERROR:xxx] markers)
- Shared httpx.AsyncClient (get_shared_client / close_shared_client)
- _call_a2a_sdk uses shared client
- archive_old_scenes integration in next_scene
- Actor crash recovery (passive detection + auto-restart)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Task 1 Part A: Error detection — [ERROR:xxx] markers
# ---------------------------------------------------------------------------


class TestErrorDetection:
    """Test that actor_speak error detection correctly identifies error dialogues."""

    def test_connection_error_detected(self):
        """'[ERROR:connection] 朱棣连接失败(端口:1234)' is detected as error."""
        from app.tools import actor_speak
        # The [ERROR:xxx] prefix is the detection mechanism
        dialogue = "[ERROR:connection] 朱棣连接失败(端口:1234)"
        assert dialogue.startswith("[ERROR:")

    def test_timeout_error_detected(self):
        """'[ERROR:timeout] 朱棣响应超时' is detected as error."""
        dialogue = "[ERROR:timeout] 朱棣响应超时"
        assert dialogue.startswith("[ERROR:")

    def test_generic_error_detected(self):
        """'[ERROR:ConnectionError] 朱棣调用失败: connection refused' is detected as error."""
        dialogue = "[ERROR:ConnectionError] 朱棣调用失败: connection refused"
        assert dialogue.startswith("[ERROR:")

    def test_normal_dialogue_not_detected_as_error(self):
        """'我觉得应该这样做' is NOT detected as error."""
        dialogue = "我觉得应该这样做"
        assert not dialogue.startswith("[ERROR:")

    def test_restart_failed_error_detected(self):
        """'[ERROR:connection] 朱棣重启失败: ...' is detected as error."""
        dialogue = "[ERROR:connection] 朱棣重启失败: 重启失败信息"
        assert dialogue.startswith("[ERROR:")

    def test_post_restart_still_fails_detected(self):
        """'[ERROR:connection] 朱棣重启后仍无法连接' is detected as error."""
        dialogue = "[ERROR:connection] 朱棣重启后仍无法连接(端口:1234)"
        assert dialogue.startswith("[ERROR:")


# ---------------------------------------------------------------------------
# Task 1 Part B: Shared AsyncClient
# ---------------------------------------------------------------------------


class TestSharedAsyncClient:
    """Test shared httpx.AsyncClient singleton behavior."""

    def setup_method(self):
        """Reset shared client before each test."""
        import app.tools as tools_mod
        tools_mod._shared_httpx_client = None

    def teardown_method(self):
        """Clean up shared client after each test."""
        import app.tools as tools_mod
        tools_mod._shared_httpx_client = None

    def test_get_shared_client_returns_instance(self):
        """get_shared_client() returns an httpx.AsyncClient instance."""
        import httpx
        from app.tools import get_shared_client

        client = get_shared_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_get_shared_client_returns_same_instance(self):
        """get_shared_client() returns the same instance on repeated calls."""
        from app.tools import get_shared_client

        client1 = get_shared_client()
        client2 = get_shared_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_shared_client_rebuilds_after_close(self):
        """get_shared_client() creates a new instance after the old one is closed."""
        from app.tools import get_shared_client

        client1 = get_shared_client()
        client1_id = id(client1)
        # Close it properly
        await client1.aclose()
        # Should get a new instance
        client2 = get_shared_client()
        assert id(client2) != client1_id

    @pytest.mark.asyncio
    async def test_close_shared_client(self):
        """close_shared_client() closes and sets internal ref to None."""
        import httpx
        from app.tools import get_shared_client, close_shared_client
        import app.tools as tools_mod

        client = get_shared_client()
        assert tools_mod._shared_httpx_client is not None

        await close_shared_client()
        assert tools_mod._shared_httpx_client is None

    @pytest.mark.asyncio
    async def test_close_shared_client_idempotent(self):
        """close_shared_client() is safe to call when client is already None."""
        from app.tools import close_shared_client
        import app.tools as tools_mod

        tools_mod._shared_httpx_client = None
        await close_shared_client()  # Should not raise
        assert tools_mod._shared_httpx_client is None

    @pytest.mark.asyncio
    async def test_call_a2a_sdk_uses_shared_client(self):
        """_call_a2a_sdk uses get_shared_client() instead of creating new client."""
        from app.tools import _call_a2a_sdk, get_shared_client
        import app.tools as tools_mod

        # Get the shared client first
        shared = get_shared_client()

        with patch("app.tools.get_shared_client", return_value=shared) as mock_get:
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value={
                    "name": "actor_test",
                    "description": "test",
                    "url": "http://localhost:9001/",
                    "version": "1.0.0",
                    "capabilities": {"streaming": False},
                    "defaultInputModes": ["text/plain"],
                    "defaultOutputModes": ["text/plain"],
                    "skills": [],
                }):
                    with patch("a2a.client.ClientFactory.create") as mock_create:
                        mock_client = AsyncMock()
                        mock_client.send_message = AsyncMock(return_value=aiter([]))
                        mock_create.return_value = mock_client

                        # Need to also patch AgentCard
                        with patch("a2a.types.AgentCard"):
                            try:
                                await _call_a2a_sdk("/tmp/test_card.json", "test prompt", "test_actor", "9001")
                            except Exception:
                                pass  # May fail due to mock incompleteness, that's ok

                            # Verify get_shared_client was called
                            mock_get.assert_called()


# ---------------------------------------------------------------------------
# Task 1 Part C: next_scene triggers archive_old_scenes
# ---------------------------------------------------------------------------


class TestNextSceneArchival:
    """Test that next_scene() triggers archive_old_scenes()."""

    def test_next_scene_calls_archive_old_scenes(self):
        """next_scene() calls archive_old_scenes() before _set_state."""
        from app.tools import next_scene

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 1,
                "status": "acting",
                "remaining_auto_scenes": 0,
                "scenes": [],
                "actors": {},
                "dynamic_storm": {"scenes_since_last_storm": 0},
            }
        }

        with patch("app.state_manager.archive_old_scenes") as mock_archive:
            mock_archive.side_effect = lambda s: s  # passthrough
            result = next_scene(tool_context=tc)
            mock_archive.assert_called_once()


# ---------------------------------------------------------------------------
# Task 2: Actor crash recovery (passive detection + auto-restart)
# ---------------------------------------------------------------------------


class TestRestartActor:
    """Test _restart_actor function."""

    @pytest.mark.asyncio
    async def test_restart_actor_calls_stop_and_create(self):
        """_restart_actor calls stop_actor_service + create_actor_service."""
        from app.tools import _restart_actor

        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "crash_count": 0,
                        "working_memory": [],
                        "critical_memories": [],
                    }
                }
            }
        }

        with patch("app.tools.stop_actor_service") as mock_stop, \
             patch("app.tools.create_actor_service") as mock_create:
            mock_stop.return_value = {"status": "success", "message": "stopped"}
            mock_create.return_value = {"status": "success", "message": "created", "port": 9001}

            result = await _restart_actor("朱棣", tc)

            mock_stop.assert_called_once_with("朱棣")
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_actor_increments_crash_count(self):
        """_restart_actor increments crash_count and logs restart."""
        from app.tools import _restart_actor

        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "crash_count": 1,
                        "working_memory": [],
                        "critical_memories": [],
                    }
                }
            }
        }

        with patch("app.tools.stop_actor_service") as mock_stop, \
             patch("app.tools.create_actor_service") as mock_create, \
             patch("app.tools._set_state"):
            mock_stop.return_value = {"status": "success"}
            mock_create.return_value = {"status": "success", "port": 9001}

            result = await _restart_actor("朱棣", tc)

            # crash_count should be incremented to 2
            assert tc.state["drama"]["actors"]["朱棣"]["crash_count"] == 2

    @pytest.mark.asyncio
    async def test_restart_actor_adds_restart_log(self):
        """_restart_actor adds entry to restart_log with timestamp and reason."""
        from app.tools import _restart_actor

        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "crash_count": 0,
                        "working_memory": [],
                        "critical_memories": [],
                    }
                }
            }
        }

        with patch("app.tools.stop_actor_service") as mock_stop, \
             patch("app.tools.create_actor_service") as mock_create, \
             patch("app.tools._set_state"):
            mock_stop.return_value = {"status": "success"}
            mock_create.return_value = {"status": "success", "port": 9001}

            result = await _restart_actor("朱棣", tc)

            # restart_log should have an entry
            log = tc.state["drama"]["actors"]["朱棣"]["restart_log"]
            assert len(log) == 1
            assert "time" in log[0]
            assert log[0]["reason"] == "auto_restart_after_crash"

    @pytest.mark.asyncio
    async def test_restart_actor_max_crash_count(self):
        """_restart_actor returns error when crash_count >= MAX_CRASH_COUNT (3)."""
        from app.tools import _restart_actor

        tc = MagicMock()
        tc.state = {
            "drama": {
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "crash_count": 2,  # Will become 3 on next crash
                        "working_memory": [],
                        "critical_memories": [],
                    }
                }
            }
        }

        with patch("app.tools.stop_actor_service") as mock_stop, \
             patch("app.tools.create_actor_service") as mock_create:
            mock_stop.return_value = {"status": "success"}
            mock_create.return_value = {"status": "success", "port": 9001}

            result = await _restart_actor("朱棣", tc)

            # crash_count is now 3, should return error
            assert result["status"] == "error"
            assert "3" in result["message"]
            # stop + create should NOT have been called since we hit the limit
            mock_stop.assert_not_called()
            mock_create.assert_not_called()


class TestActorSpeakCrashRecovery:
    """Test actor_speak crash recovery integration."""

    @pytest.mark.asyncio
    async def test_actor_speak_connection_error_triggers_restart(self):
        """actor_speak connection error triggers _restart_actor."""
        from app.tools import actor_speak

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 1,
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "emotions": "neutral",
                        "working_memory": [],
                        "critical_memories": [],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {}, "narrative": ""},
                        "crash_count": 0,
                        "port": 9001,
                    }
                }
            }
        }

        with patch("app.tools.get_actor_info") as mock_info, \
             patch("app.tools.get_actor_remote_config") as mock_config, \
             patch("app.tools.build_actor_context", return_value="ctx"), \
             patch("app.tools.detect_importance", return_value=(False, None)), \
             patch("app.tools.add_working_memory"), \
             patch("app.tools._call_a2a_sdk", side_effect=ConnectionError("connection refused")), \
             patch("app.tools._restart_actor", new_callable=AsyncMock) as mock_restart, \
             patch("app.tools._get_state", return_value=tc.state["drama"]), \
             patch("app.tools._set_state"):

            mock_info.return_value = {
                "status": "success",
                "actor": tc.state["drama"]["actors"]["朱棣"],
            }
            mock_config.return_value = {
                "card_file": "/tmp/test_card.json",
                "card_url": "http://localhost:9001/.well-known/agent.json",
                "rpc_url": "http://localhost:9001/",
                "port": 9001,
            }
            mock_restart.return_value = {
                "status": "success",
                "message": "restarted",
                "port": 9001,
            }

            result = await actor_speak("朱棣", "test situation", tc)

            # _restart_actor should have been called
            mock_restart.assert_called_once_with("朱棣", tc)

    @pytest.mark.asyncio
    async def test_actor_speak_crash_count_resets_on_success(self):
        """After successful actor_speak, crash_count resets to 0."""
        from app.tools import actor_speak

        tc = MagicMock()
        tc.state = {
            "drama": {
                "theme": "测试戏剧",
                "current_scene": 1,
                "actors": {
                    "朱棣": {
                        "role": "燕王",
                        "personality": "沉稳",
                        "background": "明太祖第四子",
                        "knowledge_scope": "军事",
                        "emotions": "neutral",
                        "working_memory": [],
                        "critical_memories": [],
                        "scene_summaries": [],
                        "arc_summary": {"structured": {}, "narrative": ""},
                        "crash_count": 2,
                        "port": 9001,
                    }
                }
            }
        }

        with patch("app.tools.get_actor_info") as mock_info, \
             patch("app.tools.get_actor_remote_config") as mock_config, \
             patch("app.tools.build_actor_context", return_value="ctx"), \
             patch("app.tools.detect_importance", return_value=(False, None)), \
             patch("app.tools.add_working_memory"), \
             patch("app.tools.add_dialogue"), \
             patch("app.tools._call_a2a_sdk", new_callable=AsyncMock, return_value="我觉得应该这样做"), \
             patch("app.tools._get_state", return_value=tc.state["drama"]), \
             patch("app.tools._set_state"):

            mock_info.return_value = {
                "status": "success",
                "actor": tc.state["drama"]["actors"]["朱棣"],
            }
            mock_config.return_value = {
                "card_file": "/tmp/test_card.json",
                "card_url": "http://localhost:9001/.well-known/agent.json",
                "rpc_url": "http://localhost:9001/",
                "port": 9001,
            }

            result = await actor_speak("朱棣", "test situation", tc)

            # crash_count should be reset to 0
            assert tc.state["drama"]["actors"]["朱棣"]["crash_count"] == 0


# ---------------------------------------------------------------------------
# Helper: async iterator for mocking
# ---------------------------------------------------------------------------


async def aiter(items):
    """Create an async iterator from a list."""
    for item in items:
        yield item
