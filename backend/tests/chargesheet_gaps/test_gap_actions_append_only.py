"""Tests for append-only enforcement on chargesheet_gap_actions — T56-E12.

Requires a live database with the migration applied.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.db


class TestGapActionsAppendOnly:
    @pytest.fixture
    def db_conn(self):
        import os
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            pytest.skip("DATABASE_URL not set")
        import psycopg2
        conn = psycopg2.connect(db_url)
        yield conn
        conn.rollback()
        conn.close()

    @pytest.fixture
    def test_gap_id(self, db_conn) -> uuid.UUID:
        cs_id = uuid.uuid4()
        report_id = uuid.uuid4()
        gap_id = uuid.uuid4()
        with db_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chargesheets (id, raw_text, created_at)
                   VALUES (%s, 'test', now())""", (cs_id,),
            )
            cur.execute(
                """INSERT INTO chargesheet_gap_reports
                   (id, chargesheet_id, generated_at, generator_version, gap_count)
                   VALUES (%s, %s, now(), 'test', 0)""",
                (report_id, cs_id),
            )
            cur.execute(
                """INSERT INTO chargesheet_gaps
                   (id, report_id, category, severity, source,
                    requires_disclaimer, title, confidence, display_order)
                   VALUES (%s, %s, 'legal', 'high', 'T54_legal_validator',
                           false, 'Test Gap', 0.9, 0)""",
                (gap_id, report_id),
            )
            db_conn.commit()
        return gap_id

    def _insert_action(self, conn, gap_id):
        action_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chargesheet_gap_actions
                   (id, gap_id, user_id, action, created_at, hash_prev, hash_self)
                   VALUES (%s, %s, 'test', 'accepted', now(), 'GENESIS', %s)""",
                (action_id, gap_id, f"hash_{action_id}"),
            )
            conn.commit()
        return action_id

    def test_insert_allowed(self, db_conn, test_gap_id):
        aid = self._insert_action(db_conn, test_gap_id)
        assert aid is not None

    def test_update_rejected(self, db_conn, test_gap_id):
        aid = self._insert_action(db_conn, test_gap_id)
        import psycopg2
        with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
            with db_conn.cursor() as cur:
                cur.execute(
                    "UPDATE chargesheet_gap_actions SET action = 'dismissed' WHERE id = %s",
                    (aid,),
                )

    def test_delete_rejected(self, db_conn, test_gap_id):
        aid = self._insert_action(db_conn, test_gap_id)
        import psycopg2
        with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
            with db_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chargesheet_gap_actions WHERE id = %s", (aid,),
                )
