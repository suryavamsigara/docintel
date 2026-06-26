import os
import mimetypes
from typing import Dict, Any
from fastapi import UploadFile, HTTPException

from app.services.pdf_parser import process_pdf
from app.services.docx_parser import process_docx
from app.services.excel_parser import process_excel
from app.services.image_parser import process_image

async def run_ingestion_stage(file: UploadFile) -> Dict[str, Any]:
    """
    Ingestion and Normalization (Pre-Pipeline Stage).
    Routes the file to the appropriate parser based on MIME type and extension,
    and returns the fully processed NormalizedDocument payload.
    """
    # Read file into memory (FastAPI spools large files to disk, 
    # but we need bytes for PyMuPDF/docx/openpyxl processing)
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
            doc = process_pdf(content, filename)
        elif is_docx:
            doc = process_docx(content, filename)
        elif is_excel:
            doc = process_excel(content, filename)
        elif is_image:
            doc = process_image(content, filename)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {extension}")
            
        # Return the payload formatted perfectly for your WebSocket orchestrator
        return {
            "stage": "ingestion", 
            "status": "complete", 
            "filename": filename,
            "data": doc.model_dump()
        }
            
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
        # Adjust path as necessary to point to your test documents
        root = Path(__file__).parent.parent.parent.parent
        file_path = root / 'docs' / 'inv.jpg' 
        
        if not file_path.exists():
            print(f"❌ Test file not found: {file_path}")
            print("Please ensure the directory structure is correct or change the path.")
            return
            
        mock_file = MockUploadFile(file_path)
        
        print(f"🚀 Starting ingestion pipeline for: {mock_file.filename}\n" + "-"*50)
        
        try:
            # Wait for the entire ingestion stage to complete
            result = await run_ingestion_stage(mock_file)
            doc_data = result["data"]
            
            print(f"✅ Ingestion Stage Complete!")
            print(f"📄 Filename: {result['filename']}")
            print(f"📑 Total Pages: {len(doc_data['pages'])}")
            print(f"🔍 OCR Used: {doc_data['ocr_used']}")
            print(f"⚠️ Low Quality Flag: {doc_data['low_quality']}")
            
            if doc_data['pages']:
                print(f"🧩 Elements on Page 1: {len(doc_data['pages'][0]['elements'])}")
                print(f"Pages: {doc_data['pages']}")
                
        except Exception as e:
            print(f"❌ Pipeline failed: {str(e)}")
            
    asyncio.run(run_test())