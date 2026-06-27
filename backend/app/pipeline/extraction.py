"""
Stage 2 — Entity & Clause Extraction
Routes to a document-type-specific extractor, each with its own
focused DeepSeek prompt and validation schema.
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
        _client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return _client


def _call_deepseek(system: str, user: str, max_tokens: int = 2500) -> dict:
    """Single structured JSON call. Raises on API error or bad JSON."""
    response = _get_client().chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=max_tokens,
    )
    return json.loads(response.choices[0].message.content)


def _build_text(doc_data: dict, max_chars: int = 12000) -> str:
    """
    Concatenates all page elements into a single text string.
    Uses more of the document than Stage 1 — clauses live anywhere,
    not just the preamble.
    """
    parts = []
    for page in doc_data.get("pages", []):
        for el in page.get("elements", []):
            t = el.get("text", "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts)[:max_chars]


# ===========================================================================
# CONTRACT extractor
# ===========================================================================
_CONTRACT_SYSTEM = """You are a senior contract attorney performing clause extraction.
You read contract text and extract every named clause with precision.
Respond with valid JSON only — no markdown, no commentary."""

_CONTRACT_USER = """Extract all clauses from the contract below.

Return a JSON object with this exact structure:
{{
  "clauses": [
    {{
      "clause_type": string — one of the standard types listed below,
      "present": boolean — true if this clause exists in the document,
      "value": string | null — the specific extracted value, amount, duration, or condition.
        Be precise: "Net 30 days from invoice date", "£2,000,000 per occurrence", "12 months".
        null if the clause is absent.
      "raw_text": string | null — the exact sentence or short paragraph from the document
        that contains this clause (max 300 chars). null if absent.
      "notes": string | null — any unusual conditions, exceptions, or qualifications
        on this clause worth flagging (e.g. "Cap excludes gross negligence"). null if none.
    }}
  ],
  "governing_law": string | null,
  "contract_term": string | null — overall duration of the agreement,
  "auto_renewal": boolean | null — true if the contract auto-renews,
  "signed": boolean | null — true if signatures are present in the text
}}

Standard clause types to look for (include ALL of these in the output array,
setting present=false and value=null for any that are absent):
- "payment_terms"          — when and how payment must be made
- "payment_amount"         — the contract value or fee amounts
- "termination_for_cause"  — conditions under which a party may terminate for breach
- "termination_for_convenience" — right to terminate without cause
- "notice_period"          — advance notice required for termination or action
- "liability_cap"          — maximum financial liability of either party
- "indemnification"        — who indemnifies whom for what losses
- "ip_assignment"          — transfer or ownership of intellectual property
- "ip_license"             — licence granted to use IP without transfer
- "non_compete"            — restrictions on competing activities
- "non_solicitation"       — restrictions on poaching staff or clients
- "confidentiality"        — obligations to keep information secret
- "confidentiality_period" — duration of the confidentiality obligation
- "warranty"               — representations and guarantees made
- "force_majeure"          — what happens when performance is impossible
- "dispute_resolution"     — how disputes are resolved (arbitration, courts, etc.)
- "assignment"             — whether rights can be transferred to third parties
- "entire_agreement"       — merger clause excluding prior representations

Contract text:
---
{text}
---"""


def _validate_contract(raw: dict) -> dict:
    valid_clause_types = {
        "payment_terms", "payment_amount", "termination_for_cause",
        "termination_for_convenience", "notice_period", "liability_cap",
        "indemnification", "ip_assignment", "ip_license", "non_compete",
        "non_solicitation", "confidentiality", "confidentiality_period",
        "warranty", "force_majeure", "dispute_resolution", "assignment",
        "entire_agreement",
    }
    clauses = []
    seen_types: set[str] = set()
    for c in raw.get("clauses") or []:
        if not isinstance(c, dict):
            continue
        ct = c.get("clause_type", "")
        if ct not in valid_clause_types:
            continue
        if ct in seen_types:
            continue
        seen_types.add(ct)
        clauses.append({
            "clause_type": ct,
            "present":    bool(c.get("present", False)),
            "value":      str(c["value"])[:500]   if c.get("value")    else None,
            "raw_text":   str(c["raw_text"])[:300] if c.get("raw_text") else None,
            "notes":      str(c["notes"])[:300]    if c.get("notes")    else None,
        })

    # Ensure all standard types are represented even if model omitted them
    for ct in valid_clause_types:
        if ct not in seen_types:
            clauses.append({"clause_type": ct, "present": False,
                            "value": None, "raw_text": None, "notes": None})

    return {
        "clauses":        clauses,
        "governing_law":  str(raw["governing_law"])[:200]  if raw.get("governing_law")  else None,
        "contract_term":  str(raw["contract_term"])[:200]  if raw.get("contract_term")  else None,
        "auto_renewal":   bool(raw["auto_renewal"])         if raw.get("auto_renewal") is not None else None,
        "signed":         bool(raw["signed"])               if raw.get("signed")        is not None else None,
    }


# ===========================================================================
# NDA extractor
# ===========================================================================
_NDA_SYSTEM = """You are a legal analyst specialising in non-disclosure agreements.
Extract NDA-specific clauses with precision. Respond with valid JSON only."""

_NDA_USER = """Extract all clauses from the NDA below.

