import fitz
import pymupdf4llm
import pytesseract
from PIL import Image
from typing import Iterator
from app.models import Page, Paragraph, Heading, Table, ListGroup, OcrText

def process_pdf_stream(file_bytes: bytes, filename: str) -> Iterator[Page]:
    """
    Generator that yields one processed Page at a time using PyMuPDF's 
    advanced layout engine (pymupdf4llm), augmented with targeted high-DPI 
    Tesseract OCR for embedded images in "Fake Digital" PDFs.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # --- 1. Detect "Fake Digital" Trap ---
        # If there is very little digital text but images exist, it's likely a scan
        # with a small digital artifact (like "Hello").
        raw_text = page.get_text("text").strip()
        digital_text_len = len(raw_text)
        page_area = page.rect.width * page.rect.height
        
        should_run_custom_ocr = False
        if digital_text_len < 100 and len(page.get_images()) > 0:
            should_run_custom_ocr = True
            
            # Smart safeguard: Check if it's a "Searchable PDF" (digital text mapped over an image)
            for img_info in page.get_image_info(xrefs=True):
                bbox = img_info["bbox"]
                img_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if img_area > (page_area * 0.8) and digital_text_len > 100:
                    should_run_custom_ocr = False
                    break

        # --- 2. Extract Superior Digital Layout via pymupdf4llm ---
        elements = []
        chunk_list = pymupdf4llm.to_markdown(doc, pages=[page_num], page_chunks=True)
        
        if chunk_list:
            chunk = chunk_list[0]
            md_text = chunk.get("text", "")
            
            for box in chunk.get("page_boxes", []):
                start, stop = box.get("pos", (0, 0))
                box_text = md_text[start:stop].strip()
                
                if not box_text:
                    continue
                    
                bbox = tuple(box.get("bbox", [0, 0, 0, 0]))
                box_class = box.get("class", "text")
                
                if box_class == "section-header":
                    level = 1
                    if box_text.startswith("#"):
                        level = min(len(box_text.split()[0]), 6)
                        box_text = box_text.lstrip("# \t")
                    elements.append(Heading(bbox=bbox, text=box_text, level=level))
                    
                elif box_class == "table":
                    lines = [line.strip() for line in box_text.split('\n') if line.strip()]
                    headers = []
                    rows = []
                    
                    if len(lines) >= 3 and "|" in lines[0]:
                        headers = [col.strip() for col in lines[0].split("|")[1:-1]]
                        for row_line in lines[2:]: 
                            if "---" in row_line and set(row_line.replace("|", "").replace("-", "").strip()) == set():
                                continue
                            if "|" in row_line:
                                rows.append([col.strip() for col in row_line.split("|")[1:-1]])
                                
                    elements.append(Table(bbox=bbox, headers=headers, rows=rows))
                    
                elif box_class == "list-item":
                    clean_text = box_text.lstrip("* -")
                    elements.append(ListGroup(bbox=bbox, items=[clean_text]))
                    
                else:
                    elements.append(Paragraph(bbox=bbox, text=box_text))

        # --- 3. Augment with High-DPI Targeted Image OCR ---
        low_quality = False
        if should_run_custom_ocr:
            for img_info in page.get_image_info(xrefs=True):
                bbox = img_info["bbox"]
                rect = fitz.Rect(bbox)
                
                if rect.is_empty or rect.is_infinite: continue

                # Crop to exact image boundaries and upscale 3x (~216 DPI) for Tesseract clarity
                mat = fitz.Matrix(3, 3) 
                pix = page.get_pixmap(clip=rect, matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                blocks_dict = {}
                for i, word in enumerate(ocr_data['text']):
                    if not word.strip(): continue
                    
                    conf = float(ocr_data['conf'][i])
                    if conf < 70.0: low_quality = True
                        
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

                del pix
                del img

        # Stitch everything (Digital + Image text) back together in top-to-bottom reading order
        if should_run_custom_ocr:
             elements.sort(key=lambda e: (e.bbox[1] if e.bbox else 0, e.bbox[0] if e.bbox else 0))

        # Stream it instantly to the router
        yield Page(
            number=page_num + 1,
            elements=elements,
            requires_ocr=should_run_custom_ocr,
            low_quality=low_quality
        )
        
        page = None
        
    doc.close()





















































"""
import fitz
import pymupdf4llm
from typing import Iterator
from app.models import Page, Paragraph, Heading, Table, ListGroup

def process_pdf_stream(file_bytes: bytes, filename: str) -> Iterator[Page]:
    ""
    # Generator that yields one processed Page at a time using PyMuPDF's 
    # advanced layout engine (pymupdf4llm + pymupdf_layout).
    ""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # We iterate page by page to maintain the WebSocket real-time streaming requirement!
    for page_num in range(len(doc)):
        
        # to_markdown with page_chunks=True invokes the advanced layout engine
        # It automatically handles hybrid OCR if it detects scanned images!
        chunk_list = pymupdf4llm.to_markdown(doc, pages=[page_num], page_chunks=True)
        
        if not chunk_list:
            continue
            
        chunk = chunk_list[0]
        md_text = chunk.get("text", "")
        elements = []
        
        # page_boxes contains the precise semantic reading order (Columns, Abstracts, etc.)
        for box in chunk.get("page_boxes", []):
            start, stop = box.get("pos", (0, 0))
            box_text = md_text[start:stop].strip()
            
            if not box_text:
                continue
                
            bbox = tuple(box.get("bbox", [0, 0, 0, 0]))
            box_class = box.get("class", "text")
            
            # Map the layout engine's classification back to your Pydantic Models
            if box_class == "section-header":
                level = 1
                if box_text.startswith("#"):
                    # Count the markdown hashes to determine heading level
                    level = min(len(box_text.split()[0]), 6)
                    box_text = box_text.lstrip("# \t")
                elements.append(Heading(bbox=bbox, text=box_text, level=level))
                
            elif box_class == "table":
                # Convert the GitHub Flavored Markdown table back to our Table schema
                lines = [line.strip() for line in box_text.split('\n') if line.strip()]
                headers = []
                rows = []
                
                if len(lines) >= 3 and "|" in lines[0]:
                    headers = [col.strip() for col in lines[0].split("|")[1:-1]]
                    for row_line in lines[2:]: 
                        # Skip the markdown table separator line (e.g., ---|---)
                        if "---" in row_line and set(row_line.replace("|", "").replace("-", "").strip()) == set():
                            continue
                        if "|" in row_line:
                            rows.append([col.strip() for col in row_line.split("|")[1:-1]])
                            
                elements.append(Table(bbox=bbox, headers=headers, rows=rows))
                
            elif box_class == "list-item":
                # Clean up markdown list bullets
                clean_text = box_text.lstrip("* -")
                elements.append(ListGroup(bbox=bbox, items=[clean_text]))
                
            else:
                elements.append(Paragraph(bbox=bbox, text=box_text))

        # Stream it instantly to the router
        yield Page(
            number=page_num + 1,
            elements=elements,
            requires_ocr=False, # Hybrid OCR is now handled automatically inside to_markdown
            low_quality=False
        )
        
    doc.close()
"""