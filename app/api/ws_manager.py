"""WebSocket connection manager for the Drama API.

Manages active WS connections, event broadcasting, and replay buffer.
D-13: Uses set[WebSocket] for connection pool management.
D-08: Global shared deque(maxlen=100) as replay buffer.
D-14: Application-level heartbeat with 15s ping, 30s timeout.
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

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
                    logger.warning(
                        "Heartbeat timeout: closing WS connection (last_pong=%.1fs ago, active=%d)",
                        time.monotonic() - self._last_pong.get(websocket, 0),
                        len(self.active_connections),
                    )
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
                    logger.info("Heartbeat ping failed: connection already broken, disconnecting (active=%d)",
                                len(self.active_connections))
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

        ★ WS 去重：ADK 可能对同一工具调用发出重复的 function_response 事件，
        REST 层在 runner_utils.py 中有去重，但 WS 通道的 event_callback 在去重之前
        被调用。因此需要在此处对内容型事件（dialogue/narration/actor_chime_in）
        进行去重，防止客户端创建重复气泡。
        """
        from app.api.event_mapper import map_runner_event

        # ★ WS 去重：滑动窗口，记录最近推送的内容型事件摘要
        # key = (event_type, content_fingerprint), 防止同一段文本被推送两次
        _seen_content_keys: dict[tuple[str, str], float] = {}
        _DEDUP_WINDOW = 10.0  # 10秒内的重复事件视为去重对象
        # 这些事件类型包含实际文本内容，客户端会创建气泡，需要去重
        _CONTENT_EVENT_TYPES = {"dialogue", "narration", "actor_chime_in", "end_narration"}

        async def _callback(event) -> None:
            # Only broadcast if there are active WS connections
            if not self.active_connections:
                return

            import time as _time
            now = _time.monotonic()

            ws_events = map_runner_event(event)
            for ws_event in ws_events:
                event_type = ws_event.get("type", "")
                data = ws_event.get("data", {})

                # ★ 内容型事件去重：基于 (type, text, actor_name) 指纹
                if event_type in _CONTENT_EVENT_TYPES:
                    text = str(data.get("text", data.get("message", "")))[:100]
                    actor = data.get("actor_name", data.get("sender_name", ""))
                    dedup_key = (event_type, f"{actor}:{text}")

                    # 清理过期的去重记录
                    expired = [k for k, t in _seen_content_keys.items() if now - t > _DEDUP_WINDOW]
                    for k in expired:
                        del _seen_content_keys[k]

                    if dedup_key in _seen_content_keys:
                        # 跳过重复内容事件
                        continue
                    _seen_content_keys[dedup_key] = now

                # D-16: flush state before push
                if flush_fn:
                    try:
                        flush_fn()
                    except Exception:
                        pass
                await self.broadcast(ws_event)

        return _callback
