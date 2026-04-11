"""Tamper-evident audit chain with SHA-256 hash linking.

Each audit entry stores a hash of (action + detail + timestamp + previous_hash).
The chain can be verified by recomputing hashes and comparing.
"""

from __future__ import annotations

import csv
import hashlib
import io
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

_GENESIS = "GENESIS"


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _compute_hash(action: str, detail: dict, timestamp: str, previous_hash: str) -> str:
    """Compute SHA-256 hash for an audit entry."""
    payload = f"{action}|{json.dumps(detail, sort_keys=True, default=str)}|{timestamp}|{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditChain:
    """Append-only tamper-evident audit trail for chargesheets."""

    def __init__(self, conn: PgConnection):
        self._conn = conn

    def log(
        self,
        chargesheet_id: str,
        user_id: str,
        action: str,
        detail: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an audit entry linked to the previous one via hash chain.

        Returns the created entry as a dict.
        """
        detail = detail or {}
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Fetch previous hash
        with _dict_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT entry_hash FROM audit_log_chargesheet
                WHERE chargesheet_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chargesheet_id,),
            )
            prev = cur.fetchone()
            previous_hash = prev["entry_hash"] if prev else _GENESIS

        entry_hash = _compute_hash(action, detail, now_iso, previous_hash)
        entry_id = uuid.uuid4()

        with self._conn:
            with _dict_cursor(self._conn) as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log_chargesheet (
                        id, chargesheet_id, user_id, action,
                        detail_json, ip_address, user_agent,
                        previous_hash, entry_hash, created_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        entry_id, chargesheet_id, user_id, action,
                        PgJson(detail), ip_address, user_agent,
                        previous_hash, entry_hash,
                        now.replace(tzinfo=None),
                    ),
                )
                row = dict(cur.fetchone())

        logger.info(
            "Audit logged: cs=%s action=%s hash=%s",
            chargesheet_id, action, entry_hash[:12],
        )
        return row

    def verify_chain(self, chargesheet_id: str) -> Dict[str, Any]:
        """Walk all entries and verify the hash chain integrity."""
        with _dict_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT * FROM audit_log_chargesheet
                WHERE chargesheet_id = %s
                ORDER BY created_at ASC
                """,
                (chargesheet_id,),
            )
            entries = [dict(r) for r in cur.fetchall()]

        if not entries:
            return {
                "valid": True,
                "total_entries": 0,
                "first_break_at": None,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

        expected_prev = _GENESIS
        for idx, entry in enumerate(entries):
            # Verify previous_hash matches expected
            if entry["previous_hash"] != expected_prev:
                return {
                    "valid": False,
                    "total_entries": len(entries),
                    "first_break_at": idx,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }

            # Recompute and verify entry_hash
            ts = entry["created_at"]
            if hasattr(ts, "isoformat"):
                ts_iso = ts.replace(tzinfo=timezone.utc).isoformat()
            else:
                ts_iso = str(ts)

            recomputed = _compute_hash(
                entry["action"],
                entry.get("detail_json") or {},
                ts_iso,
                entry["previous_hash"],
            )
            if recomputed != entry["entry_hash"]:
                return {
                    "valid": False,
                    "total_entries": len(entries),
                    "first_break_at": idx,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }

            expected_prev = entry["entry_hash"]

        return {
            "valid": True,
            "total_entries": len(entries),
            "first_break_at": None,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_history(
        self,
        chargesheet_id: str,
        action_filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """Paginated audit history with optional action type filter."""
        offset = (page - 1) * per_page
        params: Dict[str, Any] = {
            "cs_id": chargesheet_id,
            "limit": per_page,
            "offset": offset,
        }

        where = "WHERE chargesheet_id = %(cs_id)s"
        if action_filter:
            where += " AND action = %(action)s"
            params["action"] = action_filter

        with _dict_cursor(self._conn) as cur:
            cur.execute(
                f"""
                SELECT * FROM audit_log_chargesheet
                {where}
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def export_chain(self, chargesheet_id: str) -> bytes:
        """Export full audit chain as CSV bytes."""
        with _dict_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT * FROM audit_log_chargesheet
                WHERE chargesheet_id = %s
                ORDER BY created_at ASC
                """,
                (chargesheet_id,),
            )
            entries = [dict(r) for r in cur.fetchall()]

        output = io.StringIO()
        fieldnames = [
            "id", "chargesheet_id", "user_id", "action",
            "detail_json", "ip_address", "user_agent",
            "previous_hash", "entry_hash", "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            row = {k: str(entry.get(k, "")) for k in fieldnames}
            row["detail_json"] = json.dumps(entry.get("detail_json") or {})
            writer.writerow(row)

        return output.getvalue().encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation actions CRUD
# ─────────────────────────────────────────────────────────────────────────────


def create_recommendation_action(
    conn: PgConnection,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a recommendation action record."""
    rec_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with conn:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO recommendation_actions (
                    id, chargesheet_id, recommendation_id,
                    recommendation_type, source_rule, action_taken,
                    original_text, modified_text, reason,
                    reviewer_id, audit_entry_id, created_at
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING *
                """,
                (
                    rec_id, data.get("chargesheet_id"),
                    data.get("recommendation_id"),
                    data.get("recommendation_type"),
                    data.get("source_rule"),
                    data.get("action_taken"),
                    data.get("original_text"),
                    data.get("modified_text"),
                    data.get("reason"),
                    data.get("reviewer_id"),
                    data.get("audit_entry_id"),
                    now,
                ),
            )
            return dict(cur.fetchone())


def get_recommendation_actions(
    conn: PgConnection,
    chargesheet_id: str,
) -> List[Dict[str, Any]]:
    """Return all recommendation actions for a chargesheet."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT * FROM recommendation_actions
            WHERE chargesheet_id = %s
            ORDER BY created_at ASC
            """,
            (chargesheet_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def has_recommendation_action(
    conn: PgConnection,
    chargesheet_id: str,
    recommendation_id: str,
) -> bool:
    """Check if a recommendation already has an action taken."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT 1 FROM recommendation_actions
            WHERE chargesheet_id = %s AND recommendation_id = %s
            LIMIT 1
            """,
            (chargesheet_id, recommendation_id),
        )
        return cur.fetchone() is not None
