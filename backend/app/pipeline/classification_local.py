"""
Stage 1 (LOCAL) — Document Classification & Metadata Extraction

Strategy
--------
• Classification  : BGE-small-en-v1.5 (ONNX, ~40 MB)  via cosine similarity
                    against per-class prototype sentences.  No PyTorch required.
• Party / date    : spaCy en_core_web_sm (NER) + targeted regex patterns.
• Jurisdiction    : Gazetteer + regex anchored to governing-law boilerplate.

Memory contract  : BGE ONNX session + spaCy model are module-level singletons
                   loaded on first call and kept resident (~55 MB total).
                   Neither object is reloaded per request.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_ort_session():
    """
    Load BGE-small-en-v1.5 ONNX model.

    Download once (CI / build step or first request):
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="BAAI/bge-small-en-v1.5",
            filename="onnx/model.onnx",
            local_dir="models/bge-small",
        )

    Expected path: models/bge-small/onnx/model.onnx  (relative to project root)
    Override with env var BGE_ONNX_PATH.
    """
    import os
    import onnxruntime as ort

    default = Path(__file__).resolve().parent.parent / "models" / "bge-small" / "onnx" / "model.onnx"
    model_path = Path(os.environ.get("BGE_ONNX_PATH", str(default)))

    if not model_path.exists():
        raise FileNotFoundError(
            f"BGE ONNX model not found at {model_path}. "
            "Run: python scripts/download_models.py"
        )

    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 2
    opts.intra_op_num_threads = 2
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
    logger.info("BGE-small ONNX session loaded from %s", model_path)
    return session


@lru_cache(maxsize=1)
def _get_tokenizer():
    """
    Load BGE tokenizer from local cache.
    Falls back to HuggingFace download on first run.
    """
    import os
    from tokenizers import Tokenizer

    default = Path(__file__).resolve().parent.parent / "models" / "bge-small" / "tokenizer.json"
    tok_path = Path(os.environ.get("BGE_TOKENIZER_PATH", str(default)))

    if tok_path.exists():
        return Tokenizer.from_file(str(tok_path))

    # Fallback: download via transformers (only on cold start)
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5")


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
# BGE embedding helper
# ---------------------------------------------------------------------------

def _embed(texts: list[str]) -> np.ndarray:
    """
    Returns L2-normalised float32 embeddings, shape (N, 384).
    Uses the BGE instruction prefix for retrieval tasks.
    """
    session = _get_ort_session()
    tokenizer = _get_tokenizer()

    # BGE-small instruction prefix for classification
    prefixed = [f"Represent this sentence: {t}" for t in texts]

    # Tokenise — handle both HF tokenizer and tokenizers.Tokenizer
    if hasattr(tokenizer, "batch_encode_plus"):
        enc = tokenizer.batch_encode_plus(
            prefixed,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np",
        )
        input_ids      = enc["input_ids"].astype(np.int64)
        attention_mask = enc["attention_mask"].astype(np.int64)
        token_type_ids = enc.get("token_type_ids", np.zeros_like(input_ids)).astype(np.int64)
    else:
        enc = tokenizer.encode_batch(prefixed)
        import numpy as np
        max_len = max(len(e.ids) for e in enc)

        def _pad(seq, length, val=0):
            return seq + [val] * (length - len(seq))

        input_ids      = np.array([_pad(e.ids,              max_len) for e in enc], dtype=np.int64)
        attention_mask = np.array([_pad(e.attention_mask,   max_len) for e in enc], dtype=np.int64)
        token_type_ids = np.array([_pad(e.type_ids,         max_len) for e in enc], dtype=np.int64)

    outputs = session.run(
        None,
        {
            "input_ids":      input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    # CLS token pooling (index 0 of last hidden state)
    embeddings = outputs[0][:, 0, :]

    # L2 normalise
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    return embeddings / norms


# ---------------------------------------------------------------------------
# Classification prototypes
# ---------------------------------------------------------------------------
#
# Each class gets 6 prototype sentences that are diverse but representative.
# The document embedding is compared (cosine) against the *mean* prototype
# embedding for each class; highest score wins.
#
_PROTOTYPES: dict[str, list[str]] = {
    "contract": [
        "This Services Agreement governs the terms under which the vendor will provide services to the client.",
        "The parties agree that payment shall be due within 30 days of invoice date.",
        "Either party may terminate this agreement upon 60 days written notice.",
        "The liability of each party shall not exceed the total fees paid in the preceding 12 months.",
        "This agreement constitutes the entire understanding between the parties regarding the subject matter hereof.",
        "The contractor shall deliver the software system by the agreed milestone dates.",
    ],
    "nda": [
        "The receiving party agrees to keep all disclosed information strictly confidential.",
        "Confidential Information means any non-public information disclosed by the Disclosing Party.",
        "This Non-Disclosure Agreement shall remain in effect for a period of two years.",
        "The parties agree not to disclose proprietary business information to third parties.",
        "Information that becomes publicly available through no fault of the Receiving Party is excluded.",
        "Upon termination, the receiving party shall destroy or return all confidential materials.",
    ],
    "invoice": [
        "Invoice Number: INV-2024-0042. Due Date: 15 March 2024.",
        "Please remit payment by bank transfer to the account details below.",
        "Line Item: Software development services. Quantity: 40 hours. Unit Price: $150.",
        "Subtotal: $6,000.00. VAT (20%): $1,200.00. Total Due: $7,200.00.",
        "This invoice is payable within 30 days of the invoice date.",
        "Vendor: Acme Corp. Bill To: GlobalTech Ltd. Purchase Order: PO-8821.",
    ],
    "rfp": [
        "Proposals must be submitted by 5pm on 30 April 2024 via the online procurement portal.",
        "This Request for Proposal invites qualified vendors to submit bids for IT infrastructure services.",
        "Evaluation criteria: Technical capability 40%, Price 30%, Experience 20%, References 10%.",
        "The successful bidder will be required to sign an NDA prior to contract award.",
        "Mandatory requirements: ISO 27001 certification and minimum five years of relevant experience.",
        "Questions regarding this RFP must be submitted in writing by 15 March 2024.",
    ],
    "financial_statement": [
        "Total Revenue for the year ended 31 December 2023 was $42.5 million.",
        "Net income attributable to shareholders increased by 12% year-over-year.",
        "The balance sheet as at 30 June 2024 shows total assets of £185 million.",
        "Operating cash flow for Q3 2024 was $3.2 million, up from $2.8 million in Q3 2023.",
        "Earnings per share (basic): $1.47. Diluted EPS: $1.42.",
        "The audited financial statements have been prepared in accordance with IFRS.",
    ],
    "other": [
        "This document does not fall into any standard commercial or legal category.",
        "General correspondence, memoranda, or miscellaneous business documents.",
        "Internal policy document or procedural guideline.",
        "Technical specification or product description document.",
    ],
}


@lru_cache(maxsize=1)
def _build_prototype_matrix() -> tuple[list[str], np.ndarray]:
    """
    Returns (class_labels, matrix) where matrix shape is (num_classes, 384).
    Each row is the mean normalised prototype embedding for that class.
    Cached after first call.
    """
    labels: list[str] = []
    rows: list[np.ndarray] = []

    for label, sentences in _PROTOTYPES.items():
        vecs = _embed(sentences)          # shape: (N, 384)
        mean_vec = vecs.mean(axis=0)
        norm = np.linalg.norm(mean_vec)
        mean_vec = mean_vec / (norm if norm > 0 else 1e-9)
        labels.append(label)
        rows.append(mean_vec)

    return labels, np.stack(rows, axis=0)  # (num_classes, 384)


def _classify_document(text: str) -> tuple[str, float]:
    """
    Returns (predicted_class, confidence_score 0-1).
    Confidence is the cosine similarity of the top class.
    """
    truncated_text = text[:1500]
    doc_vec = _embed([truncated_text])            # (1, 384)
    labels, proto_matrix = _build_prototype_matrix()

    scores = (proto_matrix @ doc_vec.T).flatten()  # (num_classes,)
    best_idx = int(np.argmax(scores))
    return labels[best_idx], float(scores[best_idx])


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

# --- Jurisdiction ---

_JURISDICTION_PHRASES = [
    r"governed\s+by\s+(?:the\s+)?laws?\s+of\s+([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;|\s+and\b)",
    r"courts?\s+of\s+([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;|\s+shall\b|\s+will\b)",
    r"venue\s+(?:shall|will)\s+be\s+(?:in\s+)?([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;)",
    r"subject\s+to\s+(?:the\s+)?(?:exclusive\s+)?jurisdiction\s+of\s+([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;)",
    r"applicable\s+law\s+(?:shall\s+be|is)\s+(?:the\s+)?(?:law\s+of\s+)?([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;)",
    r"construed\s+(?:under|in\s+accordance\s+with)\s+(?:the\s+)?laws?\s+of\s+([A-Z][A-Za-z ,()&'-]{2,60}?)(?:\.|,|;)",
]

_JURISDICTION_CLEAN = re.compile(
    r"\b(the\s+state\s+of|the\s+laws?\s+of|the\s+courts?\s+of|"
    r"the\s+country\s+of|pursuant\s+to|in\s+accordance\s+with)\b",
    re.IGNORECASE,
)


def _extract_jurisdiction(text: str) -> Optional[dict]:
    for pattern in _JURISDICTION_PHRASES:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            value = _JURISDICTION_CLEAN.sub("", m.group(1)).strip().strip(".,;")
            if len(value) < 3:
                continue
            # Grab the surrounding sentence as context (up to 200 chars)
            start = max(0, m.start() - 40)
            context = text[start: m.end() + 40].strip()[:200]
            return {"value": value, "context": context}
    return None


# --- Dates ---

# Patterns ordered from most-specific to least, so we get the richest match
_DATE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("named",  re.compile(
        r"(Effective|Execution|Expir(?:y|ation)|Termination|Commencement|Due|Renewal|Reporting\s+Period|Notice)\s+"
        r"[Dd]ate[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        re.IGNORECASE,
    )),
    ("long",   re.compile(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?([A-Z][a-z]+)\s+(\d{4})\b"
    )),
    ("month",  re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        re.IGNORECASE,
    )),
    ("iso",    re.compile(r"\b(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})\b")),
    ("dmy",    re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")),
]

_DATE_LABEL_MAP = {
    "effective": "Effective Date",
    "execution":  "Execution Date",
    "expiry":     "Expiration Date",
    "expiration": "Expiration Date",
    "termination": "Termination Date",
    "commencement": "Commencement Date",
    "due":        "Due Date",
    "renewal":    "Renewal Date",
    "reporting":  "Reporting Period",
    "notice":     "Notice Period",
}


def _extract_dates(text: str) -> list[dict]:
    results: list[dict] = []
    seen_values: set[str] = set()

    # Named dates (highest confidence)
    for m in _DATE_PATTERNS[0][1].finditer(text):
        label_raw = m.group(1).lower().split()[0]
        label = _DATE_LABEL_MAP.get(label_raw, "Date")
        value = m.group(2).strip()
        if value in seen_values:
            continue
        seen_values.add(value)
        start = max(0, m.start() - 20)
        context = text[start: m.end() + 60].strip()[:200]
        results.append({"value": value, "label": label, "context": context})

    # Generic date patterns for remaining untagged dates
    for name, pat in _DATE_PATTERNS[1:]:
        for m in pat.finditer(text):
            value = m.group(0).strip()
            if value in seen_values:
                continue
            seen_values.add(value)
            start = max(0, m.start() - 40)
            context = text[start: m.end() + 80].strip()[:200]
            results.append({"value": value, "label": "Date", "context": context})

    return results[:10]  # Cap — preambles rarely have more than 10 meaningful dates


# --- Parties ---

_PARTY_ROLE_KEYWORDS: dict[str, list[str]] = {
    "Client":            ["client", "customer", "purchaser", "buyer"],
    "Vendor":            ["vendor", "supplier", "provider", "seller"],
    "Service Provider":  ["service provider", "contractor", "consultant", "developer"],
    "Disclosing Party":  ["disclosing party", "discloser"],
    "Receiving Party":   ["receiving party", "recipient"],
    "Licensor":          ["licensor", "licens"],
    "Licensee":          ["licensee"],
    "Employer":          ["employer", "company"],
    "Employee":          ["employee", "worker"],
    "Buyer":             ["buyer", "purchaser"],
    "Seller":            ["seller"],
}


def _infer_role(name: str, surrounding_text: str) -> str:
    combined = (name + " " + surrounding_text).lower()
    for role, keywords in _PARTY_ROLE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return role
    return "Party"


def _extract_parties(text: str, spacy_nlp) -> list[dict]:
    """
    Uses spaCy NER (ORG/PERSON) on the first 3000 chars (preamble territory),
    then infers a role from surrounding context.
    """
    preamble = text[:3000]
    doc = spacy_nlp(preamble)

    seen_names: set[str] = set()
    parties: list[dict] = []

    for ent in doc.ents:
        if ent.label_ not in ("ORG", "PERSON"):
            continue
        name = ent.text.strip()
        # Skip very short or very long matches (artefacts)
        if len(name) < 3 or len(name) > 100:
            continue
        # Normalise: strip common alias markers like (the "Client")
        name_clean = re.sub(r'\s*\(.*?\)\s*', '', name).strip()
        if name_clean in seen_names:
            continue
        seen_names.add(name_clean)

        # Grab 200-char window around the entity for role inference
        window_start = max(0, ent.start_char - 100)
        window_end   = min(len(preamble), ent.end_char + 100)
        window = preamble[window_start:window_end]

        role = _infer_role(name_clean, window)
        basis = window.strip()[:200]

        parties.append({
            "name":  name_clean,
            "role":  role,
            "basis": basis,
        })

        if len(parties) == 2:
            break

    return parties


# ---------------------------------------------------------------------------
# Summary generation (entirely local, no LLM)
# ---------------------------------------------------------------------------

def _build_summary(doc_type: str, parties: list[dict], dates: list[dict], jurisdiction: Optional[dict]) -> str:
    """
    Builds a deterministic 2–3 line plain-English summary from the extracted
    metadata without any LLM call.
    """
    type_labels = {
        "contract":            "service/commercial contract",
        "nda":                 "non-disclosure agreement",
        "invoice":             "invoice",
        "rfp":                 "request for proposal",
        "financial_statement": "financial statement",
        "other":               "document",
    }
    label = type_labels.get(doc_type, "document")

    # Party line
    if len(parties) >= 2:
        party_line = f"between {parties[0]['name']} ({parties[0]['role']}) and {parties[1]['name']} ({parties[1]['role']})"
    elif len(parties) == 1:
        party_line = f"involving {parties[0]['name']} ({parties[0]['role']})"
    else:
        party_line = ""

    # Date line
    eff_dates = [d for d in dates if d["label"] in ("Effective Date", "Execution Date", "Commencement Date")]
    date_str = f" dated {eff_dates[0]['value']}" if eff_dates else ""

    # Jurisdiction line
    jur_str = f" Governed by the laws of {jurisdiction['value']}." if jurisdiction else ""

    summary = f"This is a {label}{' ' + party_line if party_line else ''}{date_str}.{jur_str}"
    return summary.strip()


# ---------------------------------------------------------------------------
# Text builder (mirrors extraction.py helper)
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
        for row in el["rows"]:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)
    return ""


def _build_text(doc_data: dict, max_chars: int = 4000) -> str:
    parts = []
    for page in doc_data.get("pages", [])[:2]:   # preamble lives on pages 1-2
        for el in page.get("elements", []):
            t = _element_to_text(el).strip()
            if t:
                parts.append(t)
    return "\n\n".join(parts)[:max_chars]


# ---------------------------------------------------------------------------
# Public stage runner
# ---------------------------------------------------------------------------

def run_classification_stage_local(doc_data: dict) -> dict:
    """
    Stage 1 (LOCAL): Document classification + metadata extraction.

    Returns the same dict shape as the LLM version:
        { stage, status, data: { document_type, primary_parties, dates,
                                  jurisdiction, document_summary } }
    """
    working_text = _build_text(doc_data)

    if not working_text.strip():
        return {
            "stage":  "classification",
            "status": "error",
            "error":  "No text could be extracted from the document for classification.",
        }

    try:
        # 1. Classify
        doc_type, confidence = _classify_document(working_text)
        logger.info("Classified as '%s' (cosine=%.3f)", doc_type, confidence)

        # 2. NER for parties
        nlp = _get_spacy()
        parties = _extract_parties(working_text, nlp)

        # 3. Date extraction
        dates = _extract_dates(working_text)

        # 4. Jurisdiction
        jurisdiction = _extract_jurisdiction(working_text)

        # 5. Lightweight summary (no LLM)
        summary = _build_summary(doc_type, parties, dates, jurisdiction)

        return {
            "stage":  "classification",
            "status": "complete",
            "data": {
                "document_type":    doc_type,
                "primary_parties":  parties,
                "dates":            dates,
                "jurisdiction":     jurisdiction,
                "document_summary": summary,
                "confidence":       round(confidence, 3),  # extra field, ignored by LLM path
            },
        }

    except FileNotFoundError as e:
        logger.error("Model not found: %s", e)
        return {"stage": "classification", "status": "error", "error": str(e)}

    except Exception as e:
        logger.error("Local classification failed: %s", e, exc_info=True)
        return {"stage": "classification", "status": "error", "error": str(e)}