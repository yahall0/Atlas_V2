"""Charge-sheet field extraction from raw OCR text.

Responsibility: raw text string -> structured dict (ChargeSheetParsed).

Design principles (mirrors fir_parser.py):
- Anchor-based regex extraction, not positional
- Text normalisation applied before all pattern matching
- Gujarati numeral conversion built-in
- Tolerant of missing / re-ordered fields
- Handles Gujarati / Hindi / English mixed text
- Never raises -- always returns a best-effort dict
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_GUJARATI_DIGITS: Dict[str, str] = {
    "૦": "0", "૧": "1", "૨": "2", "૩": "3", "૪": "4",
    "૫": "5", "૬": "6", "૭": "7", "૮": "8", "૯": "9",
}
_GUJARATI_TRANS = str.maketrans(_GUJARATI_DIGITS)

# Common OCR word-break artifacts in charge-sheets
_OCR_FIXES = [
    (r"Charge[\s\-]*Sheet",      "Chargesheet"),
    (r"Investi\s*gat\w*",        "Investigation"),
    (r"Wit\s*ness",              "Witness"),
    (r"Evi\s*dence",             "Evidence"),
    (r"Accus\s*ed",              "Accused"),
    (r"Prosec\s*ution",          "Prosecution"),
    (r"Complai\s*nant",          "Complainant"),
    (r"Sectio\s+ns?\b",         "Sections"),
    (r"Distric\s+t\b",          "District"),
    (r"Polic\s+e\b",            "Police"),
    (r"Sta\s*tion\b",           "Station"),
]

# Evidence type keywords
_EVIDENCE_TYPES = {
    "documentary": "Documentary",
    "document": "Documentary",
    "physical": "Physical",
    "forensic": "Forensic",
    "digital": "Digital",
    "electronic": "Digital",
    "witness": "Witness Statement",
    "oral": "Oral",
    "medical": "Medical",
    "cctv": "Digital",
    "photograph": "Physical",
    "fingerprint": "Forensic",
}


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Normalise raw OCR text before field extraction."""
    text = text.translate(_GUJARATI_TRANS)
    text = re.sub(r"[ \t]+", " ", text)
    for broken, fixed in _OCR_FIXES:
        text = re.sub(broken, fixed, text, flags=re.IGNORECASE)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Field extractors (all operate on normalised text)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_fir_reference(text: str) -> Optional[str]:
    """Extract the FIR reference number from the charge-sheet."""
    patterns = [
        r"F\.?I\.?R\.?\s*(?:No\.?|Number|Ref)?\s*[:\-]?\s*([A-Z0-9/\-]+\d+)",
        r"(?:FIR|First\s+Information\s+Report)\s*(?:No\.?)?\s*[:\-]?\s*(\S+)",
        r"(?:એફ\.?આઈ\.?આર|ફરિયાદ)\s*(?:નં\.?|ક્રમાંક)?\s*[:\-]?\s*(\S+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".,;")
    return None


def _extract_court_name(text: str) -> Optional[str]:
    """Extract court name from the charge-sheet header."""
    patterns = [
        r"(?:IN\s+THE\s+COURT\s+OF|BEFORE\s+THE)\s+(.+?)(?:\n|$)",
        r"(?:Court|ન્યાયાલય|કોર્ટ)\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"(?:Judicial\s+Magistrate|Metropolitan\s+Magistrate|Sessions\s+Court)[\s,]*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = re.sub(r"\s+", " ", m.group(1) if "COURT OF" not in pat.upper()
                         else m.group(0)).strip().rstrip(".,;")
            if len(val) > 3:
                return val
    return None


def _extract_filing_date(text: str) -> Optional[str]:
    """Extract the charge-sheet filing date as ISO YYYY-MM-DD."""
    # Look for date near "filing" / "chargesheet" anchors
    anchored = re.search(
        r"(?:fil(?:ing|ed)|chargesheet|dated?)\s*[:\-]?\s*"
        r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
        text, re.IGNORECASE,
    )
    if anchored:
        d, m, y = anchored.group(1), anchored.group(2), anchored.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    # Gujarati date label
    anchored = re.search(
        r"(?:તારીખ)\s*[:\-]?\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
        text,
    )
    if anchored:
        d, m, y = anchored.group(1), anchored.group(2), anchored.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    return None


def _extract_io(text: str) -> Optional[str]:
    """Extract investigation officer name."""
    patterns = [
        r"(?:Investigating|Investigation)\s*Officer\s*[:\-]?\s*(.+?)(?:\n|,\s*\w+\s*Station)",
        r"(?:I\.?O\.?|IO)\s*[:\-]\s*(.+?)(?:\n|$)",
        r"(?:તપાસ\s*અધિકારી|તપાસનીશ)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;")
            if 2 < len(val) < 100:
                return val
    return None


def _extract_district(text: str) -> Optional[str]:
    """Extract district from the charge-sheet."""
    patterns = [
        r"Distric\w*\s*[:\-]?\s*([^\n,]+?)(?:\s*(?:Police|Station|PS)|[,\n])",
        r"(?:જીલ્લો|જિલ્લો)\s*[:\-]?\s*([\u0A80-\u0AFF\s]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip()
            if val:
                return val
    return None


def _extract_police_station(text: str) -> Optional[str]:
    """Extract police station from the charge-sheet."""
    patterns = [
        r"(?:P\.?S\.?|Police\s*Station)\s*[:\-]?\s*([^\n,]+?)(?:\s*(?:District|Dist)|[,\n])",
        r"(?:સ્ટેશન|પો\.સ્ટે\.)\s*[:\-]?\s*([\u0A80-\u0AFF\s]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip()
            if val:
                return val
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Structured list extractors
# ─────────────────────────────────────────────────────────────────────────────

def _extract_accused(text: str) -> List[Dict[str, Any]]:
    """Extract accused persons from the charge-sheet.

    Looks for an "Accused" section and parses name/age/address lines.
    """
    accused: List[Dict[str, Any]] = []

    # Find the accused section
    section = re.search(
        r"(?:ACCUSED|Accused\s*(?:Person|Party|No)?)\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:CHARGE|WITNESS|EVIDENCE|COMPLAINT|INVESTIGATION|SECTION|$))",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not section:
        # Fallback: numbered accused list
        section = re.search(
            r"(?:આરોપી|aaropee)\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:કલમ|સાક્ષી|પુરાવા|$))",
            text, re.DOTALL,
        )

    if not section:
        return accused

    block = section.group(1).strip()

    # Parse individual accused entries (numbered or line-separated)
    entries = re.split(r"\n\s*(?:\d+[\.\)]\s*|[A-Z]\d+[\.\)]\s*)", block)
    if len(entries) <= 1:
        entries = [line.strip() for line in block.split("\n") if line.strip()]

    for entry in entries:
        if not entry.strip() or len(entry.strip()) < 3:
            continue

        person: Dict[str, Any] = {"confidence": 0.7}

        # Name extraction
        name_m = re.match(r"(?:Name\s*[:\-]?\s*)?([A-Za-z\u0A80-\u0AFF\u0900-\u097F\s\.]+)", entry)
        if name_m:
            name = re.sub(r"\s+", " ", name_m.group(1)).strip()
            if name and len(name) > 1:
                person["name"] = name

        # Age extraction
        age_m = re.search(r"(?:Age|ઉંમર|आयु)\s*[:\-]?\s*(\d{1,3})", entry, re.IGNORECASE)
        if age_m:
            try:
                person["age"] = int(age_m.group(1))
            except ValueError:
                pass

        # Address extraction
        addr_m = re.search(r"(?:Address|Addr|સરનામું|पता)\s*[:\-]?\s*(.+?)(?:\n|$)", entry, re.IGNORECASE)
        if addr_m:
            person["address"] = addr_m.group(1).strip()

        # Role extraction
        role_m = re.search(r"(?:Role|ભૂમિકા)\s*[:\-]?\s*(.+?)(?:\n|$)", entry, re.IGNORECASE)
        if role_m:
            person["role"] = role_m.group(1).strip()

        if person.get("name"):
            accused.append(person)

    return accused


def _extract_charges(text: str) -> List[Dict[str, Any]]:
    """Extract IPC/BNS charge sections from the charge-sheet."""
    charges: List[Dict[str, Any]] = []
    seen = set()

    # Pattern: "Section 302 IPC" / "U/S 101 BNS" / "કલમ 302"
    patterns = [
        r"(?:Section|Sec\.?|U/?[Ss]\.?|કલમ)\s*(\d+[A-Za-z]?(?:\(\w+\))?)",
        r"(?:^|\s)(\d{2,3}[A-Z]?)\s+(?:IPC|BNS|CrPC|BNSS)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            sec = m.group(1).strip()
            if sec in seen:
                continue
            seen.add(sec)

            # Determine act
            ctx = text[max(0, m.start() - 20):m.end() + 30]
            act = "BNS"
            if re.search(r"\bIPC\b", ctx, re.IGNORECASE):
                act = "IPC"
            elif re.search(r"\bCrPC\b", ctx, re.IGNORECASE):
                act = "CrPC"
            elif re.search(r"\bBNSS\b", ctx, re.IGNORECASE):
                act = "BNSS"

            charges.append({
                "section": sec,
                "act": act,
                "description": None,
                "confidence": 0.9,
            })

    return charges


def _extract_evidence(text: str) -> List[Dict[str, Any]]:
    """Extract evidence items from the charge-sheet."""
    evidence: List[Dict[str, Any]] = []

    # Find evidence section
    section = re.search(
        r"(?:EVIDENCE|Evidence\s*(?:List|On\s*Record)?|LIST\s*OF\s*DOCUMENTS?|પુરાવા)\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:WITNESS|PRAYER|VERIFICATION|IO\s*CERT|$))",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not section:
        return evidence

    block = section.group(1).strip()
    lines = re.split(r"\n\s*(?:\d+[\.\)]\s*|[A-Z]\d*[\.\)]\s*|[-•]\s*)", block)
    if len(lines) <= 1:
        lines = [l.strip() for l in block.split("\n") if l.strip()]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        item: Dict[str, Any] = {"confidence": 0.7}

        # Classify evidence type
        line_lower = line.lower()
        item["type"] = "Documentary"  # default
        for keyword, etype in _EVIDENCE_TYPES.items():
            if keyword in line_lower:
                item["type"] = etype
                break

        item["description"] = re.sub(r"\s+", " ", line).strip()

        # Status
        if re.search(r"(?:collected|received|seized|obtained|recorded)", line, re.IGNORECASE):
            item["status"] = "collected"
        elif re.search(r"(?:pending|awaited|requested)", line, re.IGNORECASE):
            item["status"] = "pending"
        else:
            item["status"] = "collected"

        evidence.append(item)

    return evidence


def _extract_witnesses(text: str) -> List[Dict[str, Any]]:
    """Extract witnesses from the witness schedule."""
    witnesses: List[Dict[str, Any]] = []

    # Find witness section
    section = re.search(
        r"(?:WITNESS(?:ES)?|Witness\s*(?:Schedule|List)?|LIST\s*OF\s*WITNESS|સાક્ષી)\s*[:\-]?\s*\n?(.*?)(?=\n\s*(?:EVIDENCE|PRAYER|VERIFICATION|IO\s*CERT|SECTION|$))",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not section:
        return witnesses

    block = section.group(1).strip()
    entries = re.split(r"\n\s*(?:\d+[\.\)]\s*|[A-Z]\d*[\.\)]\s*|[-•]\s*)", block)
    if len(entries) <= 1:
        entries = [l.strip() for l in block.split("\n") if l.strip()]

    for entry in entries:
        entry = entry.strip()
        if not entry or len(entry) < 3:
            continue

        witness: Dict[str, Any] = {"confidence": 0.7}

        # Name is typically the first part
        name_m = re.match(r"([A-Za-z\u0A80-\u0AFF\u0900-\u097F\s\.]+?)(?:\s*[-–,\(]|$)", entry)
        if name_m:
            name = re.sub(r"\s+", " ", name_m.group(1)).strip()
            if name and len(name) > 1:
                witness["name"] = name

        # Role
        role_m = re.search(r"(?:Eye[\s-]*witness|Complainant|IO|Panch|Mahazar|Expert|Doctor|Medical|પંચ|ફરિયાદી)", entry, re.IGNORECASE)
        if role_m:
            witness["role"] = role_m.group(0).strip()

        # Statement summary (text after the name/role)
        rest = entry[name_m.end():] if name_m else entry
        rest = re.sub(r"^\s*[-–,\(]\s*", "", rest).strip()
        if rest and len(rest) > 5:
            witness["statement_summary"] = rest

        if witness.get("name"):
            witnesses.append(witness)

    return witnesses


# ─────────────────────────────────────────────────────────────────────────────
# Completeness scoring
# ─────────────────────────────────────────────────────────────────────────────

_FIELD_WEIGHTS = {
    "fir_reference_number": 15,
    "court_name": 10,
    "filing_date": 10,
    "investigation_officer": 10,
    "accused_list": 20,
    "charge_sections": 20,
    "evidence_list": 10,
    "witness_schedule": 5,
}


def _compute_completeness(parsed: Dict[str, Any]) -> float:
    """Compute extraction completeness as a percentage (0-100)."""
    total = sum(_FIELD_WEIGHTS.values())
    score = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        val = parsed.get(field)
        if val:
            if isinstance(val, list) and len(val) > 0:
                score += weight
            elif isinstance(val, str) and val.strip():
                score += weight
    return round((score / total) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_chargesheet_text(raw_text: str) -> Dict[str, Any]:
    """Parse raw OCR text from a charge-sheet PDF into structured fields.

    Parameters
    ----------
    raw_text:
        Plain text extracted from a charge-sheet PDF.

    Returns
    -------
    dict
        Structured fields matching ``ChargeSheetParsed`` schema.
        Never raises -- returns a best-effort dict with whatever could
        be extracted.
    """
    text = _normalise(raw_text)

    parsed: Dict[str, Any] = {
        "fir_reference_number": _extract_fir_reference(text),
        "court_name": _extract_court_name(text),
        "filing_date": _extract_filing_date(text),
        "investigation_officer": _extract_io(text),
        "district": _extract_district(text),
        "police_station": _extract_police_station(text),
        "accused_list": _extract_accused(text),
        "charge_sections": _extract_charges(text),
        "evidence_list": _extract_evidence(text),
        "witness_schedule": _extract_witnesses(text),
    }

    parsed["completeness_pct"] = _compute_completeness(parsed)
    parsed["raw_text"] = raw_text

    logger.info(
        "Chargesheet parse complete. fir_ref=%s, accused=%d, charges=%d, "
        "evidence=%d, witnesses=%d, completeness=%.1f%%",
        parsed.get("fir_reference_number"),
        len(parsed.get("accused_list", [])),
        len(parsed.get("charge_sections", [])),
        len(parsed.get("evidence_list", [])),
        len(parsed.get("witness_schedule", [])),
        parsed.get("completeness_pct", 0),
    )

    return parsed
