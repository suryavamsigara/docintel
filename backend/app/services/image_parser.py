import io
import re
import pytesseract
from PIL import Image

def clean_ocr_artifacts(text: str) -> str:
    """Fixes common scanning artifacts."""
    # Fix broken words split across lines by hyphens
    text = re.sub(r'-\n\s*', '', text)
    # Fix common ligature misreadings (e.g., 'fi' read as 'fl' or separate letters)
    text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')
    # Normalize excessive whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def process_image_pil(img: Image.Image) -> dict:
    # Get verbose data from Tesseract to access confidence scores
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    valid_confidences = [int(conf) for conf in data['conf'] if int(conf) != -1]
    
    avg_conf = 0
    if valid_confidences:
        avg_conf = sum(valid_confidences) / len(valid_confidences)
    
    # Extract plain text
    raw_text = pytesseract.image_to_string(img)
    cleaned_text = clean_ocr_artifacts(raw_text)

    # Configurable threshold for low quality (e.g., 70%)
    is_low_quality = avg_conf < 70

    return {
        "data": cleaned_text, 
        "confidence": avg_conf, 
        "low_quality": is_low_quality
    }

def process_image(file_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(file_bytes))
    result = process_image_pil(img)
    return {"data": [{"type": "ocr_text", "content": result["data"]}], "low_quality": result["low_quality"]}