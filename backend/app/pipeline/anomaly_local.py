"""
Stage 3 (LOCAL) — Anomaly Detection

Strategy
--------
All checks are deterministic rule-based logic operating on the structured
extraction dict from Stage 2.  No ML, no LLM, no network calls.

Contract / NDA checks
---------------------
• Short notice period        (< 30 days)
• Long payment terms         (> 90 days)
• Asymmetric or missing liability cap
• Missing mandatory clauses  (from a per-doc-type required set)
• Auto-renewal without explicit opt-out mention
• Missing governing law / jurisdiction

Invoice checks  (already existed in LLM version, kept + extended)
-------------------
• Line item math mismatch
• Duplicate line items
• Subtotal reconciliation
• Total reconciliation
• Past due date
• Zero-amount line items

Financial statement checks
--------------------------
• Negative equity (insolvency signal)
• Current ratio < 1 (short-term liquidity risk)
• Debt-to-equity > 3 (over-leverage)
• Gross margin < 0 (selling below cost)
• Net income / revenue mismatch (sign conflict)
• Missing audited flag for high-value statements

RFP checks
----------
• Missing submission deadline
• Missing contact information
• Evaluation criteria weights don't sum to 100%

Severity taxonomy  (matches LLM version)
-----------------------------------------
  critical      — immediate action required
  warning       — should be reviewed
  informational — contextual note
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _today() -> datetime:
    return datetime.now()


def _parse_days(duration_str: Optional[str]) -> Optional[int]:
    """
    Parse a plain-English duration string into a number of days.
    '30 days' → 30, '3 months' → 90, '2 years' → 730.
    Returns None if unparseable.
    """
    if not duration_str:
        return None
    s = duration_str.lower().strip()
    m = re.search(r"(\d+)\s*(day|week|month|year)", s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return {
        "day":   n,
        "week":  n * 7,
        "month": n * 30,
        "year":  n * 365,
    }[unit]


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Try a set of common date formats, return datetime or None.
    """
    if not date_str:
        return None
    formats = [
        "%B %d, %Y", "%B %d %Y", "%d %B %Y", "%d %B, %Y",
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d",
        "%d-%m-%Y", "%m-%d-%Y",
        "%d.%m.%Y",
    ]
    clean = date_str.strip().rstrip(".,;")
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _anomaly(title: str, severity: str, category: str, explanation: str, evidence: str,
             clause_type: Optional[str] = None) -> dict:
    return {
        "title":       title,
        "severity":    severity,
        "category":    category,
        "explanation": explanation,
        "evidence":    evidence,
        "clause_type": clause_type,
    }


# ---------------------------------------------------------------------------
# CONTRACT anomaly checks
# ---------------------------------------------------------------------------

_CONTRACT_REQUIRED_CLAUSES = {
    "payment_terms":           ("warning",  "Financial",  "No payment terms clause was found. Payment obligations are undefined."),
    "termination_for_cause":   ("warning",  "Legal",      "No termination-for-cause clause. A party cannot exit the contract if the other materially breaches."),
    "liability_cap":           ("critical", "Legal",      "No liability cap clause. Either party faces unlimited financial exposure under this agreement."),
    "confidentiality":         ("warning",  "Compliance", "No confidentiality clause. Sensitive information exchanged under this contract is unprotected."),
    "dispute_resolution":      ("warning",  "Legal",      "No dispute resolution clause. There is no agreed mechanism for resolving conflicts."),
    "governing_law":           ("warning",  "Legal",      "No governing law is specified. It is unclear which jurisdiction's laws apply."),  # checked separately
}

_NDA_REQUIRED_CLAUSES = {
    "confidentiality_definition": ("critical", "Legal",      "No definition of Confidential Information found. The scope of protection is undefined."),
    "confidentiality_period":     ("warning",  "Legal",      "No confidentiality period stated. The obligation may extend indefinitely or not at all."),
    "exclusions":                 ("informational", "Legal", "No exclusion carve-outs found. Standard public-domain and independently-developed information is not explicitly excluded."),
    "remedies":                   ("warning",  "Legal",      "No remedies clause. The injured party's recourse on breach is not defined."),
    "return_or_destruction":      ("informational", "Compliance", "No return-or-destroy obligation. Confidential materials may be retained indefinitely."),
}


