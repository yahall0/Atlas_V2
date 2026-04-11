"""Legal validation API endpoints — v1.

POST  /api/v1/validate/chargesheet/{chargesheet_id}  Run full validation
GET   /api/v1/validate/report/{report_id}             Retrieve stored report
GET   /api/v1/validate/sections/lookup                Section details lookup
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rbac import Role, require_role
from app.db.crud_chargesheet import get_chargesheet_by_id
from app.db.crud_fir import get_fir_by_id
from app.db.crud_validation import create_validation_report, get_validation_report_by_id
from app.db.session import get_connection
from app.legal_db import get_section, get_bns_equivalent, get_ipc_equivalent
from app.legal_validator import LegalCrossReferenceValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validate", tags=["validation"])

_validator = LegalCrossReferenceValidator()

_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


def _district_for(user: dict) -> str | None:
    return user["district"] if user["role"] in _DISTRICT_SCOPED_ROLES else None


# ─────────────────────────────────────────────────────────────────────────────
# POST /chargesheet/{chargesheet_id}
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/chargesheet/{chargesheet_id}",
    status_code=status.HTTP_200_OK,
    summary="Run legal validation on a charge-sheet",
)
def validate_chargesheet(
    chargesheet_id: str,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    """Run full cross-reference validation against the linked FIR.

    If no FIR is linked, only internal-consistency rules (3–7) are run.
    The report is persisted to ``validation_reports`` and returned.
    """
    try:
        conn = get_connection()

        cs = get_chargesheet_by_id(conn, chargesheet_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chargesheet '{chargesheet_id}' not found.",
            )

        # Load linked FIR if present
        fir_data = None
        fir_id = cs.get("fir_id")
        if fir_id:
            fir_data = get_fir_by_id(conn, str(fir_id))

        # Run validation
        report = _validator.validate(cs, fir_data)
        report_dict = report.to_dict()

        # Persist
        db_row = create_validation_report(conn, {
            "chargesheet_id": chargesheet_id,
            "fir_id": str(fir_id) if fir_id else None,
            "findings_json": report_dict["findings"],
            "summary_json": report_dict["summary"],
            "overall_status": report_dict["overall_status"],
            "validated_by": user.get("username"),
        })

        # Merge persisted ID into response
        report_dict["id"] = str(db_row["id"])
        return report_dict

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Validation failed for chargesheet %s", chargesheet_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /report/{report_id}
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/report/{report_id}",
    summary="Retrieve a stored validation report",
)
def get_report(
    report_id: str,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> Dict[str, Any]:
    try:
        conn = get_connection()
        row = get_validation_report_by_id(conn, report_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation report '{report_id}' not found.",
            )
        return {
            "id": str(row["id"]),
            "chargesheet_id": str(row["chargesheet_id"]),
            "fir_id": str(row["fir_id"]) if row.get("fir_id") else None,
            "overall_status": row["overall_status"],
            "findings": row.get("findings_json", []),
            "summary": row.get("summary_json", {}),
            "validated_by": row.get("validated_by"),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving report %s", report_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /sections/lookup
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/sections/lookup",
    summary="Look up a legal section with BNS/IPC equivalent and evidence requirements",
)
def section_lookup(
    section: str = Query(..., description="Section number (e.g. 302, 376A)"),
    act: str = Query(default="ipc", description="Act: ipc or bns"),
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> Dict[str, Any]:
    """Return section details, BNS/IPC equivalent, and mandatory evidence.

    Useful for frontend tooltips and manual cross-referencing.
    """
    entry = get_section(section, act)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section '{section}' not found in {act.upper()} database.",
        )

    # Build equivalent info
    if act.lower() == "ipc":
        equivalent = {"bns_section": entry.get("bns_section")}
    else:
        equivalent = {"ipc_section": entry.get("ipc_section")}

    return {
        "section": section,
        "act": act.upper(),
        "title": entry.get("title"),
        "category": entry.get("category"),
        "cognizable": entry.get("cognizable"),
        "bailable": entry.get("bailable"),
        "min_sentence_years": entry.get("min_sentence_years"),
        "max_sentence": entry.get("max_sentence"),
        "mandatory_evidence": entry.get("mandatory_evidence", []),
        "companion_sections": entry.get("companion_sections", []),
        "procedural_requirements": entry.get("procedural_requirements", []),
        "mutually_exclusive_with": entry.get("mutually_exclusive_with", []),
        "equivalent": equivalent,
        "special_act": entry.get("special_act"),
    }
