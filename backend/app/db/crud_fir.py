"""CRUD operations for the FIR table and its related entities.

All queries use parameterised SQL to prevent injection.  No string
concatenation is used for user-supplied values.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json as PgJson

# Make psycopg2 return rows as dicts automatically
psycopg2.extras.register_uuid()

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────


def _dict_cursor(conn: PgConnection):
    """Return a ``RealDictCursor`` from *conn*."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _sanitize(value: Any) -> Any:
    """Strip NUL bytes from strings so PostgreSQL does not reject them.

    PostgreSQL raises ``ValueError: A string literal cannot contain NUL (0x00)
    characters`` when a string value contains embedded NUL bytes, which can
    arrive from PDF text extraction on malformed or scanned documents.
    """
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def _insert_complainants(
    conn: PgConnection,
    fir_id: uuid.UUID,
    complainants: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Insert complainant rows and return them with generated UUIDs."""
    inserted: List[Dict[str, Any]] = []
    for item in complainants:
        cid = uuid.uuid4()
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO complainants (id, fir_id, name, father_name, age, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    cid,
                    fir_id,
                    item.get("name"),
                    item.get("father_name"),
                    item.get("age"),
                    item.get("address"),
                ),
            )
            inserted.append(dict(cur.fetchone()))
    return inserted


def _insert_accused(
    conn: PgConnection,
    fir_id: uuid.UUID,
    accused_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Insert accused rows and return them with generated UUIDs."""
    inserted: List[Dict[str, Any]] = []
    for item in accused_list:
        aid = uuid.uuid4()
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO accused (id, fir_id, name, age, address)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    aid,
                    fir_id,
                    item.get("name"),
                    item.get("age"),
                    item.get("address"),
                ),
            )
            inserted.append(dict(cur.fetchone()))
    return inserted


def _fetch_related(conn: PgConnection, fir_id: uuid.UUID) -> Dict[str, List[Dict]]:
    """Fetch complainants and accused for a given *fir_id*."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM complainants WHERE fir_id = %s ORDER BY name",
            (fir_id,),
        )
        complainants = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM accused WHERE fir_id = %s ORDER BY name",
            (fir_id,),
        )
        accused = [dict(r) for r in cur.fetchall()]

    return {"complainants": complainants, "accused": accused}


# ─────────────────────────────────────────────
# Public CRUD functions
# ─────────────────────────────────────────────


def create_fir(conn: PgConnection, fir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a FIR and its nested entities, returning the full record.

    Parameters
    ----------
    conn:
        Active psycopg2 connection.
    fir_data:
        Dictionary matching the ``FIRCreate`` schema (plain dicts — call
        ``.model_dump()`` before passing).

    Returns
    -------
    dict
        The created FIR row merged with its complainants and accused lists.
    """
    fir_id = uuid.uuid4()

    # ── Sanitize all string values from PDF extraction ──────────────────────
    # PDF-extracted text can contain NUL bytes (\\x00) which PostgreSQL rejects.
    fir_data = {k: _sanitize(v) for k, v in fir_data.items()}

    # ── Normalise primary_sections ──────────────────────────────────────────
    primary_sections = fir_data.get("primary_sections")
    if isinstance(primary_sections, str):
        primary_sections = [primary_sections]
    elif not primary_sections:
        primary_sections = []

    # ── raw_text falls back to narrative if omitted ─────────────────────────
    raw_text = fir_data.get("raw_text") or fir_data.get("narrative")

    with conn:  # transaction — rolls back automatically on exception
        with _dict_cursor(conn) as cur:
            # Extract sections_flagged from sections_validation if present
            validation = fir_data.get("sections_validation") or {}
            sections_flagged = validation.get("unknown") or []

            # Wrap stolen_property dict in psycopg2-JSON for JSONB column
            stolen_property = fir_data.get("stolen_property")
            if stolen_property is not None:
                stolen_property = PgJson(stolen_property)

            cur.execute(
                """
                INSERT INTO firs (
                    id, fir_number, police_station, district,
                    fir_date, occurrence_start, occurrence_end,
                    primary_act, primary_sections, sections_flagged,
                    complainant_name, accused_name,
                    gpf_no,
                    occurrence_from, occurrence_to,
                    time_from, time_to,
                    info_received_date, info_received_time,
                    info_type,
                    place_distance_km, place_address,
                    complainant_father_name, complainant_age,
                    complainant_nationality, complainant_occupation,
                    io_name, io_rank, io_number, officer_name,
                    dispatch_date, dispatch_time,
                    stolen_property, completeness_pct,
                    narrative, raw_text,
                    source_system
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s
                )
                RETURNING *
                """,
                (
                    fir_id,
                    fir_data.get("fir_number"),
                    fir_data.get("police_station"),
                    fir_data.get("district"),
                    fir_data.get("fir_date"),
                    fir_data.get("occurrence_start"),
                    fir_data.get("occurrence_end"),
                    fir_data.get("primary_act"),
                    primary_sections,
                    sections_flagged,
                    fir_data.get("complainant_name"),
                    fir_data.get("accused_name"),
                    fir_data.get("gpf_no"),
                    fir_data.get("occurrence_from"),
                    fir_data.get("occurrence_to"),
                    fir_data.get("time_from"),
                    fir_data.get("time_to"),
                    fir_data.get("info_received_date"),
                    fir_data.get("info_received_time"),
                    fir_data.get("info_type"),
                    fir_data.get("place_distance_km"),
                    fir_data.get("place_address"),
                    fir_data.get("complainant_father_name"),
                    fir_data.get("complainant_age"),
                    fir_data.get("complainant_nationality"),
                    fir_data.get("complainant_occupation"),
                    fir_data.get("io_name"),
                    fir_data.get("io_rank"),
                    fir_data.get("io_number"),
                    fir_data.get("officer_name"),
                    fir_data.get("dispatch_date"),
                    fir_data.get("dispatch_time"),
                    stolen_property,
                    fir_data.get("completeness_pct"),
                    fir_data.get("narrative"),
                    raw_text,
                    fir_data.get("source_system", "manual"),
                ),
            )
            fir_row = dict(cur.fetchone())

        complainants = _insert_complainants(
            conn, fir_id, fir_data.get("complainants") or []
        )
        accused = _insert_accused(conn, fir_id, fir_data.get("accused") or [])

    fir_row["complainants"] = complainants
    fir_row["accused"] = accused
    return fir_row


