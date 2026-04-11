"""CRUD operations for the validation_reports table."""

from __future__ import annotations

import json
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


def create_validation_report(
    conn: PgConnection,
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a validation report and return it."""
    report_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with conn:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO validation_reports (
                    id, chargesheet_id, fir_id,
                    findings_json, summary_json, overall_status,
                    validated_by, created_at, updated_at
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING *
                """,
                (
                    report_id,
                    report_data.get("chargesheet_id"),
                    report_data.get("fir_id"),
                    PgJson(report_data.get("findings_json", [])),
                    PgJson(report_data.get("summary_json", {})),
                    report_data.get("overall_status", "pass"),
                    report_data.get("validated_by"),
                    now,
                    now,
                ),
            )
            return dict(cur.fetchone())


def get_validation_report_by_id(
    conn: PgConnection,
    report_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve a validation report by its UUID."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM validation_reports WHERE id = %s",
            (report_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
