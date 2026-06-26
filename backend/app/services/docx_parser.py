import io
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from PIL import Image
import pytesseract

from app.models import Page, Paragraph, Heading, Table, ListGroup, OcrText, NormalizedDocument

def iter_block_items(parent):
    """Yields each paragraph and table child within *parent*, in true document order."""
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Unsupported parent type for XML traversal")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield DocxParagraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield DocxTable(child, parent)

def parse_table(table: DocxTable) -> Table:
    rows = []
    headers = []
    
    for i, row in enumerate(table.rows):
        row_data = [cell.text.strip() for cell in row.cells]
        if i == 0 and len(table.rows) > 1:
            headers = row_data
        else:
            rows.append(row_data)
            
    return Table(headers=headers, rows=rows, confidence=100.0)

def process_docx_image(image_bytes: bytes) -> tuple[list, bool]:
    """Runs Tesseract OCR on an extracted image from a DOCX file."""
    img = Image.open(io.BytesIO(image_bytes))
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    blocks_dict = {}
    low_quality = False
    
    for i, word in enumerate(ocr_data['text']):
        if not word.strip(): continue
        
        conf = float(ocr_data['conf'][i])
        if conf < 70.0: low_quality = True
            
        b_num, p_num = ocr_data['block_num'][i], ocr_data['par_num'][i]
        key = (b_num, p_num)
        
        if key not in blocks_dict:
            blocks_dict[key] = {'text': [], 'conf': []}
            
        blocks_dict[key]['text'].append(word)
        blocks_dict[key]['conf'].append(conf)

    elements = []
    for key in sorted(blocks_dict.keys()):
        block = blocks_dict[key]
        text = " ".join(block['text'])
        avg_conf = sum(block['conf']) / len(block['conf'])
        
        # We don't have absolute page coordinates in DOCX, so bbox remains None
        if text.startswith(("•", "-", "*", "1.")):
            elements.append(ListGroup(items=[text], confidence=avg_conf))
        else:
            elements.append(OcrText(text=text, confidence=avg_conf))
            
    return elements, low_quality

def process_docx(file_bytes: bytes, filename: str) -> NormalizedDocument:
    doc = docx.Document(io.BytesIO(file_bytes))
    
    pages = []
    current_elements = []
    page_num = 1
    ELEMENTS_PER_PAGE = 50 
    
    doc_ocr_used = False
    doc_low_quality = False

    for block in iter_block_items(doc):
        if isinstance(block, DocxTable):
            current_elements.append(parse_table(block))
            
        elif isinstance(block, DocxParagraph):
            # --- 1. Process standard digital text ---
            text = block.text.strip()
            if text:
                style_name = block.style.name if block.style else ""
                
                # Check for Word's hidden XML bullets
                has_numbering = False
                if block._p.pPr is not None and block._p.pPr.numPr is not None:
                    has_numbering = True
                
                if style_name.startswith('Heading'):
                    try:
                        level = int(style_name.split(' ')[-1])
                    except ValueError:
                        level = 1
                    current_elements.append(Heading(text=text, level=level, confidence=100.0))
                    
                elif 'List' in style_name or text.startswith(("•", "-", "1.", "a)", "*")) or has_numbering:
                    clean_text = text.lstrip("•- * \t")
                    if current_elements and current_elements[-1].type == "list":
                        current_elements[-1].items.append(clean_text)
                    else:
                        current_elements.append(ListGroup(items=[clean_text], confidence=100.0))
                        
                else:
                    current_elements.append(Paragraph(text=text, confidence=100.0))
            
            # --- 2. Hunt for embedded images in this paragraph's XML ---
            # Define Microsoft's standard XML namespaces explicitly to avoid 'prefix not found' errors
            DOCX_NAMESPACES = {
                'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            }
            
            # Search the paragraph's XML tree for drawing tags using the explicit namespaces
            for drawing in block._p.findall('.//w:drawing', namespaces=DOCX_NAMESPACES):
                for blip in drawing.findall('.//a:blip', namespaces=DOCX_NAMESPACES):
                    # Extract the Relationship ID (rId)
                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    
                    if rId and rId in doc.part.related_parts:
                        # Grab the actual image bytes from the zipped document structure
                        image_part = doc.part.related_parts[rId]
                        image_bytes = image_part.blob
                        
                        # Run our OCR pipeline on the extracted bytes
                        ocr_elements, is_low_quality = process_docx_image(image_bytes)
                        
                        if ocr_elements:
                            doc_ocr_used = True
                            if is_low_quality:
                                doc_low_quality = True
                            # Append the OCR'd text directly into the document flow
                            current_elements.extend(ocr_elements)
                
        # Batch into a Page object when the limit is reached
        if len(current_elements) >= ELEMENTS_PER_PAGE:
            pages.append(Page(number=page_num, elements=current_elements, requires_ocr=doc_ocr_used))
            page_num += 1
            current_elements = []

    if current_elements:
        pages.append(Page(number=page_num, elements=current_elements, requires_ocr=doc_ocr_used))
        
    return NormalizedDocument(
        filename=filename,
        pages=pages,
        ocr_used=doc_ocr_used,
        low_quality=doc_low_quality
    )