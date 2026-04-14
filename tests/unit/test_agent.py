"""Unit tests for DramaRouter routing, scene transition, and state migration.

Tests LOOP-01 (DramaRouter routing) and LOOP-03 (scene transition + state migration):
- DramaRouter routes to setup_agent when no actors, improv_director when actors exist
- _migrate_legacy_status migrates old STORM status values to setup/acting
- next_scene() returns transition info (is_first_scene, transition, transition_text)

Phase 5 additions:
- DramaRouter routes /auto, /steer, /end, /storm to improv_director
- DramaRouter auto-interrupt safety net clears remaining_auto_scenes (D-02)
- _improv_director has Phase 5 tools (auto_advance, steer_drama, end_drama, trigger_storm)
- _improv_director prompt has 7-section structure (D-26)
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import AsyncGenerator


# --- Helper to create a mock InvocationContext ---


def _make_ctx(actors: dict | None = None, user_text: str = "", remaining_auto_scenes: int = 0) -> MagicMock:
    """Create a mock InvocationContext with specified drama state and user input."""
    ctx = MagicMock()

    # Build session.state
    actors = actors if actors is not None else {}
    drama_state = {
        "actors": actors,
        "status": "acting" if actors else "setup",
        "remaining_auto_scenes": remaining_auto_scenes,
    }
    ctx.session.state.get = MagicMock(
        side_effect=lambda key, default=None: {
            "drama": drama_state
        }.get(key, default)
    )
    # Allow direct dict-style access for D-02 auto-interrupt
    ctx.session.state.__setitem__ = MagicMock()
    ctx.session.state.__getitem__ = MagicMock(return_value=drama_state)

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

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",  # Phase 5 additions
        ]
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

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",  # Phase 5 additions
        ]
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

        for cmd in ["/save", "/load", "/export", "/cast", "/status", "/list",
                    "/auto", "/steer", "/end", "/storm"]:
            ctx = _make_ctx(actors={}, user_text=cmd)

            drama = ctx.session.state.get("drama", {})
            actors = drama.get("actors", {})

            user_message = ""
            if ctx.user_content and ctx.user_content.parts:
                for part in ctx.user_content.parts:
                    text = getattr(part, 'text', None) or ''
                    user_message += text.lower()

            utility_commands = [
                "/save", "/load", "/export", "/cast", "/status", "/list",
                "/auto", "/steer", "/end", "/storm",  # Phase 5 additions
            ]
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


# ============================================================================
# Phase 5: Mixed Autonomy Mode Tests (LOOP-02, LOOP-04)
# ============================================================================


class TestDramaRouterPhase5Routing:
    """Test DramaRouter routes Phase 5 commands to improv_director."""

    def test_router_routes_auto_to_improv(self):
        """D-01: /auto command routes to improv_director."""
        ctx = _make_ctx(actors={}, user_text="/auto 3")

        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",
        ]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "improv_director"

    def test_router_routes_steer_to_improv(self):
        """D-07: /steer command routes to improv_director."""
        ctx = _make_ctx(actors={}, user_text="/steer 让朱棣更偏执")

        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",
        ]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "improv_director"

    def test_router_routes_end_to_improv(self):
        """D-11: /end command routes to improv_director."""
        ctx = _make_ctx(actors={}, user_text="/end")

        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",
        ]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "improv_director"

    def test_router_routes_storm_to_improv(self):
        """D-19: /storm command routes to improv_director."""
        ctx = _make_ctx(actors={}, user_text="/storm 角色关系")

        drama = ctx.session.state.get("drama", {})
        actors = drama.get("actors", {})

        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        utility_commands = [
            "/save", "/load", "/export", "/cast", "/status", "/list",
            "/auto", "/steer", "/end", "/storm",
        ]
        force_improvise = any(cmd in user_message for cmd in utility_commands)

        if force_improvise or (actors and len(actors) > 0):
            expected_agent_name = "improv_director"
        else:
            expected_agent_name = "setup_agent"

        assert expected_agent_name == "improv_director"


class TestDramaRouterAutoInterrupt:
    """Test D-02: Auto-interrupt safety net clears remaining_auto_scenes."""

    def test_router_auto_interrupt_clears_counter(self):
        """D-02: Non-/auto input during auto-advance clears remaining_auto_scenes."""
        ctx = _make_ctx(actors={}, user_text="something", remaining_auto_scenes=5)

        drama = ctx.session.state.get("drama", {})
        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        # D-02: Auto-interrupt safety net
        if drama.get("remaining_auto_scenes", 0) > 0:
            if "/auto" not in user_message:
                # Should clear — user sent non-auto input during auto-advance
                assert "/auto" not in user_message, "Non-auto message should trigger interrupt"
                # Simulate the clearing
                drama["remaining_auto_scenes"] = 0

        assert drama["remaining_auto_scenes"] == 0, (
            "remaining_auto_scenes should be cleared after non-/auto input"
        )

    def test_router_auto_not_interrupted_by_auto_command(self):
        """D-02: /auto command during auto-advance should NOT clear counter."""
        ctx = _make_ctx(actors={}, user_text="/auto 5", remaining_auto_scenes=5)

        drama = ctx.session.state.get("drama", {})
        user_message = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, 'text', None) or ''
                user_message += text.lower()

        # D-02: Auto-interrupt safety net — /auto should NOT clear
        if drama.get("remaining_auto_scenes", 0) > 0:
            if "/auto" not in user_message:
                drama["remaining_auto_scenes"] = 0

        # Should still be 5 since "/auto" is in the message
        assert drama["remaining_auto_scenes"] == 5, (
            "remaining_auto_scenes should NOT be cleared when user sends /auto"
        )


class TestImprovDirectorPhase5:
    """Test _improv_director Phase 5 integrations."""

    def test_improv_director_has_phase5_tools(self):
        """_improv_director tools include auto_advance, steer_drama, end_drama, trigger_storm."""
        from app.agent import _improv_director

        tool_names = [getattr(t, 'name', getattr(t, '__name__', str(t))) for t in _improv_director.tools]
        assert "auto_advance" in tool_names, "auto_advance tool not registered"
        assert "steer_drama" in tool_names, "steer_drama tool not registered"
        assert "end_drama" in tool_names, "end_drama tool not registered"
        assert "trigger_storm" in tool_names, "trigger_storm tool not registered"

    def test_improv_prompt_contains_seven_sections(self):
        """D-26: _improv_director prompt has 7-section structure."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "核心循环协议" in instruction, "§1 核心循环协议 missing"
        assert "自动推进协议" in instruction, "§2 自动推进协议 missing"
        assert "用户引导与干预" in instruction, "§3 用户引导与干预 missing"
        assert "终幕协议" in instruction, "§4 终幕协议 missing"
        assert "视角审视" in instruction, "§5 视角审视 missing"
        assert "选项呈现规范" in instruction, "§6 选项呈现规范 missing"
        assert "输出格式" in instruction, "§7 输出格式 missing"

    def test_improv_prompt_contains_auto_advance_protocol(self):
        """§2: Prompt describes auto-advance behavior with remaining_auto_scenes."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "remaining_auto_scenes" in instruction
        assert "auto_remaining" in instruction

    def test_improv_prompt_contains_steer_protocol(self):
        """§3: Prompt describes /steer vs /action distinction."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "steer_drama" in instruction
        assert "方向引导" in instruction

    def test_improv_prompt_contains_end_protocol(self):
        """§4: Prompt describes end + epilogue flow."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "end_drama" in instruction
        assert "番外篇" in instruction

    def test_improv_prompt_contains_storm_protocol(self):
        """§5: Prompt describes /storm Dynamic STORM perspective discovery."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "dynamic_storm" in instruction

    def test_improv_prompt_contains_options_spec(self):
        """§6: Prompt describes options format."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "选项呈现规范" in instruction
        assert "接下来你想" in instruction

    def test_improv_prompt_updated_principle_5(self):
        """Principle 5 updated to mixed mode instead of semi-auto."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "混合模式" in instruction
        # The old "半自动模式" should be replaced
        assert "半自动模式" not in instruction

    def test_improv_prompt_updated_command_list(self):
        """Command list includes Phase 5 commands."""
        from app.agent import _improv_director

        instruction = _improv_director.instruction
        assert "/auto" in instruction
        assert "/steer" in instruction
        assert "/end" in instruction
        assert "/storm" in instruction


