import json
import logging
from datetime import datetime
from app.openai_client import _get_client

logger = logging.getLogger(__name__)

_ANOMALY_SYSTEM = """You are a senior risk and compliance auditor. 
Analyze the extracted document clauses and flag any anomalies, deviations from standard business practices, or missing critical protections.
Respond with valid JSON only."""

_ANOMALY_USER = """Analyze the following extracted contract/NDA data for anomalies.

Look specifically for:
1. Unusually short notice periods (e.g., less than 30 days for termination).
2. Asymmetric or unusually low liability caps (e.g., capped at fees paid vs unlimited for the other party).
3. Payment terms longer than 90 days.
4. Missing standard clauses (e.g., missing confidentiality, governing law, or termination clauses).
5. Indefinite auto-renewals without opt-out windows.

Return a JSON object with this exact structure:
{{
  "anomalies": [
    {{
      "title": "string — short title of the issue",
      "severity": "critical" | "warning" | "informational",
      "category": "Legal" | "Financial" | "Compliance" | "Operational",
      "explanation": "string — Plain English explanation of why this is flagged",
      "evidence": "string — The specific value or clause text that triggered this",
      "clause_type": "string — The affected clause type (if applicable)"
    }}
  ]
}}

Extracted Data:
---
{text}
---"""

def _check_invoice_anomalies(extraction: dict) -> list:
    anomalies = []
    
    # 1. Math Reconciliation: Line Items
    subtotal_calc = 0
    seen_items = set()
    
    for idx, item in enumerate(extraction.get("line_items", [])):
        qty = item.get("quantity") or 1
        price = item.get("unit_price") or 0
        amount = item.get("amount") or 0
        
        # Check math
        if price > 0 and amount > 0 and abs((qty * price) - amount) > 0.1:
            anomalies.append({
                "title": "Line Item Math Mismatch",
                "severity": "critical",
                "category": "Financial",
                "explanation": f"The quantity ({qty}) multiplied by unit price ({price}) does not equal the stated line amount ({amount}).",
                "evidence": item.get("description", f"Line item {idx+1}"),
                "clause_type": "line_items"
            })
            
        # Check duplicates
        item_hash = f"{item.get('description', '')}_{amount}"
        if item_hash in seen_items and item.get("description"):
            anomalies.append({
                "title": "Duplicate Line Item",
                "severity": "warning",
                "category": "Operational",
                "explanation": "This line item appears to be billed multiple times identically.",
                "evidence": item.get("description"),
                "clause_type": "line_items"
            })
        seen_items.add(item_hash)
        subtotal_calc += amount

    # 2. Math Reconciliation: Totals
    stated_subtotal = extraction.get("subtotal") or 0
    tax = extraction.get("tax_amount") or 0
    discount = extraction.get("discount") or 0
    stated_total = extraction.get("total_amount") or 0
    
    if stated_subtotal > 0 and abs(subtotal_calc - stated_subtotal) > 0.1:
         anomalies.append({
            "title": "Subtotal Reconciliation Failed",
            "severity": "critical",
            "category": "Financial",
            "explanation": f"The sum of the line items ({subtotal_calc}) does not match the stated subtotal ({stated_subtotal}).",
            "evidence": f"Calculated: {subtotal_calc}, Stated: {stated_subtotal}",
            "clause_type": "subtotal"
        })
         
    if stated_total > 0 and abs((stated_subtotal + tax - discount) - stated_total) > 0.1:
        anomalies.append({
            "title": "Total Reconciliation Failed",
            "severity": "critical",
            "category": "Financial",
            "explanation": "Subtotal plus tax minus discount does not equal the final total amount.",
            "evidence": f"Stated Total: {stated_total}",
            "clause_type": "total_amount"
        })

    return anomalies


def run_anomaly_stage(ext_data: dict) -> dict:
    """Stage 3: Anomaly Detection."""
    doc_type = ext_data.get("doc_type", "other")
    extraction = ext_data.get("extraction", {})
    anomalies = []

    try:
        # Route 1: Pure Python Math Checks for Invoices (Fast, Zero Token Cost)
        if doc_type == "invoice":
            anomalies = _check_invoice_anomalies(extraction)
            
        # Route 2: LLM Semantic Checks for Contracts/NDAs
        elif doc_type in ["contract", "nda"]:
            client = _get_client()
            prompt = _ANOMALY_USER.format(text=json.dumps(extraction, indent=2))
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": _ANOMALY_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw = json.loads(response.choices[0].message.content)
            anomalies = raw.get("anomalies", [])

        return {
            "stage": "anomaly",
            "status": "complete",
            "data": {"anomalies": anomalies}
        }
        
    except Exception as e:
        logger.error(f"Anomaly stage failed: {e}", exc_info=True)
        return {"stage": "anomaly", "status": "error", "error": str(e)}