"""Predict API — FIR classification endpoints (Sprint 2).

Endpoints
---------
POST /predict/classify
    Classify a text snippet and optionally persist the result to a FIR record.

GET /predict/model-info
    Return the currently loaded model variant and ATLAS category list.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.rbac import Role, get_current_user, require_role
from app.db.session import get_connection
from app.nlp.classify import ATLAS_CATEGORIES, ATLASPrediction, classify_fir
from app.nlp.language import detect_language, normalise_text, preprocess_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predict"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ClassifyRequest(BaseModel):
    """Request body for ``POST /predict/classify``."""

    text: str = Field(..., min_length=1, description="FIR narrative or excerpt to classify.")
    fir_id: Optional[str] = Field(
        None,
        description=(
            "If supplied the classification result is persisted to the "
            "``firs`` table row with this UUID."
        ),
    )
    transliterate: bool = Field(
        False,
        description="Run IndicXlit transliteration before classification.",
    )


class ClassifyResponse(BaseModel):
    """Response payload for ``POST /predict/classify``."""

    category: str
    confidence: float
    method: str
    detected_lang: str
    persisted: bool = False
    raw_scores: Optional[dict] = None


class ModelInfoResponse(BaseModel):
    """Response payload for ``GET /predict/model-info``."""

    model_variant: str
    categories: list[str]
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _persist_classification(
    conn,
    fir_id: str,
    prediction: ATLASPrediction,
    classified_by: str,
) -> bool:
    """Write NLP classification columns back to the ``firs`` table.

    Returns ``True`` on success, ``False`` if the FIR was not found.
    """
    sql = """
        UPDATE firs
        SET
            nlp_classification  = %(category)s,
            nlp_confidence      = %(confidence)s,
            nlp_classified_at   = %(classified_at)s,
            nlp_classified_by   = %(classified_by)s,
            status              = 'classified',
            nlp_metadata        = nlp_metadata || %(meta)s::jsonb
        WHERE id = %(fir_id)s
        RETURNING id
    """
    params = {
        "fir_id": fir_id,
        "category": prediction.category,
        "confidence": float(prediction.confidence),
        "classified_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "classified_by": classified_by,
        "meta": '{"method": "' + prediction.method + '"}',
    }
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            conn.commit()
            return row is not None
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to persist classification for FIR %s: %s", fir_id, exc)
        raise


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/predict/classify",
    response_model=ClassifyResponse,
    summary="Classify a FIR narrative",
    status_code=status.HTTP_200_OK,
)
def classify_endpoint(
    payload: ClassifyRequest,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)
    ),
) -> ClassifyResponse:
    """Classify *text* into one of the ATLAS crime categories.

    If ``fir_id`` is provided the result is written to the corresponding
    ``firs`` row (requires SHO / DYSP / SP / ADMIN role to persist).
    """
    try:
        pre = preprocess_text(
            payload.text,
            transliterate=payload.transliterate,
        )
        normalised = pre["normalised"]
        lang = pre["detected_lang"]

        prediction = classify_fir(normalised, log_to_mlflow=False)

        persisted = False
        if payload.fir_id:
            _can_persist = user["role"] in {
                Role.SHO.value, Role.DYSP.value, Role.SP.value, Role.ADMIN.value
            }
            if not _can_persist:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only SHO/DYSP/SP/ADMIN may persist classifications.",
                )
            conn = get_connection()
            found = _persist_classification(
                conn,
                payload.fir_id,
                prediction,
                classified_by=user.get("username", user.get("sub", "unknown")),
            )
            if not found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FIR '{payload.fir_id}' not found.",
                )
            persisted = True

        return ClassifyResponse(
            category=prediction.category,
            confidence=round(prediction.confidence, 4),
            method=prediction.method,
            detected_lang=lang,
            persisted=persisted,
            raw_scores=prediction.raw_scores,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in POST /predict/classify", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/predict/model-info",
    response_model=ModelInfoResponse,
    summary="Current model variant and category list",
)
def model_info_endpoint(
    _user: dict = Depends(get_current_user),
) -> ModelInfoResponse:
    """Return metadata about the currently active classification model."""
    import os

    checkpoint = os.getenv("INDIC_BERT_CHECKPOINT", "")
    variant = checkpoint if checkpoint else "ai4bharat/indic-bert (heuristic fallback)"
    return ModelInfoResponse(
        model_variant=variant,
        categories=ATLAS_CATEGORIES,
        status="heuristic" if not checkpoint else "fine-tuned",
    )
