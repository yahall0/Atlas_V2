"""Chargesheet review API endpoints — v1.

POST  /review/chargesheet/{id}/start            Start review
POST  /review/chargesheet/{id}/recommendation   Act on recommendation
POST  /review/chargesheet/{id}/complete          Complete review
GET   /review/chargesheet/{id}/audit             View audit history
GET   /review/chargesheet/{id}/audit/verify      Verify hash chain
GET   /review/chargesheet/{id}/audit/export      Export audit CSV
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.core.rbac import Role, require_role
from app.db.crud_chargesheet import get_chargesheet_by_id
from app.db.session import get_connection
from app.audit_chain import (
    AuditChain,
    create_recommendation_action,
    get_recommendation_actions,
    has_recommendation_action,
)
from app.models.audit import (
    AuditAction,
    RecommendationActionRequest,
    ReviewCompleteRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review", tags=["review"])

_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


def _district_for(user: dict) -> str | None:
    return user["district"] if user["role"] in _DISTRICT_SCOPED_ROLES else None


def _client_info(request: Request) -> tuple[str, str]:
    """Extract IP and user-agent from request."""
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    return ip, ua


# ─────────────────────────────────────────────────────────────────────────────
# POST /chargesheet/{id}/start
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/chargesheet/{cs_id}/start",
    summary="Start a chargesheet review",
)
def start_review(
    cs_id: str,
    request: Request,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    """Mark chargesheet as under review and log audit entry."""
    try:
        conn = get_connection()
        cs = get_chargesheet_by_id(conn, cs_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(status_code=404, detail=f"Chargesheet '{cs_id}' not found.")

        # Update status
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chargesheets SET status = 'under_review', updated_at = %s WHERE id = %s",
                (now, cs_id),
            )
        conn.commit()

        # Audit
        ip, ua = _client_info(request)
        chain = AuditChain(conn)
        chain.log(cs_id, user["username"], AuditAction.REVIEW_STARTED.value,
                  {"reviewer": user["username"]}, ip, ua)

        # Get existing actions
        actions = get_recommendation_actions(conn, cs_id)

        return {
            "chargesheet_id": cs_id,
            "status": "under_review",
            "reviewer": user["username"],
            "existing_actions": [_serialize_row(a) for a in actions],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("start_review failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# POST /chargesheet/{id}/recommendation
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/chargesheet/{cs_id}/recommendation",
    summary="Act on a recommendation (accept/modify/dismiss)",
)
def act_on_recommendation(
    cs_id: str,
    body: RecommendationActionRequest,
    request: Request,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    """Record an action on an AI recommendation."""
    # Validate action-specific requirements
    if body.action == "dismissed" and not body.reason:
        raise HTTPException(status_code=400, detail="Reason is required when dismissing a recommendation.")
    if body.action == "modified" and not body.modified_text:
        raise HTTPException(status_code=400, detail="Modified text is required when modifying a recommendation.")

    try:
        conn = get_connection()
        cs = get_chargesheet_by_id(conn, cs_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(status_code=404, detail=f"Chargesheet '{cs_id}' not found.")

        # Check for duplicate
        if has_recommendation_action(conn, cs_id, body.recommendation_id):
            raise HTTPException(status_code=409, detail="Action already taken on this recommendation.")

        # Determine audit action
        action_map = {
            "accepted": AuditAction.RECOMMENDATION_ACCEPTED.value,
            "modified": AuditAction.RECOMMENDATION_MODIFIED.value,
            "dismissed": AuditAction.RECOMMENDATION_DISMISSED.value,
        }
        audit_action = action_map[body.action]

        # Log audit entry first to get its ID
        ip, ua = _client_info(request)
        chain = AuditChain(conn)
        audit_entry = chain.log(
            cs_id, user["username"], audit_action,
            {
                "recommendation_id": body.recommendation_id,
                "recommendation_type": body.recommendation_type,
                "action": body.action,
                "source_rule": body.source_rule,
                "modified_text": body.modified_text,
                "reason": body.reason,
            },
            ip, ua,
        )

        # Store recommendation action
        rec_action = create_recommendation_action(conn, {
            "chargesheet_id": cs_id,
            "recommendation_id": body.recommendation_id,
            "recommendation_type": body.recommendation_type,
            "source_rule": body.source_rule,
            "action_taken": body.action,
            "original_text": body.original_text,
            "modified_text": body.modified_text,
            "reason": body.reason,
            "reviewer_id": user["username"],
            "audit_entry_id": str(audit_entry["id"]),
        })

        return _serialize_row(rec_action)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("act_on_recommendation failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# POST /chargesheet/{id}/complete
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/chargesheet/{cs_id}/complete",
    summary="Complete a chargesheet review",
)
def complete_review(
    cs_id: str,
    body: ReviewCompleteRequest,
    request: Request,
    user: dict = Depends(require_role(Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    """Complete review: validates all recommendations actioned."""
    try:
        conn = get_connection()
        cs = get_chargesheet_by_id(conn, cs_id, district=_district_for(user))
        if cs is None:
            raise HTTPException(status_code=404, detail=f"Chargesheet '{cs_id}' not found.")

        # Get actions taken
        actions = get_recommendation_actions(conn, cs_id)
        action_count = len(actions)
        accepted = sum(1 for a in actions if a.get("action_taken") == "accepted")
        modified = sum(1 for a in actions if a.get("action_taken") == "modified")
        dismissed = sum(1 for a in actions if a.get("action_taken") == "dismissed")

        # Determine status
        new_status = "flagged" if body.flag_for_senior else "reviewed"
        audit_action = AuditAction.REVIEW_FLAGGED.value if body.flag_for_senior else AuditAction.REVIEW_COMPLETED.value

        # Update chargesheet
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chargesheets SET status = %s, reviewer_notes = %s, updated_at = %s WHERE id = %s",
                (new_status, body.overall_assessment, now, cs_id),
            )
        conn.commit()

        # Audit
        ip, ua = _client_info(request)
        chain = AuditChain(conn)
        chain.log(
            cs_id, user["username"], audit_action,
            {
                "overall_assessment": body.overall_assessment,
                "flag_for_senior": body.flag_for_senior,
                "action_summary": {
                    "total": action_count,
                    "accepted": accepted,
                    "modified": modified,
                    "dismissed": dismissed,
                },
            },
            ip, ua,
        )

        return {
            "chargesheet_id": cs_id,
            "status": new_status,
            "summary": {
                "total_actions": action_count,
                "accepted": accepted,
                "modified": modified,
                "dismissed": dismissed,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("complete_review failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# GET /chargesheet/{id}/audit
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/chargesheet/{cs_id}/audit",
    summary="View paginated audit history",
)
def get_audit_history(
    cs_id: str,
    action_filter: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    user: dict = Depends(require_role(Role.DYSP, Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    try:
        conn = get_connection()
        chain = AuditChain(conn)
        entries = chain.get_history(cs_id, action_filter, page, per_page)
        return {
            "chargesheet_id": cs_id,
            "page": page,
            "per_page": per_page,
            "entries": [_serialize_row(e) for e in entries],
        }
    except Exception as exc:
        logger.error("get_audit_history failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# GET /chargesheet/{id}/audit/verify
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/chargesheet/{cs_id}/audit/verify",
    summary="Verify hash chain integrity",
)
def verify_chain(
    cs_id: str,
    user: dict = Depends(require_role(Role.SP, Role.ADMIN)),
) -> Dict[str, Any]:
    try:
        conn = get_connection()
        chain = AuditChain(conn)
        return chain.verify_chain(cs_id)
    except Exception as exc:
        logger.error("verify_chain failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# GET /chargesheet/{id}/audit/export
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/chargesheet/{cs_id}/audit/export",
    summary="Export audit chain as CSV",
)
def export_chain(
    cs_id: str,
    request: Request,
    user: dict = Depends(require_role(Role.DYSP, Role.SP, Role.ADMIN)),
) -> Response:
    try:
        conn = get_connection()

        # Log the export
        ip, ua = _client_info(request)
        chain = AuditChain(conn)
        chain.log(cs_id, user["username"], AuditAction.EXPORT_GENERATED.value,
                  {"format": "csv"}, ip, ua)

        csv_bytes = chain.export_chain(cs_id)
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_{cs_id}.csv",
            },
        )
    except Exception as exc:
        logger.error("export_chain failed for %s", cs_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert UUID and datetime fields to strings for JSON serialization."""
    out = {}
    for k, v in row.items():
        if hasattr(v, "hex"):  # UUID
            out[k] = str(v)
        elif hasattr(v, "isoformat"):  # datetime
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
