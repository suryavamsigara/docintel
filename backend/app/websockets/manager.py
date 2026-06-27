import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Maps a unique client/job ID to an active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")

    async def emit_stage_update(self, client_id: str, stage: str, status: str, data: dict = None, error: str = None):
        """
        Emits a standardised JSON payload to the React frontend.
        status: "running" | "complete" | "error"
        """
        if client_id not in self.active_connections:
            return

        payload = {
            "stage": stage,
            "status": status,
        }
        if data is not None:
            payload["data"] = data
        if error is not None:
            payload["error"] = error

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to send WS message to {client_id}: {str(e)}")
            self.disconnect(client_id)

ws_manager = WebSocketManager()