def _check_contract_anomalies(extraction: dict) -> list[dict]:
    anomalies: list[dict] = []
    clauses_by_type = {c["clause_type"]: c for c in extraction.get("clauses", [])}

    # 1. Missing mandatory clauses
    for clause_type, (severity, category, explanation) in _CONTRACT_REQUIRED_CLAUSES.items():
        if clause_type == "governing_law":
            continue  # handled below via top-level field
        clause = clauses_by_type.get(clause_type)
        if not clause or not clause.get("present"):
            anomalies.append(_anomaly(
                title=f"Missing Clause: {clause_type.replace('_', ' ').title()}",
                severity=severity,
                category=category,
                explanation=explanation,
                evidence="Clause not found in document.",
                clause_type=clause_type,
            ))

    # 2. Governing law missing
    if not extraction.get("governing_law"):
        sev, cat, exp = _CONTRACT_REQUIRED_CLAUSES["governing_law"]
        anomalies.append(_anomaly(
            "Missing Governing Law", sev, cat, exp,
            "No governing law field extracted.",
        ))

    # 3. Short notice period (< 30 days)
    notice_clause = clauses_by_type.get("notice_period")
    if notice_clause and notice_clause.get("present") and notice_clause.get("value"):
        days = _parse_days(notice_clause["value"])
        if days is not None and days < 30:
            anomalies.append(_anomaly(
                "Unusually Short Notice Period",
                severity="warning",
                category="Legal",
                explanation=f"The notice period is only {days} day(s). Industry standard is at least 30 days, giving parties inadequate time to make arrangements.",
                evidence=notice_clause["value"],
                clause_type="notice_period",
            ))

    # 4. Long payment terms (> 90 days)
    pay_terms_clause = clauses_by_type.get("payment_terms")
    if pay_terms_clause and pay_terms_clause.get("present") and pay_terms_clause.get("value"):
        days = _parse_days(pay_terms_clause["value"])
        if days is not None and days > 90:
            anomalies.append(_anomaly(
                "Extended Payment Terms",
                severity="warning",
                category="Financial",
                explanation=f"Payment terms of {days} days exceed the typical 90-day maximum, creating significant cash-flow risk for the payee.",
                evidence=pay_terms_clause["value"],
                clause_type="payment_terms",
            ))

    # 5. Auto-renewal without opt-out window
    if extraction.get("auto_renewal"):
        # Check if there's a corresponding opt-out window mentioned
        renewal_clause = clauses_by_type.get("termination_for_convenience")
        has_opt_out = bool(renewal_clause and renewal_clause.get("present"))
        if not has_opt_out:
            anomalies.append(_anomaly(
                "Auto-Renewal Without Explicit Opt-Out",
                severity="warning",
                category="Operational",
                explanation="The contract auto-renews but no explicit opt-out window or termination-for-convenience clause is present. A party could be locked in for another full term unintentionally.",
                evidence="auto_renewal: true, termination_for_convenience: absent",
                clause_type="auto_renewal",
            ))

    # 6. No IP assignment but tech context implied
    ip_assign = clauses_by_type.get("ip_assignment")
    ip_lic     = clauses_by_type.get("ip_license")
    pay_amt    = clauses_by_type.get("payment_amount")
    if (pay_amt and pay_amt.get("present")
            and not (ip_assign and ip_assign.get("present"))
            and not (ip_lic   and ip_lic.get("present"))):
        anomalies.append(_anomaly(
            "No IP Ownership Clause",
            severity="informational",
            category="Legal",
            explanation="A payment amount is defined but neither an IP assignment nor IP license clause was found. Ownership of work product is ambiguous.",
            evidence="ip_assignment: absent, ip_license: absent",
        ))

    return anomalies