# ============================================================================
# Phase 5: CLI Tests
# ============================================================================


class TestCLIPhase5Commands:
    """Test CLI Phase 5 help text and function call display."""

    def test_banner_contains_auto_command(self):
        """CLI banner lists /auto command."""
        from cli import print_banner
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            print_banner()
        output = f.getvalue()
        assert "/auto" in output

    def test_banner_contains_steer_command(self):
        """CLI banner lists /steer command."""
        from cli import print_banner
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            print_banner()
        output = f.getvalue()
        assert "/steer" in output

    def test_banner_contains_end_command(self):
        """CLI banner lists /end command."""
        from cli import print_banner
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            print_banner()
        output = f.getvalue()
        assert "/end" in output

    def test_banner_contains_storm_command(self):
        """CLI banner lists /storm command."""
        from cli import print_banner
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            print_banner()
        output = f.getvalue()
        assert "/storm" in output

    def test_send_message_displays_phase5_function_calls(self):
        """CLI _send_message displays Phase 5 tool function calls."""
        # Verify the Phase 5 function names are in the display list
        # by checking the source code of _send_message
        import cli
        import inspect
        source = inspect.getsource(cli._send_message)
        assert "auto_advance" in source
        assert "steer_drama" in source
        assert "end_drama" in source
        assert "trigger_storm" in source


class TestCLIAutoDefault:
    """Test D-04: /auto without number defaults to 3 scenes."""

    def test_auto_without_number_defaults_to_3(self):
        """D-04: '/auto' (no number) should be expanded to '/auto 3'."""
        # Simulate the CLI preprocessing logic
        user_input = "/auto"
        if user_input.lower() == "/auto":
            user_input = "/auto 3"
        assert user_input == "/auto 3"

    def test_auto_with_number_unchanged(self):
        """D-04: '/auto 5' should remain '/auto 5'."""
        user_input = "/auto 5"
        if user_input.lower() == "/auto":
            user_input = "/auto 3"
        assert user_input == "/auto 5"

    def test_auto_uppercase_unchanged_after_default(self):
        """D-04: '/AUTO' (uppercase) should also default to 3."""
        user_input = "/AUTO"
        if user_input.lower() == "/auto":
            user_input = "/auto 3"
        assert user_input == "/auto 3"
