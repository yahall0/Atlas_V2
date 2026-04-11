"""FIR field extraction from raw OCR text.

Responsibility: raw text string → structured dict.

Design principles:
- Anchor-based regex extraction, not positional
- Text normalisation applied before all pattern matching
- Gujarati numeral conversion built-in
- BNS section validation with flagging of unknowns
- PII masking in narrative (phone numbers, Aadhaar)
- Tolerant of missing / re-ordered fields
- Never raises — always returns a best-effort dict
- narrative is the highest-priority field; always populated
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Gujarati digit → ASCII digit mapping
_GUJARATI_DIGITS: Dict[str, str] = {
    "૦": "0", "૧": "1", "૨": "2", "૩": "3", "૪": "4",
    "૫": "5", "૬": "6", "૭": "7", "૮": "8", "૯": "9",
}
_GUJARATI_TRANS = str.maketrans(_GUJARATI_DIGITS)

# Known valid BNS sections (2023 Act). Sections outside this set are flagged.
# BNS has 358 sections; include all from 1 upward.
_VALID_BNS_SECTIONS: Set[str] = {str(n) for n in range(1, 359)}

# Common IPC sections for reference
_VALID_IPC_SECTIONS: Set[str] = {
    "302", "304", "304B", "307", "319", "320", "323", "324", "325", "326",
    "354", "376", "379", "380", "392", "395", "396", "406", "409", "420",
    "427", "436", "447", "448", "449", "450", "452", "457", "465", "468",
    "471", "489A", "489B", "498A", "506", "509",
}

# Common Tesseract word-break artifacts in eGujCop FIRs
_OCR_FIXES: List[Tuple[str, str]] = [
    (r"Distric\s+t\b",         "District"),
    (r"Polic\s+e\b",            "Police"),
    (r"Sta\s*tion\b",           "Station"),
    (r"Sectio\s+ns?\b",         "Sections"),
    (r"Complai\s*nant\b",       "Complainant"),
    (r"Infor\s*mant\b",         "Informant"),
    (r"Infor\s*ma\s*tion\b",    "Information"),
    (r"Occur\s*rence\b",        "Occurrence"),
    (r"F\s*I\s*R\s*N\b",       "FIRN"),
    (r"dis\s*patch\b",          "dispatch"),
    (r"Signa\s*ture\b",         "Signature"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Normalise raw OCR text before field extraction.

    1. Convert Gujarati digits to ASCII.
    2. Collapse horizontal whitespace (preserving newlines as field separators).
    3. Fix common Tesseract word-break artifacts.
    """
    text = text.translate(_GUJARATI_TRANS)
    text = re.sub(r"[ \t]+", " ", text)
    for broken, fixed in _OCR_FIXES:
        text = re.sub(broken, fixed, text, flags=re.IGNORECASE)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# PII masking
# ─────────────────────────────────────────────────────────────────────────────

