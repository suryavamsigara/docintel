import uuid
import json
import hashlib
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks, Header, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from app.websockets.manager import ws_manager
from app.pipeline.orchestrator_mode_aware import run_full_pipeline
# FIX: Import get_client instead of the raw client
from app.db import init_db, get_client, generate_id
from app.pipeline.crm import sync_to_notion

app = FastAPI(title="Contract Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # This runs safely inside the event loop!
    await init_db()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    client = get_client()
    result = await client.execute("SELECT id, name, created_at FROM projects WHERE id = ?", [project_id])
    if not result.rows:
        raise HTTPException(status_code=404, detail="Project not found")
    
    row = result.rows[0]
    # FIX: Use bracket notation
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}

@app.post("/api/projects")
async def create_project(name: str = Form(...)):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Project name required")
    
    client = get_client()
    project_id = generate_id("proj")
    await client.execute("INSERT INTO projects (id, name) VALUES (?, ?)", [project_id, name])
    return {"id": project_id, "name": name, "docCount": 0}

@app.get("/api/projects/{project_id}/documents")
async def get_project_documents(project_id: str):
    client = get_client()
    
    # We use SELECT * to grab everything available without hardcoding columns that might be missing
    result = await client.execute(
        "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC", 
        [project_id]
    )
    
    docs = []
    for r in result.rows:
        # Safely attempt to read the CRM status; if the DB hasn't updated yet, default to "pending"
        try:
            crm_val = r["crm_status"]
        except KeyError:
            crm_val = "pending"
            
        docs.append({
            "id": r["id"], 
            "name": r["name"], 
            "status": r["status"], 
            "crm_status": crm_val,
            "created_at": r["created_at"]
        })
        
    return docs

@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    client = get_client()
    result = await client.execute(
        "SELECT id, name, status, file_url, analysis_data FROM documents WHERE id = ?", 
        [doc_id]
    )
    if not result.rows:
        raise HTTPException(status_code=404, detail="Document not found")
    
    row = result.rows[0]
    
    # Parse final analysis data if the document is already completed
    stages = None
    if row["analysis_data"]:
        try:
            stages = json.loads(row["analysis_data"])
        except:
            pass
            
    return {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "fileUrl": row["file_url"],
        "stages": stages
    }

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    client_id: str = Form(None), 
    x_processing_mode: Literal["local", "llm"] = Header(default="local"),
):
    if not client_id: client_id = generate_id("doc")
    
    # Read file to calculate hash, then seek back to 0 so the pipeline can read it
    file_bytes = await file.read()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    await file.seek(0)
    
    client = get_client()
    await client.execute(
        "INSERT INTO documents (id, project_id, name, status, content_hash, crm_status) VALUES (?, ?, ?, ?, ?, ?)",
        [client_id, project_id, file.filename, "processing", content_hash, "pending"]
    )

    mode = x_processing_mode if x_processing_mode in ("local", "llm") else "local"
    background_tasks.add_task(run_full_pipeline, file, client_id, project_id, mode)

    return {"message": "Processing started", "doc_id": client_id}


@app.get("/api/projects")
async def get_projects():
    client = get_client()
    result = await client.execute("SELECT id, name, created_at FROM projects ORDER BY created_at DESC")
    counts = await client.execute("SELECT project_id, COUNT(*) as count FROM documents GROUP BY project_id")
    
    # FIX: Use bracket notation for the counts
    count_map = {row["project_id"]: row["count"] for row in counts.rows}
    
    projects = []
    for row in result.rows:
        projects.append({
            # FIX: Use bracket notation for the rows
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "docCount": count_map.get(row["id"], 0)
        })
    return projects

@app.get("/api/projects/{project_id}/contradictions")
async def get_project_contradictions(project_id: str):
    client = get_client()
    result = await client.execute(
        "SELECT analysis_data FROM documents WHERE project_id = ? AND status = 'completed'",
        [project_id]
    )
    all_contradictions = []
    seen_desc = set()
    
    for row in result.rows:
        if not row["analysis_data"]: continue
        try:
            data = json.loads(row["analysis_data"])
            cross = data.get("cross_document", {}).get("data", {})
            if cross and cross.get("contradictions"):
                for c in cross["contradictions"]:
                    if c["description"] not in seen_desc:
                        all_contradictions.append(c)
                        seen_desc.add(c["description"])
        except:
            pass
            
    return all_contradictions

@app.post("/api/documents/{doc_id}/sync")
async def trigger_crm_sync(doc_id: str):
    result = await sync_to_notion(doc_id)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return {"message": "Sync successful", "detail": result.get("detail")}

@app.get("/api/health")
async def health_check():
    """Health check endpoint for deployment platforms (e.g., Railway)."""
    try:
        client = get_client()
        await client.execute("SELECT 1")
        db_status = "connected"
        is_healthy = True
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
        is_healthy = False

    return {
        "status": "ok" if is_healthy else "error",
        "database": db_status,
    }