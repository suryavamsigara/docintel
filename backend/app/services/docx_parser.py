import io
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

from app.models import Page, Paragraph, Heading, Table, ListGroup, DocumentElement, NormalizedDocument

def iter_block_items(parent):
    """
    Advanced XML traversal: Yields each paragraph and table child within *parent*, 
    in true document order. This solves the classic python-docx issue where 
    tables and paragraphs are extracted separately and lose their context.
    """
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
    """Extracts rows and columns from a DOCX table into our Pydantic schema."""
    rows = []
    headers = []
    
    for i, row in enumerate(table.rows):
        row_data = [cell.text.strip() for cell in row.cells]
        
        # Assume first row is header if the table has more than 1 row
        if i == 0 and len(table.rows) > 1:
            headers = row_data
        else:
            rows.append(row_data)
            
    return Table(headers=headers, rows=rows, confidence=100.0)

def process_docx(file_bytes: bytes, filename: str) -> NormalizedDocument:
    """
    Parses a DOCX file while preserving document structure (Headings, Lists, Tables, Paragraphs).
    Returns a complete NormalizedDocument ready for the next pipeline stage.
    """
    doc = docx.Document(io.BytesIO(file_bytes))
    
    pages = []
    current_elements = []
    page_num = 1
    
    # Virtual Pagination limit: Batch elements into logical "Pages" of 50 items
    # Since Word is a flowing document, this simply prevents giant single arrays.
    ELEMENTS_PER_PAGE = 50 

    for block in iter_block_items(doc):
        
        # Handle Tables
        if isinstance(block, DocxTable):
            current_elements.append(parse_table(block))
            
        # Handle Text (Paragraphs, Headings, Lists)
        elif isinstance(block, DocxParagraph):
            text = block.text.strip()
            if not text:
                continue
                
            style_name = block.style.name if block.style else ""
            
            # --- NEW: Check for XML numbering properties (Word's built-in bullets) ---
            has_numbering = False
            pPr = block._p.pPr
            if pPr is not None and pPr.numPr is not None:
                has_numbering = True
            
            # --- Structure Classification Heuristics ---
            
            # 1. Headings
            if style_name.startswith('Heading'):
                try:
                    level = int(style_name.split(' ')[-1])
                except ValueError:
                    level = 1
                current_elements.append(Heading(text=text, level=level, confidence=100.0))
                
            # 2. Lists (Now checks for explicit bullets, 'List' styles, or XML numPr tags)
            elif 'List' in style_name or text.startswith(("•", "-", "1.", "a)", "*")) or has_numbering:
                clean_text = text.lstrip("•- * \t")
                if current_elements and current_elements[-1].type == "list":
                    current_elements[-1].items.append(clean_text)
                else:
                    current_elements.append(ListGroup(items=[clean_text], confidence=100.0))
                    
            # 3. Standard Paragraphs
            else:
                current_elements.append(Paragraph(text=text, confidence=100.0))
                
        # Batch into a Page object when the limit is reached
        if len(current_elements) >= ELEMENTS_PER_PAGE:
            pages.append(Page(
                number=page_num,
                elements=current_elements,
                requires_ocr=False,
                low_quality=False
            ))
            page_num += 1
            current_elements = []

    # Catch the remaining elements at the end
    if current_elements:
        pages.append(Page(
            number=page_num,
            elements=current_elements,
            requires_ocr=False,
            low_quality=False
        ))
        
    return NormalizedDocument(
        filename=filename,
        pages=pages,
        ocr_used=False,
        low_quality=False,
        metadata={"source": "docx"}
    )