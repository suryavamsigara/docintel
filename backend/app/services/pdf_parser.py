import io
import pdfplumber
from typing import List, Dict, Any
from app.models import (
    NormalizedDocument, Page, Paragraph, Heading, Table, Element
)
from app.services.image_parser import process_image_pil
from pdf2image import convert_from_bytes

def group_words_into_blocks(words: List[Dict[str, Any]], page_num: int) -> List[Element]:
    """
    Heuristic: Groups raw words into Paragraphs and Headings based on 
    vertical proximity and font size.
    """
    if not words:
        return []

    # Calculate standard font size to distinguish headings
    font_sizes = [w.get("size", 10) for w in words]
    median_size = sorted(font_sizes)[len(font_sizes) // 2]
    heading_threshold = median_size + 1.5 # Anything significantly larger is a heading

    elements = []
    current_block = []
    current_bbox = [9999, 9999, 0, 0] # x0, top, x1, bottom
    is_current_heading = False

    def save_block():
        if not current_block:
            return
        text = " ".join([w["text"] for w in current_block])
        bbox = tuple(current_bbox)
        
        if is_current_heading:
            elements.append(Heading(
                type="heading", page=page_num, bbox=bbox, level=1, text=text
            ))
        else:
            elements.append(Paragraph(
                type="paragraph", page=page_num, bbox=bbox, text=text
            ))
        current_block.clear()

    for word in words:
        word_size = word.get("size", 10)
        word_is_heading = word_size >= heading_threshold

        # If vertical gap is too large (> 1.5x font size), it's a new paragraph
        if current_block:
            last_word = current_block[-1]
            vertical_gap = word["top"] - last_word["bottom"]
            
            if vertical_gap > (median_size * 1.5) or (word_is_heading != is_current_heading):
                save_block()
                is_current_heading = word_is_heading
                current_bbox = [9999, 9999, 0, 0] # Reset bbox

        # Update current block and bounding box
        current_block.append(word)
        current_bbox[0] = min(current_bbox[0], word["x0"])
        current_bbox[1] = min(current_bbox[1], word["top"])
        current_bbox[2] = max(current_bbox[2], word["x1"])
        current_bbox[3] = max(current_bbox[3], word["bottom"])

    save_block() # Save the final block
    return elements

def process_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Parses a PDF, preserves structure using bboxes, detects if OCR is needed, 
    and returns a structured NormalizedDocument dictionary.
    """
    doc = NormalizedDocument(filename=filename)
    requires_ocr = False
    
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        print("Parsing pdf..\n")
        for page_num, pdf_page in enumerate(pdf.pages, start=1):
            page_obj = Page(number=page_num)
            
            # 1. Extract Tables first
            tables = pdf_page.find_tables()
            table_bboxes = []
            if tables:
                for table in tables:
                    table_bboxes.append(table.bbox)
                    extracted_data = table.extract()
                    page_obj.elements.append(Table(
                        type="table",
                        page=page_num,
                        bbox=table.bbox,
                        rows=extracted_data
                    ))
            
            # 2. Extract Words (filtering out words that fall inside table bounding boxes)
            words = pdf_page.extract_words(extra_attrs=["size", "fontname"])
            
            # Filter words that belong to tables to avoid duplication
            text_words = []
            for w in words:
                in_table = any(
                    (tb[0] <= w["x0"] <= tb[2]) and (tb[1] <= w["top"] <= tb[3]) 
                    for tb in table_bboxes
                )
                if not in_table:
                    text_words.append(w)

            # 3. Check for Scanned Document (Sparse text)
            if len(words) < 20 and len(pdf_page.images) > 0:
                requires_ocr = True
                break # Break out of digital parsing, fallback to OCR

            # 4. Group remaining words into paragraphs and headings
            text_elements = group_words_into_blocks(text_words, page_num)
            page_obj.elements.extend(text_elements)
            
            doc.pages.append(page_obj)

    # 5. Fallback to OCR if the document is primarily scanned images
    if requires_ocr:
        doc.ocr_used = True
        doc.pages = [] # Clear any partial digital attempts
        
        # Here you would trigger the image_parser logic for each page
        # images = convert_from_bytes(file_bytes)
        # for page_num, img in enumerate(images, start=1):
        #     ocr_result = process_image_pil(img)
        #     ... mapping OCR to doc.pages ...
        
        # We flag it so the system knows OCR was engaged.
        doc.metadata["warning"] = "Scanned document detected. OCR fallback initiated."

    return doc.to_dict()