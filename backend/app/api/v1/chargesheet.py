"""Charge-sheet API endpoints -- v1.

POST   /api/v1/chargesheet/upload       Upload a charge-sheet PDF
GET    /api/v1/chargesheet/              List charge-sheets (filtered)
GET    /api/v1/chargesheet/{id}          Retrieve a single charge-sheet
PATCH  /api/v1/chargesheet/{id}/review   Accept / flag with reviewer notes
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from psycopg2.errors import UndefinedTable

from app.core.rbac import Role, get_current_user, require_role
from app.db.crud_chargesheet import (
    create_chargesheet,
    find_fir_by_number,
    get_chargesheet_by_id,
    list_chargesheets,
    update_chargesheet_review,
)
from app.db.session import get_connection
from app.ingestion.chargesheet_parser import parse_chargesheet_text
from app.ingestion.pdf_parser import extract_text_from_pdf
from app.schemas.chargesheet import (
    ChargeSheetResponse,
    ChargeSheetReviewRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chargesheet", tags=["chargesheet"])

_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


def _district_for(user: dict) -> str | None:
    return user["district"] if user["role"] in _DISTRICT_SCOPED_ROLES else None


def _schema_not_ready_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Charge-sheet schema is not initialized in the database. "
            "Run Alembic migrations (`alembic upgrade head`) or restart the backend "
            "with the migration-enabled image."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health (preserved from original stub)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/health")
def chargesheet_health():
    return {"status": "ok", "module": "chargesheet"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /upload
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/upload",
    response_model=ChargeSheetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a charge-sheet PDF for parsing",
)
async def upload_chargesheet(
    file: UploadFile = File(...),
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> ChargeSheetResponse:
    """Accept a PDF upload, extract text, parse charge-sheet fields, and store.

    Pipeline
    --------
    1. Validate PDF content type.
    2. Extract text via pdfplumber / OCR fallback.
    3. Parse structured fields via ``parse_chargesheet_text``.
    4. Auto-link to existing FIR if ``fir_reference_number`` matches.
    5. Persist to ``chargesheets`` table.
    """
    # Validate content type
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

    # Extract text
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except Exception:
        logger.error("PDF text extraction failed.", exc_info=True)
        raw_text = ""

    if not raw_text.strip():
        raw_text = "[No extractable text from PDF]"

    # Parse
    try:
        parsed = parse_chargesheet_text(raw_text)
    except Exception:
        logger.warning("Chargesheet parser failed; storing raw text.", exc_info=True)
        parsed = {"raw_text": raw_text}

    # Auto-link FIR
    fir_id = None
    fir_ref = parsed.get("fir_reference_number")
    if fir_ref:
        try:
            conn = get_connection()
            fir_id = find_fir_by_number(conn, fir_ref)
            if fir_id:
                logger.info("Auto-linked chargesheet to FIR %s (fir_number=%s)", fir_id, fir_ref)
        except Exception:
            logger.warning("FIR linkage lookup failed.", exc_info=True)

    # Build DB row
    cs_data = {
        "fir_id": fir_id,
        "filing_date": parsed.get("filing_date"),
        "court_name": parsed.get("court_name"),
        "accused_json": parsed.get("accused_list", []),
        "charges_json": parsed.get("charge_sections", []),
        "evidence_json": parsed.get("evidence_list", []),
        "witnesses_json": parsed.get("witness_schedule", []),
        "io_name": parsed.get("investigation_officer"),
        "raw_text": raw_text,
        "parsed_json": parsed,
        "status": "parsed",
        "uploaded_by": user.get("username"),
        "district": parsed.get("district") or user.get("district"),
        "police_station": parsed.get("police_station"),
    }

    try:
        conn = get_connection()
        created = create_chargesheet(conn, cs_data)
    except UndefinedTable:
        logger.error("Chargesheet schema is missing during upload.", exc_info=True)
        raise _schema_not_ready_error()
    except Exception as exc:
        logger.error("DB insert failed for chargesheet.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return ChargeSheetResponse(**created)


# ─────────────────────────────────────────────────────────────────────────────
# GET /{id}
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/{cs_id}",
    response_model=ChargeSheetResponse,
    summary="Retrieve a charge-sheet by ID",
)
def get_chargesheet_endpoint(
    cs_id: str,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> ChargeSheetResponse:
    try:
        conn = get_connection()
        cs = get_chargesheet_by_id(conn, cs_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chargesheet '{cs_id}' not found.",
            )
        return ChargeSheetResponse(**cs)
    except HTTPException:
        raise
    except UndefinedTable:
        logger.error("Chargesheet schema is missing during get by id.", exc_info=True)
        raise _schema_not_ready_error()
    except Exception as exc:
        logger.error("API error in GET /chargesheet/%s", cs_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[ChargeSheetResponse],
    summary="List charge-sheets (paginated, filtered)",
)
def list_chargesheets_endpoint(
    limit: int = 10,
    offset: int = 0,
    district: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> list[ChargeSheetResponse]:
    try:
        conn = get_connection()
        # District scoping for IO/SHO
        effective_district = _district_for(user) or district
        rows = list_chargesheets(
            conn,
            limit=limit,
            offset=offset,
            district=effective_district,
            status=status_filter,
            date_from=date_from,
            date_to=date_to,
        )
        return [ChargeSheetResponse(**r) for r in rows]
    except UndefinedTable:
        logger.error("Chargesheet schema is missing during list.", exc_info=True)
        raise _schema_not_ready_error()
    except Exception as exc:
        logger.error("API error in GET /chargesheet/", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /{id}/review
# ─────────────────────────────────────────────────────────────────────────────


@router.patch(
    "/{cs_id}/review",
    response_model=ChargeSheetResponse,
    summary="Review (accept/flag) a charge-sheet",
)
def review_chargesheet_endpoint(
    cs_id: str,
    body: ChargeSheetReviewRequest,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> ChargeSheetResponse:
    try:
        conn = get_connection()

        # Verify exists
        existing = get_chargesheet_by_id(conn, cs_id, district=_district_for(user))
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chargesheet '{cs_id}' not found.",
            )

        updated = update_chargesheet_review(
            conn,
            cs_id,
            status=body.status,
            reviewer_notes=body.reviewer_notes,
            reviewer_username=user.get("username", "unknown"),
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Update failed.",
            )
        return ChargeSheetResponse(**updated)

    except HTTPException:
        raise
    except UndefinedTable:
        logger.error("Chargesheet schema is missing during review.", exc_info=True)
        raise _schema_not_ready_error()
    except Exception as exc:
        logger.error("API error in PATCH /chargesheet/%s/review", cs_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
