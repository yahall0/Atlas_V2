"""Charge-sheet field extraction from raw OCR text.

Responsibility: raw text string -> structured dict (ChargeSheetParsed).

Design principles:
- Anchor-based extraction first, then resilient block parsing
- Tolerant of OCR noise and reordered fields
- Supports English-first mixed documents with Gujarati numerals
- Returns additive metadata so downstream review can judge confidence
- Never raises; always returns best-effort output
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_INDIC_SPAN = "\u0A80-\u0AFF\u0900-\u097F"

_GUJARATI_DIGITS: Dict[str, str] = {
    "\u0AE6": "0",
    "\u0AE7": "1",
    "\u0AE8": "2",
    "\u0AE9": "3",
    "\u0AEA": "4",
    "\u0AEB": "5",
    "\u0AEC": "6",
    "\u0AED": "7",
    "\u0AEE": "8",
    "\u0AEF": "9",
}
_GUJARATI_TRANS = str.maketrans(_GUJARATI_DIGITS)

_OCR_FIXES = [
    (r"Charge[\s\-]*Sheet", "Chargesheet"),
    (r"Investi\s*gat\w*", "Investigation"),
    (r"Wit\s*ness", "Witness"),
    (r"Evi\s*dence", "Evidence"),
    (r"Accus\s*ed", "Accused"),
    (r"Prosec\s*ution", "Prosecution"),
    (r"Complai\s*nant", "Complainant"),
    (r"Sectio\s+ns?\b", "Sections"),
    (r"Distric\s+t\b", "District"),
    (r"Polic\s+e\b", "Police"),
    (r"Sta\s*tion\b", "Station"),
    (r"Magis\s*trate", "Magistrate"),
]

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
    "photo": "Physical",
    "fingerprint": "Forensic",
    "bank": "Documentary",
}

_SECTION_ALIASES: Dict[str, List[str]] = {
    "accused": [
        "accused persons",
        "accused person",
        "accused list",
        "accused details",
        "accused",
    ],
    "charges": [
        "charge sections",
        "charge",
        "charges",
        "sections",
        "u/s",
    ],
    "evidence": [
        "evidence on record",
        "evidence list",
        "list of documents",
        "list of material objects",
        "material objects",
        "material object",
        "documents relied upon",
        "evidence",
    ],
    "witnesses": [
        "witness schedule",
        "list of witnesses",
        "witness list",
        "witnesses",
        "witness",
    ],
}

_STOP_HEADERS = [
    "accused",
    "charge",
    "charges",
    "sections",
    "evidence",
    "documents",
    "witness",
    "witnesses",
    "verification",
    "prayer",
    "io certification",
    "investigation",
    "complainant",
    "brief facts",
    "facts of the case",
    "gist of the case",
    "synopsis",
    "conclusion of investigation",
    "conclusion",
]

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


def _normalise(text: str) -> str:
    """Normalise raw OCR text before field extraction."""
    text = (text or "").translate(_GUJARATI_TRANS)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for broken, fixed in _OCR_FIXES:
        text = re.sub(broken, fixed, text, flags=re.IGNORECASE)
    return text.strip()


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" \t:;,-")
    return value


def _iter_lines(text: str) -> List[str]:
    return [_clean_value(line) for line in text.split("\n")]


def _strip_bullet(line: str) -> str:
    return re.sub(r"^(?:\d+|[A-Z])[\.\)]\s*|^(?:[-*])\s*", "", line).strip()


def _strip_page_artifacts(value: str) -> str:
    value = re.sub(
        r"\b(?:supplementary\s+)?chargesheet\s*:.*?page\s+\d+\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\bpage\s+\d+\b", "", value, flags=re.IGNORECASE)
    return _clean_value(value)


def _looks_like_header(line: str) -> bool:
    lower = line.lower().strip()
    if not lower:
        return False
    if len(lower) > 70:
        return False
    return any(
        lower.startswith(header)
        or lower == header
        or lower.startswith(f"{header}:")
        for header in _STOP_HEADERS
    )


def _extract_named_block(text: str, aliases: List[str]) -> List[str]:
    """Extract a logical section by heading aliases.

    Works line-by-line because OCR output often loses paragraph structure.
    """
    lines = _iter_lines(text)
    start: Optional[int] = None
    collected: List[str] = []

    for idx, line in enumerate(lines):
        lower = line.lower()
        if any(alias in lower for alias in aliases):
            start = idx
            tail = re.split(r"\s*:\s*", line, maxsplit=1)
            if len(tail) == 2 and tail[1].strip():
                tail_value = _strip_page_artifacts(tail[1])
                if tail_value and not _looks_like_header(tail_value):
                    collected.append(tail_value)
            break

    if start is None:
        return []

    for line in lines[start + 1:]:
        if not line:
            if collected:
                collected.append("")
            continue
        if _looks_like_header(line):
            break
        collected.append(line)

    while collected and not collected[-1]:
        collected.pop()
    return collected


def _collapse_entries(lines: List[str]) -> List[str]:
    """Collapse section lines into logical list entries."""
    entries: List[str] = []
    current: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current:
                entries.append(" ".join(current).strip())
                current = []
            continue

        is_new_entry = bool(
            re.match(r"^(?:\d+|[A-Z])[\.\)]\s*", line)
            or line.startswith("- ")
            or line.startswith("* ")
            or re.match(r"^Name\s*[:\-]", line, re.IGNORECASE)
        )

        if is_new_entry and current:
            entries.append(" ".join(current).strip())
            current = [_strip_bullet(line)]
        elif current:
            current.append(_strip_bullet(line))
        else:
            current = [_strip_bullet(line)]

    if current:
        entries.append(" ".join(current).strip())

    return [entry for entry in entries if entry and len(entry) > 2]


def _extract_fir_reference(text: str) -> Optional[str]:
    patterns = [
        r"F\.?\s*I\.?\s*R\.?\s*(?:No\.?|Number|Ref(?:erence)?)?\s*[:\-]?\s*([A-Z0-9/\-]{4,})",
        r"(?:First\s+Information\s+Report)\s*(?:No\.?)?\s*[:\-]?\s*([A-Z0-9/\-]{4,})",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))
    return None


def _extract_court_name(text: str) -> Optional[str]:
    patterns = [
        r"(IN\s+THE\s+COURT\s+OF.+?)(?:\n|$)",
        r"(BEFORE\s+THE.+?)(?:\n|$)",
        r"((?:Judicial|Metropolitan|Sessions)\s+Magistrate.+?)(?:\n|$)",
        r"(Court\s*[:\-]\s*.+?)(?:\n|$)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = _clean_value(match.group(1))
            if len(candidate) > 8:
                return candidate
    return None


def _extract_filing_date(text: str) -> Optional[str]:
    label_patterns = [
        r"(?:Filed\s+Date|Filing\s+Date|Chargesheet\s+Date|Dated?)\s*[:\-]?\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
        r"(?:\u0AA4\u0ABE\u0AB0\u0AC0\u0A96)\s*[:\-]?\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})",
    ]
    for pat in label_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if not match:
            continue
        day, month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    generic = re.search(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b", text)
    if generic:
        day, month, year = generic.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def _extract_io(text: str) -> Optional[str]:
    patterns = [
        r"(?:Investigating|Investigation)\s*Officer\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"(?:I\.?O\.?|IO)\s*[:\-]\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if not match:
            continue
        value = _clean_value(match.group(1))
        value = re.sub(r"(?:Police\s+Station.*)$", "", value, flags=re.IGNORECASE).strip()
        if 2 < len(value) < 100:
            return value
    return None


def _extract_district(text: str) -> Optional[str]:
    patterns = [
        r"District\s*[:\-]?\s*([^\n,]+)",
        r"Dist\.?\s*[:\-]?\s*([^\n,]+)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))
    return None


def _extract_police_station(text: str) -> Optional[str]:
    patterns = [
        r"(?:Police\s*Station|P\.?S\.?)\s*[:\-]?\s*([^\n,]+)",
        r"(?:Station)\s*[:\-]?\s*([^\n,]+?)(?:\s+District\b|$)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return _clean_value(match.group(1))
    return None


def _extract_accused(text: str) -> List[Dict[str, Any]]:
    accused: List[Dict[str, Any]] = []
    entries = _collapse_entries(_extract_named_block(text, _SECTION_ALIASES["accused"]))

    if not entries:
        entries = [
            _clean_value(line)
            for line in _iter_lines(text)
            if re.search(r"\bName\s*[:\-]", line, re.IGNORECASE)
        ]

    for entry in entries:
        person: Dict[str, Any] = {"confidence": 0.72}

        name_match = re.search(
            r"(?:Name\s*[:\-]?\s*)?(.+?)(?=\s*(?:Age|Address|Role)\s*[:\-]|$)",
            entry,
            re.IGNORECASE,
        )
        if name_match:
            name = _clean_value(name_match.group(1))
            if name and len(name) > 1:
                person["name"] = name

        age_match = re.search(r"(?:Age)\s*[:\-]?\s*(\d{1,3})", entry, re.IGNORECASE)
        if age_match:
            try:
                person["age"] = int(age_match.group(1))
            except ValueError:
                pass

        address_match = re.search(
            r"(?:Address|Addr)\s*[:\-]?\s*(.+?)(?=\s*Role\s*[:\-]|$)",
            entry,
            re.IGNORECASE,
        )
        if address_match:
            person["address"] = _clean_value(address_match.group(1))

        role_match = re.search(r"(?:Role)\s*[:\-]?\s*(.+?)(?:$)", entry, re.IGNORECASE)
        if role_match:
            person["role"] = _clean_value(role_match.group(1))

        if person.get("name"):
            accused.append(person)

    return accused


def _extract_charges(text: str) -> List[Dict[str, Any]]:
    charges: List[Dict[str, Any]] = []
    seen = set()
    charge_lines = _extract_named_block(text, _SECTION_ALIASES["charges"])
    search_texts = ["\n".join(charge_lines)] if charge_lines else []
    search_texts.append(text)

    patterns = [
        r"(?:Section|Sec\.?|U/?[Ss]\.?|U/S|Under\s+Section)\s*(\d+[A-Za-z]?(?:\(\w+\))?)\s*(IPC|BNS|CrPC|BNSS|NDPS)?",
        r"(?:^|\s)(\d{2,3}[A-Z]?)\s+(IPC|BNS|CrPC|BNSS|NDPS)",
    ]

    for sample in search_texts:
        for pat in patterns:
            for match in re.finditer(pat, sample, re.IGNORECASE):
                section = _clean_value(match.group(1))
                act = _clean_value(match.group(2) or "BNS").upper()
                key = (section, act)
                if key in seen:
                    continue
                seen.add(key)
                charges.append(
                    {
                        "section": section,
                        "act": act,
                        "description": None,
                        "confidence": 0.9 if "Section" in match.group(0) or "Sec" in match.group(0) else 0.82,
                    }
                )
    return charges


def _is_probable_evidence_entry(entry: str) -> bool:
    lowered = entry.lower().strip()
    if len(lowered) < 12:
        return False

    reject_patterns = [
        r"\bbrief facts\b",
        r"\bfacts of the case\b",
        r"\bgist of the case\b",
        r"\bit was alleged\b",
        r"\bduring the course of investigation\b",
        r"\binvestigation has (?:also )?established\b",
        r"\bif f\.?i\.?r\.? is false\b",
        r"\baction taken\b.*\bnot applicable\b",
        r"\bwas the investigation officer\b",
        r"\bthe then superintendent of police\b",
        r"\bthe following facts have been established\b",
        r"\bunder sections?\b",
    ]
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in reject_patterns):
        return False

    evidence_signals = [
        r"\breport\b",
        r"\banalysis\b",
        r"\bexpert opinion\b",
        r"\bopinion\b",
        r"\bforensic\b",
        r"\bfsl\b",
        r"\blaboratory\b",
        r"\bseiz(?:ed|ure)\b",
        r"\bpanchnama\b",
        r"\bmemo\b",
        r"\bstatement\b",
        r"\brecords?\b",
        r"\bcctv\b",
        r"\bfootage\b",
        r"\bscreenshot\b",
        r"\bcall detail\b",
        r"\bcertificate\b",
        r"\bdocumentary\b",
        r"\bdigital\b",
        r"\bmedical\b",
        r"\bphysical\b",
        r"\bfingerprint\b",
        r"\bdna\b",
        r"\brecovery\b",
        r"\bfirearms?\b",
        r"\brifles?\b",
        r"\bslr\b",
        r"\bmagazines?\b",
        r"\bammunition\b",
        r"\bbayonet\b",
        r"\bweapon\b",
        r"\bmaterial object\b",
        r"\bcollected\b",
        r"\breceived\b",
        r"\bobtained\b",
        r"\brequested\b",
        r"\bpending\b",
    ]

    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in evidence_signals)


def _is_evidence_noise_line(line: str) -> bool:
    lowered = line.lower().strip()
    noise_patterns = [
        r"\bbrief facts\b",
        r"\bfacts of the case\b",
        r"\bgist of the case\b",
        r"\bif f\.?i\.?r\.? is false\b",
        r"\baction taken\b.*\bnot applicable\b",
        r"\bthe case was initially registered\b",
        r"\bduring the course of investigation\b",
        r"\bthe following facts have been established\b",
    ]
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in noise_patterns)


def _extract_evidence(text: str) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    lines = _extract_named_block(text, _SECTION_ALIASES["evidence"])
    if not lines:
        lines = [
            line
            for line in _iter_lines(text)
            if (
                re.search(r"\b(collected|pending|received|seized|obtained|recorded)\b", line, re.IGNORECASE)
                or re.search(r"\b(documentary|digital|forensic|medical|electronic|cctv|fingerprint)\b", line, re.IGNORECASE)
            )
        ]

    filtered_lines = [_strip_page_artifacts(line) for line in lines if not _is_evidence_noise_line(line)]

    for entry in _collapse_entries(filtered_lines):
        entry = _strip_page_artifacts(entry)
        if not _is_probable_evidence_entry(entry):
            continue

        item: Dict[str, Any] = {"confidence": 0.74}
        lowered = entry.lower()
        item["type"] = "Documentary"
        for keyword, evidence_type in _EVIDENCE_TYPES.items():
            if keyword in lowered:
                item["type"] = evidence_type
                break

        item["description"] = _clean_value(entry)

        if re.search(r"\b(collected|received|seized|obtained|recorded)\b", entry, re.IGNORECASE):
            item["status"] = "collected"
        elif re.search(r"\b(pending|awaited|requested)\b", entry, re.IGNORECASE):
            item["status"] = "pending"
        else:
            item["status"] = "collected"

        evidence.append(item)

    return evidence


def _extract_witnesses(text: str) -> List[Dict[str, Any]]:
    witnesses: List[Dict[str, Any]] = []
    lines = _extract_named_block(text, _SECTION_ALIASES["witnesses"])
    if not lines:
        lines = [
            line
            for line in _iter_lines(text)
            if re.search(r"\b(complainant|witness|eye-witness|expert|doctor|io)\b", line, re.IGNORECASE)
        ]

    for entry in _collapse_entries(lines):
        witness: Dict[str, Any] = {"confidence": 0.72}
        name_match = re.match(r"(.+?)(?=\s*-\s*|\s*\(|$)", entry)
        if name_match:
            name = _clean_value(name_match.group(1))
            if name and len(name) > 1:
                witness["name"] = name

        role_match = re.search(
            r"\b(Eye[\s-]*witness|Complainant|IO|Panch|Expert|Doctor|Medical|Investigating Officer)\b",
            entry,
            re.IGNORECASE,
        )
        if role_match:
            witness["role"] = _clean_value(role_match.group(0))

        summary = entry[name_match.end():] if name_match else entry
        summary = re.sub(r"^\s*[-,(]\s*", "", summary).strip()
        if summary and len(summary) > 5:
            witness["statement_summary"] = _clean_value(summary)

        if witness.get("name"):
            witnesses.append(witness)

    return witnesses


def _compute_completeness(parsed: Dict[str, Any]) -> float:
    total = sum(_FIELD_WEIGHTS.values())
    score = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        value = parsed.get(field)
        if isinstance(value, list) and value:
            score += weight
        elif isinstance(value, str) and value.strip():
            score += weight
    return round((score / total) * 100, 1)


def _classify_document_family(text: str) -> str:
    lower = text.lower()
    if "judicial magistrate" in lower or "metropolitan magistrate" in lower or "sessions court" in lower:
        return "court_filing"
    if "chargesheet" in lower or "charge-sheet" in lower:
        return "chargesheet_report"
    if "final report" in lower:
        return "final_report"
    return "mixed_format"


def _build_field_confidence(parsed: Dict[str, Any], raw_text: str) -> Dict[str, float]:
    return {
        "fir_reference_number": 0.96 if parsed.get("fir_reference_number") else 0.0,
        "court_name": 0.88 if parsed.get("court_name") else 0.0,
        "filing_date": 0.9 if parsed.get("filing_date") else 0.0,
        "investigation_officer": 0.82 if parsed.get("investigation_officer") else 0.0,
        "district": 0.8 if parsed.get("district") else 0.0,
        "police_station": 0.8 if parsed.get("police_station") else 0.0,
        "accused_list": min(0.58 + 0.12 * len(parsed.get("accused_list") or []), 0.95),
        "charge_sections": min(0.62 + 0.1 * len(parsed.get("charge_sections") or []), 0.95),
        "evidence_list": min(0.55 + 0.08 * len(parsed.get("evidence_list") or []), 0.92),
        "witness_schedule": min(0.5 + 0.08 * len(parsed.get("witness_schedule") or []), 0.9),
        "raw_text": 0.2 if raw_text.strip() else 0.0,
    }


def _build_quality_flags(parsed: Dict[str, Any], raw_text: str) -> List[str]:
    flags: List[str] = []
    if len(raw_text.strip()) < 120:
        flags.append("low_text_volume")
    if not parsed.get("fir_reference_number"):
        flags.append("missing_fir_reference")
    if not parsed.get("charge_sections"):
        flags.append("missing_charge_sections")
    if not parsed.get("accused_list"):
        flags.append("missing_accused_list")
    if not parsed.get("evidence_list"):
        flags.append("missing_evidence_list")
    return flags


def parse_chargesheet_text(raw_text: str) -> Dict[str, Any]:
    """Parse raw OCR text from a charge-sheet PDF into structured fields."""
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
    parsed["document_family"] = _classify_document_family(text)
    parsed["extraction_strategy"] = "hybrid_anchor_block_parser"
    parsed["field_confidence"] = _build_field_confidence(parsed, raw_text)
    parsed["field_sources"] = {
        "fir_reference_number": "header_anchor",
        "court_name": "header_anchor",
        "filing_date": "header_anchor",
        "investigation_officer": "header_anchor",
        "district": "header_anchor",
        "police_station": "header_anchor",
        "accused_list": "section_block",
        "charge_sections": "section_block_or_global_scan",
        "evidence_list": "section_block_or_fallback_scan",
        "witness_schedule": "section_block_or_fallback_scan",
    }
    parsed["quality_flags"] = _build_quality_flags(parsed, raw_text)
    parsed["raw_text"] = raw_text

    logger.info(
        "Chargesheet parse complete. fir_ref=%s, accused=%d, charges=%d, evidence=%d, "
        "witnesses=%d, completeness=%.1f%%, family=%s",
        parsed.get("fir_reference_number"),
        len(parsed.get("accused_list", [])),
        len(parsed.get("charge_sections", [])),
        len(parsed.get("evidence_list", [])),
        len(parsed.get("witness_schedule", [])),
        parsed.get("completeness_pct", 0.0),
        parsed.get("document_family"),
    )

    return parsed
