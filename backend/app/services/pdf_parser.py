import io
import pdfplumber
from pdf2image import convert_from_bytes
from app.services.image_parser import process_image_pil

def process_pdf(file_bytes: bytes) -> dict:
    structured_content = []
    requires_ocr = False
    low_quality_flag = False

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            tables = page.extract_tables()

            # If text is extremely sparse, assume it's a scanned page
            if not text or len(text.strip()) < 20:
                requires_ocr = True
                break
            
            # Append digital text as a page block
            structured_content.append({
                "type": "page_text",
                "page": page_num + 1,
                "content": text
            })

            # Append tables if found
            if tables:
                for table in tables:
                    structured_content.append({
                        "type": "table",
                        "page": page_num + 1,
                        "content": table
                    })

    # Fallback to OCR if digital extraction yielded nothing useful
    if requires_ocr:
        structured_content = [] # Reset
        images = convert_from_bytes(file_bytes)
        for page_num, image in enumerate(images):
            ocr_result = process_image_pil(image)
            structured_content.append({
                "type": "ocr_text",
                "page": page_num + 1,
                "content": ocr_result["data"]
            })
            if ocr_result.get("low_quality"):
                low_quality_flag = True

    return {"data": structured_content, "low_quality": low_quality_flag}