def _check_nda_anomalies(extraction: dict) -> list[dict]:
    anomalies: list[dict] = []
    clauses_by_type = {c["clause_type"]: c for c in extraction.get("clauses", [])}

    # 1. Missing required NDA clauses
    for clause_type, (severity, category, explanation) in _NDA_REQUIRED_CLAUSES.items():
        clause = clauses_by_type.get(clause_type)
        if not clause or not clause.get("present"):
            anomalies.append(_anomaly(
                f"Missing Clause: {clause_type.replace('_', ' ').title()}",
                severity=severity, category=category,
                explanation=explanation,
                evidence="Clause not found in document.",
                clause_type=clause_type,
            ))

    # 2. Indefinitely long confidentiality period
    conf_period = clauses_by_type.get("confidentiality_period")
    if conf_period and conf_period.get("present") and conf_period.get("value"):
        val = conf_period["value"].lower()
        if "perpetual" in val or "indefinite" in val or "no expir" in val:
            anomalies.append(_anomaly(
                "Perpetual Confidentiality Obligation",
                severity="warning",
                category="Legal",
                explanation="The confidentiality obligation is stated as perpetual or indefinite. This may be unenforceable in some jurisdictions and creates an indefinite burden.",
                evidence=conf_period["value"],
                clause_type="confidentiality_period",
            ))
        else:
            years = _parse_days(conf_period["value"])
            if years is not None and years > 365 * 5:
                anomalies.append(_anomaly(
                    "Very Long Confidentiality Period",
                    severity="informational",
                    category="Legal",
                    explanation=f"The confidentiality period of {conf_period['value']} exceeds 5 years, which may be difficult to enforce.",
                    evidence=conf_period["value"],
                    clause_type="confidentiality_period",
                ))

    # 3. One-sided NDA but framed as mutual
    if extraction.get("mutual") is False:
        if not clauses_by_type.get("disclosing_party") and not clauses_by_type.get("permitted_use"):
            anomalies.append(_anomaly(
                "One-Sided NDA — Limited Receiving-Party Protections",
                severity="informational",
                category="Legal",
                explanation="This NDA is unilateral (one party discloses, one receives). Ensure the receiving party's permitted use is clearly scoped.",
                evidence="mutual: false",
            ))

    # 4. No governing law
    if not extraction.get("governing_law"):
        anomalies.append(_anomaly(
            "Missing Governing Law",
            severity="warning",
            category="Legal",
            explanation="No governing law is specified in this NDA. Enforcement jurisdiction is undefined.",
            evidence="governing_law: absent",
        ))

    return anomalies


# ---------------------------------------------------------------------------
# INVOICE anomaly checks  (extended from existing LLM version)
# ---------------------------------------------------------------------------

