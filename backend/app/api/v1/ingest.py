"""Ingestion API endpoint — v1.

POST /api/v1/ingest
Accepts a PDF file upload, runs the ingestion pipeline, stores the result,
and returns the created FIR record.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from app.core.rbac import Role, require_role
from app.db.crud_fir import create_fir
from app.db.session import get_connection
from app.ingestion.pipeline import process_pdf
from app.schemas.fir import FIRResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


def _background_classify(fir_id: str, fir_data: dict, username: str) -> None:
    """Run NLP classification and MongoDB write in the background.

    This is intentionally fire-and-forget so the upload response returns
    immediately instead of blocking for 30+ seconds of model inference.
    """
    # MongoDB write
    try:
        from app.db.mongo import get_raw_ocr_collection
        import asyncio as _aio

        async def _write_mongo():
            collection = get_raw_ocr_collection()
            await collection.insert_one(
                {
                    "fir_id": fir_id,
                    "fir_number": fir_data.get("fir_number"),
                    "district": fir_data.get("district"),
                    "raw_text": fir_data.get("raw_text", ""),
                    "ingested_by": username,
                    "ingested_at": datetime.now(timezone.utc),
                }
            )

        try:
            loop = _aio.get_event_loop()
            if loop.is_running():
                _aio.ensure_future(_write_mongo())
            else:
                loop.run_until_complete(_write_mongo())
        except RuntimeError:
            _aio.run(_write_mongo())
    except Exception:
        logger.warning("MongoDB write failed for fir_id=%s; continuing.", fir_id, exc_info=True)

    # NLP auto-classification
    try:
        from app.nlp.classify import classify_fir
        from app.nlp.language import normalise_text
        from app.nlp.section_map import infer_category_from_sections

        narrative = fir_data.get("narrative", "")
        if not narrative or narrative == "[No extractable text from PDF]":
            return

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

        section_category = infer_category_from_sections(
            fir_data.get("primary_act"),
            fir_data.get("primary_sections") or [],
        )

        mismatch = (
            section_category is not None
            and prediction.category != section_category
        )

        final_category = section_category if section_category is not None else prediction.category
        final_confidence = 1.0 if section_category is not None else float(prediction.confidence)
        final_classified_by = "section_map" if section_category is not None else "auto_ingest"
        new_status = "review_needed" if mismatch else "classified"

        if mismatch:
            logger.warning(
                "Section mismatch for fir_id=%s: NLP=%s, sections imply=%s — flagged review_needed",
                fir_id, prediction.category, section_category,
            )

        conn = get_connection()
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
                    nlp_metadata       = COALESCE(nlp_metadata, '{}'::jsonb) || %s::jsonb,
                    status             = %s
                WHERE id = %s
                """,
                (
                    final_category,
                    final_confidence,
                    datetime.now(timezone.utc).replace(tzinfo=None),
                    final_classified_by,
                    model_version,
                    _json.dumps({
                        "section_inferred_category": section_category,
                        "nlp_category": prediction.category,
                        "nlp_confidence": float(prediction.confidence),
                        "mismatch": mismatch,
                    }),
                    new_status,
                    fir_id,
                ),
            )
        conn.commit()
        logger.info(
            "Auto-classified fir_id=%s → %s (method=%s) status=%s",
            fir_id, final_category, final_classified_by, new_status,
        )
    except Exception:
        logger.warning(
            "Auto-classification failed for fir_id=%s; FIR saved without NLP category.",
            fir_id, exc_info=True,
        )


@router.post(
    "/ingest",
    response_model=FIRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a FIR PDF",
)
async def ingest_fir(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
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

    # Schedule MongoDB write and NLP classification as a background task so the
    # response returns immediately.  The NLP step can take 30+ seconds on CPU
    # (zero-shot model download + inference) which causes the Next.js proxy to
    # timeout — the frontend sees "upload failed" even though the FIR was saved.
    background_tasks.add_task(
        _background_classify,
        str(created["id"]),
        fir_data,
        user.get("username", ""),
    )

    return FIRResponse(**created)
