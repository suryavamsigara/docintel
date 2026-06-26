import re
import fitz
import pymupdf4llm
import pytesseract
from PIL import Image
from app.models import Page, Paragraph, Heading, Table, ListGroup, OcrText, NormalizedDocument

def clean_markdown(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)

    # Remove trailing spaces but preserve line breaks
    text = "\n".join(line.strip() for line in text.splitlines())

    return text.strip()

def process_pdf(file_bytes: bytes, filename: str) -> NormalizedDocument:
    """
    Parses a PDF using PyMuPDF's advanced layout engine, augmented with targeted 
    high-DPI Tesseract OCR for embedded images in "Fake Digital" PDFs.
    Returns a complete NormalizedDocument.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    pages = []
    doc_ocr_used = False
    doc_low_quality = False
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # --- 1. Detect "Fake Digital" Trap ---
        raw_text = page.get_text("text").strip()
        digital_text_len = len(raw_text)
        page_area = page.rect.width * page.rect.height
        
        should_run_custom_ocr = False
        if digital_text_len < 100 and len(page.get_images()) > 0:
            should_run_custom_ocr = True
            
            # Safeguard: Check if it's a "Searchable PDF" (digital text mapped over an image)
            for img_info in page.get_image_info(xrefs=True):
                bbox = img_info["bbox"]
                img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if img_area > (page_area * 0.8) and digital_text_len > 100:
                    should_run_custom_ocr = False
                    break

        # --- 2. Extract Superior Digital Layout via pymupdf4llm ---
        elements = []
        list_buffer = []
        list_bbox = None
        chunk_list = pymupdf4llm.to_markdown(doc, pages=[page_num], page_chunks=True)
        
        if chunk_list:
            chunk = chunk_list[0]
            md_text = chunk.get("text", "")
            
            for box in chunk.get("page_boxes", []):
                start, stop = box.get("pos", (0, 0))
                raw_box_text = md_text[start:stop].strip()

                if not raw_box_text:
                    continue

                bbox = tuple(box.get("bbox", [0, 0, 0, 0]))
                box_class = box.get("class", "text")

                # Flush buffered list if we reached another element
                if box_class != "list-item" and list_buffer:
                    elements.append(
                        ListGroup(
                            bbox=list_bbox,
                            items=list_buffer
                        )
                    )
                    list_buffer = []
                    list_bbox = None

                if box_class == "section-header":
                    clean_text = clean_markdown(raw_box_text)

                    level = 1
                    if raw_box_text.startswith("#"):
                        level = min(len(raw_box_text.split()[0]), 6)

                    elements.append(
                        Heading(
                            bbox=bbox,
                            text=clean_text,
                            level=level
                        )
                    )

                elif box_class == "table":
                    lines = [
                        line.strip()
                        for line in raw_box_text.split("\n")
                        if line.strip()
                    ]

                    headers = []
                    rows = []

                    if len(lines) >= 3 and "|" in lines[0]:

                        headers = [
                            clean_markdown(col.strip())
                            for col in lines[0].split("|")[1:-1]
                        ]

                        for row_line in lines[2:]:

                            if (
                                "---" in row_line
                                and set(row_line.replace("|", "").replace("-", "").strip()) == set()
                            ):
                                continue

                            if "|" in row_line:
                                rows.append([
                                    clean_markdown(col.strip())
                                    for col in row_line.split("|")[1:-1]
                                ])

                    elements.append(
                        Table(
                            bbox=bbox,
                            headers=headers,
                            rows=rows
                        )
                    )

                elif box_class == "list-item":

                    if list_bbox is None:
                        list_bbox = bbox

                    clean_text = clean_markdown(
                        raw_box_text.lstrip("*-• ")
                    )

                    list_buffer.append(clean_text)

                else:

                    elements.append(
                        Paragraph(
                            bbox=bbox,
                            text=clean_markdown(raw_box_text)
                        )
                    )

            # Flush trailing list
            if list_buffer:
                elements.append(
                    ListGroup(
                        bbox=list_bbox,
                        items=list_buffer
                    )
                )

        # --- 3. Augment with High-DPI Targeted Image OCR ---
        page_low_quality = False
        if should_run_custom_ocr:
            doc_ocr_used = True
            for img_info in page.get_image_info(xrefs=True):
                bbox = img_info["bbox"]
                rect = fitz.Rect(bbox)
                
                if rect.is_empty or rect.is_infinite: continue

                # Crop to exact image boundaries and upscale 3x (~216 DPI)
                mat = fitz.Matrix(3, 3) 
                pix = page.get_pixmap(clip=rect, matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                blocks_dict = {}
                for i, word in enumerate(ocr_data['text']):
                    if not word.strip(): continue
                    
                    conf = float(ocr_data['conf'][i])
                    if conf < 70.0: 
                        page_low_quality = True
                        doc_low_quality = True
                        
                    b_num, p_num = ocr_data['block_num'][i], ocr_data['par_num'][i]
                    key = (b_num, p_num)
                    
                    if key not in blocks_dict:
                        blocks_dict[key] = {'text': [], 'conf': [], 'bbox': [9999, 9999, 0, 0]}
                        
                    # Reverse the 3x scale and align to the PDF page coordinates
                    x = (ocr_data['left'][i] / 3.0) + rect.x0
                    y = (ocr_data['top'][i] / 3.0) + rect.y0
                    w = ocr_data['width'][i] / 3.0
                    h = ocr_data['height'][i] / 3.0
                    
                    blocks_dict[key]['text'].append(word)
                    blocks_dict[key]['conf'].append(conf)
                    blocks_dict[key]['bbox'][0] = min(blocks_dict[key]['bbox'][0], x)
                    blocks_dict[key]['bbox'][1] = min(blocks_dict[key]['bbox'][1], y)
                    blocks_dict[key]['bbox'][2] = max(blocks_dict[key]['bbox'][2], x + w)
                    blocks_dict[key]['bbox'][3] = max(blocks_dict[key]['bbox'][3], y + h)

                for key, block in blocks_dict.items():
                    text = " ".join(block['text'])
                    avg_conf = sum(block['conf']) / len(block['conf'])
                    el_bbox = tuple(block['bbox'])
                    
                    if text.startswith(("•", "-", "*", "1.")):
                        elements.append(ListGroup(bbox=el_bbox, items=[text], confidence=avg_conf))
                    else:
                        elements.append(OcrText(bbox=el_bbox, text=text, confidence=avg_conf))

                # Free up memory explicitly to satisfy Railway limits
                del pix
                del img

        if should_run_custom_ocr:
             elements.sort(key=lambda e: (e.bbox[1] if e.bbox else 0, e.bbox[0] if e.bbox else 0))

        pages.append(Page(
            number=page_num + 1,
            elements=elements,
            requires_ocr=should_run_custom_ocr,
            low_quality=page_low_quality
        ))
        
        page = None
        
    doc.close()
    
    metadata = {}
    if doc_low_quality:
        metadata["warning"] = "Low OCR confidence detected in some parts of the document. Flagged for review."
        
    return NormalizedDocument(
        filename=filename,
        pages=pages,
        ocr_used=doc_ocr_used,
        low_quality=doc_low_quality,
        metadata=metadata
    )