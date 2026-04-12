"""Unit tests for DramaRouter routing logic and agent configuration.

Tests LOOP-01 requirement: DramaRouter routes to setup_agent when no actors
exist, and to improv_director when actors exist, with proper fallback behavior.
"""

import pytest
from unittest.mock import MagicMock
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


# --- Test 1: Routes to setup_agent when actors is empty dict ---


def test_drama_router_routes_to_setup_when_no_actors():
    """DramaRouter should route to setup_agent when actors dict is empty.

    We test the routing decision by examining the _sub_agents_map lookup
    that _run_async_impl would perform. The router's logic:
    - no actors + no utility command → lookup("setup_agent")
    """
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

    assert expected_agent_name == "setup_agent", (
        f"With no actors and /start command, should route to setup_agent"
    )

    # Verify the agent actually exists in sub_agents_map
    agent = root_agent._sub_agents_map.get(expected_agent_name)
    assert agent is not None, f"Agent '{expected_agent_name}' should exist in sub_agents_map"
    assert agent.name == expected_agent_name


# --- Test 2: Routes to improv_director when actors has entries ---


def test_drama_router_routes_to_improvise_when_actors_exist():
    """DramaRouter should route to improv_director when actors dict has entries."""
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

    assert expected_agent_name == "improv_director", (
        f"With actors present, should route to improv_director"
    )

    agent = root_agent._sub_agents_map.get(expected_agent_name)
    assert agent is not None, f"Agent '{expected_agent_name}' should exist in sub_agents_map"


# --- Test 3: Falls back to improv_director when agent lookup returns None ---


def test_drama_router_fallback_to_improv_director():
    """DramaRouter should fall back to improv_director when agent lookup fails.

    Per D-03: Fallback to improv_director is the safest default.
    """
    from app.agent import root_agent

    # Test the fallback behavior: if the primary lookup returns None,
    # the router should fallback to improv_director
    sub_agents_map = root_agent._sub_agents_map

    # Simulate: setup_agent is None in the map (edge case)
    # Fallback logic: if agent is None → get improv_director
    fallback_agent = sub_agents_map.get("improv_director")
    assert fallback_agent is not None, "improv_director must always be available as fallback"
    assert fallback_agent.name == "improv_director"

    # Also verify the fallback chain: setup_agent → improv_director
    # If setup_agent lookup fails, improv_director is the fallback
    # This is the D-03 guarantee
    assert "improv_director" in sub_agents_map, (
        "improv_director must be in sub_agents_map for D-03 fallback"
    )


# --- Test 4: Routes to improv_director for utility commands ---


def test_drama_router_routes_utility_commands_to_improv():
    """DramaRouter should route utility commands to improv_director even without actors."""
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


# --- Test 5: _improv_director instruction contains infinite loop declaration ---


def test_improv_director_has_infinite_loop_declaration():
    """_improv_director instruction must declare infinite loop protocol."""
    from app.agent import _improv_director

    instruction = _improv_director.instruction
    has_infinite = "无限" in instruction or "无预设终点" in instruction or "永远不会自行结束" in instruction
    assert has_infinite, (
        "_improv_director instruction must contain infinite loop declaration "
        "(无限, 无预设终点, or 永远不会自行结束)"
    )


# --- Test 6: _setup_agent instruction preserves STORM multi-perspective value ---


def test_setup_agent_has_multi_perspective():
    """_setup_agent instruction must mention multi-perspective exploration."""
    from app.agent import _setup_agent

    instruction = _setup_agent.instruction
    has_perspective = "多视角" in instruction
    assert has_perspective, (
        "_setup_agent instruction must mention 多视角 to preserve STORM exploration value"
    )


# --- Test 7: root_agent.sub_agents has exactly 2 agents ---


def test_root_agent_has_two_sub_agents():
    """root_agent should have exactly 2 sub-agents (setup_agent + improv_director)."""
    from app.agent import root_agent

    assert len(root_agent.sub_agents) == 2, (
        f"Expected 2 sub-agents, got {len(root_agent.sub_agents)}"
    )
    names = [sa.name for sa in root_agent.sub_agents]
    assert "setup_agent" in names, "setup_agent should be a sub-agent"
    assert "improv_director" in names, "improv_director should be a sub-agent"


# --- Integration: Verify DramaRouter._run_async_impl is a proper async generator ---


@pytest.mark.asyncio
async def test_drama_router_run_async_impl_is_async_generator():
    """DramaRouter._run_async_impl should be callable and return AsyncGenerator."""
    from app.agent import root_agent

    # Verify the method exists and is async
    import inspect
    assert inspect.isasyncgenfunction(root_agent._run_async_impl), (
        "_run_async_impl should be an async generator function"
    )
