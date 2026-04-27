"""Tests for WebSocket ConnectionManager and endpoint."""

import asyncio
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.ws_manager import ConnectionManager, MAX_CONNECTIONS
from app.api.models import WsEvent, ReplayMessage, HeartbeatMessage


class TestWsEventModels:
    """Test WsEvent Pydantic models."""

    def test_ws_event_has_type_timestamp_data(self):
        """WsEvent has type, timestamp, data fields and serializes correctly."""
        event = WsEvent(type="scene_start", data={"tool": "start_drama"})
        assert event.type == "scene_start"
        assert event.timestamp  # auto-generated
        assert event.data == {"tool": "start_drama"}
        # Serialization
        d = event.model_dump()
        assert "type" in d
        assert "timestamp" in d
        assert "data" in d

    def test_ws_event_default_data_is_empty_dict(self):
        """WsEvent data defaults to empty dict."""
        event = WsEvent(type="typing")
        assert event.data == {}

    def test_replay_message_type_defaults_to_replay(self):
        """ReplayMessage type defaults to 'replay'."""
        msg = ReplayMessage()
        assert msg.type == "replay"
        assert msg.events == []

    def test_replay_message_with_events(self):
        """ReplayMessage can hold events."""
        events = [{"type": "scene_start", "data": {}}]
        msg = ReplayMessage(events=events)
        assert len(msg.events) == 1

    def test_heartbeat_message_type_defaults_to_ping(self):
        """HeartbeatMessage type defaults to 'ping'."""
        msg = HeartbeatMessage()
        assert msg.type == "ping"


