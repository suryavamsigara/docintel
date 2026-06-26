import os
import mimetypes
from typing import AsyncGenerator, Dict, Any
from fastapi import UploadFile, HTTPException

# Import the streaming parser we just built
from app.services.pdf_parser import process_pdf_stream
# from app.services.docx_parser import process_docx_stream
# from app.services.excel_parser import process_excel_stream
# from app.services.image_parser import process_image_stream

async def run_ingestion_stream(file: UploadFile) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stage 1: Ingestion and Normalization.
    Routes the file to the appropriate parser based on MIME type and extension,
    and streams the extracted pages back to the caller for real-time WebSocket delivery.
    """
    # Read file into memory (FastAPI spools large files to disk, 
    # but we need bytes for PyMuPDF/fitz stream processing)
    content = await file.read()
    filename = file.filename
    mime_type, _ = mimetypes.guess_type(filename)
    extension = os.path.splitext(filename)[1].lower()

    # Robust routing logic: check both extension and mime_type 
    # as uploads from clients can sometimes be inaccurate
    is_pdf = extension == ".pdf" or mime_type == "application/pdf"
    is_docx = extension == ".docx" or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    is_excel = extension in [".xlsx", ".xls"] or (mime_type and "spreadsheetml" in mime_type)
    is_image = extension in [".jpg", ".jpeg", ".png"] or (mime_type and mime_type.startswith("image/"))

    try:
        if is_pdf:
            # Iterate over the sync generator and yield async-friendly chunks
            for page in process_pdf_stream(content, filename):
                yield {
                    "stage": "ingestion", 
                    "status": "processing", 
                    "filename": filename,
                    "data": page.model_dump()
                }
                
        elif is_docx:
            yield {"stage": "ingestion", "status": "error", "message": "DOCX parser not yet implemented"}
            # for page in process_docx_stream(content, filename): 
            #     yield {"stage": "ingestion", "status": "processing", "data": page.model_dump()}
            
        elif is_excel:
            yield {"stage": "ingestion", "status": "error", "message": "Excel parser not yet implemented"}
            # for sheet in process_excel_stream(content, filename): ...
            
        elif is_image:
            yield {"stage": "ingestion", "status": "error", "message": "Image parser not yet implemented"}
            # for page in process_image_stream(content, filename): ...
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {extension}")
            
    finally:
        # Crucial for Railway: aggressively release file handles and memory
        await file.close()
        del content


# --- Local Testing Block ---
if __name__ == "__main__":
    import asyncio
    from pathlib import Path
    
    class MockUploadFile:
        def __init__(self, path: Path):
            self.path = path
            self.filename = path.name
            
        async def read(self):
            with open(self.path, "rb") as f:
                return f.read()
                
        async def close(self):
            pass

    async def run_test():
        root = Path(__file__).parent.parent.parent.parent
        file_path = root / 'docs' / 'suryavamsigara_resume.pdf'
        
        if not file_path.exists():
            print(f"❌ Test file not found: {file_path}")
            print("Please ensure the directory structure is correct or change the path.")
            return
            
        mock_file = MockUploadFile(file_path)
        
        print(f"🚀 Starting ingestion pipeline for: {mock_file.filename}\n" + "-"*50)
        
        try:
            async for result in run_ingestion_stream(mock_file):
                if result.get("status") == "processing":
                    page_data = result["data"]
                    print(f"✅ Yielded Page {page_data['number']} | "
                          f"OCR Used: {page_data['requires_ocr']} | "
                          f"Elements: {page_data['elements']} | "
                          f"Elements Extracted: {len(page_data['elements'])}")
                else:
                    print(f"⚠️ Pipeline Message: {result}")
        except Exception as e:
            print(f"❌ Pipeline failed: {str(e)}")
            
    asyncio.run(run_test())