Return a JSON object with this exact structure:
{{
  "clauses": [
    {{
      "clause_type": string — one of the types listed below,
      "present": boolean,
      "value": string | null — the specific value, duration, or scope extracted verbatim-ish,
      "raw_text": string | null — exact source sentence (max 300 chars),
      "notes": string | null — qualifications or exceptions worth noting
    }}
  ],
  "mutual": boolean | null — true if the NDA is mutual/bilateral, false if one-directional,
  "governing_law": string | null,
  "signed": boolean | null
}}

Clause types to extract (include ALL, mark absent ones present=false):
- "confidentiality_definition"  — what information is defined as confidential
- "confidentiality_period"      — how long the obligation lasts after disclosure or termination
- "permitted_disclosures"       — who the receiving party may share information with (employees, advisors)
- "permitted_use"               — what purposes the receiving party may use the information for
- "exclusions"                  — categories explicitly excluded from confidentiality (public domain, etc.)
- "return_or_destruction"       — obligation to return or destroy confidential material on request
- "non_compete"                 — any restriction on competing with the disclosing party
- "non_solicitation"            — restriction on poaching employees or clients
- "remedies"                    — what remedies (injunction, damages) are available for breach
- "term"                        — overall duration of the NDA itself
- "notice_period"               — notice required to terminate
- "dispute_resolution"          — how disputes are handled
- "assignment"                  — whether the NDA can be transferred

NDA text:
---
{text}
---"""


def _validate_nda(raw: dict) -> dict:
    valid_clause_types = {
        "confidentiality_definition", "confidentiality_period", "permitted_disclosures",
        "permitted_use", "exclusions", "return_or_destruction", "non_compete",
        "non_solicitation", "remedies", "term", "notice_period",
        "dispute_resolution", "assignment",
    }
    clauses = []
    seen_types: set[str] = set()
    for c in raw.get("clauses") or []:
        if not isinstance(c, dict):
            continue
        ct = c.get("clause_type", "")
        if ct not in valid_clause_types or ct in seen_types:
            continue
        seen_types.add(ct)
        clauses.append({
            "clause_type": ct,
            "present":  bool(c.get("present", False)),
            "value":    str(c["value"])[:500]    if c.get("value")    else None,
            "raw_text": str(c["raw_text"])[:300] if c.get("raw_text") else None,
            "notes":    str(c["notes"])[:300]    if c.get("notes")    else None,
        })
    for ct in valid_clause_types:
        if ct not in seen_types:
            clauses.append({"clause_type": ct, "present": False,
                            "value": None, "raw_text": None, "notes": None})
    return {
        "clauses":      clauses,
        "mutual":       bool(raw["mutual"])         if raw.get("mutual")       is not None else None,
        "governing_law": str(raw["governing_law"])  if raw.get("governing_law") else None,
        "signed":       bool(raw["signed"])         if raw.get("signed")       is not None else None,
    }


# ===========================================================================
# INVOICE extractor
# ===========================================================================
_INVOICE_SYSTEM = """You are an accounts-payable specialist performing invoice data extraction.
Extract every line item and financial detail with precision.
Respond with valid JSON only — no markdown, no commentary."""

_INVOICE_USER = """Extract all data from the invoice below.