def get_fir_by_id(conn: PgConnection, fir_id: str, district: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single FIR by its UUID primary key.

    When *district* is provided only FIRs belonging to that district are
    returned, enforcing row-level security for IO/SHO roles.
    Returns ``None`` when no matching record exists.
    """
    with _dict_cursor(conn) as cur:
        if district is not None:
            cur.execute(
                "SELECT * FROM firs WHERE id = %s AND district = %s",
                (fir_id, district),
            )
        else:
            cur.execute("SELECT * FROM firs WHERE id = %s", (fir_id,))
        row = cur.fetchone()

    if row is None:
        return None

    fir_row = dict(row)
    fir_row.update(_fetch_related(conn, fir_row["id"]))
    return fir_row


def delete_fir(
    conn: PgConnection,
    fir_id: str,
    district: Optional[str] = None,
) -> bool:
    """Delete a FIR and every cascaded child row.

    The cascade chain (per migrations 001/005/006/007/009):
      firs -> complainants, accused, property_details         (CASCADE)
      firs -> chargesheet_mindmaps -> mindmap_nodes
                                  -> mindmap_node_status      (CASCADE; gated)
      firs -> chargesheets, validation_reports,
              evidence_gap_reports                            (SET NULL)

    The append-only trigger on ``mindmap_node_status`` is bypassed for
    the lifetime of this transaction by setting
    ``atlas.allow_status_delete`` (see migration 014).

    Returns
    -------
    bool
        ``True`` if a row was deleted, ``False`` if no matching FIR existed
        (so the caller can return 404).
    """
    with conn:  # transaction scope
        with _dict_cursor(conn) as cur:
            # Open the narrow trigger escape hatch for this txn only.
            cur.execute("SET LOCAL atlas.allow_status_delete = 'on'")

            if district is not None:
                cur.execute(
                    "DELETE FROM firs WHERE id = %s AND district = %s RETURNING id",
                    (fir_id, district),
                )
            else:
                cur.execute(
                    "DELETE FROM firs WHERE id = %s RETURNING id",
                    (fir_id,),
                )
            row = cur.fetchone()
    return row is not None


def list_firs(
    conn: PgConnection,
    limit: int = 10,
    offset: int = 0,
    district: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return a paginated list of FIRs (without nested entities for performance).

    Parameters
    ----------
    limit:
        Maximum number of records to return (capped at 100, default 10).
    offset:
        Number of records to skip (default 0).
    district:
        When set, only FIRs for that district are returned (IO/SHO scope).
    """
    limit = min(limit, 100)  # guard against runaway queries
    with _dict_cursor(conn) as cur:
        if district is not None:
            cur.execute(
                "SELECT * FROM firs WHERE district = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (district, limit, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM firs ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
        return [dict(r) for r in cur.fetchall()]
