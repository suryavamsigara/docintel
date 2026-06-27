import asyncio
import logging
import traceback
from fastapi import UploadFile

from app.websockets.manager import ws_manager
from app.pipeline.ingestion import run_ingestion_stage
from app.pipeline.classification import run_classification_stage
from app.pipeline.extraction import run_extraction_stage

logger = logging.getLogger(__name__)

async def run_full_pipeline(file: UploadFile, client_id: str):
    try:
        # --- STAGE 1: INGESTION ---
        await ws_manager.emit_stage_update(client_id, "ingestion", "running", detail="Analysing file format and extracting layout...")
        ingestion_result = await run_ingestion_stage(file)
        
        if ingestion_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "ingestion", "error", error=ingestion_result.get("error"))
            return
            
        doc_data = ingestion_result["data"]
        
        # Build a safe preview string for the UI (first ~2000 chars)
        preview_text = ""
        for page in doc_data.get("pages", [])[:3]:
            for el in page.get("elements", []):
                preview_text += el.get("text", "") + "\n\n"
        
        ui_doc_data = {
            "filename": ingestion_result["filename"],
            "pages_count": len(doc_data.get("pages", [])),
            "ocr_used": doc_data.get("ocr_used", False),
            "preview_text": preview_text.strip()[:2000] + ("..." if len(preview_text) > 2000 else "")
        }
        await ws_manager.emit_stage_update(client_id, "ingestion", "complete", data=ui_doc_data, detail="Document parsed successfully.")

        # --- STAGE 2: CLASSIFICATION ---
        await ws_manager.emit_stage_update(client_id, "classification", "running", detail="Running LLM classification heuristics...")
        class_result = await asyncio.to_thread(run_classification_stage, doc_data)
        
        if class_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "classification", "error", error=class_result.get("error"))
            return
            
        classification_data = class_result["data"]
        doc_type_formatted = classification_data.get('document_type', 'unknown').replace('_', ' ').title()
        
        await ws_manager.emit_stage_update(client_id, "classification", "complete", data=classification_data, detail=f"Identified as {doc_type_formatted}.")

        print("="*50)
        print(classification_data)
        print("="*50)

        # --- STAGE 3: EXTRACTION ---
        await ws_manager.emit_stage_update(client_id, "extraction", "running", detail=f"Applying targeted {doc_type_formatted} extraction schema...")
        ext_result = await asyncio.to_thread(run_extraction_stage, doc_data, classification_data)

        print("="*50)
        print(ext_result)
        print("="*50)
        
        if ext_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "extraction", "error", error=ext_result.get("error"))
            return
            
        await ws_manager.emit_stage_update(client_id, "extraction", "complete", data=ext_result["data"], detail="Structured entities and clauses extracted.")

        # Pipeline continues for Anomaly & Risk...
        
    except Exception as e:
        logger.error(f"Pipeline orchestrator failed: {traceback.format_exc()}")
        await ws_manager.emit_stage_update(client_id, "system", "error", error=f"Fatal pipeline error: {str(e)}")