Return a JSON object with this exact structure:
{{
  "vendor": {{
    "name": string | null,
    "address": string | null,
    "email": string | null,
    "phone": string | null,
    "tax_id": string | null      — VAT number, EIN, GST number, etc.
  }},
  "bill_to": {{
    "name": string | null,
    "address": string | null,
    "email": string | null
  }},
  "invoice_number": string | null,
  "invoice_date":   string | null,
  "due_date":       string | null,
  "purchase_order": string | null — PO number if referenced,
  "currency":       string | null — ISO code e.g. "USD", "GBP", "EUR",
  "line_items": [
    {{
      "description": string,
      "quantity":    number | null,
      "unit_price":  number | null,
      "amount":      number — the line total (quantity × unit_price, or stated amount),
      "tax_rate":    number | null — as a percentage e.g. 20 for 20%
    }}
  ],
  "subtotal":      number | null — sum before tax,
  "tax_amount":    number | null — total tax charged,
  "discount":      number | null — any discount applied,
  "total_amount":  number | null — final amount due,
  "payment_terms": string | null — e.g. "Net 30", "Due on receipt",
  "payment_method": string | null — e.g. "Bank transfer", "Credit card",
  "bank_details": {{
    "bank_name":      string | null,
    "account_number": string | null,
    "sort_code":      string | null,
    "iban":           string | null,
    "swift":          string | null
  }},
  "notes": string | null — any payment notes or special instructions
}}

Rules:
- All monetary amounts must be numbers (not strings). Strip currency symbols.
- If a line item amount is not explicitly stated, compute it from quantity × unit_price.
- If the document has multiple invoices, extract only the primary one.

Invoice text:
---
{text}
---"""


def _validate_invoice(raw: dict) -> dict:
    def _clean_party(p: dict | None) -> dict:
        if not isinstance(p, dict):
            return {"name": None, "address": None, "email": None}
        return {k: (str(v)[:300] if v else None) for k, v in p.items()}

    def _num(v) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    line_items = []
    for li in (raw.get("line_items") or []):
        if not isinstance(li, dict):
            continue
        line_items.append({
            "description": str(li.get("description", ""))[:300],
            "quantity":    _num(li.get("quantity")),
            "unit_price":  _num(li.get("unit_price")),
            "amount":      _num(li.get("amount")),
            "tax_rate":    _num(li.get("tax_rate")),
        })

    bank = raw.get("bank_details") or {}
    return {
        "vendor":          _clean_party(raw.get("vendor")),
        "bill_to":         _clean_party(raw.get("bill_to")),
        "invoice_number":  str(raw["invoice_number"])  if raw.get("invoice_number")  else None,
        "invoice_date":    str(raw["invoice_date"])    if raw.get("invoice_date")    else None,
        "due_date":        str(raw["due_date"])        if raw.get("due_date")        else None,
        "purchase_order":  str(raw["purchase_order"])  if raw.get("purchase_order")  else None,
        "currency":        str(raw["currency"])[:10]   if raw.get("currency")        else None,
        "line_items":      line_items,
        "subtotal":        _num(raw.get("subtotal")),
        "tax_amount":      _num(raw.get("tax_amount")),
        "discount":        _num(raw.get("discount")),
        "total_amount":    _num(raw.get("total_amount")),
        "payment_terms":   str(raw["payment_terms"])   if raw.get("payment_terms")   else None,
        "payment_method":  str(raw["payment_method"])  if raw.get("payment_method")  else None,
        "bank_details": {
            "bank_name":      str(bank.get("bank_name"))      if bank.get("bank_name")      else None,
            "account_number": str(bank.get("account_number")) if bank.get("account_number") else None,
            "sort_code":      str(bank.get("sort_code"))      if bank.get("sort_code")      else None,
            "iban":           str(bank.get("iban"))           if bank.get("iban")           else None,
            "swift":          str(bank.get("swift"))          if bank.get("swift")          else None,
        },
        "notes": str(raw["notes"])[:500] if raw.get("notes") else None,
    }


# ===========================================================================
# FINANCIAL STATEMENT extractor
# ===========================================================================
_FINANCIAL_SYSTEM = """You are a CFA-qualified financial analyst performing structured data extraction
from financial statements. Extract every named metric with its value and period.
Respond with valid JSON only — no markdown, no commentary."""

_FINANCIAL_USER = """Extract all financial data from the statement below.

