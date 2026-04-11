"""FIR ingestion pipeline.

Orchestrates the full flow:
    PDF bytes → text extraction → field parsing → enriched structured dict

The returned dict is compatible with ``FIRCreate`` / ``create_fir()`` from T3.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.ingestion.fir_parser import parse_fir_text
from app.ingestion.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)


def process_pdf(file_bytes: bytes, source_system: str = "pdf_upload") -> Dict[str, Any]:
    """Run the full FIR ingestion pipeline on raw PDF bytes.

    Steps
    -----
    1. Extract plain text from the PDF (``pdf_parser``).
    2. Parse FIR fields from the text (``fir_parser``).
    3. Attach ``raw_text`` (full extracted text, unmodified).
    4. Set ``source_system`` metadata.

    Parameters
    ----------
    file_bytes:
        Raw PDF content as bytes.
    source_system:
        Label identifying the upload origin (default ``"pdf_upload"``).

    Returns
    -------
    dict
        A dict ready to be validated by ``FIRCreate`` and passed to
        ``create_fir()``.  The ``narrative`` key is always present.
    """
    # Step 1: extract text
    raw_text = extract_text_from_pdf(file_bytes)
    logger.info("PDF text extraction complete. Characters extracted: %d.", len(raw_text))

    # Step 2: parse structured fields
    parsed = parse_fir_text(raw_text)

    # Step 3: Flatten nested dicts for DB / FIRCreate schema compatibility
    occ          = parsed.get("occurrence")          or {}
    info_recv    = parsed.get("info_received")       or {}
    place        = parsed.get("place_of_occurrence") or {}
    complainant  = parsed.get("complainant")         or {}
    action       = parsed.get("action_taken")        or {}
    officer      = parsed.get("officer")             or {}
    dispatch     = parsed.get("dispatch")            or {}
    accused_list = parsed.get("accused")             or []

    result: dict = {
        # ── Core identification ────────────────────────────────────────────
        "fir_number":    parsed.get("fir_number"),
        "district":      parsed.get("district"),
        "police_station": parsed.get("police_station"),
        "fir_date":      parsed.get("fir_date"),

        # ── Legal classification ───────────────────────────────────────────
        "primary_sections":   parsed.get("primary_sections") or [],
        "primary_act":        parsed.get("primary_act"),
        "sections_validation": parsed.get("sections_validation"),

        # ── Occurrence window ──────────────────────────────────────────────
        "occurrence_from": occ.get("date_from") or parsed.get("occurrence_from"),
        "occurrence_to":   occ.get("date_to"),
        "time_from":       occ.get("time_from") or parsed.get("time_from"),
        "time_to":         occ.get("time_to"),

        # ── Information received at PS ─────────────────────────────────────
        "info_received_date": info_recv.get("date"),
        "info_received_time": info_recv.get("time"),

        # ── Information type ───────────────────────────────────────────────
        "info_type": parsed.get("info_type"),

        # ── Place of occurrence ────────────────────────────────────────────
        "place_distance_km": place.get("distance_km"),
        "place_address":     place.get("address"),

        # ── Complainant (flat cols for firs table) ─────────────────────────
        "complainant_name":         complainant.get("name") or parsed.get("complainant_name"),
        "complainant_father_name":  complainant.get("father_husband_name"),
        "complainant_age":          complainant.get("age"),
        "complainant_nationality":  complainant.get("nationality"),
        "complainant_occupation":   complainant.get("occupation"),

        # ── Accused ────────────────────────────────────────────────────────
        "accused_name": (
            accused_list[0].get("name") if accused_list else None
        ) or parsed.get("accused_name"),

        # ── Investigating / signing officer ────────────────────────────────
        "gpf_no":       officer.get("gpf_no") or parsed.get("gpf_no"),
        "io_name":      action.get("io_name"),
        "io_rank":      action.get("io_rank"),
        "io_number":    action.get("io_number"),
        "officer_name": officer.get("name"),

        # ── Dispatch ───────────────────────────────────────────────────────
        "dispatch_date": dispatch.get("date") or parsed.get("dispatch_date"),
        "dispatch_time": dispatch.get("time"),

        # ── Stolen property (JSONB) ────────────────────────────────────────
        "stolen_property": parsed.get("stolen_property"),

        # ── Completeness percentage ────────────────────────────────────────
        "completeness_pct": (parsed.get("completeness") or {}).get("completeness_pct"),

        # ── Narrative + raw text ───────────────────────────────────────────
        "narrative": parsed.get("narrative"),
        "raw_text":  raw_text,

        # ── Metadata ──────────────────────────────────────────────────────
        "source_system": source_system,

        # ── Nested entities for complainants / accused tables ──────────────
        "complainants": (
            [{
                "name":        complainant.get("name"),
                "father_name": complainant.get("father_husband_name"),
                "age":         complainant.get("age"),
                "address":     complainant.get("address"),
            }]
            if complainant.get("name") else []
        ),
        "accused": [
            {
                "name":    a.get("name"),
                "age":     a.get("age"),
                "address": a.get("address"),
            }
            for a in accused_list
        ],
    }

    # Safety guarantee: narrative must not be empty after the full pipeline
    if not result.get("narrative", "").strip():
        logger.warning("Pipeline produced empty narrative; using raw_text as fallback.")
        result["narrative"] = raw_text.strip() or "No extractable content."

    logger.info(
        "Pipeline complete. fir_number=%s, sections=%d, completeness=%s%%, narrative_len=%d.",
        result.get("fir_number"),
        len(result.get("primary_sections") or []),
        (result.get("completeness_pct") or "?"),
        len(result.get("narrative", "")),
    )

    return result
