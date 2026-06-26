import io
from PIL import Image
import pytesseract
from typing import Dict, Any
from app.models import Page, ListGroup, OcrText, NormalizedDocument

def process_image(file_bytes: bytes, filename: str) -> NormalizedDocument:
    """
    Runs Tesseract OCR directly on uploaded image files (JPG/PNG).
    """
    img = Image.open(io.BytesIO(file_bytes))
    
    # Convert to grayscale for slightly better OCR accuracy on receipts
    img = img.convert('L') 
    
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    blocks_dict: Dict[tuple, Any] = {}
    low_quality = False
    
    for i, word in enumerate(ocr_data['text']):
        if not word.strip(): continue
        
        conf = float(ocr_data['conf'][i])
        if conf < 70.0:
            low_quality = True
            
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
    # Sort logically by layout
    for key in sorted(blocks_dict.keys()):
        block = blocks_dict[key]
        text = " ".join(block['text'])
        avg_conf = sum(block['conf']) / len(block['conf'])
        bbox = tuple(block['bbox'])
        
        if text.startswith(("•", "-", "*", "1.")):
            elements.append(ListGroup(bbox=bbox, items=[text], confidence=avg_conf))
        else:
            elements.append(OcrText(bbox=bbox, text=text, confidence=avg_conf))

    return NormalizedDocument(
        filename=filename,
        pages=[Page(number=1, elements=elements, requires_ocr=True, low_quality=low_quality)],
        ocr_used=True,
        low_quality=low_quality
    )