Return a JSON object with this exact structure:
{{
  "entity_name":      string | null — the company or organisation this statement relates to,
  "statement_type":   string | null — one of ["income_statement", "balance_sheet",
                                               "cash_flow_statement", "combined", "other"],
  "reporting_period": string | null — e.g. "Year ended 31 December 2023", "Q3 2024",
  "currency":         string | null — ISO code,
  "unit":             string | null — e.g. "thousands", "millions", "actual",

  "income_statement": {{
    "revenue":               number | null,
    "cost_of_goods_sold":    number | null,
    "gross_profit":          number | null,
    "operating_expenses":    number | null,
    "ebitda":                number | null,
    "ebit":                  number | null,
    "interest_expense":      number | null,
    "tax_expense":           number | null,
    "net_income":            number | null,
    "earnings_per_share":    number | null
  }},

  "balance_sheet": {{
    "total_assets":          number | null,
    "current_assets":        number | null,
    "cash_and_equivalents":  number | null,
    "accounts_receivable":   number | null,
    "inventory":             number | null,
    "total_liabilities":     number | null,
    "current_liabilities":   number | null,
    "accounts_payable":      number | null,
    "long_term_debt":        number | null,
    "total_equity":          number | null,
    "retained_earnings":     number | null
  }},

  "cash_flow": {{
    "operating_cash_flow":   number | null,
    "investing_cash_flow":   number | null,
    "financing_cash_flow":   number | null,
    "free_cash_flow":        number | null,
    "capital_expenditures":  number | null
  }},

  "ratios": {{
    "gross_margin_pct":      number | null,
    "net_margin_pct":        number | null,
    "current_ratio":         number | null,
    "debt_to_equity":        number | null,
    "return_on_equity_pct":  number | null,
    "return_on_assets_pct":  number | null
  }},

  "additional_metrics": [
    {{
      "name":  string — the metric name exactly as stated,
      "value": number | null,
      "unit":  string | null — e.g. "%", "USD", "days"
    }}
  ],

  "prior_period_label": string | null — label for the comparative period if present,
  "audited": boolean | null — true if the statement is described as audited
}}

Rules:
- All financial values must be numbers (strip £/$/%/commas). Apply the document's unit scale.
- If a ratio is not stated but can be computed from extracted values, compute it and include it.
- Put any named metric not covered by the fixed schema into additional_metrics.
- Set fields to null if not present — do not guess or interpolate.

Financial statement text:
---
{text}
---"""


def _validate_financial(raw: dict) -> dict:
    def _num(v) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    def _clean_block(block: dict | None, keys: list[str]) -> dict:
        if not isinstance(block, dict):
            return {k: None for k in keys}
        return {k: _num(block.get(k)) for k in keys}

    additional = []
    for m in (raw.get("additional_metrics") or []):
        if not isinstance(m, dict) or not m.get("name"):
            continue
        additional.append({
            "name":  str(m["name"])[:200],
            "value": _num(m.get("value")),
            "unit":  str(m["unit"])[:50] if m.get("unit") else None,
        })

    valid_stmt_types = {"income_statement", "balance_sheet", "cash_flow_statement", "combined", "other"}
    stmt_type = raw.get("statement_type")
    if stmt_type not in valid_stmt_types:
        stmt_type = "other"

    return {
        "entity_name":      str(raw["entity_name"])      if raw.get("entity_name")      else None,
        "statement_type":   stmt_type,
        "reporting_period": str(raw["reporting_period"])  if raw.get("reporting_period") else None,
        "currency":         str(raw["currency"])[:10]     if raw.get("currency")         else None,
        "unit":             str(raw["unit"])[:50]         if raw.get("unit")             else None,
        "income_statement": _clean_block(raw.get("income_statement"), [
            "revenue", "cost_of_goods_sold", "gross_profit", "operating_expenses",
            "ebitda", "ebit", "interest_expense", "tax_expense", "net_income", "earnings_per_share",
        ]),
        "balance_sheet": _clean_block(raw.get("balance_sheet"), [
            "total_assets", "current_assets", "cash_and_equivalents", "accounts_receivable",
            "inventory", "total_liabilities", "current_liabilities", "accounts_payable",
            "long_term_debt", "total_equity", "retained_earnings",
        ]),
        "cash_flow": _clean_block(raw.get("cash_flow"), [
            "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
            "free_cash_flow", "capital_expenditures",
        ]),
        "ratios": _clean_block(raw.get("ratios"), [
            "gross_margin_pct", "net_margin_pct", "current_ratio",
            "debt_to_equity", "return_on_equity_pct", "return_on_assets_pct",
        ]),
        "additional_metrics":  additional,
        "prior_period_label":  str(raw["prior_period_label"]) if raw.get("prior_period_label") else None,
        "audited":             bool(raw["audited"])            if raw.get("audited") is not None else None,
    }


# ===========================================================================
# RFP extractor
# ===========================================================================
_RFP_SYSTEM = """You are a procurement specialist performing structured data extraction from RFPs.
Extract all requirements, deadlines, and evaluation criteria with precision.
Respond with valid JSON only — no markdown, no commentary."""

_RFP_USER = """Extract all structured data from the RFP below.