def _mask_pii(text: str) -> str:
    """Mask obvious PII before storage.

    Replaces Indian mobile numbers and 12-digit Aadhaar patterns.
    """
    text = re.sub(r"(?:\+91|91|0)?[6-9]\d{9}", "[PHONE]", text)
    text = re.sub(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b", "[AADHAAR]", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Section validation
# ─────────────────────────────────────────────────────────────────────────────

def _validate_sections(sections: List[str], act: Optional[str]) -> Dict[str, Any]:
    """Check sections against the known lookup table.

    Returns ``{"valid": [...], "unknown": [...]}`` — unknowns are flagged for
    manual review but do NOT block storage.
    """
    valid: List[str] = []
    unknown: List[str] = []
    reference = _VALID_BNS_SECTIONS if act in (None, "BNS") else _VALID_IPC_SECTIONS
    for s in sections:
        base = re.match(r"\d+", s)
        if base and base.group() in reference:
            valid.append(s)
        else:
            unknown.append(s)
            logger.warning("Section %s not in %s lookup — flagged for review", s, act or "BNS")
    return {"valid": valid, "unknown": unknown}


# ─────────────────────────────────────────────────────────────────────────────
# Field extractors  (all operate on normalised text)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_fir_number(text: str) -> Optional[str]:
    """eGujCop full FIR number.

    The 300-DPI OCR splits the field across two lines::

        ... FIRN 11192050250 Date 01/01/20
        ... 0. 010 (તારીખ

    The serial suffix after 'o.' / '0.' on the next line is appended to give
    the complete identifier (e.g. 11192050250010).
    """
    m = re.search(r"\bFIRN\s*[:\-]?\s*([\d]+)(?:\s+Date)?", text, re.IGNORECASE)
    if m:
        part1 = m.group(1).strip()
        # Look for trailing serial on the following line: "o. 010" or "0. 010"
        m2 = re.search(r"(?:o\.|0\.|૦\.)\s*(\d+)\s*(?:\(|$)", text)
        if m2:
            part2 = m2.group(1).strip()
            return part1 + part2
        return part1
    # Fallback: F.I.R. No. label
    m = re.search(
        r"F\.?I\.?R\.?\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z0-9/\-]+)",
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def _extract_district(text: str) -> Optional[str]:
    """Extract district from the Field-1 header row.

    eGujCop 300-DPI OCR layout example::

        1 08151110 અમદાવાદગ્રા Polic સાણંદ  Ye 20 FIRN ...
        t મ્ય e Sta ar 25 ...

    The district is the Gujarati word(s) between the row-1 code and 'Polic'.
    The second OCR line sometimes carries the tail of the district name.
    """
    # Primary: row-1 starts with digit(s) + numeric-code, then Gujarati district
    m = re.search(
        r"(?:^|\n)1\s+\S+\s+([\u0A80-\u0AFF][\u0A80-\u0AFF\s]*?)Polic",
        text, re.MULTILINE,
    )
    if m:
        district = m.group(1).strip()
        # Check whether the next row carries a tail (e.g. "t મ્ય e Sta")
        tail_m = re.search(
            r"Polic.*?\n\w?\s*([\u0A80-\u0AFF]+)\s+e\s+Sta", text
        )
        if tail_m:
            district = district + tail_m.group(1).strip()
        return re.sub(r"\s+", " ", district).strip() or None

    # Fallback 1: same-line "Distric[t] <value> Polic"
    m = re.search(r"Distric\w*\s+([\S][^\n]+?)\s+Polic", text, re.IGNORECASE)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val and not re.fullmatch(r"\([^)]+\)", val):
            return val

    # Fallback 2: Gujarati label
    m = re.search(r"(?:જીલ્લો|જિલ્લો)\)?\s*([\u0A80-\u0AFF\s]+)", text)
    if m:
        return m.group(1).strip()

    return None


def _extract_police_station(text: str) -> Optional[str]:
    """Extract police station name from the Field-1 header row.

    The PS name appears immediately after 'Polic' in the header row and ends
    before the year indicator ('Ye') or a multi-digit number.
    """
    # Primary: Gujarati text between 'Polic' and 'Ye' / year
    m = re.search(
        r"Polic\s+(?:e\s+Sta\s*tion\s+)?([\u0A80-\u0AFF][\u0A80-\u0AFF\s]*?)(?:Ye|Year|\s+\d{2}\s)",
        text, re.IGNORECASE,
    )
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val:
            return val

    # Fallback 1: same-line "Distric <district> Polic <ps_name>" classic layout
    m = re.search(r"Distric\w*\s+[\S][^\n]+?\s+Polic\w*\s+([^\n\(]+)", text, re.IGNORECASE)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val and not re.fullmatch(r"\([^)]+\)", val):
            return val

    # Fallback 2: "Police Station <value>"
    m = re.search(r"Police\s+Station\s+(.+?)[\(\n]", text, re.IGNORECASE | re.DOTALL)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(")")
        if val:
            return val

    # Fallback 3: Gujarati label
    m = re.search(r"(?:સ્ટેશન)\)?\s*([\u0A80-\u0AFF]+)", text)
    if m:
        val = m.group(1).strip()
        if val and val not in ("નું", "ની", "નો"):
            return val

    return None


def _extract_fir_date(text: str) -> Optional[str]:
    """Return ISO YYYY-MM-DD for the FIR registration date."""
    m = re.search(r"\b(20\d{2})[/\-](0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})\b", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _extract_occurrence_from(text: str) -> Optional[str]:
    """Return occurrence start date (ISO).

    eGujCop forms place the date value on a separate line from the label
    (multi-column layout), so we look for the first DD/MM/YYYY date that
    appears near the 'Date from' label within a 600-char window.
    """
    m = re.search(r"Date\s+from", text, re.IGNORECASE)
    if m:
        window = text[m.start():m.start() + 600]
        dm = re.search(r"(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})", window)
        if dm:
            return f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
    return None


def _extract_time_from(text: str) -> Optional[str]:
    """Return occurrence start time (HH:MM).

    Looks for the first HH:MM value within 600 chars of 'Time from' label.
    """
    m = re.search(r"Time\s+from", text, re.IGNORECASE)
    if m:
        window = text[m.start():m.start() + 600]
        tm = re.search(r"(\d{1,2}:\d{2})", window)
        if tm:
            return tm.group(1)
    return None


def _extract_complainant_name(text: str) -> Optional[str]:
    """Extract complainant name from form field anchored at '(a) Name'."""
    m = re.search(
        r"\(a\)\s*Name\s+(.+?)(?:Father|Husband|\(b\)|\n)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val:
            return val
    return None


def _extract_accused_name(text: str) -> Optional[str]:
    """Extract first accused name from the accused details block."""
    m = re.search(
        r"Accused\s+Name\s*(?:\([^)]*\))?\s*\n?\s*(.+?)(?:Age|Address|\n\n|$)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val and len(val) < 120:
            return val
    return None


def _extract_gpf_no(text: str) -> Optional[str]:
    """Extract GPF / badge number of the investigating officer."""
    m = re.search(r"GPF\s*No\.?\s*[:\-]?\s*(\w+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _extract_dispatch_date(text: str) -> Optional[str]:
    """Return court dispatch date (ISO) from 'dispatch to' anchor."""
    m = re.search(
        r"dispatch\s+to\s+(?:[^\d]*)?(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})",
        text, re.IGNORECASE,
    )
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _extract_primary_sections(text: str) -> List[str]:
    """Return deduplicated offence section list.

    Strategy 1 (preferred): Pattern like '305(a),331(4),54' — comma-separated
    with at least one sub-section qualifier.  Reliably extracted from
    eGujCop Field-2 regardless of OCR column layout.

    Strategy 2: Field-2 Gujarati label anchor 'કલમો' followed by sections.

    Strategy 3: 'Sectio\w*' label scan (classic layout).

    Never falls back to the document-wide digit scan which over-extracts.
    """
    # ── Strategy 1: comma-separated with sub-qualifier ───────────────────────
    m = re.search(
        r"(\d{1,4}\([a-zA-Z0-9]+\)(?:\s*,\s*\d{1,4}(?:\([a-zA-Z0-9]+\))?)+)",
        text,
    )
    if m:
        raw = m.group(1)
        sections = re.findall(r"\d{1,4}(?:\([a-zA-Z0-9]+\))?", raw)
        return list(dict.fromkeys(s for s in sections if int(re.match(r"\d+", s).group()) <= 600))

    # ── Strategy 2: Gujarati label 'કલમો' ────────────────────────────────────
    m = re.search(r"કલમો\)?\s*([\d\(\),a-zA-Z\s]+?)(?:\n|$)", text)
    if m:
        sections = re.findall(r"\d{1,4}(?:\([a-zA-Z0-9]+\))?", m.group(1))
        return [s for s in sections if int(re.match(r"\d+", s).group()) <= 600]

    # ── Strategy 3: classic 'Sections <digits>' label scan ───────────────────
    for m in re.finditer(r"Sectio\w*\s+([0-9][^\n]{1,80})", text, re.IGNORECASE):
        raw_line = m.group(1).strip()
        if re.match(r"^\d+\s+[A-Z]", raw_line):
            continue  # skip procedural "173 B.N.S.S"
        nums = re.findall(r"\d{2,4}(?:\([a-zA-Z0-9]\))?", raw_line)
        if nums:
            return list(dict.fromkeys(nums))

    return []


def _extract_primary_act(text: str, sections: Optional[List[str]] = None) -> Optional[str]:
    """Infer primary act via four cascading strategies.

    Strategy 1: ASCII keyword match (BNS, IPC, …) — also handles abbreviated
    dot-separated forms like 'B.N.S'.
    Strategy 2: Gujarati / Devanagari act name in the text.
    Strategy 3: Gujarati abbreviation 'બી.એન.એસ' (= B.N.S = BNS).
    Strategy 4: Section suffix heuristic — sub-section '(' implies BNS.
    """
    sections = sections or []

    # Strategy 1: ASCII (including dot-separated abbreviations)
    for act_name, pattern in [
        ("BNS",      r"\bBNS\b|\bB\.N\.S\b"),
        ("IPC",      r"\bIPC\b|\bI\.P\.C\b"),
        ("NDPS",     r"\bNDPS\b|\bN\.D\.P\.S\b"),
        ("POCSO",    r"\bPOCSO\b"),
        ("IT Act",   r"\bIT\s+Act\b"),
        ("Arms Act", r"\bArms\s+Act\b"),
        ("MV Act",   r"\bMV\s+Act\b"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            logger.info("Primary act inferred (direct match): %s", act_name)
            return act_name

    # Strategy 2: Gujarati / Hindi act names
    if "ન્યાય સંહિતા" in text or "न्याय संहिता" in text:
        logger.info("Primary act inferred (multilingual keyword): BNS")
        return "BNS"
    if "દંડ સંહિતા" in text or "दंड संहिता" in text:
        logger.info("Primary act inferred (multilingual keyword): IPC")
        return "IPC"

    # Strategy 3: Gujarati abbreviation for B.N.S (બી.એન.એસ)
    if "\u0AAC\u0AC0.\u0A8F\u0AA8.\u0A8F\u0AB8" in text:  # બી.એન.એસ
        logger.info("Primary act inferred (Gujarati abbreviation): BNS")
        return "BNS"

    # Strategy 4: section suffix heuristic
    if sections:
        if any("(" in s for s in sections):
            logger.info("Primary act inferred (section suffix heuristic): BNS")
            return "BNS"
        if any(re.fullmatch(r"\d{3,4}", s) for s in sections):
            logger.info("Primary act inferred (section number heuristic): IPC")
            return "IPC"

    logger.info("Primary act: could not be determined")
    return None


def _extract_narrative(text: str) -> str:
    """Extract Field-12 complaint narrative and mask PII before returning.

    Uses the Field-12 label 'First Information contents' as the anchor.
    Falls back to the Gujarati narrative opener 'તે એવી રીતે' if the
    English label is absent (rarer bilingual layouts).

    Deliberately does NOT use 'Information Received' (Field 3b) or generic
    'Complaint' as anchors — those labels appear earlier in the form and
    would capture only form fields rather than the actual narrative.
    """
    # Primary: Field-12 label, optionally preceded by "12 "
    m = re.search(
        r"(?:12\s+)?First\s+Information\s+contents.*?\n(.+?)"
        r"(?:Complaint\s*\(ફરિયાદ\)|pો\.s્ટે\.|Action\s+Taken|Signature)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        narrative = m.group(1).strip()
        narrative = re.sub(r"Page\s+\d+\s+of\s+\d+", "", narrative, flags=re.IGNORECASE)
        return _mask_pii(narrative.strip())

    # Fallback A: Gujarati narrative opener
    m = re.search(r"તે\s+એવી\s+રીતે\s+(.+?)(?:પો\.s્ટે\.|Action\s+Taken)", text, re.DOTALL)
    if m:
        return _mask_pii(("\u0aa4\u0ac7 \u0a8f\u0ab5\u0ac0 \u0ab0\u0ac0\u0aa4\u0ac7 " + m.group(1)).strip())

    # Fallback B: everything after the last Field-15 dispatch block
    m = re.search(r"dispatch\s+to.+?\n(.+)", text, re.IGNORECASE | re.DOTALL)
    if m:
        return _mask_pii(m.group(1).strip())

    return _mask_pii(text.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Rich (nested) field extractors  — operate on normalised text
# ─────────────────────────────────────────────────────────────────────────────


def _extract_occurrence_dates(text: str) -> Dict[str, Any]:
    """Return occurrence window as a dict: date_from, date_to, time_from, time_to."""
    result: Dict[str, Any] = {}

    # Date from / to
    for key, label in (("date_from", "from"), ("date_to", "to")):
        m = re.search(
            rf"Date\s+{label}\s*(?:\([^)]*\))?\s*(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{{2}})",
            text, re.IGNORECASE,
        )
        if not m:
            # Multi-column OCR: date sits up to 600 chars after the label
            anchor = re.search(rf"Date\s+{label}", text, re.IGNORECASE)
            if anchor:
                window = text[anchor.start(): anchor.start() + 600]
                m = re.search(
                    r"(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})", window
                )
                if m:
                    result[key] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                continue
        if m:
            result[key] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # Time from / to
    for key, label in (("time_from", "from"), ("time_to", "to")):
        anchor = re.search(rf"Time\s+{label}", text, re.IGNORECASE)
        if anchor:
            window = text[anchor.start(): anchor.start() + 600]
            tm = re.search(r"(\d{1,2}:\d{2})", window)
            if tm:
                result[key] = tm.group(1)

    return result


def _extract_info_received(text: str) -> Dict[str, Any]:
    """Return date + time when the PS received the information."""
    result: Dict[str, Any] = {}
    m = re.search(
        r"Information\s+received\s+Date\s*(?:\([^)]*\))?\s*"
        r"(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})",
        text, re.IGNORECASE,
    )
    if m:
        result["date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(
        r"Information\s+received.*?Time\s*(\d{1,2}:\d{2})",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        result["time"] = m.group(1)
    return result


def _extract_info_type(text: str) -> Optional[str]:
    """Oral / Written / Other — field 4 of the eGujCop form."""
    m = re.search(
        r"Type\s+of\s+Informa\s*(?:tion)?[:\s]*(.+?)(?:\n|માહિતીનો)",
        text, re.IGNORECASE,
    )
    if m:
        val = re.sub(r"[0-9]+|:|\(", "", m.group(1)).strip()
        return val if val else None
    return None


def _extract_place_of_occurrence(text: str) -> Dict[str, Any]:
    """Field 5: distance from PS (km) and address."""
    result: Dict[str, Any] = {}

    dm = re.search(r"distance\s+from\s+(.+?)(?:Beat|બીટ)", text, re.IGNORECASE | re.DOTALL)
    if dm:
        dist_m = re.search(r"([\d.]+)\s*(?:\(કિ\.મી|કિ\.મી|km)", dm.group(1), re.IGNORECASE)
        if dist_m:
            result["distance_km"] = dist_m.group(1)

    am = re.search(
        r"Addres\s*s\s+(.+?)(?:In\s+case|outside\s+|Name\s+of\s+P)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if am:
        addr = re.sub(r"\([^)]*\)|\n", " ", am.group(1)).strip()
        result["address"] = re.sub(r"\s+", " ", addr)

    return result


def _extract_complainant_details(text: str) -> Dict[str, Any]:
    """Field 6: full complainant dict (name, father, age, nationality, occupation, address)."""
    result: Dict[str, Any] = {}

    # Name (from form header)
    m = re.search(
        r"\(a\)\s*Name\s+(.+?)(?:\(0\)|\(b\)|Father|Husband)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        name = re.sub(r"\n.*", "", m.group(1)).strip()
        result["name"] = name

    # Father / Husband name
    m = re.search(
        r"(?:Father'?s?/?\s*|Husband'?\s*s?\s*Name)\s*(.+?)(?:\(c\)|\(ગ\)|Date/Year)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        fname = re.sub(r"\([^)]*\)|\n", " ", m.group(1)).strip()
        # Strip OCR page-header artefact ("Page N of M ...")
        fname = re.sub(r"Page\s+\d+\s+of\s+\d+.*", "", fname, flags=re.IGNORECASE).strip()
        result["father_husband_name"] = re.sub(r"\s+", " ", fname)

    # Full name re-stated in Gujarati narrative: "મારૂ નામ X ઉ.વ."
    m = re.search(r"મારૂ\s+નામ\s+(.+?)(?:ઉ\.વ\.|ઉ\.વ|ધંધો)", text, re.DOTALL)
    if m:
        full = re.sub(r"\n|\s+", " ", m.group(1)).strip()
        result["full_name_from_narrative"] = full

    # Age (from birth year field)
    m = re.search(r"Date/Year\s+of\s+Bi\s*(?:rth)?\s*(\d+)", text, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            result["age"] = int(m.group(1))
        except ValueError:
            pass

    # Nationality
    m = re.search(r"Nationality\s+(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        result["nationality"] = m.group(1).strip()

    # Occupation
    m = re.search(
        r"Occupation\s+(.+?)(?:\(વ\)|\(g\)|Address)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        occ = re.sub(r"\([^)]*\)|\n", " ", m.group(1)).strip()
        result["occupation"] = re.sub(r"\s+", " ", occ)

    # Address — mobile is masked in-place
    m = re.search(
        r"Address\s+(.+?)(?:\n7\s+Details|\nDetails\s+of)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        addr = re.sub(r"\([^)]*\)|\n", " ", m.group(1)).strip()
        addr = re.sub(r"\s+", " ", addr)
        # Detect phone; store masked version only
        if re.search(r"(?:\+91|91|0)?[6-9]\d{9}", addr):
            result["mobile_present"] = True
        result["address"] = _mask_pii(addr)

    return result


def _extract_accused_list(text: str) -> List[Dict[str, Any]]:
    """Field 7: list of accused dicts — each has name, is_unknown, age, address."""
    accused: List[Dict[str, Any]] = []

    m = re.search(
        r"Accused\s+Name\s*(.+?)(?:\n8\s+Reasons|\nReasons\s+for)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        block = m.group(1)
        # Unknown accused (Gujarati: અજાણ્યું)
        if re.search(r"અજ[ાણ]+[્]?[યું]*", block):
            accused.append({
                "name": "Unknown (અજાણ્યું)",
                "is_unknown": True,
                "age": None,
                "address": None,
            })
        else:
            # Numbered entries: (1) Name ...
            entries = re.findall(r"\(\d+\)\s*(.+?)(?=\(\d+\)|$)", block, re.DOTALL)
            for entry in entries:
                entry = entry.strip()
                if entry:
                    accused.append({
                        "name": entry.split("\n")[0].strip(),
                        "is_unknown": False,
                        "age": None,
                        "address": None,
                    })

    # Fallback: use existing simple extractor
    if not accused:
        name = _extract_accused_name(text)
        if name:
            is_unk = bool(re.search(r"Unknown|અજ[ાણ]+[્]?[યું]*", name))
            accused.append({"name": name, "is_unknown": is_unk, "age": None, "address": None})

    return accused


def _extract_action_taken(text: str) -> Dict[str, Any]:
    """Field 13: IO name, rank, and badge/number."""
    result: Dict[str, Any] = {}

    m = re.search(
        r"(?:Directed|Investigation).*?નામ\)?:?-?\s*\n?\s*(.+?)(?:Rank|$)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if not m:
        m = re.search(r"take\s+up.*?\n(.+?)(?:Rank|\n\s*No)", text, re.IGNORECASE | re.DOTALL)
    if m:
        result["io_name"] = re.sub(r"\n", " ", m.group(1)).strip()

    m = re.search(r"Rank\s*(?:\([^)]*\))?:?-?\s*(.+?)(?:\n|No\.)", text, re.IGNORECASE | re.DOTALL)
    if m:
        rank = re.sub(r"\([^)]*\)|\n", " ", m.group(1)).strip()
        result["io_rank"] = re.sub(r"\s+", " ", rank)

    m = re.search(r"No\.?\s*:?-?\s*(\w+)\s*to\s+take", text, re.IGNORECASE)
    if m:
        result["io_number"] = m.group(1)

    return result


def _extract_officer_details(text: str) -> Dict[str, Any]:
    """Field 14: signing officer name, rank, GPF number."""
    result: Dict[str, Any] = {}

    m = re.search(r"14.*?Name\s+(.+?)(?:\n|nant)", text, re.IGNORECASE | re.DOTALL)
    if m:
        result["name"] = m.group(1).strip()

    m = re.search(r"Rank\s+(.+?)(?:GPF|$)", text, re.IGNORECASE | re.DOTALL)
    if m:
        rank = re.sub(r"\([^)]*\)|\n", " ", m.group(1)).strip()
        result["rank"] = re.sub(r"\s+", " ", rank)

    m = re.search(r"GPF\s*No\.?\s*[:\-]?\s*(\w+)", text, re.IGNORECASE)
    if m:
        result["gpf_no"] = m.group(1)

    return result


def _extract_dispatch_details(text: str) -> Dict[str, Any]:
    """Field 15: court dispatch date and time."""
    result: Dict[str, Any] = {}
    m = re.search(
        r"dispatch\s+to\s+(?:[^\d]*)?"
        r"(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})"
        r"\s+(\d{1,2}:\d{2})",
        text, re.IGNORECASE,
    )
    if m:
        result["date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        result["time"] = m.group(4)
    else:
        # Date only
        m = re.search(
            r"dispatch\s+to\s+(?:[^\d]*)?"
            r"(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](20\d{2})",
            text, re.IGNORECASE,
        )
        if m:
            result["date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return result


def _extract_stolen_property(text: str) -> Dict[str, Any]:
    """Extract stolen items from the narrative with approximate values (Gujarati)."""
    result: Dict[str, Any] = {"items": [], "total_value": None}

    items = re.findall(
        r"((?:સોનાન[ોી]|ચાંદીન[ોી]|રોકડ|એક).+?)"
        r"(?:જેની\s+)?(?:કિ\.?\s*)?રૂ\.?\s*([\d,]+)",
        text,
    )
    for desc, value in items:
        desc = re.sub(r"\n|\s+", " ", desc).strip()
        result["items"].append({"description": desc, "value": value.replace(",", "")})

    m = re.search(r"(?:કુલ|Total)\s*(?:કિ\.?\s*)?રૂ\.?\s*([\d,]+)", text, re.IGNORECASE)
    if m:
        result["total_value"] = m.group(1).replace(",", "")

    return result


def _detect_pii(text: str) -> List[Dict[str, Any]]:
    """Detect (but not expose) PII present in the normalised text."""
    pii: List[Dict[str, Any]] = []
    for m in re.finditer(r"\b[6-9]\d{9}\b", text):
        pii.append({"type": "mobile", "position": m.start()})
    for m in re.finditer(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b", text):
        pii.append({"type": "aadhaar", "position": m.start()})
    for m in re.finditer(r"(?:રહે\.?\s*)?મકાન\s*નં\.?\s*[\d\u0AE6-\u0AEF]+", text):
        pii.append({"type": "address_house_no", "position": m.start()})
    return pii


def _check_completeness(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Return a completeness score for the mandatory FIR fields."""
    occ = extracted.get("occurrence") or {}
    complainant = extracted.get("complainant") or {}
    action = extracted.get("action_taken") or {}

    mandatory = {
        "district":         extracted.get("district"),
        "police_station":   extracted.get("police_station"),
        "fir_number":       extracted.get("fir_number"),
        "fir_date":         extracted.get("fir_date"),
        "sections":         extracted.get("primary_sections"),
        "occurrence_dates": occ.get("date_from"),
        "complainant_name": complainant.get("name") or extracted.get("complainant_name"),
        "narrative":        extracted.get("narrative"),
        "action_taken":     action.get("io_name"),
    }

    filled = sum(1 for v in mandatory.values() if v)
    total = len(mandatory)
    missing = [k for k, v in mandatory.items() if not v]

    return {
        "total_fields":     total,
        "filled_fields":    filled,
        "completeness_pct": round(filled / total * 100, 1),
        "missing_fields":   missing,
        "status":           "COMPLETE" if not missing else "INCOMPLETE",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def parse_fir_text(text: str) -> Dict[str, Any]:
    """Convert raw OCR FIR text into a structured dictionary.

    All extractors run independently — a failure in one never blocks the rest.
    The ``narrative`` key is always present and non-empty.

    The returned dict contains both flat fields (backward-compatible with the
    existing ``FIRCreate`` schema) and nested dicts for richer downstream
    processing by the pipeline.
    """
    if not text or not text.strip():
        logger.warning("parse_fir_text received empty text; returning bare narrative.")
        return {"narrative": "No extractable text found in document."}

    # Normalise once; all extractors use the cleaned copy
    norm = _normalise(text)

    result: Dict[str, Any] = {}

    # ── Simple / flat extractors (backward-compatible keys) ───────────────────
    for field, fn in [
        ("fir_number",       _extract_fir_number),
        ("district",         _extract_district),
        ("police_station",   _extract_police_station),
        ("fir_date",         _extract_fir_date),
        ("complainant_name", _extract_complainant_name),
        ("accused_name",     _extract_accused_name),
        ("gpf_no",           _extract_gpf_no),
    ]:
        try:
            result[field] = fn(norm)
        except Exception:
            logger.error("%s extraction failed.", field, exc_info=True)

    # ── Rich / nested extractors ───────────────────────────────────────────────
    for field, fn, default in [
        ("occurrence",          _extract_occurrence_dates,   {}),
        ("info_received",       _extract_info_received,      {}),
        ("info_type",           _extract_info_type,          None),
        ("place_of_occurrence", _extract_place_of_occurrence, {}),
        ("complainant",         _extract_complainant_details, {}),
        ("action_taken",        _extract_action_taken,       {}),
        ("officer",             _extract_officer_details,    {}),
        ("dispatch",            _extract_dispatch_details,   {}),
    ]:
        try:
            result[field] = fn(norm)
        except Exception:
            logger.error("%s extraction failed.", field, exc_info=True)
            result[field] = default

    try:
        result["accused"] = _extract_accused_list(norm)
    except Exception:
        logger.error("accused extraction failed.", exc_info=True)
        result["accused"] = []

    try:
        result["stolen_property"] = _extract_stolen_property(norm)
    except Exception:
        result["stolen_property"] = {"items": [], "total_value": None}

    # ── Sections & act ────────────────────────────────────────────────────────
    try:
        result["primary_sections"] = _extract_primary_sections(norm)
    except Exception:
        logger.error("primary_sections extraction failed.", exc_info=True)
        result["primary_sections"] = []

    try:
        result["primary_act"] = _extract_primary_act(norm, result.get("primary_sections"))
    except Exception:
        logger.error("primary_act extraction failed.", exc_info=True)

    try:
        result["sections_validation"] = _validate_sections(
            result.get("primary_sections") or [],
            result.get("primary_act"),
        )
    except Exception:
        logger.error("section validation failed.", exc_info=True)

    # ── PII detection + completeness ──────────────────────────────────────────
    try:
        result["pii_detected"] = _detect_pii(norm)
    except Exception:
        result["pii_detected"] = []

    # ── Narrative (last — highest priority, masks PII) ────────────────────────
    try:
        result["narrative"] = _extract_narrative(norm)
    except Exception:
        logger.error("narrative extraction failed; using full text as fallback.", exc_info=True)
        result["narrative"] = _mask_pii(text.strip()) or "Extraction failed."

    # ── Completeness (needs narrative to be set first) ────────────────────────
    try:
        result["completeness"] = _check_completeness(result)
    except Exception:
        result["completeness"] = {}

    # ── Back-fill flat backward-compat keys from nested dicts ─────────────────
    occ = result.get("occurrence") or {}
    dispatch = result.get("dispatch") or {}
    comp = result.get("complainant") or {}
    accused_list = result.get("accused") or []
    officer = result.get("officer") or {}

    if not result.get("occurrence_from"):
        result["occurrence_from"] = occ.get("date_from")
    if not result.get("time_from"):
        result["time_from"] = occ.get("time_from")
    if not result.get("dispatch_date"):
        result["dispatch_date"] = dispatch.get("date")
    if not result.get("gpf_no"):
        result["gpf_no"] = officer.get("gpf_no")
    if not result.get("complainant_name") and comp.get("name"):
        result["complainant_name"] = comp["name"]
    if not result.get("accused_name") and accused_list:
        result["accused_name"] = accused_list[0].get("name")

    logger.debug(
        "Parsed FIR: fir_number=%s, act=%s, sections=%s, completeness=%s%%, narrative_len=%d",
        result.get("fir_number"),
        result.get("primary_act"),
        result.get("primary_sections"),
        result.get("completeness", {}).get("completeness_pct"),
        len(result.get("narrative", "")),
    )

    return result
