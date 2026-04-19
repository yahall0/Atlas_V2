"""FIR API endpoints — v1."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.pii import mask_pii_for_role
from app.core.rbac import Role, get_current_user, require_role
from app.db.crud_fir import create_fir, get_fir_by_id, list_firs
from app.db.session import get_connection
from app.schemas.fir import FIRCreate, FIRResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["firs"])

# Roles that only see their own district's FIRs
_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


def _district_for(user: dict) -> str | None:
    """Return district filter value based on the caller's role."""
    return user["district"] if user["role"] in _DISTRICT_SCOPED_ROLES else None


def _trigger_recommender_in_background(fir_record: dict) -> None:
    """Run the section recommender + Compendium-scenario lookup for a new FIR.

    Persists results to ``firs.nlp_metadata['recommended_sections']`` and
    ``firs.nlp_metadata['compendium_scenarios']``. Best-effort: failures are
    logged and never block the FIR-creation response.
    """
    try:
        from app.legal_sections.auto_trigger import (  # noqa: PLC0415
            run_recommender_for_fir,
        )
    except Exception:
        logger.warning("auto_trigger import failed; skipping for fir=%s",
                       fir_record.get("id"))
        return

    try:
        occurrence_iso = None
        occ = fir_record.get("occurrence_start")
        if occ:
            occurrence_iso = occ.isoformat() if hasattr(occ, "isoformat") else str(occ)

        accused = fir_record.get("accused") or []
        accused_count = max(len(accused) if isinstance(accused, list) else 0, 1)

        narrative = fir_record.get("narrative") or fir_record.get("raw_text") or ""
        if not narrative.strip():
            logger.info("auto_trigger.skip empty_narrative fir=%s", fir_record.get("id"))
            return

        conn = get_connection()
        run_recommender_for_fir(
            fir_id=str(fir_record["id"]),
            narrative=narrative,
            occurrence_date_iso=occurrence_iso,
            accused_count=accused_count,
            conn=conn,
        )
    except Exception:
        logger.exception("auto_trigger background task failed for fir=%s",
                         fir_record.get("id"))


@router.post(
    "/firs",
    response_model=FIRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FIR",
)
def create_fir_endpoint(
    payload: FIRCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role(Role.IO, Role.SHO, Role.ADMIN)),
) -> FIRResponse:
    """Accept a ``FIRCreate`` payload, persist it, and return the full record.

    On successful creation, schedule the section recommender + Compendium
    scenario lookup as a background task (per ADR-D17 + ADR-D19). The
    recommendation results land in ``firs.nlp_metadata`` and become available
    to the mindmap engine and chargesheet gap analyser on their next call.
    """
    try:
        conn = get_connection()
        fir_dict = payload.model_dump()
        created = create_fir(conn, fir_dict)
        # Schedule auto-trigger AFTER the response goes out
        background_tasks.add_task(_trigger_recommender_in_background, dict(created))
        return FIRResponse(**mask_pii_for_role(created, user["role"]))
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
def get_fir_endpoint(
    fir_id: str,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> FIRResponse:
    """Return a single FIR identified by its UUID."""
    try:
        conn = get_connection()
        fir = get_fir_by_id(conn, fir_id, district=_district_for(user))
        if fir is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FIR '{fir_id}' not found.",
            )
        return FIRResponse(**mask_pii_for_role(fir, user["role"]))
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
def list_firs_endpoint(
    limit: int = 10,
    offset: int = 0,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> list[FIRResponse]:
    """Return a paginated list of FIRs ordered by creation date (newest first)."""
    try:
        conn = get_connection()
        rows = list_firs(conn, limit=limit, offset=offset, district=_district_for(user))
        return [FIRResponse(**mask_pii_for_role(r, user["role"])) for r in rows] or []
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API error in GET /firs", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.patch(
    "/firs/{fir_id}/classification",
    response_model=FIRResponse,
    summary="Manually set NLP classification on a FIR",
)
def patch_fir_classification(
    fir_id: str,
    classification: str,
    user: dict = Depends(
        require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)
    ),
) -> FIRResponse:
    """Override or set the ``nlp_classification`` for a FIR.

    Only SHO / DYSP / SP / ADMIN may call this endpoint.  The action is
    recorded in ``audit_log``.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Ensure FIR exists and is district-accessible
            cur.execute(
                "SELECT id FROM firs WHERE id = %s" + (
                    " AND district = %s" if _district_for(user) else ""
                ),
                (fir_id, user["district"]) if _district_for(user) else (fir_id,),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"FIR '{fir_id}' not found.",
                )

            from datetime import datetime, timezone  # noqa: PLC0415

            cur.execute(
                """
                UPDATE firs
                SET
                    nlp_classification  = %s,
                    nlp_classified_at   = %s,
                    nlp_classified_by   = %s,
                    status              = 'reviewed'
                WHERE id = %s
                """,
                (
                    classification,
                    datetime.now(timezone.utc).replace(tzinfo=None),
                    user.get("username", user.get("sub", "unknown")),
                    fir_id,
                ),
            )

            # Audit log
            cur.execute(
                """
                INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
                VALUES (%s, 'patch_classification', 'fir', %s, %s::jsonb)
                """,
                (
                    user.get("sub"),
                    fir_id,
                    '{"classification": "' + classification + '"}',
                ),
            )
            conn.commit()

        fir = get_fir_by_id(conn, fir_id, district=None)
        return FIRResponse(**mask_pii_for_role(fir, user["role"]))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("API error in PATCH /firs/%s/classification", fir_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
