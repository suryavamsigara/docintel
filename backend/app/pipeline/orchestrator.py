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
    """
    Orchestrates the CPU-bound pipeline while ensuring real-time WebSocket 
    emissions to the client at the start and end of every stage.
    """
    try:
        # ---------------------------------------------------------
        # STAGE 1: INGESTION (Async native)
        # ---------------------------------------------------------
        await ws_manager.emit_stage_update(client_id, "ingestion", "running")
        ingestion_result = await run_ingestion_stage(file)
        
        if ingestion_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "ingestion", "error", error=ingestion_result.get("error"))
            return
            
        doc_data = ingestion_result["data"]
        # Do not send the full text blob to UI to save bandwidth, just metadata
        ui_doc_data = {
            "filename": ingestion_result["filename"],
            "pages_count": len(doc_data.get("pages", [])),
            "ocr_used": doc_data.get("ocr_used", False),
            "low_quality": doc_data.get("low_quality", False)
        }
        await ws_manager.emit_stage_update(client_id, "ingestion", "complete", data=ui_doc_data)

        # ---------------------------------------------------------
        # STAGE 2: CLASSIFICATION (CPU-bound / Network-bound blocking)
        # ---------------------------------------------------------
        await ws_manager.emit_stage_update(client_id, "classification", "running")
        
        # Offload blocking synchronous API calls to thread pool
        class_result = await asyncio.to_thread(run_classification_stage, doc_data)
        
        if class_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "classification", "error", error=class_result.get("error"))
            return
            
        classification_data = class_result["data"]
        await ws_manager.emit_stage_update(client_id, "classification", "complete", data=classification_data)

        # ---------------------------------------------------------
        # STAGE 3: EXTRACTION (CPU-bound / Network-bound blocking)
        # ---------------------------------------------------------
        await ws_manager.emit_stage_update(client_id, "extraction", "running")
        
        ext_result = await asyncio.to_thread(run_extraction_stage, doc_data, classification_data)
        
        if ext_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "extraction", "error", error=ext_result.get("error"))
            return
            
        await ws_manager.emit_stage_update(client_id, "extraction", "complete", data=ext_result["data"])

        # Note: Further stages (Anomaly, Risk, CRM Sync, Cross-Contradiction) 
        # follow this exact same pattern.
        
    except Exception as e:
        logger.error(f"Pipeline orchestrator failed: {traceback.format_exc()}")
        await ws_manager.emit_stage_update(client_id, "system", "error", error=f"Fatal pipeline error: {str(e)}")