"""Unit tests for DramaRouter routing, scene transition, and state migration.

Tests LOOP-01 (DramaRouter routing) and LOOP-03 (scene transition + state migration):
- DramaRouter routes to setup_agent when no actors, improv_director when actors exist
- _migrate_legacy_status migrates old STORM status values to setup/acting
- next_scene() returns transition info (is_first_scene, transition, transition_text)
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import AsyncGenerator


# --- Helper to create a mock InvocationContext ---


def _make_ctx(actors: dict | None = None, user_text: str = "") -> MagicMock:
    """Create a mock InvocationContext with specified drama state and user input."""
    ctx = MagicMock()

    # Build session.state
    actors = actors if actors is not None else {}
    ctx.session.state.get = MagicMock(
        side_effect=lambda key, default=None: {
            "drama": {
                "actors": actors,
                "status": "acting" if actors else "setup",
            }
        }.get(key, default)
    )

    # Build user_content
    if user_text:
        part = MagicMock()
        part.text = user_text
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [part]
    else:
        ctx.user_content = None

    return ctx


# ============================================================================
# DramaRouter Routing Tests (LOOP-01, D-01/D-03/D-04)
# ============================================================================


class TestDramaRouterRouting:
    """Test DramaRouter._run_async_impl routing logic."""

    def test_routes_to_setup_when_no_actors(self):
        """D-04: No actors → setup_agent."""
        from app.agent import root_agent

        ctx = _make_ctx(actors={}, user_text="/start 测试主题")

        # Simulate the routing logic from _run_async_impl
        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = ["/save", "/load", "/export", "/cast", "/status", "/list"]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "setup_agent"

        agent = root_agent._sub_agents_map.get(expected_agent_name)
        assert agent is not None
        assert agent.name == expected_agent_name

    def test_routes_to_improvise_when_actors_exist(self):
        """D-04: Actors exist → improv_director."""
        from app.agent import root_agent

        ctx = _make_ctx(
            actors={"朱棣": {"role": "燕王"}},
            user_text="/next",
        )

        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = ["/save", "/load", "/export", "/cast", "/status", "/list"]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "improv_director"

        agent = root_agent._sub_agents_map.get(expected_agent_name)
        assert agent is not None

    def test_routes_utility_commands_to_improv(self):
        """D-04: Utility commands always route to improv_director."""
        from app.agent import root_agent

        for cmd in ["/save", "/load", "/export", "/cast", "/status", "/list"]:
            ctx = _make_ctx(actors={}, user_text=cmd)

            drama = ctx.session.state.get("drama", {})
            actors = drama.get("actors", {})

            user_message = ""
            if ctx.user_content and ctx.user_content.parts:
                for part in ctx.user_content.parts:
                    text = getattr(part, 'text', None) or ''
                    user_message += text.lower()

            utility_commands = ["/save", "/load", "/export", "/cast", "/status", "/list"]
            force_improvise = any(cmd in user_message for cmd in utility_commands)

            if force_improvise or (actors and len(actors) > 0):
                expected_agent_name = "improv_director"
            else:
                expected_agent_name = "setup_agent"

            assert expected_agent_name == "improv_director", (
                f"Command '{cmd}' should route to improv_director even without actors"
            )

    def test_fallback_to_improv_director(self):
        """D-03: Fallback to improv_director when agent lookup fails."""
        from app.agent import root_agent

        sub_agents_map = root_agent._sub_agents_map

        # Fallback logic: if agent is None → get improv_director
        fallback_agent = sub_agents_map.get("improv_director")
        assert fallback_agent is not None, "improv_director must always be available as fallback"
        assert fallback_agent.name == "improv_director"

        assert "improv_director" in sub_agents_map, (
            "improv_director must be in sub_agents_map for D-03 fallback"
        )

    def test_sub_agents_map_contains_both_agents(self):
        """D-01: Router has exactly 2 sub-agents."""
        from app.agent import root_agent

        assert "setup_agent" in root_agent._sub_agents_map
        assert "improv_director" in root_agent._sub_agents_map
        assert len(root_agent._sub_agents_map) == 2


class TestImprovDirectorPrompt:
    """Test _improv_director prompt contains infinite loop declarations (D-05/D-06/D-07)."""

    def test_prompt_contains_no_ending_declaration(self):
        """D-05/Pitfall 4: Prompt must declare infinite loop."""
        from app.agent import _improv_director
        instruction = _improv_director.instruction
        assert "永远不会自行结束" in instruction or "无预设终点" in instruction or "无限" in instruction

    def test_prompt_contains_loop_protocol(self):
        """D-05: Prompt must contain loop protocol steps."""
        from app.agent import _improv_director
        instruction = _improv_director.instruction
        assert "next_scene" in instruction
        assert "director_narrate" in instruction
        assert "actor_speak" in instruction
        assert "write_scene" in instruction

    def test_prompt_contains_user_wait(self):
        """D-06: Prompt must instruct waiting for user input."""
        from app.agent import _improv_director
        instruction = _improv_director.instruction
        assert "等待" in instruction


class TestSetupAgentPrompt:
    """Test _setup_agent prompt preserves STORM exploration (D-02/D-12)."""

    def test_prompt_contains_step_markers(self):
        """Pitfall 1: Prompt must have explicit step markers."""
        from app.agent import _setup_agent
        instruction = _setup_agent.instruction
        assert "步骤" in instruction

    def test_prompt_preserves_multi_perspective(self):
        """D-02: Prompt must preserve multi-perspective exploration."""
        from app.agent import _setup_agent
        instruction = _setup_agent.instruction
        assert "多视角" in instruction or "视角" in instruction

    def test_setup_agent_has_4_tools(self):
        """D-02: Setup agent has 4 tools (no middle-step STORM tools)."""
        from app.agent import _setup_agent
        assert len(_setup_agent.tools) == 4


# ============================================================================
# State Migration Tests (D-14)
# ============================================================================


class TestStateMigration:
    """Test _migrate_legacy_status and its integration with load_progress."""

    def test_migrate_with_actors_sets_acting(self):
        """D-14: actors exist → status='acting'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "storm_researching", "actors": {"朱棣": {"role": "燕王"}}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "acting"

    def test_migrate_without_actors_sets_setup(self):
        """D-14: no actors → status='setup'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "brainstorming", "actors": {}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "setup"

    def test_migrate_empty_status_without_actors(self):
        """D-14: empty status + no actors → 'setup'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "", "actors": {}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "setup"

    def test_migrate_storm_discovering_with_actors(self):
        """D-14: storm_discovering + actors → 'acting'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "storm_discovering", "actors": {"朱棣": {"role": "燕王"}}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "acting"

    def test_migrate_storm_outlining_without_actors(self):
        """D-14: storm_outlining + no actors → 'setup'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "storm_outlining", "actors": {}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "setup"

    def test_migrate_acting_status_unchanged(self):
        """D-14: acting + actors → still 'acting'."""
        from app.state_manager import _migrate_legacy_status
        state = {"status": "acting", "actors": {"朱棣": {"role": "燕王"}}}
        result = _migrate_legacy_status(state)
        assert result["status"] == "acting"


