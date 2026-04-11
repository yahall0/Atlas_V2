"""Dashboard statistics endpoint — live DB queries (Sprint 2).

Returns per-role aggregated KPIs for the ATLAS dashboard.  All queries
are district-scoped for IO/SHO roles.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from psycopg2.errors import UndefinedTable

from app.core.rbac import Role, get_current_user
from app.db.session import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DISTRICT_SCOPED_ROLES = {Role.IO.value, Role.SHO.value}


class DashboardStats(BaseModel):
    total_firs: int
    pending_review: int
    districts: int
    completeness_avg: float
    ingested_today: int
    total_chargesheets: int


def _get_stats(conn, district: str | None) -> DashboardStats:
    """Run 5 live SQL queries and return aggregated stats."""
    where = "WHERE district = %(d)s" if district else ""
    params = {"d": district} if district else {}

    with conn.cursor() as cur:
        # 1 — total FIRs
        cur.execute(f"SELECT COUNT(*) FROM firs {where};", params)
        total_firs: int = cur.fetchone()[0]

        # 2 — pending review (status = 'pending' OR status IS NULL)
        pending_where = (
            "WHERE (status = 'pending' OR status IS NULL) AND district = %(d)s"
            if district
            else "WHERE status = 'pending' OR status IS NULL"
        )
        cur.execute(f"SELECT COUNT(*) FROM firs {pending_where};", params)
        pending_review: int = cur.fetchone()[0]

        # 3 — distinct districts (global — not scoped)
        cur.execute("SELECT COUNT(DISTINCT district) FROM firs;")
        distinct_districts: int = cur.fetchone()[0]

        # 4 — average completeness_pct
        cur.execute(
            f"SELECT COALESCE(AVG(completeness_pct), 0) FROM firs {where};", params
        )
        completeness_avg: float = float(cur.fetchone()[0])

        # 5 — FIRs ingested today (UTC date)
        today_where = (
            "WHERE DATE(created_at) = CURRENT_DATE AND district = %(d)s"
            if district
            else "WHERE DATE(created_at) = CURRENT_DATE"
        )
        cur.execute(f"SELECT COUNT(*) FROM firs {today_where};", params)
        ingested_today: int = cur.fetchone()[0]

        # 6 — total chargesheets
        # Chargesheet tables are introduced in later migrations. If the running
        # database is older, we keep the dashboard functional and report 0
        # instead of failing the whole page.
        cs_where = "WHERE district = %(d)s" if district else ""
        try:
            cur.execute(f"SELECT COUNT(*) FROM chargesheets {cs_where};", params)
            total_chargesheets: int = cur.fetchone()[0]
        except UndefinedTable:
            conn.rollback()
            logger.warning("Chargesheet table missing; returning total_chargesheets=0 in dashboard stats.")
            total_chargesheets = 0

    return DashboardStats(
        total_firs=total_firs,
        pending_review=pending_review,
        districts=distinct_districts,
        completeness_avg=round(completeness_avg, 1),
        ingested_today=ingested_today,
        total_chargesheets=total_chargesheets,
    )


@router.get("/health")
def dashboard_health():
    return {"status": "ok", "module": "dashboard"}


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Aggregated KPIs for the ATLAS dashboard",
)
def dashboard_stats(
    user: dict = Depends(get_current_user),
) -> DashboardStats:
    """Return live dashboard statistics, district-scoped for IO/SHO."""
    try:
        conn = get_connection()
        district = (
            user.get("district")
            if user["role"] in _DISTRICT_SCOPED_ROLES
            else None
        )
        return _get_stats(conn, district)
    except Exception as exc:
        logger.error("Dashboard stats query failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
