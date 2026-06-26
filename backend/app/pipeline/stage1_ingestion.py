import os
import mimetypes
from fastapi import UploadFile
from typing import Dict, Any

# Import parsers (defined below)
from app.services.pdf_parser import process_pdf
from app.services.docx_parser import process_docx
from app.services.excel_parser import process_excel
from app.services.image_parser import process_image

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
        "structured_data": None,
        "warnings": []
    }

    try:
        if extension == '.pdf' or mime_type == 'application/pdf':
            extraction = process_pdf(content)
        elif extension == '.docx' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            extraction = process_docx(content)
        elif extension == '.xlsx' or mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            extraction = process_excel(content)
        elif extension in ['.png', '.jpg', '.jpeg'] or (mime_type and mime_type.startswith('image/')):
            extraction = process_image(content)
        else:
            raise ValueError(f"Unsupported file format: {extension}")

        result["structured_data"] = extraction.get("data")
        
        # Surface OCR warnings if confidence is low
        if extraction.get("low_quality"):
            result["warnings"].append("Low OCR confidence detected. Output may contain errors.")

    except Exception as e:
        result["status"] = "error"
        result["error_message"] = str(e)

    return result

import asyncio
import io

if __name__ == "__main__":
    from pathlib import Path
    root = Path(__file__).parent.parent.parent.parent
    file_path = root / 'docs' / 'suryavamsigara_resume.pdf'

    file_bytes = file_path.read_bytes()
    
    # 3. Mock FastAPI's UploadFile
    mock_file = UploadFile(
        file=io.BytesIO(file_bytes), 
        filename=file_path.name
    )

    output = asyncio.run(run_ingestion_stage(mock_file))
    print(output)