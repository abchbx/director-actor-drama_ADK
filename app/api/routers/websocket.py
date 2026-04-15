"""WebSocket endpoint for real-time scene event push.

WS-01: Endpoint at /api/v1/ws receives real-time scene events.
WS-05: Connection lifecycle: connect → replay → heartbeat → live push → disconnect.
D-11: WS is pure receiver, does NOT hold Runner Lock.
D-14: Heartbeat 15s ping/pong, 30s timeout.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time scene event push.

    Flow (D-09/D-10/D-14):
    1. Accept connection → ConnectionManager sends replay buffer
    2. Start heartbeat task (15s ping, 30s timeout)
    3. Receive loop: handle pong responses from client
    4. On disconnect: cancel heartbeat + remove from pool
    """
    manager = websocket.app.state.connection_manager
    accepted = await manager.connect(websocket)
    if not accepted:
        return  # Connection rejected — limit exceeded

    # D-14: Start heartbeat as background task
    heartbeat_task = asyncio.create_task(manager.heartbeat(websocket))

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "pong":
                manager.record_pong(websocket)
            # Ignore unknown message types — WS is pure receiver (D-11)
    except WebSocketDisconnect:
        pass
    except Exception:
        # Unexpected error — still clean up
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket)
