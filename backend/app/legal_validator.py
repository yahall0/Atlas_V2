"""Legal cross-reference validation engine.

Validates charge-sheet sections against the linked FIR and flags
mismatches, missing charges, procedural errors, and evidence gaps
that a prosecutor would catch before court submission.

Seven validation rules:
  RULE_1 — Section mismatch (CS has sections absent from FIR)
  RULE_2 — Dropped sections (FIR has sections absent from CS)
  RULE_3 — Invalid section combinations (mutually exclusive)
  RULE_4 — Missing companion sections
  RULE_5 — Procedural gaps
  RULE_6 — IPC/BNS act mismatch (wrong act for case date)
  RULE_7 — Evidence sufficiency
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.legal_db import (
    get_bns_commencement_date,
    get_companion_sections,
    get_mandatory_evidence,
    get_mutually_exclusive,
    get_procedural_requirements,
    get_section,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────


class Finding:
    """A single validation finding."""

    __slots__ = ("rule_id", "severity", "section", "description",
                 "recommendation", "confidence")

    def __init__(
        self,
        rule_id: str,
        severity: str,
        section: str,
        description: str,
        recommendation: str,
        confidence: float = 0.9,
    ):
        self.rule_id = rule_id
        self.severity = severity
        self.section = section
        self.description = description
        self.recommendation = recommendation
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "section": self.section,
            "description": self.description,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }


class ValidationReport:
    """Aggregated result of all validation rules."""

    def __init__(
        self,
        chargesheet_id: str,
        fir_id: Optional[str] = None,
    ):
        self.chargesheet_id = chargesheet_id
        self.fir_id = fir_id
        self.validation_timestamp = datetime.now(timezone.utc)
        self.findings: List[Finding] = []
        self._sections_validated: int = 0
        self._evidence_coverage_pct: float = 100.0

    @property
    def overall_status(self) -> str:
        severities = {f.severity for f in self.findings}
        if "CRITICAL" in severities:
            return "critical"
        if "ERROR" in severities:
            return "errors"
        if "WARNING" in severities:
            return "warnings"
        return "pass"

    def to_dict(self) -> Dict[str, Any]:
        critical = sum(1 for f in self.findings if f.severity == "CRITICAL")
        errors = sum(1 for f in self.findings if f.severity == "ERROR")
        warnings = sum(1 for f in self.findings if f.severity == "WARNING")
        return {
            "chargesheet_id": self.chargesheet_id,
            "fir_id": self.fir_id,
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "overall_status": self.overall_status,
            "findings": [f.to_dict() for f in self.findings],
            "summary": {
                "total_findings": len(self.findings),
                "critical": critical,
                "errors": errors,
                "warnings": warnings,
                "sections_validated": self._sections_validated,
                "evidence_coverage_pct": round(self._evidence_coverage_pct, 1),
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    """Strip sub-clause suffixes: '302(1)' -> '302'."""
    return re.sub(r"[\(\[].*$", "", s.strip().replace(" ", ""))


def _extract_sections_set(charges: List[Dict[str, Any]]) -> Set[str]:
    """Extract normalised section numbers from a list of charge dicts."""
    out: Set[str] = set()
    for c in charges:
        sec = c.get("section")
        if sec:
            out.add(_normalise(sec))
    return out


def _extract_evidence_keywords(evidence_list: List[Dict[str, Any]]) -> Set[str]:
    """Build a normalised keyword set from evidence descriptions and types."""
    keywords: Set[str] = set()
    for e in evidence_list:
        desc = (e.get("description") or "").lower()
        etype = (e.get("type") or "").lower()
        combined = f"{desc} {etype}"
        # Map common phrases to canonical evidence keys
        _KEYWORD_MAP = {
            "post mortem": "post_mortem_report",
            "post-mortem": "post_mortem_report",
            "postmortem": "post_mortem_report",
            "autopsy": "post_mortem_report",
            "scene of crime": "scene_of_crime_report",
            "crime scene": "scene_of_crime_report",
            "spot panchnama": "scene_of_crime_report",
            "witness": "witness_statements",
            "statement": "witness_statements",
            "weapon": "weapon_recovery",
            "recovery": "recovery_memo",
            "medical": "medical_report",
            "injury": "medical_report",
            "doctor": "medical_report",
            "forensic": "forensic_report",
            "dna": "forensic_report",
            "fingerprint": "fingerprint_report",
            "digital": "digital_evidence",
            "electronic": "digital_evidence",
            "cctv": "digital_evidence",
            "computer": "digital_evidence",
            "server": "server_logs",
            "seizure": "seizure_memo",
            "seized": "seizure_memo",
            "weighment": "weighment_memo",
            "document": "documentary_evidence",
            "receipt": "documentary_evidence",
            "contract": "documentary_evidence",
            "financial": "financial_records",
            "bank": "financial_records",
            "transaction": "financial_records",
            "stolen property": "stolen_property_list",
            "property list": "stolen_property_list",
            "identification parade": "identification_parade_report",
            "test identification": "identification_parade_report",
            "tip": "identification_parade_report",
            "inquest": "inquest_report",
            "164": "victim_statement_164",
            "magistrate statement": "victim_statement_164",
            "dowry": "dowry_demand_evidence",
            "stridhan": "dowry_demand_evidence",
            "ransom": "ransom_demand_evidence",
            "call record": "call_records",
            "cdr": "call_records",
            "fire brigade": "fire_brigade_report",
            "damage assessment": "damage_assessment",
            "audit": "audit_report",
            "handwriting": "handwriting_analysis",
            "threat": "threat_evidence",
            "suicide note": "suicide_note",
            "sample seal": "sample_sealing",
        }
        for phrase, key in _KEYWORD_MAP.items():
            if phrase in combined:
                keywords.add(key)
    return keywords


def _detect_act(charges: List[Dict[str, Any]]) -> str:
    """Determine the primary act used in the charge-sheet ('IPC' or 'BNS')."""
    acts = [c.get("act", "").upper() for c in charges if c.get("act")]
    if not acts:
        return "IPC"
    bns_count = sum(1 for a in acts if a == "BNS")
    ipc_count = sum(1 for a in acts if a == "IPC")
    return "BNS" if bns_count > ipc_count else "IPC"


# ─────────────────────────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────────────────────────


class LegalCrossReferenceValidator:
    """Validates a charge-sheet against a linked FIR and the legal database."""

    def validate(
        self,
        chargesheet_data: Dict[str, Any],
        fir_data: Optional[Dict[str, Any]] = None,
    ) -> ValidationReport:
        """Run all validation rules and return a ``ValidationReport``.

        Parameters
        ----------
        chargesheet_data : dict
            Charge-sheet row from DB (with ``charges_json``, ``evidence_json``,
            ``filing_date``, etc.).
        fir_data : dict or None
            Linked FIR row from DB. If ``None``, only internal-consistency
            rules (3–7) are run.
        """
        cs_id = str(chargesheet_data.get("id", ""))
        fir_id = str(fir_data["id"]) if fir_data else chargesheet_data.get("fir_id")
        if fir_id:
            fir_id = str(fir_id)

        report = ValidationReport(chargesheet_id=cs_id, fir_id=fir_id)

        cs_charges = chargesheet_data.get("charges_json") or []
        cs_evidence = chargesheet_data.get("evidence_json") or []
        cs_sections = _extract_sections_set(cs_charges)
        evidence_keywords = _extract_evidence_keywords(cs_evidence)
        cs_act = _detect_act(cs_charges)

        fir_sections: Set[str] = set()
        if fir_data:
            for s in (fir_data.get("primary_sections") or []):
                fir_sections.add(_normalise(s))

        report._sections_validated = len(cs_sections)

        # Rules 1 & 2 only when FIR is linked
        if fir_data and fir_sections:
            self._rule_1_section_mismatch(report, cs_sections, fir_sections, cs_act)
            self._rule_2_dropped_sections(report, cs_sections, fir_sections, cs_act)

        # Rules 3–7 always apply
        self._rule_3_invalid_combinations(report, cs_sections, cs_act)
        self._rule_4_missing_companions(report, cs_sections, cs_act, cs_charges)
        self._rule_5_procedural_gaps(report, cs_sections, cs_act, evidence_keywords)
        self._rule_6_ipc_bns_mismatch(report, cs_charges, chargesheet_data, fir_data)
        self._rule_7_evidence_sufficiency(report, cs_sections, cs_act, evidence_keywords)

        return report

    # ── Rule 1 ──────────────────────────────────────────────────────────────

    def _rule_1_section_mismatch(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        fir_sections: Set[str],
        act: str,
    ) -> None:
        """Sections in charge-sheet but NOT in FIR."""
        new_sections = cs_sections - fir_sections
        # Exclude generic sections (34, 120B, 149) — commonly added later
        generic = {"34", "120B", "149"}
        for sec in sorted(new_sections - generic):
            report.findings.append(Finding(
                rule_id="RULE_1",
                severity="WARNING",
                section=f"{sec} {act}",
                description=f"Section {sec} present in chargesheet but absent in FIR.",
                recommendation="Verify supplementary statement filed under 173(8) CrPC / 193(8) BNSS.",
                confidence=0.95,
            ))

    # ── Rule 2 ──────────────────────────────────────────────────────────────

    def _rule_2_dropped_sections(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        fir_sections: Set[str],
        act: str,
    ) -> None:
        """Sections in FIR but NOT in charge-sheet (dropped charges)."""
        dropped = fir_sections - cs_sections
        generic = {"34", "120B", "149"}
        for sec in sorted(dropped - generic):
            report.findings.append(Finding(
                rule_id="RULE_2",
                severity="ERROR",
                section=f"{sec} {act}",
                description=f"Section {sec} present in FIR but missing from chargesheet (dropped charge).",
                recommendation="Document reason for dropping section in investigation summary. File B-report if section unsubstantiated.",
                confidence=0.90,
            ))

    # ── Rule 3 ──────────────────────────────────────────────────────────────

    def _rule_3_invalid_combinations(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        act: str,
    ) -> None:
        """Mutually exclusive sections charged together."""
        checked: Set[str] = set()
        for sec in cs_sections:
            exclusives = get_mutually_exclusive(sec, act.lower())
            for exc in exclusives:
                exc_norm = _normalise(exc)
                pair_key = tuple(sorted([sec, exc_norm]))
                if exc_norm in cs_sections and pair_key not in checked:
                    checked.add(pair_key)
                    report.findings.append(Finding(
                        rule_id="RULE_3",
                        severity="ERROR",
                        section=f"{sec} + {exc_norm} {act}",
                        description=f"Sections {sec} and {exc_norm} are mutually exclusive and cannot be charged together on the same victim.",
                        recommendation=f"Remove either Section {sec} or Section {exc_norm}. Apply the section supported by evidence.",
                        confidence=0.95,
                    ))

    # ── Rule 4 ──────────────────────────────────────────────────────────────

    def _rule_4_missing_companions(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        act: str,
        cs_charges: List[Dict[str, Any]],
    ) -> None:
        """Primary section charged but standard companion absent."""
        for sec in cs_sections:
            companions = get_companion_sections(sec, act.lower())
            if not companions:
                continue
            entry = get_section(sec, act.lower())
            if not entry:
                continue
            # Only flag missing companions that are substantive (not generic)
            generic = {"34", "120B", "149"}
            for comp in companions:
                comp_norm = _normalise(comp)
                if comp_norm not in cs_sections and comp_norm not in generic:
                    entry_title = entry.get("title", sec)
                    report.findings.append(Finding(
                        rule_id="RULE_4",
                        severity="WARNING",
                        section=f"{sec} {act}",
                        description=f"Section {sec} ({entry_title}) charged without companion section {comp_norm}.",
                        recommendation=f"Consider adding Section {comp_norm} if facts support it.",
                        confidence=0.75,
                    ))

    # ── Rule 5 ──────────────────────────────────────────────────────────────

    def _rule_5_procedural_gaps(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        act: str,
        evidence_keywords: Set[str],
    ) -> None:
        """Required procedural steps not reflected in evidence."""
        _PROCEDURE_TO_EVIDENCE = {
            "magistrate_statement_164": {"victim_statement_164"},
            "medical_examination": {"medical_report"},
            "identification_parade": {"identification_parade_report"},
            "inquest_under_174": {"inquest_report"},
            "women_police_officer": set(),  # can't verify from evidence list
            "digital_evidence_preservation": {"digital_evidence"},
            "independent_witness_seizure": {"witness_statements", "seizure_memo"},
            "sample_sealing": {"sample_sealing"},
        }

        for sec in cs_sections:
            requirements = get_procedural_requirements(sec, act.lower())
            for req in requirements:
                expected_evidence = _PROCEDURE_TO_EVIDENCE.get(req, set())
                if not expected_evidence:
                    continue
                if not expected_evidence.intersection(evidence_keywords):
                    entry = get_section(sec, act.lower())
                    title = entry.get("title", sec) if entry else sec
                    report.findings.append(Finding(
                        rule_id="RULE_5",
                        severity="CRITICAL",
                        section=f"{sec} {act}",
                        description=f"Section {sec} ({title}) requires {req.replace('_', ' ')} but no corresponding evidence found in chargesheet.",
                        recommendation=f"Ensure {req.replace('_', ' ')} is completed and evidence attached before filing.",
                        confidence=0.90,
                    ))

    # ── Rule 6 ──────────────────────────────────────────────────────────────

    def _rule_6_ipc_bns_mismatch(
        self,
        report: ValidationReport,
        cs_charges: List[Dict[str, Any]],
        chargesheet_data: Dict[str, Any],
        fir_data: Optional[Dict[str, Any]],
    ) -> None:
        """Wrong act for case date (IPC on post-BNS case or vice versa)."""
        commencement = get_bns_commencement_date()  # "2024-07-01"

        # Determine the case date (FIR registration date or filing date)
        case_date_str = None
        if fir_data:
            case_date_str = str(fir_data.get("fir_date") or "")
        if not case_date_str:
            case_date_str = str(chargesheet_data.get("filing_date") or "")

        if not case_date_str or len(case_date_str) < 10:
            return  # Cannot determine date — skip

        try:
            # Handle both YYYY-MM-DD and DD/MM/YYYY
            if "-" in case_date_str:
                case_date = case_date_str[:10]
            else:
                return
        except Exception:
            return

        is_post_bns = case_date >= commencement

        for charge in cs_charges:
            charge_act = (charge.get("act") or "").upper()
            sec = charge.get("section") or "?"
            if not charge_act:
                continue

            if is_post_bns and charge_act == "IPC":
                report.findings.append(Finding(
                    rule_id="RULE_6",
                    severity="ERROR",
                    section=f"{sec} IPC",
                    description=f"Section {sec} IPC used but case registered after BNS commencement ({commencement}). BNS sections should be used.",
                    recommendation=f"Replace IPC Section {sec} with its BNS equivalent.",
                    confidence=0.95,
                ))
            elif not is_post_bns and charge_act == "BNS":
                report.findings.append(Finding(
                    rule_id="RULE_6",
                    severity="ERROR",
                    section=f"{sec} BNS",
                    description=f"Section {sec} BNS used but case registered before BNS commencement ({commencement}). IPC sections should be used.",
                    recommendation=f"Replace BNS Section {sec} with its IPC equivalent.",
                    confidence=0.95,
                ))

    # ── Rule 7 ──────────────────────────────────────────────────────────────

    def _rule_7_evidence_sufficiency(
        self,
        report: ValidationReport,
        cs_sections: Set[str],
        act: str,
        evidence_keywords: Set[str],
    ) -> None:
        """Check mandatory evidence for each charged section."""
        total_required = 0
        total_present = 0

        for sec in cs_sections:
            mandatory = get_mandatory_evidence(sec, act.lower())
            if not mandatory:
                continue

            total_required += len(mandatory)
            missing = [e for e in mandatory if e not in evidence_keywords]
            present_count = len(mandatory) - len(missing)
            total_present += present_count

            for m in missing:
                entry = get_section(sec, act.lower())
                title = entry.get("title", sec) if entry else sec
                report.findings.append(Finding(
                    rule_id="RULE_7",
                    severity="WARNING",
                    section=f"{sec} {act}",
                    description=f"Section {sec} ({title}) requires {m.replace('_', ' ')} but it is missing from evidence list.",
                    recommendation=f"Attach {m.replace('_', ' ')} to the chargesheet before filing.",
                    confidence=0.85,
                ))

        if total_required > 0:
            report._evidence_coverage_pct = (total_present / total_required) * 100
        else:
            report._evidence_coverage_pct = 100.0
