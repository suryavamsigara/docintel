"""
Stage 2 (LOCAL) — Entity & Clause Extraction

Strategy
--------
• Clause detection   : Heading-based section splitter using a fuzzy-matched
                       clause-header dictionary (rapidfuzz, threshold=82).
                       Each matched section becomes a clause span.
• Value extraction   : Typed regex extractors for money, duration, percentage,
                       party names — one extractor per value class.
• Invoice / FS       : Pure table/regex extraction — no ML needed.
• NDA / Contract     : Clause header scan + value regex on clause body.
• RFP / other        : spaCy EntityRuler + key-value regex.

Memory contract      : spaCy singleton from classification_local is reused.
                       rapidfuzz is a pure-C extension, zero ML weight.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, date
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared lazy imports
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_spacy():
    import spacy
    try:
        return spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except OSError:
        from spacy.cli import download as spacy_download
        spacy_download("en_core_web_sm")
        return spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def _element_to_text(el: dict) -> str:
    if "text" in el:
        return el["text"]
    if "items" in el:
        return "\n".join(f"- {item}" for item in el["items"])
    if "rows" in el:
        lines = []
        if el.get("headers"):
            lines.append(" | ".join(str(h) for h in el["headers"]))
            lines.append("-" * 20)
        for row in el["rows"]:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)
    return ""


def _build_full_text(doc_data: dict, max_chars: int = 14000) -> str:
    parts = []
    for page in doc_data.get("pages", []):
        for el in page.get("elements", []):
            t = _element_to_text(el).strip()
            if t:
                parts.append(t)
    return "\n\n".join(parts)[:max_chars]


def _build_structured_elements(doc_data: dict) -> list[dict]:
    """Return all elements with their type tag preserved."""
    elements = []
    for page in doc_data.get("pages", []):
        for el in page.get("elements", []):
            elements.append(el)
    return elements


# ---------------------------------------------------------------------------
# Typed value regex extractors
# ---------------------------------------------------------------------------

# Money: "$1,200,000", "£2M", "USD 500,000", "€1.5 million"
_RE_MONEY = re.compile(
    r"(?:USD|GBP|EUR|INR|£|\$|€|₹)\s*[\d,]+(?:\.\d{1,2})?(?:\s*(?:million|m|k|thousand|lakh|lakhs|crore|crores))?"
    r"|[\d,]+(?:\.\d{1,2})?\s*(?:USD|GBP|EUR|INR|dollars?|pounds?|euros?|rupees?)"
    r"(?:\s*(?:million|m|k|thousand|lakh|lakhs|crore|crores))?",
    re.IGNORECASE,
)

# Duration: "30 days", "12 months", "2 years", "6-month period"
_RE_DURATION = re.compile(
    r"\b\d+[\-\s]?(?:calendar\s+)?(?:business\s+)?(?:days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)

# Percentage: "20%", "15 percent"
_RE_PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent(?:age)?)\b", re.IGNORECASE)

# Payment terms pattern: "Net 30", "Net 60 days", "Due on receipt"
_RE_PAYMENT_TERMS = re.compile(
    r"\b(?:net\s+\d+(?:\s+days?)?|due\s+on\s+receipt|payable\s+(?:within|in)\s+\d+\s+days?)\b",
    re.IGNORECASE,
)

# Date patterns
_RE_DATE_FULL = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}"
    r"|\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b"
    r"|\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b",
    re.IGNORECASE,
)

# Number (for financial statements)
_RE_NUMBER = re.compile(r"[\$£€]?\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand|m|b|k))?", re.IGNORECASE)


def _first_money(text: str) -> Optional[str]:
    m = _RE_MONEY.search(text)
    return m.group(0).strip() if m else None


def _first_duration(text: str) -> Optional[str]:
    m = _RE_DURATION.search(text)
    return m.group(0).strip() if m else None


def _first_payment_terms(text: str) -> Optional[str]:
    m = _RE_PAYMENT_TERMS.search(text)
    return m.group(0).strip() if m else None


def _first_date(text: str) -> Optional[str]:
    m = _RE_DATE_FULL.search(text)
    return m.group(0).strip() if m else None


def _parse_number(s: str) -> Optional[float]:
    """Convert '£1,200,000' or '42.5 million' → float."""
    if s is None:
        return None
    s = s.strip()
    multiplier = 1.0
    lower = s.lower()
    if "billion" in lower or lower.endswith("b"):
        multiplier = 1e9
    elif "million" in lower or lower.endswith("m"):
        multiplier = 1e6
    elif "thousand" in lower or lower.endswith("k"):
        multiplier = 1e3
    cleaned = re.sub(r"[^\d.]", "", s)
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Clause header dictionary + section splitter
# ---------------------------------------------------------------------------
#
# Maps canonical clause_type → list of header variants.
# rapidfuzz partial_ratio is used so "14. TERMINATION FOR CAUSE" still matches.
#

_CLAUSE_HEADERS: dict[str, list[str]] = {
    "payment_terms": [
        "payment terms", "payment schedule", "invoicing", "billing terms",
        "terms of payment", "payment conditions",
    ],
    "payment_amount": [
        "fees", "compensation", "contract price", "contract value",
        "remuneration", "consideration", "pricing",
    ],
    "termination_for_cause": [
        "termination for cause", "termination for breach", "termination for default",
        "termination with cause",
    ],
    "termination_for_convenience": [
        "termination for convenience", "termination without cause",
        "termination at will", "convenience termination",
    ],
    "notice_period": [
        "notice", "notice period", "notices", "notification",
    ],
    "liability_cap": [
        "limitation of liability", "liability cap", "liability limit",
        "cap on liability", "limitation on damages",
    ],
    "indemnification": [
        "indemnification", "indemnity", "hold harmless", "indemnify",
    ],
    "ip_assignment": [
        "intellectual property assignment", "ip assignment", "work for hire",
        "assignment of intellectual property", "ownership of work",
    ],
    "ip_license": [
        "intellectual property license", "license grant", "ip license",
        "licence grant", "software license",
    ],
    "non_compete": [
        "non-compete", "non compete", "noncompete",
        "covenant not to compete", "non-competition",
    ],
    "non_solicitation": [
        "non-solicitation", "non solicitation", "nonsolicitation",
        "covenant not to solicit",
    ],
    "confidentiality": [
        "confidentiality", "confidential information", "non-disclosure",
        "nondisclosure", "secrecy obligations",
    ],
    "confidentiality_period": [
        "confidentiality period", "duration of confidentiality",
        "term of confidentiality obligation",
    ],
    "warranty": [
        "warranty", "warranties", "representations and warranties",
        "disclaimer of warranties",
    ],
    "force_majeure": [
        "force majeure", "acts of god", "unforeseeable circumstances",
        "impossibility of performance",
    ],
    "dispute_resolution": [
        "dispute resolution", "arbitration", "governing law and disputes",
        "jurisdiction and disputes", "mediation",
    ],
    "assignment": [
        "assignment", "transfer of rights", "assignment of agreement",
        "assignment and delegation",
    ],
    "entire_agreement": [
        "entire agreement", "merger clause", "integration clause",
        "complete agreement", "supersedes all prior",
    ],
}

# NDA-specific additions
_NDA_CLAUSE_HEADERS: dict[str, list[str]] = {
    "confidentiality_definition": [
        "definition of confidential information", "confidential information means",
        "definition", "what is confidential",
    ],
    "permitted_disclosures": [
        "permitted disclosures", "permitted disclosure", "exceptions to disclosure",
        "disclosure to representatives",
    ],
    "permitted_use": [
        "permitted use", "use of information", "authorized use", "purpose",
    ],
    "exclusions": [
        "exclusions", "excluded information", "exceptions",
        "carve-outs", "information not covered",
    ],
    "return_or_destruction": [
        "return of information", "destruction of information",
        "return or destroy", "return or destruction",
    ],
    "remedies": [
        "remedies", "equitable relief", "injunctive relief",
        "damages", "specific performance",
    ],
    "term": [
        "term", "duration", "effectiveness", "term of agreement",
    ],
}


def _split_into_sections(text: str) -> list[dict]:
    """
    Splits full document text into {header, body, start_char} sections.
    A section starts at any line that looks like a clause heading:
    - Short (<= 80 chars)
    - Title-cased or ALL-CAPS or starts with a numbered prefix
    - Not ending with a full stop mid-sentence (headings rarely do)
    """
    lines = text.split("\n")
    sections: list[dict] = []
    current_header = ""
    current_body_lines: list[str] = []
    char_pos = 0

    _heading_re = re.compile(
        r"^(?:\d+[\.\)]\s+)?([A-Z][A-Za-z\s\-&/,]{2,70})$"
    )

    for line in lines:
        stripped = line.strip()
        is_heading = (
            stripped
            and len(stripped) <= 80
            and (
                stripped.isupper()
                or _heading_re.match(stripped)
                or re.match(r"^\d+[\.\)]\s+[A-Z]", stripped)
            )
            and not stripped.endswith(".")
        )

        if is_heading and current_body_lines:
            sections.append({
                "header": current_header,
                "body":   "\n".join(current_body_lines).strip(),
                "start":  char_pos,
            })
            current_body_lines = []
            current_header = stripped
        elif is_heading:
            current_header = stripped
        else:
            current_body_lines.append(line)

        char_pos += len(line) + 1  # +1 for the \n

    # Flush last section
    if current_body_lines:
        sections.append({
            "header": current_header,
            "body":   "\n".join(current_body_lines).strip(),
        })

    return sections


def _match_clause_header(header: str, clause_dict: dict[str, list[str]], threshold: int = 75) -> Optional[str]:
    """
    Returns the clause_type key whose header variants best match `header`,
    or None if no match exceeds the threshold.
    Uses rapidfuzz if available, falls back to simple substring matching.
    """
    header_lower = header.lower()

    try:
        from rapidfuzz import fuzz
        best_score = 0
        best_type  = None
        for clause_type, variants in clause_dict.items():
            for variant in variants:
                score = fuzz.partial_ratio(header_lower, variant.lower())
                if score > best_score:
                    best_score = score
                    best_type  = clause_type
        return best_type if best_score >= threshold else None
    except ImportError:
        # Fallback: simple substring
        for clause_type, variants in clause_dict.items():
            for variant in variants:
                if variant in header_lower or header_lower in variant:
                    return clause_type
        return None


def _extract_clause_value(clause_type: str, body: str) -> Optional[str]:
    """
    Returns the most relevant extracted value string for a clause body.
    Each clause type knows what kind of value to look for.
    """
    _money_types = {"payment_amount", "liability_cap"}
    _duration_types = {"notice_period", "confidentiality_period", "non_compete",
                       "non_solicitation", "term"}
    _terms_types = {"payment_terms"}

    if clause_type in _money_types:
        return _first_money(body)
    if clause_type in _duration_types:
        return _first_duration(body)
    if clause_type in _terms_types:
        return _first_payment_terms(body) or _first_duration(body)
    # For clause types where the value IS the presence itself (e.g. force_majeure),
    # return a short excerpt of the body (first sentence, max 150 chars)
    first_sentence = re.split(r"(?<=[.!?])\s+", body.strip())
    if first_sentence:
        return first_sentence[0][:150]
    return body[:150] if body else None


def _extract_raw_text_snippet(body: str, max_chars: int = 300) -> str:
    return body[:max_chars].strip() if body else ""


# ---------------------------------------------------------------------------
# CONTRACT extractor
# ---------------------------------------------------------------------------

_ALL_CONTRACT_CLAUSE_TYPES = list(_CLAUSE_HEADERS.keys())
_COMBINED_CONTRACT_DICT = {**_CLAUSE_HEADERS}


def _extract_contract(full_text: str) -> dict:
    sections = _split_into_sections(full_text)

    found: dict[str, dict] = {}

    for section in sections:
        header = section.get("header", "")
        body   = section.get("body", "")
        if not header:
            continue

        clause_type = _match_clause_header(header, _COMBINED_CONTRACT_DICT)
        if clause_type and clause_type not in found:
            value    = _extract_clause_value(clause_type, body)
            raw_text = _extract_raw_text_snippet(body)
            found[clause_type] = {
                "clause_type": clause_type,
                "present":     True,
                "value":       value,
                "raw_text":    raw_text,
                "notes":       None,
            }

    # Build complete clause list: present ones + absent placeholders
    clauses = []
    for ct in _ALL_CONTRACT_CLAUSE_TYPES:
        if ct in found:
            clauses.append(found[ct])
        else:
            clauses.append({
                "clause_type": ct,
                "present":     False,
                "value":       None,
                "raw_text":    None,
                "notes":       None,
            })

    # Top-level contract metadata via targeted regex on full text
    governing_law_m = re.search(
        r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+([A-Z][A-Za-z ,]+?)(?:\.|,|;)",
        full_text, re.IGNORECASE,
    )
    governing_law = governing_law_m.group(1).strip() if governing_law_m else None

    term_m = _RE_DURATION.search(full_text[:2000])
    contract_term = term_m.group(0) if term_m else None

    auto_renewal = bool(re.search(
        r"\bauto(?:matically)?\s*renew(?:s|ed|al)?\b|\brenews?\s+automatically\b",
        full_text, re.IGNORECASE,
    ))

    signed = bool(re.search(
        r"\bsignature[s]?\b|\bsigned\s+by\b|\b(?:IN\s+WITNESS|EXECUTED)\b",
        full_text, re.IGNORECASE,
    ))

    return {
        "clauses":       clauses,
        "governing_law": governing_law,
        "contract_term": contract_term,
        "auto_renewal":  auto_renewal,
        "signed":        signed,
    }


# ---------------------------------------------------------------------------
# NDA extractor
# ---------------------------------------------------------------------------

_ALL_NDA_CLAUSE_TYPES = list(_NDA_CLAUSE_HEADERS.keys()) + [
    "non_compete", "non_solicitation", "dispute_resolution",
    "assignment", "notice_period",
]

_COMBINED_NDA_DICT = {**_CLAUSE_HEADERS, **_NDA_CLAUSE_HEADERS}


def _extract_nda(full_text: str) -> dict:
    sections = _split_into_sections(full_text)

    found: dict[str, dict] = {}

    for section in sections:
        header = section.get("header", "")
        body   = section.get("body", "")
        if not header:
            continue
        clause_type = _match_clause_header(header, _COMBINED_NDA_DICT)
        if clause_type and clause_type not in found:
            found[clause_type] = {
                "clause_type": clause_type,
                "present":     True,
                "value":       _extract_clause_value(clause_type, body),
                "raw_text":    _extract_raw_text_snippet(body),
                "notes":       None,
            }

    # Unique NDA types not in contracts
    nda_specific_types = list(_NDA_CLAUSE_HEADERS.keys())
    shared_types = ["non_compete", "non_solicitation", "dispute_resolution",
                    "assignment", "notice_period", "confidentiality", "confidentiality_period"]
    all_types = nda_specific_types + [t for t in shared_types if t not in nda_specific_types]

    clauses = []
    for ct in all_types:
        if ct in found:
            clauses.append(found[ct])
        else:
            clauses.append({
                "clause_type": ct, "present": False,
                "value": None, "raw_text": None, "notes": None,
            })

    mutual = bool(re.search(
        r"\bmutual\b|\bbilateral\b|\bboth\s+parties\s+(?:agree|shall)\b",
        full_text[:3000], re.IGNORECASE,
    ))

    governing_law_m = re.search(
        r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+([A-Z][A-Za-z ,]+?)(?:\.|,|;)",
        full_text, re.IGNORECASE,
    )
    governing_law = governing_law_m.group(1).strip() if governing_law_m else None

    signed = bool(re.search(r"\bsignature[s]?\b|\bsigned\s+by\b", full_text, re.IGNORECASE))

    return {
        "clauses":       clauses,
        "mutual":        mutual,
        "governing_law": governing_law,
        "signed":        signed,
    }


# ---------------------------------------------------------------------------
# INVOICE extractor
# ---------------------------------------------------------------------------

def _extract_invoice(elements: list[dict]) -> dict:
    """
    Extracts invoice data from the structured element list.
    Prioritises Table elements for line items and paragraph/heading regex
    for metadata fields.
    """
    full_text = "\n".join(_element_to_text(e) for e in elements)

    # --- Vendor / Bill-To ---
    vendor = {"name": None, "address": None, "email": None, "phone": None, "tax_id": None}
    bill_to = {"name": None, "address": None, "email": None}

    # Email detection
    emails = re.findall(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", full_text)
    if emails:
        vendor["email"] = emails[0]
        if len(emails) > 1:
            bill_to["email"] = emails[1]

    # Phone detection
    phone_m = re.search(
        r"\+?[\d\s\-\(\)]{7,15}(?=\s|$)", full_text
    )
    if phone_m:
        vendor["phone"] = phone_m.group(0).strip()

    # VAT / EIN / GST
    tax_id_m = re.search(
        r"\b(?:VAT|GST|EIN|TIN)\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9]{5,20})\b",
        full_text, re.IGNORECASE,
    )
    if tax_id_m:
        vendor["tax_id"] = tax_id_m.group(1)

    # Invoice metadata
    inv_num_m = re.search(r"(?:Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*)([A-Z0-9\-]+)", full_text, re.IGNORECASE)
    invoice_number = inv_num_m.group(1) if inv_num_m else None

    po_m = re.search(r"(?:P\.?O\.?\s*(?:No\.?|Number|#)\s*[:\-]?\s*)([A-Z0-9\-]+)", full_text, re.IGNORECASE)
    purchase_order = po_m.group(1) if po_m else None

    # Dates
    dates_found = _RE_DATE_FULL.findall(full_text)
    invoice_date = dates_found[0] if len(dates_found) > 0 else None
    due_date     = dates_found[1] if len(dates_found) > 1 else None

    # Currency
    currency_m = re.search(r"\b(USD|GBP|EUR|CAD|AUD|INR|SGD)\b", full_text)
    if not currency_m:
        currency_m = re.search(r"(£|\$|€)", full_text)
    currency = currency_m.group(1) if currency_m else None

    # Payment terms
    payment_terms = _first_payment_terms(full_text)

    # Line items — try to extract from Table elements
    line_items: list[dict] = []
    for el in elements:
        if "rows" not in el:
            continue
        headers = [h.lower() for h in (el.get("headers") or [])]
        # Look for tables with description/amount columns
        if not any(kw in " ".join(headers) for kw in ["desc", "item", "service", "qty", "amount", "price"]):
            continue
        for row in el.get("rows", []):
            if len(row) < 2:
                continue
            desc = row[0].strip() if row[0] else ""
            if not desc or desc.lower() in ("total", "subtotal", "tax", "discount"):
                continue
            # Try to find amount from the rightmost numeric column
            amount_str = next((c for c in reversed(row[1:]) if re.search(r"\d", c)), None)
            amount = _parse_number(re.sub(r"[^\d.,]", "", amount_str)) if amount_str else None

            qty_str = row[1] if len(row) > 2 else None
            qty = _parse_number(qty_str) if qty_str and re.match(r"[\d.]+", qty_str.strip()) else None

            unit_price_str = row[2] if len(row) > 3 else None
            unit_price = _parse_number(re.sub(r"[^\d.,]", "", unit_price_str)) if unit_price_str else None

            line_items.append({
                "description": desc,
                "quantity":    qty,
                "unit_price":  unit_price,
                "amount":      amount,
                "tax_rate":    None,
            })

    # Totals via labeled-row regex
    def _labeled_amount(label_pattern: str) -> Optional[float]:
        m = re.search(
            label_pattern + r"[:\s]*([£\$€]?\s*[\d,]+(?:\.\d{1,2})?)",
            full_text, re.IGNORECASE,
        )
        return _parse_number(m.group(1)) if m else None

    subtotal    = _labeled_amount(r"(?:sub\s*[-]?total|net\s+amount)")
    tax_amount  = _labeled_amount(r"(?:tax|vat|gst)(?:\s+amount)?(?:\s+\d+%)?")
    discount    = _labeled_amount(r"discount")
    total_amount = _labeled_amount(r"(?:total\s+(?:amount\s+)?due|total\s+payable|amount\s+due|grand\s+total|total)")

    # Bank details
    bank_details = {
        "bank_name":      _re_labeled(r"(?:bank\s*name|bank)[:\s]+([A-Za-z\s&]+?)(?:\n|,|$)", full_text),
        "account_number": _re_labeled(r"(?:account\s*(?:no\.?|number|#))[:\s]+([\d\s\-]+)", full_text),
        "sort_code":      _re_labeled(r"sort\s*code[:\s]+([\d\-]+)", full_text),
        "iban":           _re_labeled(r"\b((?:[A-Z]{2}\d{2}[\s\-]?){4,}[A-Z0-9]*)\b", full_text),
        "swift":          _re_labeled(r"\b(?:SWIFT|BIC)[:\s]+([A-Z]{6}[A-Z0-9]{2,5})\b", full_text),
    }

    return {
        "vendor":          vendor,
        "bill_to":         bill_to,
        "invoice_number":  invoice_number,
        "invoice_date":    invoice_date,
        "due_date":        due_date,
        "purchase_order":  purchase_order,
        "currency":        currency,
        "line_items":      line_items,
        "subtotal":        subtotal,
        "tax_amount":      tax_amount,
        "discount":        discount,
        "total_amount":    total_amount,
        "payment_terms":   payment_terms,
        "payment_method":  None,
        "bank_details":    bank_details,
        "notes":           None,
    }


def _re_labeled(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# FINANCIAL STATEMENT extractor
# ---------------------------------------------------------------------------

_FS_INCOME_LABELS: dict[str, list[str]] = {
    "revenue":            ["revenue", "total revenue", "net revenue", "sales", "turnover"],
    "cost_of_goods_sold": ["cost of goods sold", "cogs", "cost of sales", "cost of revenue"],
    "gross_profit":       ["gross profit"],
    "operating_expenses": ["operating expenses", "opex", "total operating expenses"],
    "ebitda":             ["ebitda"],
    "ebit":               ["ebit", "operating income", "operating profit"],
    "interest_expense":   ["interest expense", "finance costs", "finance charges"],
    "tax_expense":        ["income tax", "tax expense", "provision for taxes"],
    "net_income":         ["net income", "net profit", "net earnings", "profit after tax", "profit for the year"],
    "earnings_per_share": ["earnings per share", "eps", "basic eps", "diluted eps"],
}

_FS_BS_LABELS: dict[str, list[str]] = {
    "total_assets":         ["total assets"],
    "current_assets":       ["total current assets", "current assets"],
    "cash_and_equivalents": ["cash and cash equivalents", "cash & equivalents", "cash"],
    "accounts_receivable":  ["accounts receivable", "trade receivables"],
    "inventory":            ["inventory", "inventories"],
    "total_liabilities":    ["total liabilities"],
    "current_liabilities":  ["total current liabilities", "current liabilities"],
    "accounts_payable":     ["accounts payable", "trade payables"],
    "long_term_debt":       ["long-term debt", "long term debt", "long-term borrowings"],
    "total_equity":         ["total equity", "shareholders equity", "stockholders equity", "net assets"],
    "retained_earnings":    ["retained earnings"],
}

_FS_CF_LABELS: dict[str, list[str]] = {
    "operating_cash_flow":  ["operating activities", "cash from operations", "net cash from operating"],
    "investing_cash_flow":  ["investing activities", "cash used in investing"],
    "financing_cash_flow":  ["financing activities", "cash from financing"],
    "free_cash_flow":       ["free cash flow"],
    "capital_expenditures": ["capital expenditures", "capex", "purchase of property", "additions to property"],
}


def _scan_labeled_row(labels: list[str], text: str) -> Optional[float]:
    """
    Searches text for any of the label strings on a line, then extracts
    the first number on that line (handling commas, parentheses for negatives).
    """
    for label in labels:
        pattern = re.compile(
            r"^.*\b" + re.escape(label) + r"\b.*?([\(\-]?\s*[\d,]+(?:\.\d+)?\s*\)?)",
            re.IGNORECASE | re.MULTILINE,
        )
        m = pattern.search(text)
        if m:
            raw = m.group(1).replace(",", "").replace("(", "-").replace(")", "").replace(" ", "")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _extract_financial(full_text: str) -> dict:
    def _block(label_map: dict[str, list[str]]) -> dict[str, Optional[float]]:
        return {key: _scan_labeled_row(labels, full_text) for key, labels in label_map.items()}

    # Determine statement type
    has_income  = bool(re.search(r"\b(?:revenue|net\s+income|gross\s+profit)\b", full_text, re.IGNORECASE))
    has_balance = bool(re.search(r"\b(?:total\s+assets|total\s+liabilities|equity)\b", full_text, re.IGNORECASE))
    has_cf      = bool(re.search(r"\b(?:operating\s+activities|investing\s+activities)\b", full_text, re.IGNORECASE))

    if has_income and has_balance:
        stmt_type = "combined"
    elif has_income:
        stmt_type = "income_statement"
    elif has_balance:
        stmt_type = "balance_sheet"
    elif has_cf:
        stmt_type = "cash_flow_statement"
    else:
        stmt_type = "other"

    # Currency
    curr_m = re.search(r"\b(USD|GBP|EUR|CAD|AUD|INR|SGD)\b", full_text)
    if not curr_m:
        curr_m = re.search(r"(£|\$|€)", full_text)
    currency = curr_m.group(1) if curr_m else None

    # Unit (millions / thousands)
    unit_m = re.search(r"(?:in|expressed\s+in)\s+(thousands?|millions?|billions?)", full_text, re.IGNORECASE)
    unit = unit_m.group(1) if unit_m else "actual"

    # Reporting period
    period_m = re.search(
        r"(?:year|period|quarter)\s+ended?\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
        full_text, re.IGNORECASE,
    )
    reporting_period = period_m.group(0)[:80] if period_m else None

    # Entity name — first ORG from spaCy
    nlp = _get_spacy()
    doc = nlp(full_text[:2000])
    entity_name = next((ent.text for ent in doc.ents if ent.label_ == "ORG"), None)

    income  = _block(_FS_INCOME_LABELS)
    balance = _block(_FS_BS_LABELS)
    cf      = _block(_FS_CF_LABELS)

    # Compute ratios if data allows
    ratios: dict[str, Optional[float]] = {k: None for k in [
        "gross_margin_pct", "net_margin_pct", "current_ratio",
        "debt_to_equity", "return_on_equity_pct", "return_on_assets_pct",
    ]}
    rev = income.get("revenue")
    if rev and rev != 0:
        gp = income.get("gross_profit")
        if gp is not None:
            ratios["gross_margin_pct"] = round(gp / rev * 100, 2)
        ni = income.get("net_income")
        if ni is not None:
            ratios["net_margin_pct"] = round(ni / rev * 100, 2)
    ca = balance.get("current_assets")
    cl = balance.get("current_liabilities")
    if ca and cl and cl != 0:
        ratios["current_ratio"] = round(ca / cl, 2)
    td = balance.get("long_term_debt")
    eq = balance.get("total_equity")
    if td is not None and eq and eq != 0:
        ratios["debt_to_equity"] = round(td / eq, 2)
    ni = income.get("net_income")
    if ni is not None and eq and eq != 0:
        ratios["return_on_equity_pct"] = round(ni / eq * 100, 2)
    ta = balance.get("total_assets")
    if ni is not None and ta and ta != 0:
        ratios["return_on_assets_pct"] = round(ni / ta * 100, 2)

    audited = bool(re.search(r"\baudited\b|\bindependent\s+auditor\b", full_text, re.IGNORECASE))

    return {
        "entity_name":       entity_name,
        "statement_type":    stmt_type,
        "reporting_period":  reporting_period,
        "currency":          currency,
        "unit":              unit,
        "income_statement":  income,
        "balance_sheet":     balance,
        "cash_flow":         cf,
        "ratios":            ratios,
        "additional_metrics": [],
        "prior_period_label": None,
        "audited":           audited,
    }


# ---------------------------------------------------------------------------
# RFP extractor
# ---------------------------------------------------------------------------

def _extract_rfp(full_text: str, elements: list[dict]) -> dict:
    nlp = _get_spacy()
    doc = nlp(full_text[:4000])

    org_names = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    issuing_org = org_names[0] if org_names else None

    title_m = re.search(
        r"(?:Request\s+for\s+Proposal|RFP)[:\s]+(.{5,120}?)(?:\n|$)",
        full_text, re.IGNORECASE,
    )
    rfp_title = title_m.group(1).strip() if title_m else None

    rfp_num_m = re.search(
        r"RFP\s*(?:No\.?|Number|#|Ref\.?)[:\s]+([\w\-\/]+)", full_text, re.IGNORECASE,
    )
    rfp_number = rfp_num_m.group(1) if rfp_num_m else None

    # Deadline
    deadline_m = re.search(
        r"(?:submission\s+deadline|proposals?\s+(?:must\s+be\s+)?(?:received|submitted)\s+by)[:\s]+"
        r"([A-Z][a-z]+ \d{1,2},? \d{4}[^\n]{0,30})",
        full_text, re.IGNORECASE,
    )
    submission_deadline = deadline_m.group(1).strip() if deadline_m else _first_date(full_text)

    # Budget
    budget_m = re.search(
        r"(?:budget|contract\s+value|estimated\s+value)[:\s]+" + r"([\$£€]?\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|k))?)",
        full_text, re.IGNORECASE,
    )
    contract_value = budget_m.group(1).strip() if budget_m else None

    # Contact
    contact: dict = {"name": None, "email": None, "phone": None}
    emails = re.findall(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", full_text)
    if emails:
        contact["email"] = emails[-1]

    # Requirements — any bullet list items
    requirements = []
    for el in elements:
        if "items" not in el:
            continue
        for item in el.get("items", []):
            if len(item) > 20:
                mandatory = bool(re.search(r"\b(?:must|shall|required|mandatory)\b", item, re.IGNORECASE))
                requirements.append({
                    "category":    "General",
                    "description": item[:500],
                    "mandatory":   mandatory,
                })

    # Evaluation criteria
    criteria = []
    crit_block_m = re.search(
        r"(?:evaluation\s+criteria?|scoring\s+criteria?)[:\n](.{50,800}?)(?:\n\n|\Z)",
        full_text, re.IGNORECASE | re.DOTALL,
    )
    if crit_block_m:
        block = crit_block_m.group(1)
        for line in block.split("\n"):
            pct_m = re.search(r"(\d+)\s*%", line)
            label = re.sub(r"[\-•*\d%]", "", line).strip()
            if label and len(label) > 3:
                criteria.append({
                    "criterion": label[:200],
                    "weight_pct": float(pct_m.group(1)) if pct_m else None,
                })

    return {
        "issuing_organisation": issuing_org,
        "rfp_title":            rfp_title,
        "rfp_number":           rfp_number,
        "issue_date":           None,
        "submission_deadline":  submission_deadline,
        "submission_method":    None,
        "contract_value":       contract_value,
        "contract_duration":    None,
        "scope_of_work":        None,
        "requirements":         requirements[:20],
        "evaluation_criteria":  criteria[:10],
        "deliverables":         [],
        "contact":              contact,
        "qa_deadline":          None,
        "award_date":           None,
        "incumbent":            None,
        "confidentiality":      None,
    }


# ---------------------------------------------------------------------------
# GENERIC / OTHER extractor
# ---------------------------------------------------------------------------

def _extract_other(full_text: str) -> dict:
    nlp = _get_spacy()
    doc_nlp = nlp(full_text[:6000])

    entities = []
    seen_ents: set[str] = set()
    for ent in doc_nlp.ents:
        if ent.text in seen_ents or len(ent.text) < 3:
            continue
        seen_ents.add(ent.text)
        entities.append({
            "type":    ent.label_,
            "name":    ent.text,
            "context": full_text[max(0, ent.start_char - 60): ent.end_char + 60].strip()[:200],
        })

    # Key facts — any "Label: Value" pairs on their own lines
    key_facts = []
    for m in re.finditer(r"^([A-Z][A-Za-z\s]{2,50}?)\s*:\s*(.{3,200}?)$", full_text, re.MULTILINE):
        key_facts.append({
            "label": m.group(1).strip(),
            "value": m.group(2).strip(),
        })

    # Dates
    dates = [
        {"value": v, "label": "Date"}
        for v in dict.fromkeys(_RE_DATE_FULL.findall(full_text))
    ][:8]

    # Minimal summary
    first_para = full_text.strip()[:400]
    summary = re.sub(r"\s+", " ", first_para).strip()

    return {
        "document_summary": summary[:500],
        "key_entities":     entities[:15],
        "key_facts":        key_facts[:15],
        "dates":            dates,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run_extraction_stage_local(doc_data: dict, classification_data: dict) -> dict:
    """
    Stage 2 (LOCAL): Entity & Clause Extraction.

    Mirrors the return shape of the LLM version exactly:
        { stage, status, data: { doc_type, extraction } }
    """
    doc_type = classification_data.get("document_type", "other")
    if doc_type not in {"contract", "nda", "invoice", "financial_statement", "rfp", "other"}:
        doc_type = "other"

    full_text = _build_full_text(doc_data)
    elements  = _build_structured_elements(doc_data)

    if not full_text.strip():
        return {
            "stage":  "extraction",
            "status": "error",
            "error":  "No text available for extraction.",
        }

    try:
        if doc_type == "contract":
            extraction = _extract_contract(full_text)
        elif doc_type == "nda":
            extraction = _extract_nda(full_text)
        elif doc_type == "invoice":
            extraction = _extract_invoice(elements)
        elif doc_type == "financial_statement":
            extraction = _extract_financial(full_text)
        elif doc_type == "rfp":
            extraction = _extract_rfp(full_text, elements)
        else:
            extraction = _extract_other(full_text)

        return {
            "stage":  "extraction",
            "status": "complete",
            "data": {
                "doc_type":   doc_type,
                "extraction": extraction,
            },
        }

    except Exception as e:
        logger.error("Local extraction failed (%s): %s", doc_type, e, exc_info=True)
        return {
            "stage":  "extraction",
            "status": "error",
            "error":  str(e),
        }