Return a JSON object with this exact structure:
{{
  "issuing_organisation": string | null,
  "rfp_title":            string | null,
  "rfp_number":           string | null,
  "issue_date":           string | null,
  "submission_deadline":  string | null — exact date/time,
  "submission_method":    string | null — e.g. "Email to procurement@acme.com", "Online portal",
  "contract_value":       string | null — budget or estimated contract value,
  "contract_duration":    string | null,

  "scope_of_work": string | null — a concise summary of what is being procured (max 500 chars),

  "requirements": [
    {{
      "category": string — e.g. "Technical", "Financial", "Legal", "Experience", "Compliance",
      "description": string — the requirement as stated,
      "mandatory": boolean — true if explicitly required/mandatory, false if preferred/desirable
    }}
  ],

  "evaluation_criteria": [
    {{
      "criterion": string,
      "weight_pct": number | null — percentage weighting if stated
    }}
  ],

  "deliverables": [
    {{
      "name": string,
      "due_date": string | null
    }}
  ],

  "contact": {{
    "name":    string | null,
    "email":   string | null,
    "phone":   string | null
  }},

  "qa_deadline":     string | null — deadline for submitting clarification questions,
  "award_date":      string | null — expected date the contract will be awarded,
  "incumbent":       string | null — name of current supplier if mentioned,
  "confidentiality": boolean | null — true if bidders must sign an NDA
}}

RFP text:
---
{text}
---"""


def _validate_rfp(raw: dict) -> dict:
    def _str(v, maxlen=500):
        return str(v)[:maxlen] if v else None

    requirements = []
    for r in (raw.get("requirements") or []):
        if not isinstance(r, dict) or not r.get("description"):
            continue
        requirements.append({
            "category":    _str(r.get("category", "General"), 100),
            "description": _str(r["description"], 500),
            "mandatory":   bool(r.get("mandatory", False)),
        })

    criteria = []
    for c in (raw.get("evaluation_criteria") or []):
        if not isinstance(c, dict) or not c.get("criterion"):
            continue
        try:
            weight = float(c["weight_pct"]) if c.get("weight_pct") is not None else None
        except (TypeError, ValueError):
            weight = None
        criteria.append({"criterion": _str(c["criterion"], 200), "weight_pct": weight})

    deliverables = []
    for d in (raw.get("deliverables") or []):
        if not isinstance(d, dict) or not d.get("name"):
            continue
        deliverables.append({"name": _str(d["name"], 200), "due_date": _str(d.get("due_date"), 100)})

    contact = raw.get("contact") or {}
    return {
        "issuing_organisation": _str(raw.get("issuing_organisation"), 200),
        "rfp_title":            _str(raw.get("rfp_title"), 200),
        "rfp_number":           _str(raw.get("rfp_number"), 100),
        "issue_date":           _str(raw.get("issue_date"), 100),
        "submission_deadline":  _str(raw.get("submission_deadline"), 100),
        "submission_method":    _str(raw.get("submission_method"), 300),
        "contract_value":       _str(raw.get("contract_value"), 200),
        "contract_duration":    _str(raw.get("contract_duration"), 100),
        "scope_of_work":        _str(raw.get("scope_of_work"), 500),
        "requirements":         requirements,
        "evaluation_criteria":  criteria,
        "deliverables":         deliverables,
        "contact": {
            "name":  _str(contact.get("name"),  200),
            "email": _str(contact.get("email"), 200),
            "phone": _str(contact.get("phone"), 100),
        },
        "qa_deadline":     _str(raw.get("qa_deadline"),     100),
        "award_date":      _str(raw.get("award_date"),      100),
        "incumbent":       _str(raw.get("incumbent"),       200),
        "confidentiality": bool(raw["confidentiality"]) if raw.get("confidentiality") is not None else None,
    }


# ===========================================================================
# OTHER / GENERIC extractor
# ===========================================================================
_OTHER_SYSTEM = """You are a document analyst performing generic information extraction.
Extract all meaningful named entities, facts, and key-value pairs from the document.
Respond with valid JSON only — no markdown, no commentary."""

_OTHER_USER = """Extract structured data from the document below.

