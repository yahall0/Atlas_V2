"""CRUD operations for the chargesheets table.

All queries use parameterised SQL to prevent injection.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json as PgJson

psycopg2.extras.register_uuid()

logger = logging.getLogger(__name__)


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _sanitize(value: Any) -> Any:
    """Strip NUL bytes from strings so PostgreSQL does not reject them."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def create_chargesheet(
    conn: PgConnection,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a charge-sheet record and return it."""
    cs_id = uuid.uuid4()
    data = {k: _sanitize(v) for k, v in data.items()}

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with conn:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO chargesheets (
                    id, fir_id, filing_date, court_name,
                    accused_json, charges_json, evidence_json, witnesses_json,
                    io_name, raw_text, parsed_json,
                    status, uploaded_by, district, police_station,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                RETURNING *
                """,
                (
                    cs_id,
                    data.get("fir_id"),
                    data.get("filing_date"),
                    data.get("court_name"),
                    PgJson(data.get("accused_json") or []),
                    PgJson(data.get("charges_json") or []),
                    PgJson(data.get("evidence_json") or []),
                    PgJson(data.get("witnesses_json") or []),
                    data.get("io_name"),
                    data.get("raw_text", ""),
                    PgJson(data.get("parsed_json") or {}),
                    data.get("status", "parsed"),
                    data.get("uploaded_by"),
                    data.get("district"),
                    data.get("police_station"),
                    now,
                    now,
                ),
            )
            return dict(cur.fetchone())


def get_chargesheet_by_id(
    conn: PgConnection,
    cs_id: str,
    district: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single charge-sheet by UUID."""
    with _dict_cursor(conn) as cur:
        if district is not None:
            cur.execute(
                "SELECT * FROM chargesheets WHERE id = %s AND district = %s",
                (cs_id, district),
            )
        else:
            cur.execute("SELECT * FROM chargesheets WHERE id = %s", (cs_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_chargesheets(
    conn: PgConnection,
    limit: int = 10,
    offset: int = 0,
    district: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return a paginated, filtered list of charge-sheets."""
    limit = min(limit, 100)

    clauses: List[str] = []
    params: Dict[str, Any] = {}

    if district:
        clauses.append("district = %(district)s")
        params["district"] = district
    if status:
        clauses.append("status = %(status)s")
        params["status"] = status
    if date_from:
        clauses.append("created_at >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        clauses.append("created_at <= %(date_to)s::date + INTERVAL '1 day'")
        params["date_to"] = date_to

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params["limit"] = limit
    params["offset"] = offset

    with _dict_cursor(conn) as cur:
        cur.execute(
            f"SELECT * FROM chargesheets {where} "
            f"ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def update_chargesheet_review(
    conn: PgConnection,
    cs_id: str,
    status: str,
    reviewer_notes: Optional[str],
    reviewer_username: str,
) -> Optional[Dict[str, Any]]:
    """Update the review status of a charge-sheet."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with conn:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                UPDATE chargesheets
                SET status = %s,
                    reviewer_notes = %s,
                    updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                (status, reviewer_notes, now, cs_id),
            )
            row = cur.fetchone()

            # Audit log
            if row:
                cur.execute(
                    """
                    INSERT INTO audit_log
                        (user_id, action, resource_type, resource_id, details)
                    VALUES (%s, 'review_chargesheet', 'chargesheet', %s, %s::jsonb)
                    """,
                    (
                        None,
                        cs_id,
                        json.dumps({
                            "reviewer": reviewer_username,
                            "status": status,
                            "notes": reviewer_notes,
                        }),
                    ),
                )

    return dict(row) if row else None


def find_fir_by_number(
    conn: PgConnection,
    fir_number: str,
) -> Optional[str]:
    """Look up a FIR ID by its fir_number. Returns UUID string or None."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT id FROM firs WHERE fir_number = %s LIMIT 1",
            (fir_number,),
        )
        row = cur.fetchone()
    return str(row["id"]) if row else None
