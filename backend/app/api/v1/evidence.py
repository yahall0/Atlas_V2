"""Evidence gap analysis API endpoints — v1.

POST  /api/v1/evidence/analyze/{chargesheet_id}  Run evidence gap detection
GET   /api/v1/evidence/report/{report_id}         Retrieve stored report
GET   /api/v1/evidence/taxonomy                   Return full taxonomy
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.rbac import Role, require_role
from app.db.crud_chargesheet import get_chargesheet_by_id
from app.db.crud_evidence import create_evidence_gap_report, get_evidence_gap_report_by_id
from app.db.crud_fir import get_fir_by_id
from app.db.session import get_connection
from app.ml.evidence_gap_model import EvidenceGapDetector
from app.ml.evidence_taxonomy import EVIDENCE_CATEGORIES
from app.ml.legal_nlp_filter import enhance_evidence_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])

_detector = EvidenceGapDetector()

_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


def _district_for(user: dict) -> str | None:
    return user["district"] if user["role"] in _DISTRICT_SCOPED_ROLES else None


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyze/{chargesheet_id}
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/analyze/{chargesheet_id}",
    status_code=status.HTTP_200_OK,
    summary="Run evidence gap analysis on a charge-sheet",
)
def analyze_evidence(
    chargesheet_id: str,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    """Detect evidence gaps using two-tier analysis (rule-based + ML).

    Loads the charge-sheet from DB, optionally loads the linked FIR,
    runs the detector, persists the report, and returns it.
    """
    try:
        conn = get_connection()

        cs = get_chargesheet_by_id(conn, chargesheet_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chargesheet '{chargesheet_id}' not found.",
            )

        # Load linked FIR
        fir_data = None
        fir_id = cs.get("fir_id")
        if fir_id:
            fir_data = get_fir_by_id(conn, str(fir_id))

        # Run gap detection
        report = _detector.detect_gaps(cs, fir_data)

        # Post-process: add narrative summary.
        enhance_evidence_report(report)

        # Persist
        db_row = create_evidence_gap_report(conn, {
            "chargesheet_id": chargesheet_id,
            "fir_id": str(fir_id) if fir_id else None,
            "crime_category": report.get("crime_category"),
            "gaps_json": report.get("evidence_gaps", []),
            "present_json": report.get("evidence_present", []),
            "coverage_pct": report.get("evidence_coverage_pct", 0.0),
            "total_gaps": report.get("total_gaps", 0),
            "analyzed_by": user.get("username"),
        })

        report["id"] = str(db_row["id"])
        return report

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Evidence analysis failed for %s", chargesheet_id, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /report/{report_id}
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/report/{report_id}",
    summary="Retrieve a stored evidence gap report",
)
def get_report(
    report_id: str,
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> Dict[str, Any]:
    try:
        conn = get_connection()
        row = get_evidence_gap_report_by_id(conn, report_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence gap report '{report_id}' not found.",
            )
        return {
            "id": str(row["id"]),
            "chargesheet_id": str(row["chargesheet_id"]),
            "fir_id": str(row["fir_id"]) if row.get("fir_id") else None,
            "crime_category": row.get("crime_category"),
            "evidence_gaps": row.get("gaps_json", []),
            "evidence_present": row.get("present_json", []),
            "evidence_coverage_pct": float(row.get("coverage_pct", 0)),
            "total_gaps": row.get("total_gaps", 0),
            "analyzed_by": row.get("analyzed_by"),
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
# GET /taxonomy
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/taxonomy",
    summary="Return the full evidence taxonomy",
)
def get_taxonomy(
    user: dict = Depends(
        require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
    ),
) -> Dict[str, Any]:
    return {"categories": EVIDENCE_CATEGORIES}
