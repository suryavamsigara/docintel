import io
import re
from PIL import Image
import pytesseract
from typing import Dict, Any
from app.models import Page, ListGroup, OcrText, NormalizedDocument

MIN_OCR_CONFIDENCE = 50.0

def post_process_ocr_text(text: str) -> str:
    """
    Detects and corrects common scanning artefacts produced by OCR engines.
    """
    if not text:
        return ""
        
    text = re.sub(r'([a-zA-Z]+)-\s+([a-zA-Z]+)', r'\1\2', text)
    
    ligatures = {
        'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl',
        '|': 'l', '[': 'l', ']': 'l', 'rn': 'm',
    }
    
    text = re.sub(r'([a-zA-Z])\|([a-zA-Z])', r'\1l\2', text)
    text = re.sub(r'([a-zA-Z])\[([a-zA-Z])', r'\1l\2', text)
    text = re.sub(r'([a-zA-Z])\]([a-zA-Z])', r'\1l\2', text)
    
    for search, replace in ligatures.items():
        if search in ['|', '[', ']', 'rn']: continue
        text = text.replace(search, replace)
        
    text = re.sub(r'\s+([.,;:?!])', r'\1', text)
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()

def process_image(file_bytes: bytes, filename: str) -> NormalizedDocument:
    """
    Runs Tesseract OCR directly on uploaded image files (JPG/PNG).
    """
    img = Image.open(io.BytesIO(file_bytes))
    
    # Convert to grayscale for slightly better OCR accuracy on receipts/scans
    img = img.convert('L') 
    
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    blocks_dict: Dict[tuple, Any] = {}
    doc_low_quality = False
    
    for i, word in enumerate(ocr_data['text']):
        if not word.strip(): continue
        
        conf = float(ocr_data['conf'][i])
            
        b_num, p_num = ocr_data['block_num'][i], ocr_data['par_num'][i]
        key = (b_num, p_num)
        
        if key not in blocks_dict:
            blocks_dict[key] = {'text': [], 'conf': [], 'bbox': [9999, 9999, 0, 0]}
            
        x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
        
        blocks_dict[key]['text'].append(word)
        blocks_dict[key]['conf'].append(conf)
        blocks_dict[key]['bbox'][0] = min(blocks_dict[key]['bbox'][0], x)
        blocks_dict[key]['bbox'][1] = min(blocks_dict[key]['bbox'][1], y)
        blocks_dict[key]['bbox'][2] = max(blocks_dict[key]['bbox'][2], x + w)
        blocks_dict[key]['bbox'][3] = max(blocks_dict[key]['bbox'][3], y + h)

    elements = []
    list_buffer = []
    list_bbox = None
    
    # Sort logically by layout
    for key in sorted(blocks_dict.keys()):
        block = blocks_dict[key]
        raw_text = " ".join(block['text'])
        
        # 1. RUN OCR POST-PROCESSING
        clean_text = post_process_ocr_text(raw_text)
        if not clean_text: continue
        
        avg_conf = sum(block['conf']) / len(block['conf'])
        bbox = tuple(block['bbox'])
        
        # 2. Block-level quality check
        if avg_conf < MIN_OCR_CONFIDENCE and len(clean_text) > 5:
            doc_low_quality = True
            
        is_list_item = clean_text.startswith(("•", "-", "*", "1."))
        
        # Flush buffered list if we reached a non-list element
        if not is_list_item and list_buffer:
            elements.append(ListGroup(bbox=list_bbox, items=list_buffer, confidence=avg_conf))
            list_buffer = []
            list_bbox = None
            
        if is_list_item:
            if list_bbox is None:
                list_bbox = bbox
            clean_item = clean_text.lstrip("•- * \t")
            list_buffer.append(clean_item)
        else:
            elements.append(OcrText(bbox=bbox, text=clean_text, confidence=avg_conf))

    # Flush any trailing lists
    if list_buffer:
        elements.append(ListGroup(bbox=list_bbox, items=list_buffer, confidence=avg_conf))
        
    metadata = {}
    if doc_low_quality:
        metadata["warning"] = f"OCR confidence dropped below {MIN_OCR_CONFIDENCE}%. Flagged for review."

    return NormalizedDocument(
        filename=filename,
        pages=[Page(number=1, elements=elements, requires_ocr=True, low_quality=doc_low_quality)],
        ocr_used=True,
        low_quality=doc_low_quality,
        metadata=metadata
    )