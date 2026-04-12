"""Unit tests for DramaRouter routing logic and agent configuration.

Tests LOOP-01 requirement: DramaRouter routes to setup_agent when no actors
exist, and to improv_director when actors exist, with proper fallback behavior.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
        # Ensure getattr(part, 'text', None) returns user_text
        ctx.user_content.parts = [part]
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [part]
    else:
        ctx.user_content = None

    return ctx


# --- Test 1: Routes to setup_agent when actors is empty dict ---


@pytest.mark.asyncio
async def test_drama_router_routes_to_setup_when_no_actors():
    """DramaRouter should route to setup_agent when actors dict is empty."""
    from app.agent import root_agent, DramaRouter

    assert isinstance(root_agent, DramaRouter), "root_agent should be a DramaRouter"

    ctx = _make_ctx(actors={}, user_text="/start 测试主题")

    # Track which agent's run_async was called
    called_agent_name = None
    original_run_async_map = {}

    for sa in root_agent.sub_agents:
        original_run_async_map[sa.name] = sa.run_async
        sa.run_async = AsyncMock()

    async def capture_run_async(agent_ctx):
        return iter([])

    for sa in root_agent.sub_agents:
        sa.run_async = AsyncMock(return_value=capture_run_async(ctx))

    # Execute router
    events = []
    async for event in root_agent._run_async_impl(ctx):
        events.append(event)

    # Find which agent's run_async was called
    for sa in root_agent.sub_agents:
        if sa.run_async.called:
            called_agent_name = sa.name

    assert called_agent_name == "setup_agent", (
        f"Expected setup_agent to be called, got {called_agent_name}"
    )

    # Restore
    for sa in root_agent.sub_agents:
        sa.run_async = original_run_async_map[sa.name]


# --- Test 2: Routes to improv_director when actors has entries ---


@pytest.mark.asyncio
async def test_drama_router_routes_to_improvise_when_actors_exist():
    """DramaRouter should route to improv_director when actors dict has entries."""
    from app.agent import root_agent, DramaRouter

    ctx = _make_ctx(
        actors={"朱棣": {"role": "燕王"}},
        user_text="/next",
    )

    original_run_async_map = {}
    for sa in root_agent.sub_agents:
        original_run_async_map[sa.name] = sa.run_async
        sa.run_async = AsyncMock()

    async def empty_gen(ctx):
        return iter([])

    for sa in root_agent.sub_agents:
        sa.run_async = AsyncMock(return_value=empty_gen(ctx))

    events = []
    async for event in root_agent._run_async_impl(ctx):
        events.append(event)

    called_agent_name = None
    for sa in root_agent.sub_agents:
        if sa.run_async.called:
            called_agent_name = sa.name

    assert called_agent_name == "improv_director", (
        f"Expected improv_director to be called, got {called_agent_name}"
    )

    for sa in root_agent.sub_agents:
        sa.run_async = original_run_async_map[sa.name]


# --- Test 3: Falls back to improv_director when agent lookup returns None ---


@pytest.mark.asyncio
async def test_drama_router_fallback_to_improv_director():
    """DramaRouter should fall back to improv_director when agent lookup fails."""
    from app.agent import DramaRouter

    # Create a DramaRouter with no sub_agents (so lookup returns None)
    setup_agent = MagicMock()
    setup_agent.name = "setup_agent"
    setup_agent.run_async = AsyncMock()

    improv_director = MagicMock()
    improv_director.name = "improv_director"

    async def empty_async_gen(ctx):
        """Yield nothing."""
        return
        yield  # make it an async generator

    improv_director.run_async = MagicMock(return_value=empty_async_gen(None))

    router = DramaRouter(
        name="test_router",
        description="test",
        sub_agents=[setup_agent, improv_director],
    )

    # Override _sub_agents_map to simulate lookup failure for setup_agent
    # We patch it so that get("setup_agent") returns None
    original_map = router._sub_agents_map

    # Create a context with no actors and no utility commands → should try setup_agent
    ctx = _make_ctx(actors={}, user_text="/start test")

    # Patch the _sub_agents_map property to return a dict where setup_agent is None
    with patch.object(type(router), "_sub_agents_map", new_callable=lambda: property(lambda self: {"setup_agent": None, "improv_director": improv_director})):
        events = []
        async for event in router._run_async_impl(ctx):
            events.append(event)

    # Verify improv_director.run_async was called (fallback)
    assert improv_director.run_async.called, (
        "improv_director.run_async should be called as fallback"
    )


# --- Test 4: Routes to improv_director for utility commands ---


@pytest.mark.asyncio
async def test_drama_router_routes_utility_commands_to_improv():
    """DramaRouter should route utility commands to improv_director even without actors."""
    from app.agent import root_agent, DramaRouter

    # Test each utility command
    for cmd in ["/save", "/load", "/export", "/cast", "/status", "/list"]:
        ctx = _make_ctx(actors={}, user_text=cmd)

        original_run_async_map = {}
        for sa in root_agent.sub_agents:
            original_run_async_map[sa.name] = sa.run_async

            async def empty_gen(ctx):
                return iter([])

            sa.run_async = AsyncMock(return_value=empty_gen(ctx))

        events = []
        async for event in root_agent._run_async_impl(ctx):
            events.append(event)

        called_agent_name = None
        for sa in root_agent.sub_agents:
            if sa.run_async.called:
                called_agent_name = sa.name

        assert called_agent_name == "improv_director", (
            f"Command '{cmd}' should route to improv_director, got {called_agent_name}"
        )

        for sa in root_agent.sub_agents:
            sa.run_async = original_run_async_map[sa.name]


# --- Test 5: _improv_director instruction contains infinite loop declaration ---


def test_improv_director_has_infinite_loop_declaration():
    """_improv_director instruction must declare infinite loop protocol."""
    from app.agent import _improv_director

    instruction = _improv_director.instruction
    # Check for Chinese keywords for infinite/no-preset-ending
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
