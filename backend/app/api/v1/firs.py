"""FIR API endpoints — v1."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.db.crud_fir import create_fir, get_fir_by_id, list_firs
from app.db.session import get_connection
from app.schemas.fir import FIRCreate, FIRResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["firs"])


@router.post(
    "/firs",
    response_model=FIRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FIR",
)
def create_fir_endpoint(payload: FIRCreate) -> FIRResponse:
    """Accept a ``FIRCreate`` payload, persist it, and return the full record."""
    try:
        conn = get_connection()
        fir_dict = payload.model_dump()
        created = create_fir(conn, fir_dict)
        return FIRResponse(**created)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API error in POST /firs", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/firs/{fir_id}",
    response_model=FIRResponse,
    summary="Retrieve a FIR by ID",
)
def get_fir_endpoint(fir_id: str) -> FIRResponse:
    """Return a single FIR identified by its UUID."""
    try:
        conn = get_connection()
        fir = get_fir_by_id(conn, fir_id)
        if fir is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FIR '{fir_id}' not found.",
            )
        return FIRResponse(**fir)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API error in GET /firs/%s", fir_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/firs",
    response_model=list[FIRResponse],
    summary="List FIRs (paginated)",
)
def list_firs_endpoint(limit: int = 10, offset: int = 0) -> list[FIRResponse]:
    """Return a paginated list of FIRs ordered by creation date (newest first)."""
    try:
        conn = get_connection()
        rows = list_firs(conn, limit=limit, offset=offset)
        return [FIRResponse(**r) for r in rows] or []
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API error in GET /firs", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
