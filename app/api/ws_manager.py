"""WebSocket connection manager for the Drama API.

Manages active WS connections, event broadcasting, and replay buffer.
D-13: Uses set[WebSocket] for connection pool management.
D-08: Global shared deque(maxlen=100) as replay buffer.
"""

import asyncio
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

    async def connect(self, websocket: WebSocket):
        """Accept WS connection, add to pool, send replay buffer (D-09).

        T-14-01: Reject connection if MAX_CONNECTIONS exceeded.
        """
        if len(self.active_connections) >= MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Max connections reached")
            return
        await websocket.accept()
        self.active_connections.add(websocket)
        # D-09: Send replay buffer on connect
        if self.replay_buffer:
            await websocket.send_json({
                "type": "replay",
                "events": list(self.replay_buffer),
            })

    def disconnect(self, websocket: WebSocket):
        """Remove WS connection from pool."""
        self.active_connections.discard(websocket)

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
