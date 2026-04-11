"""Canonical evidence taxonomy for ATLAS charge-sheet analysis.

Defines 20 evidence categories with crime-type applicability and weight,
plus functions to map free-text evidence descriptions to canonical keys.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

# ─────────────────────────────────────────────────────────────────────────────
# Evidence taxonomy — 20 categories
# ─────────────────────────────────────────────────────────────────────────────

EVIDENCE_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "post_mortem_report": {
        "applies_to": ["murder", "attempt_to_murder"],
        "weight": "critical",
        "description": "Post-mortem / autopsy report",
    },
    "scene_of_crime_report": {
        "applies_to": ["murder", "robbery", "dacoity", "property_crime"],
        "weight": "critical",
        "description": "Scene of crime / spot panchnama report",
    },
    "forensic_report": {
        "applies_to": ["murder", "sexual_offences", "narcotics"],
        "weight": "critical",
        "description": "Forensic Science Laboratory (FSL) report",
    },
    "cctv_footage": {
        "applies_to": ["robbery", "dacoity", "fraud", "cybercrime", "property_crime"],
        "weight": "important",
        "description": "CCTV / surveillance camera footage",
    },
    "witness_statements_161": {
        "applies_to": ["all"],
        "weight": "critical",
        "description": "Witness statements under Section 161 CrPC / 180 BNSS",
    },
    "victim_statement_164": {
        "applies_to": ["sexual_offences", "kidnapping"],
        "weight": "critical",
        "description": "Victim statement before Magistrate under Section 164 CrPC / 183 BNSS",
    },
    "medical_examination": {
        "applies_to": ["murder", "attempt_to_murder", "sexual_offences"],
        "weight": "critical",
        "description": "Medical examination / injury report",
    },
    "weapon_recovery": {
        "applies_to": ["murder", "attempt_to_murder", "robbery", "dacoity"],
        "weight": "important",
        "description": "Weapon / instrument recovery memo",
    },
    "electronic_evidence": {
        "applies_to": ["cybercrime", "fraud"],
        "weight": "critical",
        "description": "Electronic / digital evidence (devices, data)",
    },
    "financial_records": {
        "applies_to": ["fraud", "cybercrime"],
        "weight": "critical",
        "description": "Bank statements, transaction records, financial documents",
    },
    "identification_parade": {
        "applies_to": ["robbery", "dacoity", "kidnapping"],
        "weight": "important",
        "description": "Test identification parade (TIP) report",
    },
    "call_detail_records": {
        "applies_to": ["kidnapping", "cybercrime", "narcotics"],
        "weight": "important",
        "description": "Call detail records (CDR) / tower location data",
    },
    "narcotics_test_report": {
        "applies_to": ["narcotics"],
        "weight": "critical",
        "description": "Chemical analysis / narcotics test report",
    },
    "property_valuation": {
        "applies_to": ["property_crime", "robbery", "dacoity", "fraud"],
        "weight": "important",
        "description": "Property valuation / stolen property assessment",
    },
    "confession_statement": {
        "applies_to": ["all"],
        "weight": "supplementary",
        "description": "Confession or disclosure statement",
    },
    "site_plan_map": {
        "applies_to": ["murder", "robbery", "dacoity", "property_crime"],
        "weight": "important",
        "description": "Site plan / sketch map of crime scene",
    },
    "dna_report": {
        "applies_to": ["murder", "sexual_offences"],
        "weight": "important",
        "description": "DNA analysis report",
    },
    "fingerprint_report": {
        "applies_to": ["robbery", "dacoity", "property_crime"],
        "weight": "important",
        "description": "Fingerprint / latent print analysis report",
    },
    "seizure_memo": {
        "applies_to": ["narcotics", "robbery", "dacoity"],
        "weight": "critical",
        "description": "Seizure memo / panchnama for seized items",
    },
    "fsl_report": {
        "applies_to": ["murder", "narcotics", "sexual_offences"],
        "weight": "critical",
        "description": "Forensic Science Laboratory detailed report",
    },
}

ALL_CATEGORIES: List[str] = sorted(EVIDENCE_CATEGORIES.keys())

ALL_CRIME_TYPES: List[str] = [
    "murder", "attempt_to_murder", "robbery", "dacoity", "kidnapping",
    "sexual_offences", "fraud", "cybercrime", "narcotics",
    "property_crime", "missing_persons",
]

# ─────────────────────────────────────────────────────────────────────────────
# Keyword → category mapping for free-text classification
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORD_MAP: List[tuple[list[str], str]] = [
    (["post mortem", "post-mortem", "postmortem", "autopsy", "pm report",
      "પોસ્ટ મોર્ટમ", "शव परीक्षा"],
     "post_mortem_report"),
    (["scene of crime", "crime scene", "spot panchnama", "spot panch",
      "ઘટના સ્થળ", "घटनास्थल"],
     "scene_of_crime_report"),
    (["forensic report", "forensic analysis", "forensic lab", "fsl",
      "ફોરેન્સિક", "फॉरेंसिक"],
     "forensic_report"),
    (["cctv", "surveillance", "camera footage", "video recording",
      "સીસીટીવી"],
     "cctv_footage"),
    (["witness statement", "statement of witness", "161 crpc", "180 bnss",
      "examination of witness", "સાક્ષીનું નિવેદન", "गवाह का बयान"],
     "witness_statements_161"),
    (["164 crpc", "183 bnss", "magistrate statement", "victim statement",
      "statement before magistrate", "મેજિસ્ટ્રેટ નિવેદન"],
     "victim_statement_164"),
    (["medical examination", "medical report", "injury report", "mlc",
      "medico-legal", "doctor report", "તબીબી", "चिकित्सा"],
     "medical_examination"),
    (["weapon recovery", "weapon seized", "knife recovered", "gun recovered",
      "firearm", "હથિયાર", "हथियार"],
     "weapon_recovery"),
    (["electronic evidence", "digital evidence", "computer", "mobile phone",
      "hard disk", "pen drive", "laptop seized", "ડિજિટલ", "इलेक्ट्रॉनिक"],
     "electronic_evidence"),
    (["bank statement", "financial record", "transaction", "bank account",
      "cheque", "neft", "rtgs", "upi", "બેંક", "बैंक"],
     "financial_records"),
    (["identification parade", "test identification", "tip report",
      "ઓળખ પરેડ", "पहचान परेड"],
     "identification_parade"),
    (["call detail", "cdr", "call record", "tower location", "cell tower",
      "કોલ ડિટેઇલ"],
     "call_detail_records"),
    (["narcotics test", "chemical analysis", "drug test", "narcotic report",
      "ડ્રગ ટેસ્ટ", "मादक पदार्थ"],
     "narcotics_test_report"),
    (["property valuation", "stolen property", "property list",
      "value assessment", "મિલકત", "संपत्ति"],
     "property_valuation"),
    (["confession", "disclosure statement", "accused statement",
      "કબૂલાત", "इकबालिया"],
     "confession_statement"),
    (["site plan", "sketch map", "scene sketch", "spot map",
      "નકશો", "नक्शा"],
     "site_plan_map"),
    (["dna report", "dna analysis", "dna test", "dna sample",
      "ડીએનએ"],
     "dna_report"),
    (["fingerprint", "latent print", "finger print", "ફિંગરપ્રિંટ",
      "अंगुली छाप"],
     "fingerprint_report"),
    (["seizure memo", "seizure panchnama", "seized property",
      "જપ્તી", "जब्ती"],
     "seizure_memo"),
    (["fsl report", "forensic science laboratory", "lab report",
      "એફએસએલ"],
     "fsl_report"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_expected_evidence(
    crime_category: str,
    charged_sections: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Return expected evidence categories for a crime type.

    Parameters
    ----------
    crime_category : str
        One of the ATLAS crime categories.
    charged_sections : list[str], optional
        Charged IPC/BNS section numbers (for future section-specific logic).

    Returns
    -------
    list[dict]
        Each dict has keys: ``category``, ``weight``, ``description``.
    """
    result: List[Dict[str, Any]] = []
    for cat_key, cat_info in EVIDENCE_CATEGORIES.items():
        applies = cat_info["applies_to"]
        if "all" in applies or crime_category in applies:
            result.append({
                "category": cat_key,
                "weight": cat_info["weight"],
                "description": cat_info["description"],
            })
    return result


