# backend/routers/live.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.services.live_ws import hub

router = APIRouter()

@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, session_id: int = Query(...)):
    await hub.connect(ws)
    try:
        while True:
            # Optional: Pong/Ping lesen, falls das Frontend was sendet
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
