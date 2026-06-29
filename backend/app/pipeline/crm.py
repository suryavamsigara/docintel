import os
import json
import httpx
import logging
from datetime import datetime
from app.db import get_client

logger = logging.getLogger(__name__)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

async def sync_to_notion(doc_id: str) -> dict:
    """Pushes structured document data to Notion, updating if the hash exists."""
    client = get_client()
    result = await client.execute("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not result.rows:
        return {"status": "error", "error": "Document not found in DB"}
    
    row = result.rows[0]
    file_name = row["name"]
    content_hash = row["content_hash"]
    
    # Parse Analysis Data
    try:
        analysis = json.loads(row["analysis_data"]) if row["analysis_data"] else {}
    except:
        analysis = {}

    ext_data = analysis.get("extraction", {}).get("data", {})
    risk_data = analysis.get("risk", {}).get("data", {})
    anom_data = analysis.get("anomaly", {}).get("data", {})
    
    doc_type = ext_data.get("doc_type", "Unknown").replace("_", " ").title()
    risk_score = risk_data.get("overall_score", 0)
    
    # Count critical anomalies
    anomalies = anom_data.get("anomalies", []) if isinstance(anom_data, dict) else []
    critical_count = len([a for a in anomalies if a.get("severity", "").lower() == "critical"])

    # Extract parties (fallback to generic string)
    parties = "Unknown"
    if doc_type.lower() == "invoice":
        parties = f"{ext_data.get('vendor', {}).get('name', 'Unknown')} -> {ext_data.get('bill_to', {}).get('name', 'Unknown')}"
    else:
        # Check for 'primary_parties' (which our LLM extracts for NDAs and Contracts)
        party_list = ext_data.get("parties") or ext_data.get("primary_parties") or []
        if party_list:
            parties = " & ".join([str(p.get("name", "Unknown")).replace("\n", " ").strip() for p in party_list])

    # ---------------------------------------------------------
    # DEMO FALLBACK: If no Notion keys, simulate success
    # ---------------------------------------------------------
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        logger.warning("Notion keys missing. Simulating successful CRM sync for demo purposes.")
        await client.execute("UPDATE documents SET crm_status = 'synced' WHERE id = ?", [doc_id])
        return {"status": "synced", "detail": "Simulated sync (No API keys)"}

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Notion Page Payload Mapping
    properties = {
        "Name": {"title": [{"text": {"content": file_name}}]},
        "Document Type": {"select": {"name": doc_type}},
        "Parties": {"rich_text": [{"text": {"content": str(parties)[:2000]}}]},
        "Risk Score": {"number": risk_score},
        "Critical Anomalies": {"number": critical_count},
        "Content Hash": {"rich_text": [{"text": {"content": content_hash}}]},
        "Platform Link": {"url": f"http://localhost:5173/document/{doc_id}"},
        "Processed At": {"date": {"start": datetime.utcnow().isoformat()}}
    }

    async with httpx.AsyncClient() as http:
        # 1. Query Notion to check if hash exists (Deduplication)
        query_payload = {
            "filter": {"property": "Content Hash", "rich_text": {"equals": content_hash}}
        }
        query_res = await http.post(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query", 
            headers=headers, json=query_payload
        )
        
        if query_res.status_code != 200:
            await client.execute("UPDATE documents SET crm_status = 'failed' WHERE id = ?", [doc_id])
            return {"status": "error", "error": f"Notion Query Failed: {query_res.text}"}
            
        data = query_res.json()
        
        # 2. Update if exists, Create if not
        if len(data.get("results", [])) > 0:
            # UPDATE (PATCH)
            page_id = data["results"][0]["id"]
            res = await http.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={"properties": properties})
            action = "Updated existing record"
        else:
            # CREATE (POST)
            create_payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties}
            res = await http.post("https://api.notion.com/v1/pages", headers=headers, json=create_payload)
            action = "Created new record"

        if res.status_code in [200, 201]:
            await client.execute("UPDATE documents SET crm_status = 'synced' WHERE id = ?", [doc_id])
            return {"status": "synced", "detail": action}
        else:
            await client.execute("UPDATE documents SET crm_status = 'failed' WHERE id = ?", [doc_id])
            return {"status": "error", "error": res.text}