def classify_evidence_text(text: str) -> Optional[str]:
    """Map free-text evidence description to a canonical category.

    Uses keyword matching first; falls back to fuzzy matching via
    rapidfuzz if available.

    Parameters
    ----------
    text : str
        Evidence description text (may be English, Gujarati, or Hindi).

    Returns
    -------
    str or None
        Canonical category key, or ``None`` if no match found.
    """
    if not text or not text.strip():
        return None

    text_lower = text.lower().strip()

    # Exact keyword match (fast path)
    for keywords, category in _KEYWORD_MAP:
        for kw in keywords:
            if kw in text_lower:
                return category

    # Fuzzy matching fallback
    try:
        from rapidfuzz import fuzz

        best_score = 0.0
        best_cat: Optional[str] = None
        for keywords, category in _KEYWORD_MAP:
            for kw in keywords:
                score = fuzz.partial_ratio(kw, text_lower)
                if score > best_score:
                    best_score = score
                    best_cat = category
        if best_score >= 75:
            return best_cat
    except ImportError:
        pass

    return None


def classify_evidence_list(
    evidence_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Classify a list of evidence items and return matched categories.

    Parameters
    ----------
    evidence_items : list[dict]
        Each dict should have ``description`` and optionally ``type`` keys.

    Returns
    -------
    list[dict]
        Each dict: ``category``, ``source_text``, ``confidence``.
    """
    classified: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for item in evidence_items:
        desc = item.get("description", "")
        etype = item.get("type", "")
        combined = f"{desc} {etype}".strip()
        cat = classify_evidence_text(combined)
        if cat and cat not in seen:
            seen.add(cat)
            classified.append({
                "category": cat,
                "source_text": combined,
                "confidence": 0.92 if cat in [
                    c for kws, c in _KEYWORD_MAP
                    for kw in kws if kw in combined.lower()
                ] else 0.75,
            })

    return classified
