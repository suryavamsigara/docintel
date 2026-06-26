import io
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import statistics
from typing import Iterator, List
from app.models import Page, Paragraph, Heading, Table, OcrText, ListGroup, DocumentElement

def get_page_median_font_size(page_dict: dict) -> float:
    """Calculates the median font size to distinguish headings from paragraphs."""
    sizes = []
    for block in page_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span.get("size", 10.0))
    return statistics.median(sizes) if sizes else 10.0

def process_scanned_page(page: fitz.Page, page_num: int) -> Page:
    """Runs CPU-bound OCR on a single page using Tesseract."""
    # Render page to an image (dpi=150 is a good balance for CPU/memory on Railway)
    pix = page.get_pixmap(dpi=150)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Run Tesseract OCR and get data including confidence scores
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    elements = []
    low_quality_flag = False
    current_block_text = []
    current_bbox = [9999, 9999, 0, 0]
    
    for i, word in enumerate(ocr_data['text']):
        if not word.strip(): continue
        
        conf = float(ocr_data['conf'][i])
        if conf < 70.0:
            low_quality_flag = True
            
        x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
        
        current_block_text.append(word)
        current_bbox[0] = min(current_bbox[0], x)
        current_bbox[1] = min(current_bbox[1], y)
        current_bbox[2] = max(current_bbox[2], x + w)
        current_bbox[3] = max(current_bbox[3], y + h)

    if current_block_text:
        elements.append(OcrText(
            text=" ".join(current_block_text),
            bbox=tuple(current_bbox),
            confidence=float(sum(ocr_data['conf']) / len(ocr_data['conf'])) if ocr_data['conf'] else 0.0
        ))

    # Free up memory explicitly
    del pix
    del img

    return Page(
        number=page_num,
        elements=elements,
        requires_ocr=True,
        low_quality=low_quality_flag
    )

def parse_digital_page(page: fitz.Page, page_num: int) -> Page:
    """Extracts structured text and tables from a digital PDF page."""
    elements: List[DocumentElement] = []
    page_dict = page.get_text("dict")
    median_size = get_page_median_font_size(page_dict)
    
    # 1. Extract Tables first
    table_bboxes = []
    tabs = page.find_tables()
    for tab in tabs:
        table_bboxes.append(tab.bbox)
        extracted_data = tab.extract()
        if extracted_data:
            elements.append(Table(
                bbox=tab.bbox,
                headers=extracted_data[0] if extracted_data else [],
                rows=extracted_data[1:] if len(extracted_data) > 1 else [],
                confidence=100.0
            ))

    # 2. Extract Text Blocks
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0: 
            continue # Skip images/drawings for text extraction

        bbox = block.get("bbox")
        
        # Skip text blocks that fall inside tables to avoid duplication
        if any(fitz.Rect(bbox).intersects(fitz.Rect(tb)) for tb in table_bboxes):
            continue

        text = ""
        max_size = 0.0
        
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text += span.get("text", "") + " "
                if span.get("size", 0) > max_size:
                    max_size = span.get("size")
        
        text = text.strip()
        if not text: continue
        
        # Structural heuristic: Is it a heading or paragraph?
        if max_size > median_size + 1.5:
            elements.append(Heading(bbox=bbox, text=text, level=1))
        # Simple heuristic for lists
        elif text.startswith(("•", "-", "1.", "a)")):
            elements.append(ListGroup(bbox=bbox, items=[text]))
        else:
            elements.append(Paragraph(bbox=bbox, text=text))

    # Sort elements top-to-bottom, left-to-right to maintain reading order
    elements.sort(key=lambda e: (e.bbox[1] if e.bbox else 0, e.bbox[0] if e.bbox else 0))

    return Page(number=page_num, elements=elements, requires_ocr=False, low_quality=False)

def process_pdf_stream(file_bytes: bytes, filename: str) -> Iterator[Page]:
    """
    Generator that yields one processed Page at a time.
    Crucial for real-time WebSocket streaming and saving memory.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Check if page is effectively empty (scanned image)
        text_length = len(page.get_text("text").strip())
        images_count = len(page.get_images())
        
        # If there's barely any text but images are present, fallback to OCR for this specific page
        if text_length < 50 and images_count > 0:
            yield process_scanned_page(page, page_num + 1)
        else:
            yield parse_digital_page(page, page_num + 1)
            
        # Aggressive memory cleanup for Railway environment
        page = None 

    doc.close()