def _check_invoice_anomalies(extraction: dict) -> list[dict]:
    anomalies: list[dict] = []

    subtotal_calc = 0.0
    seen_items: set[str] = set()

    for idx, item in enumerate(extraction.get("line_items", [])):
        qty    = item.get("quantity") or 1
        price  = item.get("unit_price") or 0.0
        amount = item.get("amount") or 0.0

        # a. Math mismatch on line item
        if price > 0 and amount > 0 and abs((qty * price) - amount) > 0.11:
            anomalies.append(_anomaly(
                "Line Item Math Mismatch", "critical", "Financial",
                f"Quantity ({qty}) × unit price ({price:.2f}) = {qty * price:.2f}, but stated amount is {amount:.2f}.",
                item.get("description", f"Line item {idx + 1}"),
                clause_type="line_items",
            ))

        # b. Zero-amount line item
        if price == 0 and amount == 0 and item.get("description"):
            anomalies.append(_anomaly(
                "Zero-Amount Line Item", "informational", "Financial",
                "A line item has no price or amount. This may be intentional (complimentary item) or a data entry error.",
                item.get("description", ""),
                clause_type="line_items",
            ))

        # c. Duplicate detection
        item_hash = f"{(item.get('description') or '').strip().lower()}_{amount:.2f}"
        if item_hash in seen_items and item.get("description"):
            anomalies.append(_anomaly(
                "Duplicate Line Item", "warning", "Financial",
                "An identical line item (same description and amount) appears more than once.",
                item.get("description", ""),
                clause_type="line_items",
            ))
        seen_items.add(item_hash)
        subtotal_calc += amount

    # d. Subtotal reconciliation
    stated_subtotal = extraction.get("subtotal") or 0.0
    if stated_subtotal > 0 and abs(subtotal_calc - stated_subtotal) > 0.11:
        anomalies.append(_anomaly(
            "Subtotal Reconciliation Failed", "critical", "Financial",
            f"Sum of line items ({subtotal_calc:.2f}) does not match stated subtotal ({stated_subtotal:.2f}).",
            f"Calculated: {subtotal_calc:.2f}, Stated: {stated_subtotal:.2f}",
            clause_type="subtotal",
        ))

    # e. Total reconciliation
    tax       = extraction.get("tax_amount") or 0.0
    discount  = extraction.get("discount")   or 0.0
    total     = extraction.get("total_amount") or 0.0
    base      = stated_subtotal or subtotal_calc
    expected  = base + tax - discount
    if total > 0 and abs(expected - total) > 0.11:
        anomalies.append(_anomaly(
            "Total Amount Reconciliation Failed", "critical", "Financial",
            f"Subtotal ({base:.2f}) + Tax ({tax:.2f}) − Discount ({discount:.2f}) = {expected:.2f}, but stated total is {total:.2f}.",
            f"Expected: {expected:.2f}, Stated: {total:.2f}",
            clause_type="total_amount",
        ))

    # f. Past due date
    due_dt = _parse_date(extraction.get("due_date"))
    if due_dt and due_dt < _today():
        days_overdue = (_today() - due_dt).days
        anomalies.append(_anomaly(
            "Invoice Overdue", "critical", "Financial",
            f"The due date ({extraction['due_date']}) is {days_overdue} day(s) in the past.",
            extraction.get("due_date", ""),
            clause_type="due_date",
        ))

    # g. Missing due date
    if not extraction.get("due_date"):
        anomalies.append(_anomaly(
            "Missing Due Date", "warning", "Financial",
            "No payment due date is specified on this invoice.",
            "due_date: absent",
            clause_type="due_date",
        ))

    # h. Missing vendor details
    vendor = extraction.get("vendor") or {}
    if not vendor.get("name"):
        anomalies.append(_anomaly(
            "Missing Vendor Name", "warning", "Compliance",
            "No vendor name is present on this invoice. Accounting attribution is impossible.",
            "vendor.name: absent",
        ))

    return anomalies


# ---------------------------------------------------------------------------
# FINANCIAL STATEMENT anomaly checks
# ---------------------------------------------------------------------------

def _check_financial_anomalies(extraction: dict) -> list[dict]:
    anomalies: list[dict] = []
    bs = extraction.get("balance_sheet", {}) or {}
    is_ = extraction.get("income_statement", {}) or {}
    ratios = extraction.get("ratios", {}) or {}

    # 1. Negative equity
    equity = bs.get("total_equity")
    if equity is not None and equity < 0:
        anomalies.append(_anomaly(
            "Negative Equity (Technical Insolvency)", "critical", "Financial",
            f"Total equity is negative ({equity:,.0f}), indicating total liabilities exceed total assets. This is a technical insolvency signal.",
            f"total_equity: {equity:,.0f}",
        ))

    # 2. Current ratio < 1
    cr = ratios.get("current_ratio")
    if cr is not None and cr < 1.0:
        anomalies.append(_anomaly(
            "Low Current Ratio", "warning", "Financial",
            f"Current ratio of {cr:.2f} indicates current liabilities exceed current assets. The entity may struggle to meet short-term obligations.",
            f"current_ratio: {cr:.2f}",
        ))

    # 3. Debt-to-equity > 3
    de = ratios.get("debt_to_equity")
    if de is not None and de > 3.0:
        anomalies.append(_anomaly(
            "High Debt-to-Equity Ratio", "warning", "Financial",
            f"Debt-to-equity ratio of {de:.2f} is above the typical threshold of 3.0, indicating high financial leverage.",
            f"debt_to_equity: {de:.2f}",
        ))

    # 4. Negative gross margin
    gm = ratios.get("gross_margin_pct")
    if gm is not None and gm < 0:
        anomalies.append(_anomaly(
            "Negative Gross Margin", "critical", "Financial",
            f"Gross margin of {gm:.1f}% means the entity is selling goods/services below their direct cost.",
            f"gross_margin_pct: {gm:.1f}%",
        ))

    # 5. Net income/revenue sign conflict
    rev = is_.get("revenue")
    ni  = is_.get("net_income")
    if rev is not None and ni is not None and rev > 0 and ni < 0:
        loss_margin = abs(ni) / rev * 100
        if loss_margin > 20:
            anomalies.append(_anomaly(
                "Large Net Loss Relative to Revenue", "warning", "Financial",
                f"Net loss is {loss_margin:.1f}% of revenue, which is unusually large and may indicate structural cost problems.",
                f"net_income: {ni:,.0f}, revenue: {rev:,.0f}",
            ))

    # 6. Total assets ≠ total liabilities + equity (balance sheet equation)
    ta = bs.get("total_assets")
    tl = bs.get("total_liabilities")
    eq = bs.get("total_equity")
    if ta is not None and tl is not None and eq is not None:
        rhs = tl + eq
        if ta > 0 and abs(ta - rhs) / ta > 0.02:  # > 2% discrepancy
            anomalies.append(_anomaly(
                "Balance Sheet Does Not Balance", "critical", "Financial",
                f"Total assets ({ta:,.0f}) ≠ Total liabilities ({tl:,.0f}) + Equity ({eq:,.0f}) = {rhs:,.0f}. "
                "This suggests extraction error or misstatement.",
                f"Δ = {abs(ta - rhs):,.0f}",
            ))

    # 7. Not audited (informational for high-stakes use)
    if extraction.get("audited") is False:
        anomalies.append(_anomaly(
            "Unaudited Financial Statement", "informational", "Compliance",
            "This financial statement does not appear to be independently audited. Figures should be treated as management representations.",
            "audited: false",
        ))

    return anomalies