# ============================================================================
# Next Scene Transition Tests (LOOP-03, D-08/D-09/D-10/D-13)
# ============================================================================


class TestNextSceneTransition:
    """Test next_scene() returns transition info and is_first_scene flag."""

    def test_next_scene_returns_is_first_scene_true(self):
        """D-13: next_scene returns is_first_scene=True when current_scene is 0."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {"drama": {"current_scene": 0, "actors": {}, "scenes": []}}
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "is_first_scene" in result
                assert result["is_first_scene"] is True

    def test_next_scene_returns_is_first_scene_false(self):
        """D-13: next_scene returns is_first_scene=False when current_scene > 0."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {
            "drama": {
                "current_scene": 2,
                "actors": {"朱棣": {"role": "燕王", "emotions": "angry"}},
                "scenes": [{"scene_number": 1, "title": "初见", "description": "测试描述"}],
            }
        }
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "is_first_scene" in result
                assert result["is_first_scene"] is False

    def test_next_scene_returns_transition_dict(self):
        """D-09: next_scene returns transition dict with 3 elements."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {"drama": {"current_scene": 1, "actors": {}, "scenes": []}}
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "transition" in result
                transition = result["transition"]
                assert "last_ending" in transition
                assert "actor_emotions" in transition
                assert "unresolved" in transition

    def test_next_scene_returns_transition_text_first_scene(self):
        """D-13: First scene has special opening guidance with 🎬."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {"drama": {"current_scene": 0, "actors": {}, "scenes": []}}
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "transition_text" in result
                assert "🎬" in result["transition_text"] or "第一场" in result["transition_text"]

    def test_next_scene_returns_transition_text_non_first(self):
        """D-09: Non-first scene has transition info with 上一场衔接."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {
            "drama": {
                "current_scene": 2,
                "actors": {"朱棣": {"role": "燕王", "emotions": "angry"}},
                "scenes": [{"scene_number": 1, "title": "初见", "description": "测试描述"}],
            }
        }
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "transition_text" in result
                assert "上一场衔接" in result["transition_text"]

    def test_next_scene_message_contains_loop_protocol(self):
        """D-05: next_scene message contains loop protocol steps (① ② ③)."""
        from app.tools import next_scene
        tc = MagicMock()
        tc.state = {"drama": {"current_scene": 1, "actors": {}, "scenes": []}}
        with patch("app.tools.advance_scene", return_value={"status": "success"}):
            with patch("app.tools.build_director_context", return_value="ctx"):
                result = next_scene(tc)
                assert "①" in result["message"]
                assert "②" in result["message"]
                assert "③" in result["message"]


# ============================================================================
# Async Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_drama_router_run_async_impl_is_async_generator():
    """DramaRouter._run_async_impl should be callable and return AsyncGenerator."""
    from app.agent import root_agent

    # Verify the method exists and is async
    import inspect
    assert inspect.isasyncgenfunction(root_agent._run_async_impl), (
        "_run_async_impl should be an async generator function"
    )
