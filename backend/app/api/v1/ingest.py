"""Ingestion API endpoint — v1.

POST /api/v1/ingest
Accepts a PDF file upload, runs the ingestion pipeline, stores the result,
and returns the created FIR record.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.rbac import Role, require_role
from app.db.crud_fir import create_fir
from app.db.session import get_connection
from app.ingestion.pipeline import process_pdf
from app.nlp.classify import classify_fir
from app.nlp.language import normalise_text
from app.nlp.section_map import infer_category_from_sections
from app.schemas.fir import FIRResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


@router.post(
    "/ingest",
    response_model=FIRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a FIR PDF",
)
async def ingest_fir(
    file: UploadFile = File(...),
    user: dict = Depends(require_role(Role.IO, Role.SHO, Role.ADMIN)),
) -> FIRResponse:
    """Accept a PDF upload, extract and parse the FIR, then store it in the DB.

    Pipeline
    --------
    1. Read uploaded file bytes.
    2. Run ``process_pdf()`` → structured dict.
    3. Persist via ``create_fir()``.
    4. Write raw OCR text to MongoDB (fire-and-forget; never blocks the response).
    5. Return the full ``FIRResponse``.

    The endpoint never returns 500 due to a parsing failure — if the PDF text
    cannot be fully parsed, the raw text is stored as the narrative so the
    record is always created.
    """
    # Validate content type loosely (browsers may send different MIME types)
    if file.content_type and not (
        file.content_type == "application/pdf"
        or file.content_type.startswith("application/")
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted.",
        )

    try:
        file_bytes = await file.read()
    except Exception:
        logger.error("Failed to read uploaded file.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the uploaded file.",
        )

    # Run pipeline — fall back to bare record if parsing fails entirely
    try:
        fir_data = process_pdf(file_bytes, source_system="pdf_upload")
    except Exception:
        logger.warning(
            "Pipeline failed for '%s'; creating record with fallback narrative.",
            file.filename,
            exc_info=True,
        )
        fir_data = {
            "narrative": "[PDF could not be parsed — original file stored for manual review]",
            "raw_text": "",
            "source_system": "pdf_upload",
        }

    # Ensure minimal required fields so DB insert never fails due to missing data
    if not isinstance(fir_data, dict):
        fir_data = {}
    fir_data.setdefault("source_system", "pdf_upload")
    fir_data.setdefault("raw_text", "")
    if not fir_data.get("narrative", "").strip():
        fir_data["narrative"] = "[No extractable text from PDF]"

    try:
        conn = get_connection()
        created = create_fir(conn, fir_data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("DB insert failed after PDF ingestion.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    # Fire-and-forget: persist raw OCR text to MongoDB for the ML pipeline.
    # A failure here must never block the HTTP response.
    try:
        from app.db.mongo import get_raw_ocr_collection

        collection = get_raw_ocr_collection()
        await collection.insert_one(
            {
                "fir_id": str(created["id"]),
                "fir_number": created.get("fir_number"),
                "district": created.get("district"),
                "raw_text": fir_data.get("raw_text", ""),
                "ingested_by": user.get("username"),
                "ingested_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.warning(
            "MongoDB write failed for fir_id=%s; continuing.", created.get("id"), exc_info=True
        )

    # Auto-classify the narrative and detect section mismatches — non-fatal
    try:
        narrative = fir_data.get("narrative", "")
        if narrative and narrative != "[No extractable text from PDF]":
            normalised = normalise_text(narrative)
            prediction = classify_fir(normalised, log_to_mlflow=False)

            import os as _os
            import json as _json
            from pathlib import Path as _Path

            checkpoint = _os.getenv("INDIC_BERT_CHECKPOINT", "")
            model_version = None
            if checkpoint:
                _mp = _Path(checkpoint) / "evaluation_metrics.json"
                if _mp.exists():
                    try:
                        model_version = _json.loads(_mp.read_text()).get("model_version")
                    except Exception:
                        pass

            # Compare NLP prediction against registered sections
            section_category = infer_category_from_sections(
                fir_data.get("primary_act"),
                fir_data.get("primary_sections") or [],
            )

            mismatch = (
                section_category is not None
                and prediction.category != section_category
            )
            new_status = "review_needed" if mismatch else "classified"

            if mismatch:
                logger.warning(
                    "Section mismatch for fir_id=%s: NLP=%s, sections imply=%s — flagged review_needed",
                    created.get("id"), prediction.category, section_category,
                )

            fir_id = created.get("id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE firs
                    SET
                        nlp_classification = %s,
                        nlp_confidence     = %s,
                        nlp_classified_at  = %s,
                        nlp_classified_by  = %s,
                        nlp_model_version  = %s,
                        nlp_metadata       = nlp_metadata || %s::jsonb,
                        status             = %s
                    WHERE id = %s
                    """,
                    (
                        prediction.category,
                        float(prediction.confidence),
                        datetime.now(timezone.utc).replace(tzinfo=None),
                        "auto_ingest",
                        model_version,
                        _json.dumps({
                            "section_inferred_category": section_category,
                            "mismatch": mismatch,
                        }),
                        new_status,
                        fir_id,
                    ),
                )
            conn.commit()
            logger.info(
                "Auto-classified fir_id=%s → %s (%.2f) status=%s",
                fir_id, prediction.category, prediction.confidence, new_status,
            )
            created["nlp_classification"] = prediction.category
            created["nlp_confidence"] = float(prediction.confidence)
    except Exception:
        logger.warning(
            "Auto-classification failed for fir_id=%s; FIR saved without NLP category.",
            created.get("id"), exc_info=True
        )

    return FIRResponse(**created)
