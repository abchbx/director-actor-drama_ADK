"""WebSocket endpoint for real-time scene event push.

WS-01: Endpoint at /api/v1/ws receives real-time scene events.
WS-05: Connection lifecycle: connect → replay → heartbeat → live push → disconnect.
D-11: WS is pure receiver, does NOT hold Runner Lock.
D-14: Heartbeat 15s ping/pong, 30s timeout.
AUTH-03: Token validation via ?token=xxx query parameter before accept.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_ws_token(websocket: WebSocket) -> None:
    """Validate WebSocket token from query parameter (AUTH-03, D-09~D-11).

    D-09: Token via ?token=xxx query parameter.
    D-10: Validate BEFORE accept — invalid raises WebSocketException(4001).
    D-11: Dev mode (auth_enabled=False) bypasses validation.

    Raises:
        WebSocketException: status_code=4001 if token invalid when auth enabled.
    """
    auth_enabled = getattr(websocket.app.state, "auth_enabled", False)

    # D-11: Dev mode bypass
    if not auth_enabled:
        logger.debug("WS auth bypass: no API_TOKEN configured (dev mode)")
        return

    # D-09: Extract token from query parameter
    token = websocket.query_params.get("token")

    if not token:
        logger.warning("WS auth failed: missing token parameter")
        raise WebSocketException(code=4001, reason="Missing token")

    # Validate against app.state.api_token (D-03)
    api_token = getattr(websocket.app.state, "api_token", None)
    if token != api_token:
        logger.warning("WS auth failed: invalid token")
        raise WebSocketException(code=4001, reason="Invalid token")

    logger.debug("WS auth succeeded: valid token")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time scene event push.

    Flow (AUTH-03, D-09/D-10/D-11/D-14):
    1. Validate token from ?token=xxx query parameter (before accept)
    2. Accept connection → ConnectionManager sends replay buffer
    3. Start heartbeat task (15s ping, 30s timeout)
    4. Receive loop: handle pong responses from client
    5. On disconnect: cancel heartbeat + remove from pool
    """
    # AUTH-03/D-10: Validate token BEFORE accept
    _validate_ws_token(websocket)

    manager = websocket.app.state.connection_manager
    try:
        accepted = await manager.connect(websocket)
    except Exception as e:
        logger.error("WS accept/replay failed: %s", e, exc_info=True)
        return
    if not accepted:
        return  # Connection rejected — limit exceeded

    # D-14: Start heartbeat as background task
    heartbeat_task = asyncio.create_task(manager.heartbeat(websocket))

    try:
        # ★ 修复：使用 while True 保持连接，配合心跳检测确保连接活性
        # 当心跳超时时循环也会退出，确保异常情况下的资源清理
        while True:
            try:
                # ★ 修复：添加 60s 接收超时，防止永远阻塞
                # 结合心跳机制，客户端应该在 30s 内响应 ping
                # 如果 60s 内没有任何消息（包括 pong），说明连接已死
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                # 60s 无消息，检查是否超时（心跳 task 会处理 ping/pong）
                # 此处仅记录日志，不主动断开
                logger.debug("WS receive timeout (60s no message), waiting...")
                continue
            except (ValueError, KeyError) as e:
                # ★ 修复：非 JSON 消息（如二进制帧、无效 JSON）不应导致连接断开
                # ValueError: JSON 解析失败
                # KeyError: receive_json() 收到二进制帧时 message["text"] 不存在
                # 继续循环等待下一条消息，而不是断开连接
                logger.warning("WS received non-JSON message, ignoring: %s", e)
                continue
            msg_type = data.get("type", "")
            if msg_type == "pong":
                manager.record_pong(websocket)
            # Ignore unknown message types — WS is pure receiver (D-11)
    except WebSocketDisconnect:
        logger.info("WS client disconnected normally")
    except Exception as e:
        # Unexpected error — still clean up
        logger.warning("WS receive loop error: %s", e, exc_info=True)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket)
