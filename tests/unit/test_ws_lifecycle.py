"""Tests for WebSocket lifecycle: replay buffer, reconnect, connection limit, slow clients."""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.ws_manager import ConnectionManager


class TestReplayBuffer:
    """Test replay buffer behavior (D-08/D-09)."""

    @pytest.mark.asyncio
    async def test_broadcast_stores_events_in_replay_buffer(self):
        """Broadcast 3 events, verify replay_buffer has 3 entries."""
        manager = ConnectionManager()
        for i in range(3):
            await manager.broadcast({"type": f"event_{i}", "data": {}})
        assert len(manager.replay_buffer) == 3

    @pytest.mark.asyncio
    async def test_replay_buffer_auto_evicts_at_maxlen(self):
        """Replay buffer auto-evicts old events when maxlen=100 reached (D-08)."""
        manager = ConnectionManager()
        for i in range(101):
            await manager.broadcast({"type": f"event_{i}", "data": {}})
        assert len(manager.replay_buffer) == 100
        # First event should have been evicted
        assert manager.replay_buffer[0]["type"] == "event_1"
        # Last event should be present
        assert manager.replay_buffer[-1]["type"] == "event_100"

    @pytest.mark.asyncio
    async def test_new_connection_receives_replay(self):
        """New connection receives full replay buffer as first message (D-09)."""
        manager = ConnectionManager()
        # Pre-populate buffer
        for i in range(3):
            manager.replay_buffer.append({"type": f"event_{i}", "data": {}})

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        accepted = await manager.connect(ws)
        assert accepted is True

        # Verify replay message was sent
        ws.send_json.assert_called_once()
        sent_data = ws.send_json.call_args[0][0]
        assert sent_data["type"] == "replay"
        assert len(sent_data["events"]) == 3

    @pytest.mark.asyncio
    async def test_reconnecting_client_receives_replay_automatically(self):
        """Reconnecting client gets full replay buffer automatically (D-10)."""
        manager = ConnectionManager()
        # Client A connects
        ws_a = AsyncMock()
        ws_a.accept = AsyncMock()
        ws_a.send_json = AsyncMock()
        await manager.connect(ws_a)

        # Broadcast 5 events while A is connected
        for i in range(5):
            await manager.broadcast({"type": f"event_{i}", "data": {}})

        # Client A disconnects
        manager.disconnect(ws_a)

        # Client B (reconnecting) connects and gets replay
        ws_b = AsyncMock()
        ws_b.accept = AsyncMock()
        ws_b.send_json = AsyncMock()
        await manager.connect(ws_b)

        # Verify B received replay with all 5 events
        ws_b.send_json.assert_called_once()
        sent_data = ws_b.send_json.call_args[0][0]
        assert sent_data["type"] == "replay"
        assert len(sent_data["events"]) == 5

    @pytest.mark.asyncio
    async def test_empty_replay_buffer_not_sent_on_connect(self):
        """No replay message sent when buffer is empty."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws)
        # No replay buffer content, so send_json should not be called
        ws.send_json.assert_not_called()


class TestConnectionLimit:
    """Test connection limit for DoS prevention (T-14-08)."""

    @pytest.mark.asyncio
    async def test_connection_limit_rejects_excess(self):
        """Connection limit prevents too many concurrent connections."""
        manager = ConnectionManager()
        # Fill up to MAX_CONNECTIONS
        for i in range(manager.MAX_CONNECTIONS):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await manager.connect(ws)

        # 11th connection should be rejected
        ws_extra = AsyncMock()
        ws_extra.close = AsyncMock()
        accepted = await manager.connect(ws_extra)
        assert accepted is False
        ws_extra.close.assert_called_once()
        assert ws_extra not in manager.active_connections

    @pytest.mark.asyncio
    async def test_connect_returns_true_for_accepted(self):
        """connect() returns True when connection is accepted."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        accepted = await manager.connect(ws)
        assert accepted is True

    @pytest.mark.asyncio
    async def test_connect_returns_false_for_rejected(self):
        """connect() returns False when connection is rejected."""
        manager = ConnectionManager()
        # Fill to capacity
        for i in range(manager.MAX_CONNECTIONS):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await manager.connect(ws)

        ws_extra = AsyncMock()
        ws_extra.close = AsyncMock()
        accepted = await manager.connect(ws_extra)
        assert accepted is False


class TestFullLifecycle:
    """Test full WS lifecycle: connect → replay → heartbeat → broadcast → disconnect."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Full lifecycle: connect → broadcast → record_pong → disconnect."""
        manager = ConnectionManager()

        # 1. Connect
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        accepted = await manager.connect(ws)
        assert accepted is True
        assert ws in manager.active_connections

        # 2. Broadcast
        event = {"type": "scene_start", "data": {"tool": "start_drama"}}
        await manager.broadcast(event)
        assert len(manager.replay_buffer) == 1

        # 3. Record pong
        manager.record_pong(ws)
        assert not manager.is_pong_expired(ws)

        # 4. Disconnect
        manager.disconnect(ws)
        assert ws not in manager.active_connections
        assert ws not in manager._last_pong


class TestSlowClientRemoval:
    """Test slow/disconnected clients are removed during broadcast."""

    @pytest.mark.asyncio
    async def test_slow_client_removed_during_broadcast(self):
        """Slow client is removed during broadcast (5s timeout)."""
        manager = ConnectionManager()
        ws_ok = AsyncMock()
        ws_slow = AsyncMock()
        ws_slow.send_json = AsyncMock(side_effect=Exception("timeout"))

        manager.active_connections.add(ws_ok)
        manager.active_connections.add(ws_slow)
        manager._last_pong[ws_ok] = time.monotonic()
        manager._last_pong[ws_slow] = time.monotonic()

        event = {"type": "scene_start", "data": {}}
        await manager.broadcast(event)

        assert ws_ok in manager.active_connections
        assert ws_slow not in manager.active_connections
        # _last_pong for slow client should also be cleaned up
        assert ws_slow not in manager._last_pong

    @pytest.mark.asyncio
    async def test_broadcast_appends_to_replay_before_sending(self):
        """Broadcast appends to replay buffer before sending to clients."""
        manager = ConnectionManager()
        ws = AsyncMock()
        manager.active_connections.add(ws)

        event = {"type": "scene_start", "data": {}}

        # Verify replay_buffer has the event after broadcast
        await manager.broadcast(event)
        assert list(manager.replay_buffer) == [event]
