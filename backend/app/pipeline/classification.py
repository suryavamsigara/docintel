"""
Stage 1 — Document Classification & Metadata Extraction
Uses DeepSeek (OpenAI-compatible API) for all intelligence.
No local ML models are loaded in this stage.
"""

import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set.")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
    return _client


_SYSTEM_PROMPT = """You are a legal and financial document analyst.
You extract structured metadata from document text with precision.
You always respond with valid JSON and nothing else — no markdown fences, no commentary."""

_USER_PROMPT_TEMPLATE = """Analyse the following document text and return a JSON object with exactly these keys:

{{
  "document_type": one of ["contract", "nda", "invoice", "rfp", "financial_statement", "other"],

  "primary_parties": array of up to 2 objects, each with:
    - "name": the legal entity or person name, cleaned of parenthetical aliases
    - "role": the party's role in THIS document, chosen from:
        ["Client", "Vendor", "Service Provider", "Disclosing Party", "Receiving Party",
         "Licensor", "Licensee", "Employer", "Employee", "Buyer", "Seller", "Party"]
    - "basis": one short sentence explaining why you assigned this role

  "dates": array of objects, each with:
    - "value": the date string exactly as it appears in the document
    - "label": the semantic role of this date, chosen from:
        ["Effective Date", "Execution Date", "Expiration Date", "Termination Date",
         "Due Date", "Commencement Date", "Renewal Date", "Reporting Period", "Notice Period", "Date"]
      Rules: only include dates that are calendar dates or periods (not durations like "30 days").
      "Effective Date" = when the agreement enters force.
      "Execution Date" = when it was signed.
      "Expiration Date" = when it expires.
      "Due Date" = payment deadline.
      "Commencement Date" = when work/services start.
      If none of the labels fit precisely, use "Date".
    - "context": the exact sentence from the document that contains this date (max 200 chars)

  "jurisdiction": null if not present, otherwise an object with:
    - "value": the place name only (e.g. "Delaware", "England and Wales", "Singapore")
    - "context": the exact clause that establishes this jurisdiction (max 200 chars)
}}

Important:
- primary_parties: extract from the preamble/recitals. Strip aliases in parentheses (e.g. ("Client")).
  Return the 2 most important parties. If only 1 is identifiable, return an array of 1.
- dates: deduplicate — if the same date appears multiple times, include it once with the most
  specific label. Skip relative durations ("within 30 days", "90-day period") unless they
  anchor to a specific calendar date in context.
- jurisdiction: look for phrases like "governed by the laws of", "courts of", "venue shall be".
- If a field cannot be determined from the text, return null (for jurisdiction) or [] (for arrays).

Document text:
---
{text}
---"""


def _call_deepseek(text: str) -> dict:
    """
    Makes a single structured JSON call to DeepSeek and returns the parsed dict.
    Raises on API error or unparseable response.
    """
    client = _get_client()
    prompt = _USER_PROMPT_TEMPLATE.format(text=text)

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


def _validate_and_clean(raw: dict) -> dict:
    """
    Validates the DeepSeek response shape and sanitises any bad values.
    Returns a clean dict that always has all expected keys.
    """
    valid_doc_types = {"contract", "nda", "invoice", "rfp", "financial_statement", "other"}
    valid_date_labels = {
        "Effective Date", "Execution Date", "Expiration Date", "Termination Date",
        "Due Date", "Commencement Date", "Renewal Date", "Reporting Period",
        "Notice Period", "Date",
    }
    valid_party_roles = {
        "Client", "Vendor", "Service Provider", "Disclosing Party", "Receiving Party",
        "Licensor", "Licensee", "Employer", "Employee", "Buyer", "Seller", "Party",
    }

    # --- document_type ---
    doc_type = raw.get("document_type", "other")
    if doc_type not in valid_doc_types:
        doc_type = "other"

    # --- primary_parties ---
    raw_parties = raw.get("primary_parties") or []
    parties = []
    for p in raw_parties[:2]:  # hard cap at 2
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        role = p.get("role", "Party")
        if role not in valid_party_roles:
            role = "Party"
        parties.append({
            "name": name,
            "role": role,
            "basis": str(p.get("basis", ""))[:300],
        })

    # --- dates ---
    raw_dates = raw.get("dates") or []
    dates = []
    seen_values: set[str] = set()
    for d in raw_dates:
        if not isinstance(d, dict):
            continue
        value = str(d.get("value", "")).strip()
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        label = d.get("label", "Date")
        if label not in valid_date_labels:
            label = "Date"
        dates.append({
            "value": value,
            "label": label,
            "context": str(d.get("context", ""))[:200],
        })

    # --- jurisdiction ---
    raw_jur = raw.get("jurisdiction")
    jurisdiction = None
    if isinstance(raw_jur, dict):
        jur_value = str(raw_jur.get("value", "")).strip().rstrip(".,;")
        if jur_value:
            jurisdiction = {
                "value": jur_value,
                "context": str(raw_jur.get("context", ""))[:200],
            }

    return {
        "document_type": doc_type,
        "primary_parties": parties,
        "dates": dates,
        "jurisdiction": jurisdiction,
    }


def run_classification_stage(doc_data: dict) -> dict:
    """
    Stage 1: Document classification + contextual metadata extraction via DeepSeek.

    Reads up to the first 2 pages of the normalised document, sends the text
    to DeepSeek in a single structured JSON call, validates the response,
    and returns the pipeline-standard {stage, status, data} dict.
    """
    # Build working text from first 2 pages (preamble is always enough)
    working_text = ""
    for page in doc_data.get("pages", [])[:2]:
        for el in page.get("elements", []):
            working_text += el.get("text", "") + "\n"

    # 4000 chars is ~1000 tokens — covers any contract preamble comfortably
    working_text = working_text[:4000].strip()

    if not working_text:
        return {
            "stage": "classification",
            "status": "error",
            "error": "No text could be extracted from the document for classification.",
        }

    try:
        raw_result = _call_deepseek(working_text)
        clean_result = _validate_and_clean(raw_result)
        return {
            "stage": "classification",
            "status": "complete",
            "data": clean_result,
        }

    except json.JSONDecodeError as e:
        logger.error("DeepSeek returned non-JSON response: %s", e)
        return {
            "stage": "classification",
            "status": "error",
            "error": "Model returned malformed JSON. Raw response logged for debugging.",
        }

    except Exception as e:
        logger.error("Classification stage failed: %s", e, exc_info=True)
        return {
            "stage": "classification",
            "status": "error",
            "error": str(e),
        }