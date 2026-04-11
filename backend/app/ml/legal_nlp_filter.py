"""Legal NLP post-processing: InLegalBERT-backed finding filter and narrator.

Two roles
---------
LegalFindingFilter
    Deduplicates semantically similar findings (same rule firing on many
    sections at once) and scores each finding against a library of known
    non-actionable patterns to surface likely false-positives.

FindingNarrator
    Groups findings by rule_id and renders a human-readable
    narrative_summary paragraph suitable for a supervisor's review screen.

Architecture
------------
  Rule engine (deterministic)
        ↓
  LegalFindingFilter  ← InLegalBERT embeddings (law-ai/InLegalBERT)
        ↓
  FindingNarrator     ← template grouper (no generative LLM required)
        ↓
  Enhanced ValidationReport dict

InLegalBERT is loaded lazily on first use. If the model cannot be loaded
(no internet, missing weights) the module degrades gracefully:
  • Deduplication falls back to exact-text matching.
  • Routine scoring falls back to rule-based heuristics on rule_id + section.
  • Narration continues unchanged (it is model-free).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_HF_CACHE = os.getenv("TRANSFORMERS_CACHE", "/transformers_cache")
_MODEL_NAME = os.getenv("LEGAL_NLP_MODEL", "law-ai/InLegalBERT")

# Cosine similarity above this → two findings are duplicates (same issue).
_DEDUP_THRESHOLD = float(os.getenv("LEGAL_NLP_DEDUP_THRESHOLD", "0.92"))

# Cosine similarity above this against a routine pattern → finding is flagged
# as likely non-actionable.
_ROUTINE_THRESHOLD = float(os.getenv("LEGAL_NLP_ROUTINE_THRESHOLD", "0.80"))

# ─────────────────────────────────────────────────────────────────────────────
# Lazy model state
# ─────────────────────────────────────────────────────────────────────────────

_tokenizer = None
_model = None
_routine_embeddings: Optional[Any] = None  # np.ndarray once loaded


def _load_model() -> bool:
    """Load InLegalBERT tokenizer + model. Returns True on success."""
    global _tokenizer, _model
    if _model is not None:
        return True
    try:
        from transformers import AutoModel, AutoTokenizer  # type: ignore

        _tokenizer = AutoTokenizer.from_pretrained(
            _MODEL_NAME, cache_dir=_HF_CACHE
        )
        _model = AutoModel.from_pretrained(_MODEL_NAME, cache_dir=_HF_CACHE)
        _model.eval()
        logger.info("InLegalBERT loaded from %s", _MODEL_NAME)
        return True
    except Exception:
        logger.warning(
            "InLegalBERT unavailable — NLP filter running in pass-through mode.",
            exc_info=True,
        )
        return False


def _encode(texts: List[str]) -> Optional[Any]:
    """Return L2-normalised mean-pool BERT embeddings or None on failure."""
    if not _load_model():
        return None
    try:
        import numpy as np
        import torch  # type: ignore

        inputs = _tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True,
        )
        with torch.no_grad():
            outputs = _model(**inputs)

        # Mean pool over token dimension, excluding padding tokens.
        mask = inputs["attention_mask"].unsqueeze(-1).float()  # (B, T, 1)
        summed = (outputs.last_hidden_state * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        embeddings = (summed / counts).numpy()  # (B, H)

        # L2 normalise for cosine similarity via dot product.
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9
        return embeddings / norms
    except Exception:
        logger.warning("InLegalBERT encoding failed.", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Routine pattern library
# Known non-actionable / expected patterns in Indian chargesheet practice.
# These are used as reference embeddings for routine-score computation.
# ─────────────────────────────────────────────────────────────────────────────

_ROUTINE_PATTERNS: List[str] = [
    # Joint liability / conspiracy sections are almost always added post-FIR
    "Section 34 IPC joint liability companion absent charged later during investigation",
    "Section 120B IPC conspiracy charge stands independently without companion offence",
    "Section 149 IPC unlawful assembly charged independently of companion section",
    "Section 109 IPC abetment companion section missing prosecution discretion applies",
    # Supplementary additions under 173(8) CrPC are routine and expected
    "Section present in chargesheet absent from FIR supplementary statement filed under 173 CrPC",
    "New section added to chargesheet after further investigation supplementary chargesheet filed",
    # Transitional IPC-to-BNS enforcement overlap
    "BNS equivalent of IPC section transitional period cases registered close to commencement date",
    # Evidence items sometimes attached separately are formatting gaps not legal gaps
    "Witness statement collected at police station may not always be attached to chargesheet",
    "Evidence item collected during investigation not listed in chargesheet document formatting gap",
    # NDPS companion sections are at prosecution discretion
    "Companion section for NDPS Act offence prosecution discretion whether to charge both",
    # Rule 4 warnings on minor companion omissions in straightforward cases
    "Companion section advisory warning review whether applicable on facts of the case",
    "Standard companion section not charged independent offence facts support single section",
]


def _get_routine_embeddings() -> Optional[Any]:
    global _routine_embeddings
    if _routine_embeddings is not None:
        return _routine_embeddings
    embs = _encode(_ROUTINE_PATTERNS)
    if embs is not None:
        _routine_embeddings = embs
    return _routine_embeddings


# ─────────────────────────────────────────────────────────────────────────────
# Rule-based fallback for routine detection (used when model is unavailable)
# ─────────────────────────────────────────────────────────────────────────────

# Sections that are almost always false-positive companions in RULE_4 warnings.
_GENERIC_SECTIONS = {"34", "120B", "149", "109"}


def _is_routine_heuristic(finding: Dict[str, Any]) -> bool:
    """Fallback routine detection without embeddings."""
    rule_id = finding.get("rule_id", "")
    severity = finding.get("severity", "")
    section_str = finding.get("section", "")

    # RULE_4 WARNING on generic sections → almost always routine.
    if rule_id == "RULE_4" and severity == "WARNING":
        section_tok = section_str.replace("IPC", "").replace("BNS", "").strip()
        if any(g in section_tok for g in _GENERIC_SECTIONS):
            return True

    # RULE_1 WARNING (section added to CS not in FIR) → typically routine 173(8).
    if rule_id == "RULE_1" and severity == "WARNING":
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# LegalFindingFilter
# ─────────────────────────────────────────────────────────────────────────────


class LegalFindingFilter:
    """InLegalBERT-backed post-processor for rule-engine findings.

    Step 1 — Deduplication
        Findings with the same rule_id whose description embeddings share
        cosine similarity ≥ DEDUP_THRESHOLD are merged into a single finding
        that lists all affected sections together.

    Step 2 — Routine scoring
        Each (deduplicated) finding is compared against the routine-pattern
        library. Findings scoring ≥ ROUTINE_THRESHOLD receive
        ``is_likely_routine: true`` as a hint to the UI.
    """

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def deduplicate(
        self, findings: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Merge semantically duplicate findings. Returns (deduped, suppressed_count)."""
        if len(findings) <= 1:
            return list(findings), 0

        texts = [f["description"] for f in findings]
        embs = _encode(texts)

        if embs is None:
            # Text-based fallback.
            seen: set = set()
            deduped: List[Dict[str, Any]] = []
            for f in findings:
                key = (f["rule_id"], f["description"][:100])
                if key not in seen:
                    seen.add(key)
                    deduped.append(dict(f))
            return deduped, len(findings) - len(deduped)

        import numpy as np

        sim_matrix = embs @ embs.T  # pre-normalised → cosine similarity

        # Greedy clustering: each finding joins the earliest cluster whose
        # representative has similarity ≥ threshold on the same rule.
        cluster_rep: Dict[int, int] = {}  # finding_idx → representative_idx
        representative_order: List[int] = []

        for i in range(len(findings)):
            assigned = False
            for rep in representative_order:
                if (
                    findings[rep]["rule_id"] == findings[i]["rule_id"]
                    and float(sim_matrix[i, rep]) >= _DEDUP_THRESHOLD
                ):
                    cluster_rep[i] = rep
                    assigned = True
                    break
            if not assigned:
                cluster_rep[i] = i
                representative_order.append(i)

        # Build merged findings: accumulate all section labels per cluster.
        merged_sections: Dict[int, List[str]] = {r: [] for r in representative_order}
        for i, finding in enumerate(findings):
            rep = cluster_rep[i]
            sec = finding.get("section", "").strip()
            if sec and sec not in merged_sections[rep]:
                merged_sections[rep].append(sec)

        deduped_out: List[Dict[str, Any]] = []
        for rep in representative_order:
            base = dict(findings[rep])
            sections = merged_sections[rep]
            if len(sections) > 1:
                base["section"] = ", ".join(sections)
                # Prefix description with multi-section note.
                base["description"] = (
                    base["description"].split(".")[0]
                    + f". [Affects {len(sections)} section(s): {', '.join(sections)}]"
                )
                base["merged_count"] = len(sections)
            else:
                base["merged_count"] = 1
            deduped_out.append(base)

        suppressed = len(findings) - len(deduped_out)
        return deduped_out, suppressed

    # ------------------------------------------------------------------
    # Routine scoring
    # ------------------------------------------------------------------

    def score_routine(
        self, findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Annotate each finding with ``routine_score`` and ``is_likely_routine``."""
        if not findings:
            return findings

        routine_embs = _get_routine_embeddings()
        texts = [
            f["description"] + " " + f.get("recommendation", "")
            for f in findings
        ]
        finding_embs = _encode(texts)

        result: List[Dict[str, Any]] = []
        for i, finding in enumerate(findings):
            f = dict(finding)
            if finding_embs is not None and routine_embs is not None:
                import numpy as np

                sims = finding_embs[i : i + 1] @ routine_embs.T  # (1, N_patterns)
                max_sim = float(sims.max())
                f["routine_score"] = round(max_sim, 3)
                f["is_likely_routine"] = max_sim >= _ROUTINE_THRESHOLD
            else:
                is_routine = _is_routine_heuristic(finding)
                f["routine_score"] = 0.85 if is_routine else 0.0
                f["is_likely_routine"] = is_routine
            result.append(f)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# FindingNarrator — template-based, no generative model required
# ─────────────────────────────────────────────────────────────────────────────

_RULE_TEMPLATES: Dict[str, str] = {
    "RULE_1": (
        "{count} section(s) appear in the charge-sheet that were not originally "
        "registered in the FIR ({sections}). This typically indicates post-investigation "
        "additions under Section 173(8) CrPC / 193(8) BNSS. Confirm that a supplementary "
        "statement has been filed for each new section."
    ),
    "RULE_2": (
        "{count} section(s) registered in the FIR have been dropped from the charge-sheet "
        "({sections}). Each dropped charge requires a documented reason in the investigation "
        "summary. A B-report must be filed where the charge is unsubstantiated."
    ),
    "RULE_3": (
        "{count} mutually exclusive section combination(s) have been detected ({sections}). "
        "These sections cannot be charged together on the same victim and the conflict must "
        "be resolved before the charge-sheet is filed in court."
    ),
    "RULE_4": (
        "{count} section(s) are charged without their standard companion sections ({sections}). "
        "These are advisory warnings — review whether the companion sections are supported "
        "by the facts of the case before accepting or dismissing."
    ),
    "RULE_5": (
        "{count} mandatory procedural requirement(s) are not reflected in the evidence list "
        "({sections}). These steps are legally required for the relevant offences and gaps "
        "in this area are likely to be challenged at trial."
    ),
    "RULE_6": (
        "{count} charge(s) cite an act inconsistent with the case date ({sections}). "
        "Cases registered on or after 1 July 2024 must use BNS sections; earlier cases "
        "must use IPC sections."
    ),
    "RULE_7": (
        "{count} mandatory evidence item(s) are absent from the charge-sheet ({sections}). "
        "Attaching all required evidence before filing will materially strengthen the "
        "prosecution case."
    ),
}

# Severity order — most serious first.
_RULE_ORDER = ["RULE_3", "RULE_6", "RULE_2", "RULE_5", "RULE_1", "RULE_7", "RULE_4"]


class FindingNarrator:
    """Renders a plain-text narrative_summary from a list of findings."""

    def narrate(self, findings: List[Dict[str, Any]]) -> str:
        """Return multi-paragraph narrative. Empty findings → pass message."""
        if not findings:
            return (
                "All legal cross-reference checks passed. "
                "No issues were identified in the charge-sheet."
            )

        # Group by rule_id.
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in findings:
            groups.setdefault(f["rule_id"], []).append(f)

        paragraphs: List[str] = []
        for rule_id in _RULE_ORDER:
            if rule_id not in groups:
                continue
            group = groups[rule_id]
            template = _RULE_TEMPLATES.get(rule_id)
            if not template:
                continue

            # Collect unique section labels across all findings in this group.
            sections: List[str] = []
            for f in group:
                for part in f.get("section", "").split(","):
                    s = part.strip()
                    if s and s not in sections:
                        sections.append(s)

            section_str = ", ".join(sections[:6])
            if len(sections) > 6:
                section_str += f" and {len(sections) - 6} more"

            paragraphs.append(template.format(count=len(group), sections=section_str))

        return "\n\n".join(paragraphs)


# ─────────────────────────────────────────────────────────────────────────────
# EvidenceGapNarrator — template-based narrator for evidence gap reports
# ─────────────────────────────────────────────────────────────────────────────

_SEVERITY_ORDER = ["critical", "important", "supplementary"]


class EvidenceGapNarrator:
    """Renders a plain-text narrative_summary from an evidence gap report.

    Groups gaps by severity and renders a summary paragraph covering:
      - Overall coverage percentage
      - Critical gaps (likely to cause acquittal)
      - Important gaps (will weaken prosecution)
      - AI-suggested gaps (pattern-based, advisory)
    """

    def narrate(self, report: Dict[str, Any]) -> str:
        gaps: List[Dict[str, Any]] = report.get("evidence_gaps", [])
        coverage_pct: float = report.get("evidence_coverage_pct", 100.0)
        crime_category: str = (
            report.get("crime_category") or "unclassified"
        ).replace("_", " ")
        total_expected: int = report.get("total_expected", 0)
        total_present: int = report.get("total_present", 0)

        if not gaps:
            return (
                f"All expected evidence for a {crime_category} case is present "
                f"({total_present}/{total_expected} items, {coverage_pct:.0f}% coverage). "
                "No evidence gaps were detected."
            )

        # Group gaps by severity.
        by_severity: Dict[str, List[Dict[str, Any]]] = {}
        for g in gaps:
            sev = (g.get("severity") or "supplementary").lower()
            by_severity.setdefault(sev, []).append(g)

        paragraphs: List[str] = []

        # Opening coverage sentence.
        paragraphs.append(
            f"Evidence coverage for this {crime_category} case is {coverage_pct:.0f}% "
            f"({total_present}/{total_expected} expected items). "
            f"{len(gaps)} gap(s) require attention before the charge-sheet can be filed."
        )

        if "critical" in by_severity:
            cats = [
                g["category"].replace("_", " ")
                for g in by_severity["critical"][:5]
            ]
            extra = len(by_severity["critical"]) - 5
            cat_str = ", ".join(cats) + (f" and {extra} more" if extra > 0 else "")
            paragraphs.append(
                f"{len(by_severity['critical'])} critical gap(s) were identified "
                f"({cat_str}). These are items typically required to sustain a conviction "
                "and their absence is likely to be exploited in cross-examination."
            )

        if "important" in by_severity:
            cats = [
                g["category"].replace("_", " ")
                for g in by_severity["important"][:4]
            ]
            extra = len(by_severity["important"]) - 4
            cat_str = ", ".join(cats) + (f" and {extra} more" if extra > 0 else "")
            paragraphs.append(
                f"{len(by_severity['important'])} important gap(s) were found "
                f"({cat_str}). These will materially weaken the prosecution case "
                "if not addressed before filing."
            )

        # AI-suggested (ml_pattern tier) items — call out separately.
        ai_gaps = [g for g in gaps if g.get("tier") == "ml_pattern"]
        if ai_gaps:
            paragraphs.append(
                f"{len(ai_gaps)} additional gap(s) were identified by pattern analysis "
                "based on similar cases. These are advisory — review whether they apply "
                "to the specific facts of this case."
            )

        return "\n\n".join(paragraphs)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singletons
# ─────────────────────────────────────────────────────────────────────────────

_filter = LegalFindingFilter()
_narrator = FindingNarrator()
_evidence_narrator = EvidenceGapNarrator()


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def enhance_validation_report(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Post-process a ValidationReport dict produced by the rule engine.

    Mutates ``report_dict`` in-place and returns it with three additional keys:

    filtered_findings : list
        Deduplicated, routine-scored version of ``findings``. All original
        findings are still in ``findings`` for the audit trail.
    suppressed_duplicate_count : int
        How many raw findings were merged during deduplication.
    narrative_summary : str
        Human-readable plain-text summary of all actionable findings,
        grouped by rule and ordered by severity.
    """
    findings: List[Dict[str, Any]] = report_dict.get("findings", [])

    # Step 1 — deduplicate.
    deduped, suppressed_count = _filter.deduplicate(findings)

    # Step 2 — score routine likelihood.
    scored = _filter.score_routine(deduped)

    # Step 3 — narrate actionable findings only (skip likely-routine ones).
    actionable = [f for f in scored if not f.get("is_likely_routine", False)]
    narrative = _narrator.narrate(actionable)

    report_dict["filtered_findings"] = scored
    report_dict["suppressed_duplicate_count"] = suppressed_count
    report_dict["narrative_summary"] = narrative

    return report_dict


def enhance_evidence_report(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Post-process an evidence gap report dict produced by EvidenceGapDetector.

    Mutates ``report_dict`` in-place and returns it with one additional key:

    narrative_summary : str
        Human-readable plain-text summary of all evidence gaps, grouped by
        severity and tier, with an opening coverage sentence.
    """
    report_dict["narrative_summary"] = _evidence_narrator.narrate(report_dict)
    return report_dict
