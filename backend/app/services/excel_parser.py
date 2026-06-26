import io
import pandas as pd

def process_excel(file_bytes: bytes) -> dict:
    structured_content = []
    
    # Read all sheets
    excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
    
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        # Skip empty sheets (metadata/chart-only sheets often read as empty DataFrames)
        if df.empty:
            continue
            
        # Drop completely empty rows and columns to clean the data
        df.dropna(how='all', inplace=True)
        df.dropna(axis=1, how='all', inplace=True)
        
        # Convert to dictionary format (list of records)
        # NaN values are replaced with None for JSON compatibility
        records = df.where(pd.notnull(df), None).to_dict(orient='records')
        
        structured_content.append({
            "type": "worksheet",
            "sheet_name": sheet_name,
            "content": records
        })
        
    return {"data": structured_content, "low_quality": False}