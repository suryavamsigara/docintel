import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

def _parse_date(d_str):
    """Robust fallback date parser for strings like '15-Jun-2026'."""
    if not d_str: return None
    clean_str = re.sub(r'[^0-9a-zA-Z]', '-', str(d_str)).strip('-')
    for fmt in ["%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%B-%Y", "%B-%d--%Y"]:
        try:
            return datetime.strptime(clean_str, fmt)
        except:
            pass
    return None

async def run_cross_document_stage(current_doc_id: str, current_doc_name: str, project_id: str, current_ext_data: dict, get_client) -> dict:
    """Stage 5: Cross-Document Contradiction Detection"""
    try:
        client = get_client()
        # Fetch sibling documents from the same project
        result = await client.execute(
            "SELECT id, name, analysis_data FROM documents WHERE project_id = ? AND status = 'completed'",
            [project_id]
        )

        siblings = []
        for row in result.rows:
            if row["id"] == current_doc_id: continue
            if not row["analysis_data"]: continue
            try:
                data = json.loads(row["analysis_data"])
                ext = data.get("extraction", {}).get("data", {})
                siblings.append({"id": row["id"], "name": row["name"], "extraction": ext})
            except:
                pass

        # Requirement: "Only runs when more than one document exists"
        if not siblings:
            return {"stage": "cross_document", "status": "skipped", "data": {"contradictions": []}}

        contradictions = []
        # Combine siblings with current document for aggregate analysis
        all_docs = siblings + [{"id": current_doc_id, "name": current_doc_name, "extraction": current_ext_data}]

        contracts = [d for d in all_docs if d["extraction"].get("doc_type") in ["contract", "nda"]]
        invoices = [d for d in all_docs if d["extraction"].get("doc_type") == "invoice"]
        financials = [d for d in all_docs if d["extraction"].get("doc_type") == "financial_statement"]

        # ---------------------------------------------------------
        # RULE 1: Contract Payment Terms vs Invoice Due Dates
        # ---------------------------------------------------------
        for contract in contracts:
            clauses = contract["extraction"].get("extraction", {}).get("clauses", [])
            pt_clause = next((c for c in clauses if c["clause_type"] == "payment_terms" and c["status"] == "present"), None)
            if not pt_clause: continue

            pt_match = re.search(r'(\d+)\s*days', str(pt_clause.get("value", "")).lower())
            if not pt_match: continue
            contract_days = int(pt_match.group(1))

            for invoice in invoices:
                inv_data = invoice["extraction"].get("extraction", {})
                i_date = _parse_date(inv_data.get("invoice_date"))
                d_date = _parse_date(inv_data.get("due_date"))
                
                if i_date and d_date:
                    delta = (d_date - i_date).days
                    if delta > contract_days:
                        # Only flag if the current document is involved in this contradiction
                        if current_doc_id in [contract["id"], invoice["id"]]:
                            contradictions.append({
                                "title": "Payment Terms Violation",
                                "description": f"The invoice demands payment in {delta} days, but the governing contract mandates a {contract_days}-day term.",
                                "doc1_name": contract["name"],
                                "doc1_value": f"{contract_days} days",
                                "doc2_name": invoice["name"],
                                "doc2_value": f"{delta} days"
                            })

        # ---------------------------------------------------------
        # RULE 2: Financial Statement Revenue vs Sum of Invoices
        # ---------------------------------------------------------
        for fin in financials:
            fin_data = fin["extraction"].get("extraction", {})
            revenue = fin_data.get("income_statement", {}).get("revenue")
            
            if revenue is not None and invoices:
                revenue = float(revenue)
                sum_inv = sum(float(inv["extraction"].get("extraction", {}).get("total_amount") or 0) for inv in invoices)
                
                if sum_inv > revenue:
                    involved_ids = [fin["id"]] + [inv["id"] for inv in invoices]
                    if current_doc_id in involved_ids:
                        contradictions.append({
                            "title": "Revenue Discrepancy",
                            "description": "The sum of project invoices exceeds the total revenue reported in the financial statement.",
                            "doc1_name": fin["name"],
                            "doc1_value": f"${revenue:,.2f}",
                            "doc2_name": "Sum of Invoices",
                            "doc2_value": f"${sum_inv:,.2f}"
                        })

        return {
            "stage": "cross_document",
            "status": "complete",
            "data": {
                "contradictions": contradictions,
                "documents_compared": len(all_docs)
            }
        }
    except Exception as e:
        logger.error(f"Cross-document stage failed: {e}", exc_info=True)
        return {"stage": "cross_document", "status": "error", "error": str(e)}