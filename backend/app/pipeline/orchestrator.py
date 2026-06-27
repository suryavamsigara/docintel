import asyncio
import logging
import traceback
import time
from fastapi import UploadFile

from app.websockets.manager import ws_manager
from app.pipeline.ingestion import run_ingestion_stage
from app.pipeline.classification import run_classification_stage
from app.pipeline.extraction import run_extraction_stage

logger = logging.getLogger(__name__)

def _find_page(pages: list, text_to_find: str) -> int:
    """Helper to locate the page number for a given snippet of text."""
    if not text_to_find: return None
    search_target = text_to_find.lower().strip()[:60] # Search using first 60 chars
    
    for page in pages:
        # Build page text
        page_text = " ".join([el.get("text", "") for el in page.get("elements", [])]).lower()
        if search_target in page_text:
            return page.get("number", 1)
    return None

def _attach_page_numbers(doc_data: dict, extracted_data: dict):
    """Mutates extracted_data to append page numbers based on raw_text/context."""
    pages = doc_data.get("pages", [])
    
    # Match Extraction Clauses
    if "extraction" in extracted_data and "clauses" in extracted_data["extraction"]:
        for clause in extracted_data["extraction"]["clauses"]:
            if clause.get("raw_text"):
                clause["page"] = _find_page(pages, clause["raw_text"])
                
    # Match Classification Dates & Parties
    if "dates" in extracted_data:
        for d in extracted_data["dates"]:
            if d.get("context"): d["page"] = _find_page(pages, d["context"])
            
    if "primary_parties" in extracted_data:
        for p in extracted_data["primary_parties"]:
            if p.get("basis"): p["page"] = _find_page(pages, p["basis"])


async def run_full_pipeline(file: UploadFile, client_id: str):
    try:
        pipeline_start = time.time()
        
        # --- STAGE 1: INGESTION ---
        t0 = time.time()
        await ws_manager.emit_stage_update(client_id, "ingestion", "running", detail="Analysing format...")
        ingestion_result = await run_ingestion_stage(file)
        
        if ingestion_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "ingestion", "error", error=ingestion_result.get("error"))
            return
            
        doc_data = ingestion_result["data"]
        ui_doc_data = {
            "filename": ingestion_result["filename"],
            "pages_count": len(doc_data.get("pages", [])),
            "ocr_used": doc_data.get("ocr_used", False),
            "low_quality": doc_data.get("low_quality", False)
        }
        duration = round(time.time() - t0, 1)
        await ws_manager.emit_stage_update(client_id, "ingestion", "complete", data=ui_doc_data, detail=f"Parsed in {duration}s", duration=duration)

        # --- STAGE 2: CLASSIFICATION ---
        t0 = time.time()
        await ws_manager.emit_stage_update(client_id, "classification", "running", detail="Identifying document...")
        class_result = await asyncio.to_thread(run_classification_stage, doc_data)
        
        if class_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "classification", "error", error=class_result.get("error"))
            return
            
        classification_data = class_result["data"]
        _attach_page_numbers(doc_data, classification_data) # Inject page numbers
        
        duration = round(time.time() - t0, 1)
        doc_type_formatted = classification_data.get('document_type', 'unknown').replace('_', ' ').title()
        await ws_manager.emit_stage_update(client_id, "classification", "complete", data=classification_data, detail=f"Identified {doc_type_formatted} in {duration}s", duration=duration)

        print("="*50)
        print(classification_data)
        print("="*50)

        # --- STAGE 3: EXTRACTION ---
        t0 = time.time()
        await ws_manager.emit_stage_update(client_id, "extraction", "running", detail="Extracting clauses...")
        ext_result = await asyncio.to_thread(run_extraction_stage, doc_data, classification_data)
        
        if ext_result.get("status") == "error":
            await ws_manager.emit_stage_update(client_id, "extraction", "error", error=ext_result.get("error"))
            return
            
        ext_data = ext_result["data"]
        _attach_page_numbers(doc_data, ext_data) # Inject page numbers
        
        duration = round(time.time() - t0, 1)
        total_time = round(time.time() - pipeline_start, 1)
        
        # We can pass total_time in the extraction data payload for the Overview card
        ext_data["processing_time"] = total_time

        print("="*50)
        print(ext_data)
        print("="*50)
        
        await ws_manager.emit_stage_update(client_id, "extraction", "complete", data=ext_data, detail=f"Extracted in {duration}s", duration=duration)

    except Exception as e:
        logger.error(f"Pipeline orchestrator failed: {traceback.format_exc()}")
        await ws_manager.emit_stage_update(client_id, "system", "error", error=f"Fatal pipeline error: {str(e)}")