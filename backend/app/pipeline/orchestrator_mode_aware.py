"""
pipeline/orchestrator.py  (MODE-AWARE VERSION)

Drop-in replacement for your existing orchestrator.
Reads processing_mode from request context (set by the frontend toggle)
and routes each stage to either the local or LLM implementation.

Usage
-----
The frontend sends a header or query param:
    X-Processing-Mode: local   (default)
    X-Processing-Mode: llm

The FastAPI endpoint extracts this and passes it to run_full_pipeline:
    await run_full_pipeline(file, client_id, mode="local")   # or "llm"

All WebSocket message shapes are identical between modes — the frontend
does not need to know which backend produced the data.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Literal

from fastapi import UploadFile

from app.websockets.manager import ws_manager

# ── Ingestion (shared, format-agnostic) ───────────────────────────────────
from app.pipeline.ingestion import run_ingestion_stage

# ── LLM implementations (your existing files, unchanged) ──────────────────
from app.pipeline.classification import run_classification_stage       as _llm_classify
from app.pipeline.extraction     import run_extraction_stage           as _llm_extract
from app.pipeline.anomaly        import run_anomaly_stage              as _llm_anomaly

# ── Local implementations (new files) ─────────────────────────────────────
from app.pipeline.classification_local import run_classification_stage_local as _local_classify
from app.pipeline.extraction_local     import run_extraction_stage_local     as _local_extract
from app.pipeline.anomaly_local        import run_anomaly_stage_local        as _local_anomaly

# ── Risk scoring (pure rule-based, same for both modes) ───────────────────
from app.pipeline.risk import run_risk_stage

ProcessingMode = Literal["local", "llm"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page-number attachment helper  (unchanged from your original orchestrator)
# ---------------------------------------------------------------------------

def _find_page(pages: list, text_to_find: str) -> int | None:
    if not text_to_find:
        return None
    search_target = text_to_find.lower().strip()[:60]
    for page in pages:
        page_text = " ".join(
            el.get("text", "") for el in page.get("elements", [])
        ).lower()
        if search_target in page_text:
            return page.get("number", 1)
    return None


def _attach_page_numbers(doc_data: dict, extracted_data: dict) -> None:
    """Mutates extracted_data to inject page numbers based on raw_text/context."""
    pages = doc_data.get("pages", [])

    if "extraction" in extracted_data and "clauses" in extracted_data["extraction"]:
        for clause in extracted_data["extraction"]["clauses"]:
            if clause.get("raw_text"):
                clause["page"] = _find_page(pages, clause["raw_text"])

    for d in extracted_data.get("dates", []):
        if d.get("context"):
            d["page"] = _find_page(pages, d["context"])

    for p in extracted_data.get("primary_parties", []):
        if p.get("basis"):
            p["page"] = _find_page(pages, p["basis"])


# ---------------------------------------------------------------------------
# Mode-aware stage runners
# ---------------------------------------------------------------------------

def _classify(doc_data: dict, mode: ProcessingMode) -> dict:
    if mode == "llm":
        return _llm_classify(doc_data)
    return _local_classify(doc_data)


def _extract(doc_data: dict, classification_data: dict, mode: ProcessingMode) -> dict:
    if mode == "llm":
        return _llm_extract(doc_data, classification_data)
    return _local_extract(doc_data, classification_data)


def _anomaly(ext_data: dict, mode: ProcessingMode) -> dict:
    if mode == "llm":
        return _llm_anomaly(ext_data)
    return _local_anomaly(ext_data)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_full_pipeline(
    file: UploadFile,
    client_id: str,
    mode: ProcessingMode = "local",
) -> None:
    """
    Orchestrates the full 5-stage pipeline.

    Emits WebSocket updates after every stage.
    Stage data shapes are identical regardless of `mode`.
    """
    try:
        pipeline_start = time.time()

        # ── STAGE 1: INGESTION (always shared) ───────────────────────────
        t0 = time.time()
        await ws_manager.emit_stage_update(
            client_id, "ingestion", "running",
            detail="Analysing format...",
        )
        ingestion_result = await run_ingestion_stage(file)

        if ingestion_result.get("status") == "error":
            await ws_manager.emit_stage_update(
                client_id, "ingestion", "error",
                error=ingestion_result.get("error"),
            )
            return

        doc_data = ingestion_result["data"]
        ui_doc_data = {
            "filename":   ingestion_result["filename"],
            "pages_count": len(doc_data.get("pages", [])),
            "ocr_used":   doc_data.get("ocr_used", False),
            "low_quality": doc_data.get("low_quality", False),
            "mode":       mode,   # surface the active mode to the UI
        }
        await ws_manager.emit_stage_update(
            client_id, "ingestion", "complete",
            data=ui_doc_data,
            detail=f"Parsed in {round(time.time() - t0, 1)}s",
            duration=round(time.time() - t0, 1),
        )

        print("="*50)
        print(doc_data)
        print("="*50)

        # ── STAGE 2: CLASSIFICATION ───────────────────────────────────────
        t0 = time.time()
        mode_label = "🤖 AI" if mode == "llm" else "⚡ Local"
        await ws_manager.emit_stage_update(
            client_id, "classification", "running",
            detail=f"Identifying document ({mode_label})...",
        )
        class_result = await asyncio.to_thread(_classify, doc_data, mode)

        if class_result.get("status") == "error":
            await ws_manager.emit_stage_update(
                client_id, "classification", "error",
                error=class_result.get("error"),
            )
            return

        classification_data = class_result["data"]
        _attach_page_numbers(doc_data, classification_data)

        doc_type_fmt = classification_data.get("document_type", "unknown").replace("_", " ").title()
        duration = round(time.time() - t0, 1)
        await ws_manager.emit_stage_update(
            client_id, "classification", "complete",
            data=classification_data,
            detail=f"Identified {doc_type_fmt} in {duration}s",
            duration=duration,
        )

        print("="*50)
        print(classification_data)
        print("="*50)

        # ── STAGE 3: EXTRACTION ───────────────────────────────────────────
        t0 = time.time()
        await ws_manager.emit_stage_update(
            client_id, "extraction", "running",
            detail=f"Extracting clauses ({mode_label})...",
        )
        ext_result = await asyncio.to_thread(_extract, doc_data, classification_data, mode)

        if ext_result.get("status") == "error":
            await ws_manager.emit_stage_update(
                client_id, "extraction", "error",
                error=ext_result.get("error"),
            )
            return

        ext_data = ext_result["data"]
        _attach_page_numbers(doc_data, ext_data)
        ext_data["processing_time"] = round(time.time() - pipeline_start, 1)

        duration = round(time.time() - t0, 1)
        await ws_manager.emit_stage_update(
            client_id, "extraction", "complete",
            data=ext_data,
            detail=f"Extracted in {duration}s",
            duration=duration,
        )

        print("="*50)
        print(ext_data)
        print("="*50)

        # ── STAGE 4: ANOMALY DETECTION ────────────────────────────────────
        t0 = time.time()
        await ws_manager.emit_stage_update(
            client_id, "anomaly", "running",
            detail=f"Scanning for anomalies ({mode_label})...",
        )
        anomaly_result = await asyncio.to_thread(_anomaly, ext_data, mode)

        if anomaly_result.get("status") == "error":
            await ws_manager.emit_stage_update(
                client_id, "anomaly", "error",
                error=anomaly_result.get("error"),
            )
            return

        anom_data = anomaly_result["data"]
        duration = round(time.time() - t0, 1)
        await ws_manager.emit_stage_update(
            client_id, "anomaly", "complete",
            data=anom_data,
            detail=f"Found {len(anom_data.get('anomalies', []))} anomalies in {duration}s",
            duration=duration,
        )

        print("="*50)
        print(anom_data)
        print("="*50)

        # ── STAGE 5: RISK SCORING (always rule-based) ─────────────────────
        t0 = time.time()
        await ws_manager.emit_stage_update(
            client_id, "risk", "running",
            detail="Calculating risk profile...",
        )
        risk_result = run_risk_stage(anom_data, ext_data)

        if risk_result.get("status") == "error":
            await ws_manager.emit_stage_update(
                client_id, "risk", "error",
                error=risk_result.get("error"),
            )
            return

        risk_data = risk_result["data"]
        duration = round(time.time() - t0, 1)
        await ws_manager.emit_stage_update(
            client_id, "risk", "complete",
            data=risk_data,
            detail=f"Risk assessed as {risk_data.get('risk_level')} in {duration}s",
            duration=duration,
        )

        print("="*50)
        print(risk_data)
        print("="*50)

    except Exception as e:
        logger.error("Pipeline orchestrator failed: %s", traceback.format_exc())
        await ws_manager.emit_stage_update(
            client_id, "system", "error",
            error=f"Fatal pipeline error: {str(e)}",
        )