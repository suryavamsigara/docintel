from fastapi import FastAPI, UploadFile, File, HTTPException
from app.pipeline.stage1_ingestion import run_ingestion_stage

app = FastAPI(title="Document Intelligence Platform")

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Day 1 Endpoint: Uploads a document, identifies format, extracts text while 
    preserving structure, and returns the normalized data.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Run the Day 1 pipeline stage
    result = await run_ingestion_stage(file)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error_message"))
        
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)