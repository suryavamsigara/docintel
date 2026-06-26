import os
import mimetypes
from fastapi import UploadFile
from typing import Dict, Any

# Import parsers (uncomment others as we build them)
from app.services.pdf_parser import process_pdf
# from app.services.docx_parser import process_docx
# from app.services.excel_parser import process_excel
# from app.services.image_parser import process_image

async def run_ingestion_stage(file: UploadFile) -> Dict[str, Any]:
    """
    Stage 1: Ingestion and Normalization.
    Routes the file to the appropriate parser based on MIME type and extension.
    """
    content = await file.read()
    filename = file.filename
    mime_type, _ = mimetypes.guess_type(filename)
    extension = os.path.splitext(filename)[1].lower()

    result = {
        "filename": filename,
        "mime_type": mime_type,
        "status": "success",
        "document_data": None,
        "warnings": []
    }

    try:
        if extension == '.pdf' or mime_type == 'application/pdf':
            extraction = process_pdf(content, filename)
        # elif extension == '.docx' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        #     extraction = process_docx(content, filename)
        # elif extension == '.xlsx' or mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        #     extraction = process_excel(content, filename)
        # elif extension in ['.png', '.jpg', '.jpeg'] or (mime_type and mime_type.startswith('image/')):
        #     extraction = process_image(content, filename)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

        result["document_data"] = extraction
        
        # Surface OCR warnings if low_quality flag was tripped
        if extraction.get("low_quality"):
            result["warnings"].append("Low OCR confidence detected. Output may contain errors.")

    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)

    return result


# ---------------------------------------------------------
# Test Runner for CLI
# ---------------------------------------------------------
import asyncio
import io

if __name__ == "__main__":
    from pathlib import Path
    
    async def run_test():
        root = Path(__file__).parent.parent.parent.parent
        file_path = root / 'docs' / 'suryavamsigara_resume.pdf'

        if not file_path.exists():
            print(f"⚠️  Could not find file at: {file_path}")
            return

        file_bytes = file_path.read_bytes()
        
        mock_file = UploadFile(
            file=io.BytesIO(file_bytes), 
            filename=file_path.name
        )

        print(f"🚀 Running Stage 1 Ingestion on '{file_path.name}'...\n")
        
        output = await run_ingestion_stage(mock_file)
        
        if output["status"] == "success":
            print("✅ Ingestion Successful! Here is the extracted structure:\n")
            
            doc_data = output["document_data"]
            print(f"📄 Document: {doc_data['filename']} (OCR Used: {doc_data.get('ocr_used', False)})")
            
            for page in doc_data.get("pages", []):
                print(f"\n--- Page {page['number']} ---")
                elements = page.get("elements", [])
                
                for elem in elements:
                    elem_type = elem.get("type", "unknown").upper()
                    
                    if elem_type in ["HEADING", "PARAGRAPH"]:
                        text = elem.get("text", "").replace("\n", " ")
                        display_text = text[:80] + "..." if len(text) > 80 else text
                        print(f"[{elem_type}] {display_text}")
                    
                    elif elem_type == "TABLE":
                        rows = len(elem.get("rows", []))
                        print(f"[TABLE] ({rows} rows extracted)")
                        
            if output["warnings"]:
                print(f"\nWarnings: {output['warnings']}")
        else:
            print(f"❌ Error: {output.get('error_message')}")

    asyncio.run(run_test())