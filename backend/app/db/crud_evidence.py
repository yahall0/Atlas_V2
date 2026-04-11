"""CRUD operations for the evidence_gap_reports table."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json as PgJson

psycopg2.extras.register_uuid()

logger = logging.getLogger(__name__)


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def create_evidence_gap_report(
    conn: PgConnection,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert an evidence gap report and return it."""
    report_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with conn:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO evidence_gap_reports (
                    id, chargesheet_id, fir_id, crime_category,
                    gaps_json, present_json, coverage_pct, total_gaps,
                    analyzed_by, created_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                RETURNING *
                """,
                (
                    report_id,
                    data.get("chargesheet_id"),
                    data.get("fir_id"),
                    data.get("crime_category"),
                    PgJson(data.get("gaps_json", [])),
                    PgJson(data.get("present_json", [])),
                    data.get("coverage_pct", 0.0),
                    data.get("total_gaps", 0),
                    data.get("analyzed_by"),
                    now,
                ),
            )
            return dict(cur.fetchone())


def get_evidence_gap_report_by_id(
    conn: PgConnection,
    report_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve an evidence gap report by UUID."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM evidence_gap_reports WHERE id = %s",
            (report_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
