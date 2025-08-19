# backend/services/live_ws.py
from typing import Dict, Any, List
from starlette.websockets import WebSocket
import asyncio

class WebSocketHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: Dict[str, Any]):
        dead = []
        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

hub = WebSocketHub()

class WebSocketSink:
    """Sink API-kompatibel; nutzt hub.broadcast via Thread→asyncio bridge."""
    def __init__(self):
        import asyncio
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None

    def write(self, session_id: int, payload: Dict[str, Any]) -> None:
        msg = {"session_id": session_id, **payload}
        coro = hub.broadcast(msg)
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            # Not ideal, aber reicht im MVP
            asyncio.get_event_loop().run_until_complete(coro)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass
