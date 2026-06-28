import uuid
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from app.websockets.manager import ws_manager
from app.pipeline.orchestrator_mode_aware import run_full_pipeline

app = FastAPI(title="Contract Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    client_id: str = "",
    x_processing_mode: Literal["local", "llm"] = Header(default="local"),
):
    """
    Accepts the file upload and immediately returns a 202 Accepted.
    The heavy lifting is pushed to a background task that communicates via WS.

    Headers:
        X-Processing-Mode: local (default) | llm
    """
    if not client_id:
        client_id = str(uuid.uuid4())

    mode = x_processing_mode if x_processing_mode in ("local", "llm") else "local"
    background_tasks.add_task(run_full_pipeline, file, client_id, mode)

    return {"message": "Processing started", "client_id": client_id, "mode": mode}