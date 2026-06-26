import io
import pandas as pd
from app.models import Page, Table, NormalizedDocument

def process_excel(file_bytes: bytes, filename: str) -> NormalizedDocument:
    """
    Parses both modern (.xlsx) and legacy (.xls) Excel files.
    Automatically filters out chart-only or low-density metadata sheets.
    """
    # pd.ExcelFile automatically detects .xls vs .xlsx and uses the right engine (xlrd vs openpyxl)
    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Failed to read Excel file. Ensure it is a valid .xls or .xlsx format. Error: {str(e)}")

    pages = []
    page_num = 1
    metadata = {"skipped_sheets": []}
    
    for sheet_name in xls.sheet_names:
        # Parse the specific sheet
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Drop completely empty rows and columns
        df = df.dropna(how="all").dropna(axis=1, how="all")
        
        # --- Filter Heuristic ---
        # Pandas ignores charts. If a sheet was just a chart, df will be empty.
        # If df is empty, it contains no tabular data.
        if df.empty:
            metadata["skipped_sheets"].append({"name": sheet_name, "reason": "empty, chart-only, or non-tabular metadata"})
            continue
            
        # Clean up remaining NaNs so they parse nicely into JSON for the frontend
        df = df.fillna("") 
        
        # Convert to our Pydantic schema
        headers = list(map(str, df.columns.tolist()))
        # Force every cell to be a string to satisfy Pydantic's strict type validation
        rows = [[str(cell) for cell in row] for row in df.values.tolist()]
        
        elements = [Table(headers=headers, rows=rows, confidence=100.0)]
        
        pages.append(Page(number=page_num, elements=elements, requires_ocr=False, low_quality=False))
        page_num += 1
        
    return NormalizedDocument(
        filename=filename,
        pages=pages,
        ocr_used=False,
        low_quality=False,
        metadata=metadata
    )