# ---------------------------------------------------------------------------
# RFP anomaly checks
# ---------------------------------------------------------------------------

def _check_rfp_anomalies(extraction: dict) -> list[dict]:
    anomalies: list[dict] = []

    if not extraction.get("submission_deadline"):
        anomalies.append(_anomaly(
            "Missing Submission Deadline", "critical", "Compliance",
            "No submission deadline is specified. Vendors cannot determine when proposals are due.",
            "submission_deadline: absent",
        ))

    contact = extraction.get("contact") or {}
    if not contact.get("email") and not contact.get("phone"):
        anomalies.append(_anomaly(
            "Missing Contact Information", "warning", "Operational",
            "No contact email or phone number is present. Vendors have no way to submit clarification questions.",
            "contact.email: absent, contact.phone: absent",
        ))

    # Evaluation criteria weights
    criteria = extraction.get("evaluation_criteria") or []
    weights = [c["weight_pct"] for c in criteria if c.get("weight_pct") is not None]
    if weights:
        total_weight = sum(weights)
        if abs(total_weight - 100) > 2:  # Allow 2% rounding tolerance
            anomalies.append(_anomaly(
                "Evaluation Criteria Weights Don't Sum to 100%",
                "warning", "Compliance",
                f"The stated evaluation criteria weights sum to {total_weight:.0f}%, not 100%. This creates scoring ambiguity.",
                f"Sum of weights: {total_weight:.0f}%",
            ))

    return anomalies


# ---------------------------------------------------------------------------
# Public stage runner
# ---------------------------------------------------------------------------

def run_anomaly_stage_local(ext_data: dict) -> dict:
    """
    Stage 3 (LOCAL): Anomaly Detection.

    Returns the same dict shape as the LLM version:
        { stage, status, data: { anomalies: [...] } }
    """
    doc_type   = ext_data.get("doc_type", "other")
    extraction = ext_data.get("extraction", {})
    anomalies: list[dict] = []

    try:
        if doc_type == "contract":
            anomalies = _check_contract_anomalies(extraction)
        elif doc_type == "nda":
            anomalies = _check_nda_anomalies(extraction)
        elif doc_type == "invoice":
            anomalies = _check_invoice_anomalies(extraction)
        elif doc_type == "financial_statement":
            anomalies = _check_financial_anomalies(extraction)
        elif doc_type == "rfp":
            anomalies = _check_rfp_anomalies(extraction)
        else:
            # No specific rules for 'other' — return empty, not an error
            anomalies = []

        return {
            "stage":  "anomaly",
            "status": "complete",
            "data":   {"anomalies": anomalies},
        }

    except Exception as e:
        logger.error("Local anomaly detection failed: %s", e, exc_info=True)
        return {"stage": "anomaly", "status": "error", "error": str(e)}