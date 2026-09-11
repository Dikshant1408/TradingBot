"""
WebSocket Manager for Real-Time Terminal Telemetry.
Broadcasts signals, orders, fills, risk halts, and PnL updates to connected browser clients.
"""
import asyncio
import json
import logging
from typing import List
from fastapi import WebSocket, WebSocketDisconnect
from app.core.event_bus import event_bus, EventType
from app.core.state import state_manager

logger = logging.getLogger("trading_bot.api.websocket")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send immediate initial state
        initial_payload = {
            "type": "INITIAL_STATE",
            "state": state_manager.state.model_dump()
        }
        await websocket.send_text(json.dumps(initial_payload, default=str))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message, default=str)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


# Register event bus listeners to broadcast telemetry over WebSocket
def setup_websocket_event_forwarding():
    async def forward_event(event_type: str, data: dict):
        await manager.broadcast({
            "type": event_type,
            "data": data,
            "state": state_manager.state.model_dump()
        })

    for evt in EventType:
        event_bus.subscribe(evt.value, lambda d, e=evt.value: asyncio.create_task(forward_event(e, d)))
