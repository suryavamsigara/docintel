# Intelligent Document Processing & Contract Intelligence Platform

A document intelligence platform that automates the extraction, classification, and risk analysis of unstructured documents. Built to process contracts, invoices, NDAs, RFPs, and financial statements, the system utilizes a multi-stage CPU-bound pipeline with real-time WebSocket streaming and seamless Notion CRM synchronization.

## Architecture Overview

The platform is divided into a decoupled frontend and backend, communicating via REST for state management and WebSockets for real-time pipeline streaming.

* **Frontend:** Implements a responsive, react UI featuring a native document viewer, real-time pipeline tracking, and project-level contradiction dashboards.
* **Backend:** FastAPI (Python). Handles asynchronous processing, WebSocket orchestration, and integration with the Notion API.
* **Database:** Turso (libSQL/SQLite). Stores project state, document metadata, content hashes for deduplication, and JSON analysis payloads.
* **CRM Integration:** Notion API (Idempotent upsert via SHA-256 content hashing).

## ⚙️ Multi-Stage Processing Pipeline

The system routes documents through a dynamic, 6-stage pipeline. Results are streamed to the client in real-time.

1.  **Ingestion & Format Normalization:** Detects input format (PDF, DOCX, XLSX, JPG/PNG). Extracts text while preserving structure (tables, headings). Scanned documents trigger Tesseract OCR with confidence scoring and artifact correction.
2.  **Classification & Extraction:** Classifies the document type and identifies primary parties. Extracts structured key fields dynamically based on the document type (e.g., clauses for NDAs, line items and taxes for invoices).
3.  **Anomaly Detection:** Flags deviations from standard business patterns (e.g., asymmetric liability caps, mismatched invoice totals). Anomalies are categorized by severity (Critical, Warning, Informational).
4.  **Risk Scoring:** Aggregates anomalies and clause contents to generate an overall numerical risk score and risk level breakdown.
5.  **Cross-Document Contradictions:** Evaluates the document against all other analyzed documents in the same project workspace. Flags logical contradictions (e.g., an invoice demanding 60-day terms against a Master Agreement mandating 30-day terms).
6.  **CRM Synchronization:** Pushes structured data (Parties, Key Fields, Risk Score, Anomaly Counts) to a Notion Database. Uses content hashing to guarantee idempotency (updates existing records instead of duplicating).

## 🧠 Memory Management Strategy (Railway Deployment)

To comply with the strict memory limits of the Railway Free Tier while running multiple CPU-bound ML models, this platform implements a **Lazy-Loading & Model Cycling** strategy:

* **JIT (Just-In-Time) Initialization:** Models (like the OCR engine and NLP classifiers) are never loaded into global memory on application startup. They are instantiated strictly inside their respective pipeline functions.
* **Async Sleep Yields:** `asyncio.sleep()` is utilized between pipeline stages to yield control back to the event loop, ensuring WebSocket pings remain active and memory gets appropriately flushed without starving the CPU.

## 📦 Models & Dependencies

* **OCR Engine:** `pytesseract` (Tesseract-OCR) for scanned PDFs and images.
* **Digital Text Extraction:** `pdfplumber` / `PyPDF2` (PDF structure mapping), `python-docx` (Word), `pandas` (Excel).
* **NLP/Extraction:** Utilizes lightweight CPU-bound NLP processing (or DeepSeek API depending on the environment configuration `X-Processing-Mode`).
* **WebSockets:** FastAPI native WebSockets.

## 🚀 Deployment Instructions

### Local Development
1. Clone the repository.
2. Setup the backend:
   ```bash
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload
   ```
2. Start frontend
   ```bash
   cd frontend
   npm run dev
   ```