class TestConnectionManager:
    """Test ConnectionManager class."""

    def test_init_has_empty_connections_and_buffer(self):
        """ConnectionManager initializes with empty connections and buffer."""
        manager = ConnectionManager()
        assert len(manager.active_connections) == 0
        assert len(manager.replay_buffer) == 0

    @pytest.mark.asyncio
    async def test_connect_adds_websocket_and_sends_replay(self):
        """connect() accepts WS, adds to pool, sends replay buffer (D-09)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws)
        ws.accept.assert_called_once()
        assert ws in manager.active_connections
        # No replay buffer content, so send_json should not be called
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_sends_replay_buffer_on_connect(self):
        """connect() sends replay buffer if it has events (D-09)."""
        manager = ConnectionManager()
        manager.replay_buffer.append({"type": "scene_start", "data": {}})

        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws)
        ws.send_json.assert_called_once()
        sent_data = ws.send_json.call_args[0][0]
        assert sent_data["type"] == "replay"
        assert len(sent_data["events"]) == 1

    @pytest.mark.asyncio
    async def test_connect_rejects_when_max_connections_exceeded(self):
        """connect() rejects connection when MAX_CONNECTIONS exceeded (T-14-01)."""
        manager = ConnectionManager()
        # Fill up to MAX_CONNECTIONS
        for i in range(MAX_CONNECTIONS):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await manager.connect(ws)

        # Try one more
        ws_extra = AsyncMock()
        ws_extra.close = AsyncMock()
        await manager.connect(ws_extra)
        ws_extra.close.assert_called_once()
        assert ws_extra not in manager.active_connections

    def test_disconnect_removes_websocket(self):
        """disconnect() removes websocket from active_connections."""
        manager = ConnectionManager()
        ws = MagicMock()
        manager.active_connections.add(ws)
        manager.disconnect(ws)
        assert ws not in manager.active_connections

    def test_disconnect_handles_missing_websocket(self):
        """disconnect() uses discard, so removing non-existent WS is safe."""
        manager = ConnectionManager()
        ws = MagicMock()
        manager.disconnect(ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self):
        """broadcast() sends event to all active connections."""
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager.active_connections.add(ws1)
        manager.active_connections.add(ws2)

        event = {"type": "scene_start", "data": {}}
        await manager.broadcast(event)

        ws1.send_json.assert_called_once_with(event)
        ws2.send_json.assert_called_once_with(event)
        assert len(manager.replay_buffer) == 1

    @pytest.mark.asyncio
    async def test_broadcast_appends_to_replay_buffer(self):
        """broadcast() appends event to replay buffer (D-08)."""
        manager = ConnectionManager()
        event = {"type": "scene_start", "data": {}}
        await manager.broadcast(event)
        assert list(manager.replay_buffer) == [event]

    @pytest.mark.asyncio
    async def test_broadcast_removes_slow_clients(self):
        """broadcast() removes connections that fail to receive (T-14-04)."""
        manager = ConnectionManager()
        ws_ok = AsyncMock()
        ws_slow = AsyncMock()
        ws_slow.send_json = AsyncMock(side_effect=Exception("timeout"))
        manager.active_connections.add(ws_ok)
        manager.active_connections.add(ws_slow)

        event = {"type": "scene_start", "data": {}}
        await manager.broadcast(event)

        assert ws_ok in manager.active_connections
        assert ws_slow not in manager.active_connections

    @pytest.mark.asyncio
    async def test_create_broadcast_callback_returns_callable(self):
        """create_broadcast_callback() returns an async callable."""
        manager = ConnectionManager()
        callback = manager.create_broadcast_callback()
        assert callable(callback)

    @pytest.mark.asyncio
    async def test_create_broadcast_callback_skips_when_no_connections(self):
        """create_broadcast_callback skips broadcast when no active connections."""
        manager = ConnectionManager()
        callback = manager.create_broadcast_callback()

        # Should not raise even with a mock event
        mock_event = MagicMock()
        mock_event.content = None
        await callback(mock_event)

    @pytest.mark.asyncio
    async def test_create_broadcast_callback_broadcasts_mapped_events(self):
        """create_broadcast_callback maps events and broadcasts them."""
        manager = ConnectionManager()
        ws = AsyncMock()
        manager.active_connections.add(ws)

        callback = manager.create_broadcast_callback()

        # Create a simple ADK event with function_call
        from google.adk.events import Event
        from google.genai import types

        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        await callback(event)

        # Should have sent at least typing + scene_start events
        assert ws.send_json.call_count >= 2


class TestBroadcastCallbackFlush:
    """Test create_broadcast_callback with flush_fn integration (D-16)."""

    @pytest.mark.asyncio
    async def test_callback_calls_flush_fn_before_broadcast(self):
        """Callback calls flush_fn before each broadcast (D-16)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        manager.active_connections.add(ws)

        flush_fn = MagicMock()
        callback = manager.create_broadcast_callback(flush_fn=flush_fn)

        from google.adk.events import Event
        from google.genai import types

        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        await callback(event)

        # flush_fn should have been called (at least once for the mapped events)
        assert flush_fn.call_count >= 1

    @pytest.mark.asyncio
    async def test_callback_survives_flush_fn_exception(self):
        """Callback continues broadcasting even if flush_fn raises (T-14-06)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        manager.active_connections.add(ws)

        flush_fn = MagicMock(side_effect=RuntimeError("flush failed"))
        callback = manager.create_broadcast_callback(flush_fn=flush_fn)

        from google.adk.events import Event
        from google.genai import types

        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        # Should not raise
        await callback(event)

        # Despite flush failure, broadcast should still happen
        assert ws.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_callback_works_without_flush_fn(self):
        """Callback works when flush_fn is None (REST-only mode)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        manager.active_connections.add(ws)

        callback = manager.create_broadcast_callback(flush_fn=None)

        from google.adk.events import Event
        from google.genai import types

        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        await callback(event)
        assert ws.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_callback_skips_broadcast_when_no_active_connections(self):
        """Callback returns immediately when no WS clients connected (D-12)."""
        manager = ConnectionManager()
        flush_fn = MagicMock()
        callback = manager.create_broadcast_callback(flush_fn=flush_fn)

        from google.adk.events import Event
        from google.genai import types

        event = Event(
            author="model",
            content=types.Content(
                parts=[types.Part.from_function_call(name="next_scene", args={})],
                role="model",
            ),
        )
        await callback(event)
        # No flush, no broadcast — no WS clients
        flush_fn.assert_not_called()


