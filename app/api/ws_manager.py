"""WebSocket connection manager for the Drama API.

Manages active WS connections, event broadcasting, and replay buffer.
D-13: Uses set[WebSocket] for connection pool management.
D-08: Global shared deque(maxlen=100) as replay buffer.
D-14: Application-level heartbeat with 15s ping, 30s timeout.
"""

import asyncio
import time
from collections import deque
from datetime import datetime

from fastapi import WebSocket

from app.api.models import WsEvent

# T-14-01: Maximum concurrent WebSocket connections
MAX_CONNECTIONS = 10


class ConnectionManager:
    """Manages WebSocket connections and event broadcasting."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()  # D-13
        self.replay_buffer: deque[dict] = deque(maxlen=100)  # D-08
        self._last_pong: dict[WebSocket, float] = {}  # websocket → timestamp
        self.HEARTBEAT_INTERVAL = 15  # D-14: 15s ping interval
        self.HEARTBEAT_TIMEOUT = 30   # D-14: 30s pong timeout
        self.MAX_CONNECTIONS = 10     # Connection limit for DoS prevention

    async def connect(self, websocket: WebSocket) -> bool:
        """Accept WS connection, add to pool, send replay buffer (D-09).

        T-14-01: Reject connection if MAX_CONNECTIONS exceeded.
        Returns True if connection accepted, False if rejected.
        """
        if len(self.active_connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Max connections reached")
            return False
        await websocket.accept()
        self.active_connections.add(websocket)
        self._last_pong[websocket] = time.monotonic()  # Initialize pong timestamp
        # D-09: Send replay buffer on connect
        if self.replay_buffer:
            await websocket.send_json({
                "type": "replay",
                "events": list(self.replay_buffer),
            })
        return True

    def disconnect(self, websocket: WebSocket):
        """Remove WS connection from pool."""
        self.active_connections.discard(websocket)
        self._last_pong.pop(websocket, None)

    def record_pong(self, websocket: WebSocket):
        """Record pong response from client for heartbeat tracking (D-14)."""
        self._last_pong[websocket] = time.monotonic()

    def is_pong_expired(self, websocket: WebSocket) -> bool:
        """Check if client's last pong exceeds heartbeat timeout (D-14)."""
        last = self._last_pong.get(websocket)
        if last is None:
            return True
        return (time.monotonic() - last) > self.HEARTBEAT_TIMEOUT

    async def heartbeat(self, websocket: WebSocket):
        """Application-level heartbeat loop (D-14).

        Sends ping every 15s, checks for 30s pong timeout.
        On timeout, closes the connection and removes from pool.

        This runs as an asyncio.Task alongside the receive loop.
        """
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                # Check timeout before sending ping
                if self.is_pong_expired(websocket):
                    # D-14: 30s timeout — close connection
                    try:
                        await websocket.close(code=1000, reason="Heartbeat timeout")
                    except Exception:
                        pass
                    self.disconnect(websocket)
                    break
                # Send application-level ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    # Connection already broken
                    self.disconnect(websocket)
                    break
        except asyncio.CancelledError:
            # Task cancelled — normal disconnect, just exit
            pass

    async def broadcast(self, event: dict):
        """Broadcast event to all connections and append to replay buffer.

        T-14-04: asyncio.wait_for with 5s timeout per send; remove slow clients.
        """
        self.replay_buffer.append(event)
        disconnected: set[WebSocket] = set()
        for connection in self.active_connections:
            try:
                await asyncio.wait_for(connection.send_json(event), timeout=5.0)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.active_connections.discard(conn)
            self._last_pong.pop(conn, None)

    def create_broadcast_callback(self, flush_fn=None):
        """Create an event_callback for run_command_and_collect (D-02).

        Args:
            flush_fn: Optional callable to flush state before push (D-16).
                Should be app.state.flush_state_sync.

        Returns:
            Async callback that maps Runner events to WS events and broadcasts.
        """
        from app.api.event_mapper import map_runner_event

        async def _callback(event) -> None:
            # Only broadcast if there are active WS connections
            if not self.active_connections:
                return
            ws_events = map_runner_event(event)
            for ws_event in ws_events:
                # D-16: flush state before push
                if flush_fn:
                    try:
                        flush_fn()
                    except Exception:
                        pass
                await self.broadcast(ws_event)

        return _callback
