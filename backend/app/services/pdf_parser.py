import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import statistics
from typing import Iterator, List, Dict, Any
from app.models import Page, Paragraph, Heading, Table, ListGroup, OcrText, DocumentElement

def get_page_median_font_size(page_dict: dict) -> float:
    """Calculates the median font size to establish a baseline for headings."""
    sizes = []
    for block in page_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(span.get("size", 10.0))
    return statistics.median(sizes) if sizes else 10.0

def merge_aligned_elements(elements: List[DocumentElement]) -> List[DocumentElement]:
    """
    Y-Axis Spatial Merge: Reconstructs borderless tables and multi-column headers
    by merging elements that sit on the exact same horizontal baseline.
    """
    if not elements:
        return []

    # Sort elements by Y-coordinate (top to bottom), then X-coordinate (left to right)
    # We round the Y-coordinate to the nearest 5 pixels to create a "tolerance band"
    elements.sort(key=lambda e: (round(e.bbox[1] / 5) * 5 if e.bbox else 0, e.bbox[0] if e.bbox else 0))
    
    merged = []
    for e in elements:
        # We only want to merge text-based elements, not existing Tables
        if not merged or e.type == "table":
            merged.append(e)
            continue
            
        prev = merged[-1]
        
        # Check if the current element is perfectly horizontally aligned with the previous one
        if prev.type in ["paragraph", "heading"] and e.type == prev.type:
            y_diff = abs(prev.bbox[1] - e.bbox[1])
            if y_diff <= 3.0:  # 3 pixels tolerance for being on the same line
                # Merge the elements, separating text with a tab space
                prev.text += f" \t {e.text}"
                prev.bbox = (
                    min(prev.bbox[0], e.bbox[0]),
                    min(prev.bbox[1], e.bbox[1]),
                    max(prev.bbox[2], e.bbox[2]),
                    max(prev.bbox[3], e.bbox[3])
                )
                continue
                
        merged.append(e)
        
    return merged

def process_scanned_page(page: fitz.Page, page_num: int) -> Page:
    """Runs OCR and groups the output spatially into blocks to preserve structure."""
    pix = page.get_pixmap(dpi=150)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Get detailed dictionary output from Tesseract
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    blocks_dict: Dict[tuple, Any] = {}
    low_quality_flag = False
    
    # Group individual words into their structural blocks identified by Tesseract
    for i, word in enumerate(ocr_data['text']):
        if not word.strip(): continue
        
        conf = float(ocr_data['conf'][i])
        if conf < 70.0:
            low_quality_flag = True
            
        b_num = ocr_data['block_num'][i]
        p_num = ocr_data['par_num'][i]
        key = (b_num, p_num)
        
        if key not in blocks_dict:
            blocks_dict[key] = {'text': [], 'conf': [], 'bbox': [9999, 9999, 0, 0]}
            
        x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
        
        blocks_dict[key]['text'].append(word)
        blocks_dict[key]['conf'].append(conf)
        
        # Expand the bounding box to fit the new word
        blocks_dict[key]['bbox'][0] = min(blocks_dict[key]['bbox'][0], x)
        blocks_dict[key]['bbox'][1] = min(blocks_dict[key]['bbox'][1], y)
        blocks_dict[key]['bbox'][2] = max(blocks_dict[key]['bbox'][2], x + w)
        blocks_dict[key]['bbox'][3] = max(blocks_dict[key]['bbox'][3], y + h)

    elements = []
    for key, block in blocks_dict.items():
        text = " ".join(block['text'])
        avg_conf = sum(block['conf']) / len(block['conf'])
        bbox = tuple(block['bbox'])
        
        # Structural Heuristics on OCR data
        if text.startswith(("•", "-", "*", "1.")):
            elements.append(ListGroup(bbox=bbox, items=[text], confidence=avg_conf))
        elif len(text) < 50 and text.istitle():
            elements.append(Heading(bbox=bbox, text=text, level=2, confidence=avg_conf))
        else:
            elements.append(Paragraph(bbox=bbox, text=text, confidence=avg_conf))

    # Free memory
    del pix
    del img

    # Sort blocks to maintain reading order
    elements.sort(key=lambda e: (e.bbox[1], e.bbox[0]))

    return Page(number=page_num, elements=elements, requires_ocr=True, low_quality=low_quality_flag)

def parse_digital_page(page: fitz.Page, page_num: int) -> Page:
    """Extracts structured text, catching hierarchical headings and borderless tables."""
    elements: List[DocumentElement] = []
    page_dict = page.get_text("dict")
    median_size = get_page_median_font_size(page_dict)
    
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

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0: 
            continue 

        bbox = block.get("bbox")
        
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
        
        # --- FIX 1: Hierarchical Heading Levels ---
        size_diff = max_size - median_size
        if size_diff >= 4.0:
            elements.append(Heading(bbox=bbox, text=text, level=1))
        elif size_diff >= 2.0:
            elements.append(Heading(bbox=bbox, text=text, level=2))
        elif size_diff >= 1.0:
            elements.append(Heading(bbox=bbox, text=text, level=3))
            
        elif text.startswith(("•", "-", "1.", "a)")):
            elements.append(ListGroup(bbox=bbox, items=[text]))
        else:
            elements.append(Paragraph(bbox=bbox, text=text))

    # --- FIX 3: Y-Axis Spatial Merge for Borderless Tables ---
    elements = merge_aligned_elements(elements)

    return Page(number=page_num, elements=elements, requires_ocr=False, low_quality=False)

def process_pdf_stream(file_bytes: bytes, filename: str) -> Iterator[Page]:
    """Generator that yields one processed Page at a time."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        text_length = len(page.get_text("text").strip())
        images_count = len(page.get_images())
        
        if text_length < 50 and images_count > 0:
            yield process_scanned_page(page, page_num + 1)
        else:
            yield parse_digital_page(page, page_num + 1)
            
        page = None 

    doc.close()