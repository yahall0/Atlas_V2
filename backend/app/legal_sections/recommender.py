"""Section recommender — orchestrates the end-to-end FIR → sections pipeline.

Pipeline (per the legal_sections README and ADR-D15):

    1. ``act_for(occurrence_date)``      — pick BNS or IPC by the 1-Jul-2024 cutoff
    2. ``retriever.retrieve(query)``     — top-K chunks ranked by cosine similarity
    3. aggregate by ``addressable_id``   — collapse multiple chunks of the same
       sub-clause to a single recommendation; max-pool the score
    4. apply confidence threshold        — drop entries below ``floor`` (default 0.40)
    5. apply conflict checks (Q10)       — drop over-charges, add required
       companions, attach warnings to remaining recommendations
    6. flag borderlines                  — top-2 within ``borderline_pct``
    7. emit ``RecommendationResponse``   — sub-clause-precise, court-ready output
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from .chunker import Chunk
from .conflicts import (
    ConflictFinding,
    RecommendContext,
    evaluate as evaluate_conflicts,
)
from .reranker import Reranker, get_reranker
from .retriever import InMemoryRetriever, RetrievedChunk

BNS_CUTOFF = date(2024, 7, 1)
DEFAULT_MODEL_VERSION = "atlas-rag-v1.0.0"


@dataclass
class Recommendation:
    section_id: str
    act: str
    section_number: str
    section_title: str | None
    sub_clause_label: str | None
    canonical_citation: str
    addressable_id: str
    confidence: float
    rationale_quote: str
    matching_fir_facts: list[str]
    related_sections: list[str]
    borderline_with: list[str]
    operator_note: str | None = None
    conflicts: list[dict] = None  # type: ignore[assignment]


@dataclass
class RecommendationResponse:
    fir_id: str
    act_basis: str
    occurrence_start: str | None
    model_version: str
    generated_at: str
    recommendations: list[Recommendation]
    conflict_findings: list[dict]


def act_for(occurrence_date_iso: str | None) -> str:
    """BNS for offences on or after 01 July 2024; IPC otherwise.

    If ``occurrence_date_iso`` is ``None`` or unparseable, default to BNS
    (the current statute). The IO can override on the recommendation surface.
    """
    if not occurrence_date_iso:
        return "BNS"
    try:
        d = datetime.fromisoformat(occurrence_date_iso.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return "BNS"
    return "BNS" if d >= BNS_CUTOFF else "IPC"


def _aggregate(
    retrieved: list[RetrievedChunk],
) -> list[tuple[str, RetrievedChunk]]:
    """Collapse retrieved chunks by addressable_id, max-pooling the score.

    Header chunks are demoted slightly so a sub-clause hit always outranks
    a section-header hit on the same parent.
    """
    by_id: dict[str, tuple[float, RetrievedChunk]] = {}
    for r in retrieved:
        score = r.score
        # Slight penalty for header / generic body — favour sub_clause hits
        if r.chunk.chunk_type in ("header", "section_body"):
            score *= 0.85
        prior = by_id.get(r.chunk.addressable_id)
        if prior is None or score > prior[0]:
            by_id[r.chunk.addressable_id] = (score, r)
    items = list(by_id.items())
    items.sort(key=lambda kv: -kv[1][0])
    return [(k, v[1]) for k, v in items]


def _flag_borderline(
    recs: list[Recommendation],
    pct: float,
) -> None:
    """Mark adjacent recommendations whose confidence is within ``pct``."""
    for i in range(len(recs) - 1):
        a, b = recs[i], recs[i + 1]
        if a.confidence > 0 and (a.confidence - b.confidence) / a.confidence <= pct:
            a.borderline_with.append(b.canonical_citation)
            b.borderline_with.append(a.canonical_citation)


def recommend(
    fir_id: str,
    fir_narrative: str,
    retriever: InMemoryRetriever,
    occurrence_date_iso: str | None = None,
    accused_count: int = 1,
    top_k_retrieve: int = 60,
    top_k_rerank: int = 25,
    confidence_floor: float = 0.20,
    borderline_pct: float = 0.10,
    model_version: str = DEFAULT_MODEL_VERSION,
    reranker: Reranker | None = None,
) -> RecommendationResponse:
    act = act_for(occurrence_date_iso)
    retrieved = retriever.retrieve(
        query=fir_narrative,
        k=top_k_retrieve,
        act_filter=act,
    )
    # Cross-encoder reranking — DevReranker by default; Bge3Reranker in
    # production (set ATLAS_RERANKER=bge-reranker-v2-m3).
    rer = reranker or get_reranker()
    reranked = rer.rerank(fir_narrative, retrieved, k=top_k_rerank)
    aggregated = _aggregate(reranked)

    recs: list[Recommendation] = []
    for addr_id, rc in aggregated:
        if rc.score < confidence_floor:
            continue
        c = rc.chunk
        recs.append(
            Recommendation(
                section_id=c.section_id,
                act=c.act,
                section_number=c.section_number,
                section_title=c.section_title,
                sub_clause_label=c.sub_clause_label,
                canonical_citation=c.canonical_citation,
                addressable_id=c.addressable_id,
                confidence=round(float(rc.score), 4),
                rationale_quote=c.text,
                matching_fir_facts=[],   # downstream NLP fills this; for now empty
                related_sections=[],
                borderline_with=[],
                operator_note=None,
                conflicts=[],
            )
        )

    # Conflict and over-charging pass (Q10)
    ctx = RecommendContext(
        fir_narrative=fir_narrative,
        occurrence_date_iso=occurrence_date_iso,
        accused_count=accused_count,
    )
    findings = evaluate_conflicts([r.canonical_citation for r in recs], ctx)

    # Apply: blocks remove the offending citation; warns attach to the entry
    blocked_ids: set[str] = set()
    for f in findings:
        if f.severity == "block" and f.rule_id.startswith("OVR-"):
            blocked_ids.update(f.affected_citations)
    if blocked_ids:
        recs = [r for r in recs if r.canonical_citation not in blocked_ids]

    # Attach warns and infos to affected recs
    for f in findings:
        if f.severity in ("warn", "info"):
            for r in recs:
                if r.canonical_citation in f.affected_citations:
                    r.conflicts.append({
                        "rule_id": f.rule_id,
                        "severity": f.severity,
                        "message": f.message,
                        "remediation": f.remediation,
                    })

    # Required companions: add as zero-confidence "must add" entries
    # — surfaced visibly to the IO with operator_note.
    for f in findings:
        if f.rule_id.startswith("REQ-"):
            for cit in f.affected_citations:
                if not any(r.canonical_citation == cit for r in recs):
                    recs.append(
                        Recommendation(
                            section_id=cit.replace(" ", "_").split("(")[0].rstrip("_"),
                            act=cit.split()[0],
                            section_number=cit.split()[1].split("(")[0],
                            section_title=None,
                            sub_clause_label=("(" + cit.split("(", 1)[1]) if "(" in cit else None,
                            canonical_citation=cit,
                            addressable_id=cit.replace(" ", "_").replace("(", "_").replace(")", ""),
                            confidence=0.0,
                            rationale_quote="(required companion — see conflicts)",
                            matching_fir_facts=[],
                            related_sections=[],
                            borderline_with=[],
                            operator_note=f"Required by rule {f.rule_id}: {f.message}",
                            conflicts=[{
                                "rule_id": f.rule_id,
                                "severity": f.severity,
                                "message": f.message,
                                "remediation": f.remediation,
                            }],
                        )
                    )

    recs.sort(key=lambda r: -r.confidence)
    _flag_borderline(recs, borderline_pct)

    return RecommendationResponse(
        fir_id=fir_id,
        act_basis=act,
        occurrence_start=occurrence_date_iso,
        model_version=model_version,
        generated_at=datetime.utcnow().isoformat() + "Z",
        recommendations=recs,
        conflict_findings=[
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "affected_citations": f.affected_citations,
                "message": f.message,
                "remediation": f.remediation,
            }
            for f in findings
        ],
    )


__all__ = ["Recommendation", "RecommendationResponse", "act_for", "recommend"]
