import uuid
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.websockets.manager import ws_manager
from app.pipeline.orchestrator import run_full_pipeline

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
            # Keep connection open, wait for client messages if any
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)

@app.post("/api/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), client_id: str = ""):
    """
    Accepts the file upload and immediately returns a 202 Accepted.
    The heavy lifting is pushed to a background task that communicates via WS.
    """
    if not client_id:
        client_id = str(uuid.uuid4())
        
    # Kick off the pipeline in the background
    background_tasks.add_task(run_full_pipeline, file, client_id)
    
    return {"message": "Processing started", "client_id": client_id}