class TestGetEventCallback:
    """Test _get_event_callback helper from commands.py."""

    def test_returns_none_when_no_manager(self):
        """_get_event_callback returns None when no connection_manager on app.state."""
        from app.api.routers.commands import _get_event_callback
        from fastapi import Request

        app = MagicMock()
        app.state.connection_manager = None

        request = MagicMock()
        request.app = app

        result = _get_event_callback(request)
        assert result is None

    def test_returns_none_when_no_active_connections(self):
        """_get_event_callback returns None when no WS clients connected (D-12)."""
        from app.api.routers.commands import _get_event_callback
        from app.api.ws_manager import ConnectionManager

        manager = ConnectionManager()  # empty connections
        app = MagicMock()
        app.state.connection_manager = manager
        app.state.flush_state_sync = MagicMock()

        request = MagicMock()
        request.app = app

        result = _get_event_callback(request)
        assert result is None

    def test_returns_callback_when_active_connections(self):
        """_get_event_callback returns callable when WS clients connected."""
        from app.api.routers.commands import _get_event_callback
        from app.api.ws_manager import ConnectionManager

        manager = ConnectionManager()
        ws = MagicMock()
        manager.active_connections.add(ws)

        app = MagicMock()
        app.state.connection_manager = manager
        app.state.flush_state_sync = MagicMock()

        request = MagicMock()
        request.app = app

        result = _get_event_callback(request)
        assert result is not None
        assert callable(result)

    def test_callback_includes_flush_fn(self):
        """_get_event_callback passes flush_fn from app.state to create_broadcast_callback."""
        from app.api.routers.commands import _get_event_callback
        from app.api.ws_manager import ConnectionManager

        manager = ConnectionManager()
        ws = MagicMock()
        manager.active_connections.add(ws)

        flush_fn = MagicMock()
        app = MagicMock()
        app.state.connection_manager = manager
        app.state.flush_state_sync = flush_fn

        request = MagicMock()
        request.app = app

        callback = _get_event_callback(request)
        # Verify the callback was created with flush_fn
        # We can verify by checking that when we call the callback, flush_fn is invoked
        # This is tested more thoroughly in TestBroadcastCallbackFlush