Return a JSON object with this exact structure:
{{
  "document_summary": string — 2-3 sentence summary of what this document is and its purpose,
  "key_entities": [
    {{
      "type":  string — e.g. "Organisation", "Person", "Location", "Product", "Amount", "Date",
      "name":  string — the entity as it appears in the document,
      "context": string — one sentence of context for why this entity is significant (max 200 chars)
    }}
  ],
  "key_facts": [
    {{
      "label": string — a concise label for this fact,
      "value": string — the extracted value
    }}
  ],
  "dates": [
    {{
      "value": string,
      "label": string — the role or meaning of this date
    }}
  ]
}}

Document text:
---
{text}
---"""


def _validate_other(raw: dict) -> dict:
    def _str(v, maxlen=500):
        return str(v)[:maxlen] if v else None

    entities = []
    for e in (raw.get("key_entities") or []):
        if not isinstance(e, dict) or not e.get("name"):
            continue
        entities.append({
            "type":    _str(e.get("type", "Entity"), 100),
            "name":    _str(e["name"], 200),
            "context": _str(e.get("context"), 200),
        })

    facts = []
    for f in (raw.get("key_facts") or []):
        if not isinstance(f, dict) or not f.get("label"):
            continue
        facts.append({
            "label": _str(f["label"], 200),
            "value": _str(f.get("value"), 500),
        })

    dates = []
    for d in (raw.get("dates") or []):
        if not isinstance(d, dict) or not d.get("value"):
            continue
        dates.append({
            "value": _str(d["value"], 100),
            "label": _str(d.get("label"), 100),
        })

    return {
        "document_summary": _str(raw.get("document_summary"), 500),
        "key_entities":     entities,
        "key_facts":        facts,
        "dates":            dates,
    }


# ===========================================================================
# Dispatch table
# ===========================================================================
# Maps doc_type → (system_prompt, user_prompt_template, validator_fn)
_EXTRACTORS: dict[str, tuple[str, str, callable]] = {
    "contract":            (_CONTRACT_SYSTEM,   _CONTRACT_USER,   _validate_contract),
    "nda":                 (_NDA_SYSTEM,        _NDA_USER,        _validate_nda),
    "invoice":             (_INVOICE_SYSTEM,    _INVOICE_USER,    _validate_invoice),
    "financial_statement": (_FINANCIAL_SYSTEM,  _FINANCIAL_USER,  _validate_financial),
    "rfp":                 (_RFP_SYSTEM,        _RFP_USER,        _validate_rfp),
    "other":               (_OTHER_SYSTEM,      _OTHER_USER,      _validate_other),
}


# ===========================================================================
# Stage runner
# ===========================================================================
def run_extraction_stage(doc_data: dict, classification_data: dict) -> dict:
    """
    Stage 2: Entity & Clause Extraction.

    Args:
        doc_data:           The NormalizedDocument payload from ingestion.
        classification_data: The `data` dict from Stage 1's output
                             (contains `document_type`).

    Returns:
        Pipeline-standard {stage, status, data} dict where `data` contains
        `doc_type` and `extraction` (the type-specific extracted payload).
    """
    doc_type = classification_data.get("document_type", "other")
    if doc_type not in _EXTRACTORS:
        doc_type = "other"

    system_prompt, user_template, validator = _EXTRACTORS[doc_type]

    # Use more of the document than Stage 1 — clauses live anywhere
    full_text = _build_text(doc_data, max_chars=12000)

    if not full_text.strip():
        return {
            "stage":  "extraction",
            "status": "error",
            "error":  "No text available for extraction.",
        }

    try:
        user_prompt = user_template.format(text=full_text)
        raw_result  = _call_deepseek(system_prompt, user_prompt, max_tokens=2500)
        clean       = validator(raw_result)
        return {
            "stage":  "extraction",
            "status": "complete",
            "data": {
                "doc_type":   doc_type,
                "extraction": clean,
            },
        }

    except json.JSONDecodeError as e:
        logger.error("DeepSeek returned non-JSON for extraction (%s): %s", doc_type, e)
        return {
            "stage":  "extraction",
            "status": "error",
            "error":  "Model returned malformed JSON during extraction.",
        }

    except Exception as e:
        logger.error("Extraction stage failed (%s): %s", doc_type, e, exc_info=True)
        return {
            "stage":  "extraction",
            "status": "error",
            "error":  str(e),
        }