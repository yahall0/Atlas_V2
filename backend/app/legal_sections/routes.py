"""FastAPI routes for the section recommender.

Endpoints (per [API Reference §12](docs/solution_design/03_api_reference.md#12-section-recommendation-sprint-6)):

* ``POST /api/v1/firs/{fir_id}/recommend-sections``
    Run the section recommender for a FIR. Either ``narrative`` is supplied
    in the request body, or the FIR is loaded from the database (when the
    DB integration lands; for now ``narrative`` is required).

* ``GET /api/v1/firs/{fir_id}/recommend-sections/latest``
    Returns the cached last recommendation. (Cache wiring lands with the
    pgvector + DB integration; until then this endpoint returns 404.)

* ``POST /api/v1/firs/{fir_id}/recommend-sections/{addressable_id}/feedback``
    Capture an IO action on a single recommendation entry. Persisted to the
    audit chain and to the feedback ledger. Used as a re-ranking signal
    (Phase 2.4).

The retriever is constructed once at process startup and held as module
state. In production this is replaced by the pgvector retriever; the
substitution happens behind the ``Retriever`` protocol.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from .chunker import iter_chunks
from .embedder import get_embedder
from .feedback import FeedbackAction, record_feedback
from .recommender import recommend
from .retriever import InMemoryRetriever
from .schemas import RecommendationResponse, SectionRecommendation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["legal-sections"])

# ---------- Process-level retriever (built once at import time) ---------- #

_DATA = Path(__file__).resolve().parent / "data"
_retriever: InMemoryRetriever | None = None


def _get_retriever() -> InMemoryRetriever:
    """Lazy-initialise and cache the retriever for the process lifetime."""
    global _retriever
    if _retriever is None:
        chunks = list(iter_chunks([
            _DATA / "ipc_sections.jsonl",
            _DATA / "bns_sections.jsonl",
        ]))
        embedder = get_embedder()  # honours ATLAS_EMBEDDER
        r = InMemoryRetriever(embedder)
        r.index(chunks)
        _retriever = r
        logger.info(
            "legal_sections.retriever_ready",
            extra={"chunk_count": len(chunks), "embedder": embedder.name},
        )
    return _retriever


# ---------- Request / response models ---------- #


class RecommendRequest(BaseModel):
    narrative: str = Field(..., description="FIR narrative (Gujarati or English).")
    occurrence_date_iso: str | None = Field(
        None,
        description="ISO-8601 date or datetime of occurrence. Drives BNS-vs-IPC act selection (cutoff 2024-07-01).",
    )
    accused_count: int = Field(1, ge=1, description="Number of accused. Drives common-intention rules.")
    confidence_floor: float = Field(0.20, ge=0.0, le=1.0)
    top_k_retrieve: int = Field(60, ge=1, le=500)


class FeedbackRequest(BaseModel):
    action: Literal["accept", "modify", "dismiss", "request_more_info"]
    notes: str | None = None
    user_id: str | None = Field(None, description="Set by the auth layer; clients SHOULD NOT supply.")


# ---------- Endpoints ---------- #


@router.post(
    "/firs/{fir_id}/recommend-sections",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Recommend statutory sections for a FIR",
)
def recommend_sections(fir_id: str, body: RecommendRequest) -> RecommendationResponse:
    if not body.narrative.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="narrative is empty",
        )
    retriever = _get_retriever()
    raw = recommend(
        fir_id=fir_id,
        fir_narrative=body.narrative,
        retriever=retriever,
        occurrence_date_iso=body.occurrence_date_iso,
        accused_count=body.accused_count,
        confidence_floor=body.confidence_floor,
        top_k_retrieve=body.top_k_retrieve,
    )
    # Convert the recommender's dataclass-shaped response into the Pydantic
    # API contract. The dataclass is internal; the Pydantic model is the
    # external surface.
    return RecommendationResponse(
        fir_id=raw.fir_id,
        act_basis=raw.act_basis,
        occurrence_start=raw.occurrence_start,
        model_version=raw.model_version,
        generated_at=raw.generated_at,
        recommendations=[
            SectionRecommendation(
                section_id=r.section_id,
                act=r.act,
                section_number=r.section_number,
                section_title=r.section_title or "",
                sub_clause_label=r.sub_clause_label,
                canonical_citation=r.canonical_citation,
                addressable_id=r.addressable_id,
                confidence=r.confidence,
                rationale_quote=r.rationale_quote,
                matching_fir_facts=r.matching_fir_facts,
                related_sections=r.related_sections,
                borderline_with=r.borderline_with,
                operator_note=r.operator_note,
            )
            for r in raw.recommendations
        ],
    )


@router.get(
    "/firs/{fir_id}/recommend-sections/latest",
    summary="Get the latest cached recommendation for a FIR",
)
def latest_recommendation(fir_id: str):
    """Cached recommendation lookup.

    Pending DB integration (Phase 2.3). Until then this endpoint returns
    404 to signal that no cache exists yet — clients SHOULD fall back to
    invoking ``POST /firs/{fir_id}/recommend-sections``.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="no cached recommendation; invoke POST recommend-sections to compute one",
    )


@router.post(
    "/firs/{fir_id}/recommend-sections/{addressable_id}/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Capture an IO action on a single recommendation entry",
)
def submit_feedback(fir_id: str, addressable_id: str, body: FeedbackRequest):
    """Persist feedback to the audit chain and the feedback ledger.

    The feedback is later used as a re-ranking signal — accepted entries
    raise weight, dismissed entries lower it (per ADR-D16 Phase 2 plan).
    """
    record_feedback(
        fir_id=fir_id,
        addressable_id=addressable_id,
        action=FeedbackAction(body.action),
        notes=body.notes,
        user_id=body.user_id,
        timestamp=datetime.now(timezone.utc),
    )
    return {
        "fir_id": fir_id,
        "addressable_id": addressable_id,
        "action": body.action,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["router", "RecommendRequest", "FeedbackRequest"]
