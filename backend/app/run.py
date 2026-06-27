from app.pipeline.ingestion import run_ingestion_stage
from app.pipeline.classification import run_classification_stage
from app.pipeline.extraction import run_extraction_stage


# --- Local Testing Block ---
if __name__ == "__main__":
    import asyncio
    from pathlib import Path
    
    class MockUploadFile:
        def __init__(self, path: Path):
            self.path = path
            self.filename = path.name
            
        async def read(self):
            with open(self.path, "rb") as f:
                return f.read()
                
        async def close(self):
            pass

    async def run_test():
        # Adjust path as necessary to point to your test documents
        root = Path(__file__).parent.parent.parent
        file_path = root / 'docs' / 'contract.pdf' 
        
        if not file_path.exists():
            print(f"❌ Test file not found: {file_path}")
            print("Please ensure the directory structure is correct or change the path.")
            return
            
        mock_file = MockUploadFile(file_path)
        
        print(f"🚀 Starting ingestion pipeline for: {mock_file.filename}\n" + "-"*50)
        
        try:
            # Wait for the entire ingestion stage to complete
            ingestion_result = await run_ingestion_stage(mock_file)
            doc_data = ingestion_result["data"]
            
            print(f"✅ Ingestion Stage Complete!")
            print(f"📄 Filename: {ingestion_result['filename']}")
            print(f"📑 Total Pages: {len(doc_data['pages'])}")
            print(f"🔍 OCR Used: {doc_data['ocr_used']}")
            print(f"⚠️ Low Quality Flag: {doc_data['low_quality']}")
            
            if doc_data['pages']:
                print(f"🧩 Elements on Page 1: {len(doc_data['pages'][0]['elements'])}")
                # print(f"Pages: {doc_data['pages']}")

            print(f"\n============================================\n")
            print("\nStarting classification...\n")
            classification_result = await asyncio.to_thread(run_classification_stage, doc_data)
            print(f"✅ Classification Stage Complete!")
            print(classification_result['data'])
            print(f"\n============================================\n")

            
            print("Running extraction..\n")
            ext_result = await asyncio.to_thread(run_extraction_stage, doc_data, classification_result["data"])
            print(ext_result['data'])
            print(f"\n============================================\n")
            

                
        except Exception as e:
            print(f"❌ Pipeline failed: {str(e)}")
            
    asyncio.run(run_test())

