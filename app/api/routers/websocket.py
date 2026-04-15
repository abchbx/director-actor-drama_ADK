"""WebSocket endpoint for real-time scene event push.

WS-01: Endpoint at /api/v1/ws receives real-time scene events.
WS-05: Connection lifecycle: connect → replay → live push → disconnect.
D-11: WS is pure receiver, does NOT hold Runner Lock.
D-12: REST and WS coexist — REST sends commands, WS receives pushes.
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time scene event push.

    Flow (D-09/D-10):
    1. Accept connection → ConnectionManager sends replay buffer
    2. Enter receive loop: handle pong responses from client
    3. On disconnect: clean up from connection pool
    """
    manager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "pong":
                # Heartbeat response — detailed tracking in Plan 03
                pass
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