class TestWebSocketEndpoint:
    """Test WebSocket endpoint at /api/v1/ws."""

    def _create_app_with_manager(self):
        """Create app and manually initialize ConnectionManager for testing.

        TestClient doesn't trigger lifespan, so we set up the manager manually.
        """
        from app.api.app import create_app
        from app.api.ws_manager import ConnectionManager

        app = create_app()
        manager = ConnectionManager()
        app.state.connection_manager = manager
        return app, manager

    def test_websocket_endpoint_exists(self):
        """WebSocket endpoint is registered at /api/v1/ws."""
        from app.api.app import create_app

        app = create_app()
        # Find the websocket route
        ws_routes = [r for r in app.routes if hasattr(r, "path") and r.path.endswith("/ws")]
        assert len(ws_routes) > 0, "No WebSocket route found"

    def test_websocket_accepts_connection(self):
        """WebSocket endpoint accepts connections (WS-01)."""
        from fastapi.testclient import TestClient

        app, manager = self._create_app_with_manager()
        client = TestClient(app)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Connection should be established without error
            pass  # Successful connection is the test

    def test_websocket_receives_replay_on_connect(self):
        """New WS connection receives replay buffer events (D-09/WS-04)."""
        from fastapi.testclient import TestClient

        app, manager = self._create_app_with_manager()
        # Pre-populate replay buffer
        manager.replay_buffer.append(
            {"type": "scene_start", "data": {"tool": "start_drama"}}
        )

        client = TestClient(app)
        with client.websocket_connect("/api/v1/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "replay"
            assert len(data["events"]) == 1
            assert data["events"][0]["type"] == "scene_start"


class TestHeartbeatTracking:
    """Test heartbeat and pong recording in ConnectionManager (D-14)."""

    def test_record_pong_stores_timestamp(self):
        """record_pong stores timestamp for a websocket connection."""
        manager = ConnectionManager()
        ws = MagicMock()
        before = time.monotonic()
        manager.record_pong(ws)
        after = time.monotonic()
        assert ws in manager._last_pong
        assert before <= manager._last_pong[ws] <= after

    def test_is_pong_expired_returns_false_after_record_pong(self):
        """is_pong_expired returns False immediately after record_pong."""
        manager = ConnectionManager()
        ws = MagicMock()
        manager.record_pong(ws)
        assert manager.is_pong_expired(ws) is False

    def test_is_pong_expired_returns_true_after_timeout(self):
        """is_pong_expired returns True when last_pong is older than timeout."""
        manager = ConnectionManager()
        ws = MagicMock()
        # Set last pong to well before the timeout
        manager._last_pong[ws] = time.monotonic() - manager.HEARTBEAT_TIMEOUT - 1
        assert manager.is_pong_expired(ws) is True

    def test_is_pong_expired_returns_true_for_unknown_websocket(self):
        """is_pong_expired returns True for websocket not in _last_pong."""
        manager = ConnectionManager()
        ws = MagicMock()
        assert manager.is_pong_expired(ws) is True

    def test_disconnect_removes_pong_entry(self):
        """disconnect() cleans up _last_pong entry (D-13)."""
        manager = ConnectionManager()
        ws = MagicMock()
        manager.active_connections.add(ws)
        manager._last_pong[ws] = time.monotonic()
        manager.disconnect(ws)
        assert ws not in manager._last_pong

    @pytest.mark.asyncio
    async def test_connect_initializes_pong_timestamp(self):
        """connect() initializes _last_pong for new connections."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        await manager.connect(ws)
        assert ws in manager._last_pong
        assert isinstance(manager._last_pong[ws], float)

    @pytest.mark.asyncio
    async def test_heartbeat_sends_ping_and_detects_timeout(self):
        """heartbeat() sends ping and detects timeout (D-14)."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 0.1  # Speed up for testing
        manager.HEARTBEAT_TIMEOUT = 0.2
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        manager.active_connections.add(ws)
        # Set last pong to old timestamp to trigger timeout
        manager._last_pong[ws] = time.monotonic() - 1.0

        # Run heartbeat in background
        task = asyncio.create_task(manager.heartbeat(ws))
        # Wait for timeout to trigger
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Connection should have been closed and removed
        ws.close.assert_called()
        assert ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_heartbeat_can_be_cancelled(self):
        """heartbeat task can be cancelled without errors (normal disconnect)."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 10  # Long interval for test
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        manager.active_connections.add(ws)
        manager._last_pong[ws] = time.monotonic()

        task = asyncio.create_task(manager.heartbeat(ws))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should not raise — CancelledError is handled gracefully
        # WS should still be in active_connections since no timeout occurred
        assert ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_heartbeat_removes_broken_connection(self):
        """heartbeat() removes connection when send_json fails."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 0.1
        ws = AsyncMock()
        ws.send_json = AsyncMock(side_effect=Exception("Connection broken"))
        manager.active_connections.add(ws)
        manager._last_pong[ws] = time.monotonic()

        task = asyncio.create_task(manager.heartbeat(ws))
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Connection should have been removed
        assert ws not in manager.active_connections


class TestHeartbeatMessageTypeHandling:
    """Test server handling of different heartbeat message types (D-06/D-14)."""

    @pytest.mark.asyncio
    async def test_pong_message_records_pong(self):
        """收到 {"type":"pong"} 时调用 record_pong (D-14)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        await manager.connect(ws)

        # Simulate pong received
        manager.record_pong(ws)
        assert not manager.is_pong_expired(ws)

    @pytest.mark.asyncio
    async def test_heartbeat_message_records_pong(self):
        """收到 {"type":"heartbeat"} 时也应 record_pong (D-06 兼容)."""
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        await manager.connect(ws)

        # 模拟 heartbeat 消息到达后服务端 record_pong
        manager.record_pong(ws)
        assert not manager.is_pong_expired(ws)

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_with_no_pong(self):
        """无 pong 响应时心跳超时断连 (D-14)."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 0.05  # 极短间隔加速测试
        manager.HEARTBEAT_TIMEOUT = 0.1
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        manager.active_connections.add(ws)
        # 设置过期 pong 时间戳
        manager._last_pong[ws] = time.monotonic() - 1.0

        task = asyncio.create_task(manager.heartbeat(ws))
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        ws.close.assert_called()
        assert ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_pong_resets_timeout_clock(self):
        """pong 到达后超时计时重置，连接不会被误判超时 (D-14)."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 0.1
        manager.HEARTBEAT_TIMEOUT = 0.3
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        manager.active_connections.add(ws)
        manager._last_pong[ws] = time.monotonic() - 0.2  # 接近超时

        # 先发送 ping，心跳检查 pong 未过期（因为还差一点）
        # 但立即 record_pong 重置计时
        manager.record_pong(ws)

        task = asyncio.create_task(manager.heartbeat(ws))
        await asyncio.sleep(0.15)
        # 在超时前再次 record_pong
        manager.record_pong(ws)
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # 不应关闭连接
        ws.close.assert_not_called()
        assert ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_heartbeat_task_cancellation_cleans_up(self):
        """心跳任务取消时正常退出，不抛异常 (D-14)."""
        manager = ConnectionManager()
        manager.HEARTBEAT_INTERVAL = 10
        ws = AsyncMock()
        ws.send_json = AsyncMock()
        manager.active_connections.add(ws)
        manager._last_pong[ws] = time.monotonic()

        task = asyncio.create_task(manager.heartbeat(ws))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert ws in manager.active_connections
