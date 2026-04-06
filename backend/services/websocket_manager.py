"""WebSocket connection manager for real-time event broadcasting."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

from backend.models.events import WSEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("WS client connected: %s (total: %d)", client_id, len(self.active_connections))

    def disconnect(self, client_id: str) -> None:
        self.active_connections.pop(client_id, None)
        logger.info("WS client disconnected: %s (total: %d)", client_id, len(self.active_connections))

    async def broadcast(self, event: WSEvent) -> None:
        """Send an event to every connected client."""
        data = event.model_dump(mode="json")
        dead: list[str] = []
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(client_id)
        for cid in dead:
            self.disconnect(cid)

    async def send_personal(self, client_id: str, event: WSEvent) -> None:
        ws = self.active_connections.get(client_id)
        if ws is None:
            return
        try:
            await ws.send_json(event.model_dump(mode="json"))
        except Exception:
            self.disconnect(client_id)
