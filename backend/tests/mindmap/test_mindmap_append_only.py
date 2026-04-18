"""Tests for append-only enforcement on mindmap_node_status — T53-M8.

These tests verify the DB trigger rejects UPDATE and DELETE operations.
They require a live database connection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

# These tests are integration tests that require a real database.
# They are marked with the 'db' marker and skipped if no DATABASE_URL is set.
pytestmark = pytest.mark.db


def _insert_test_status(conn, node_id: uuid.UUID) -> uuid.UUID:
    """Helper to insert a test status row."""
    status_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO mindmap_node_status
               (id, node_id, user_id, status, updated_at, hash_prev, hash_self)
               VALUES (%s, %s, 'test_user', 'open', %s, 'GENESIS', %s)""",
            (status_id, node_id, now, f"hash_{status_id}"),
        )
        conn.commit()
    return status_id


class TestAppendOnlyTrigger:
    """Verify the DB trigger rejects UPDATE and DELETE on mindmap_node_status."""

    @pytest.fixture
    def db_conn(self):
        """Get a database connection. Skip if not available."""
        import os
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            pytest.skip("DATABASE_URL not set — skipping DB integration test")

        import psycopg2
        conn = psycopg2.connect(db_url)
        yield conn
        conn.rollback()
        conn.close()

    @pytest.fixture
    def test_node_id(self, db_conn) -> uuid.UUID:
        """Create test fixtures: mindmap -> node -> return node_id."""
        fir_id = uuid.uuid4()
        mindmap_id = uuid.uuid4()
        node_id = uuid.uuid4()

        with db_conn.cursor() as cur:
            # Create test FIR
            cur.execute(
                """INSERT INTO firs (id, narrative, fir_number, district)
                   VALUES (%s, 'test narrative', 'TEST/001', 'TestDistrict')""",
                (fir_id,),
            )
            # Create test mindmap
            cur.execute(
                """INSERT INTO chargesheet_mindmaps
                   (id, fir_id, case_category, template_version, generated_at, status)
                   VALUES (%s, %s, 'murder', '1.0.0', now(), 'active')""",
                (mindmap_id, fir_id),
            )
            # Create test node
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, node_type, title, source, priority,
                    requires_disclaimer, display_order)
                   VALUES (%s, %s, 'evidence', 'Test Node', 'static_template',
                           'recommended', false, 0)""",
                (node_id, mindmap_id),
            )
            db_conn.commit()

        return node_id

    def test_insert_allowed(self, db_conn, test_node_id):
        """INSERT should succeed (append-only allows inserts)."""
        status_id = _insert_test_status(db_conn, test_node_id)
        assert status_id is not None

    def test_update_rejected(self, db_conn, test_node_id):
        """UPDATE should be rejected by the trigger."""
        status_id = _insert_test_status(db_conn, test_node_id)

        import psycopg2
        with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
            with db_conn.cursor() as cur:
                cur.execute(
                    "UPDATE mindmap_node_status SET status = 'addressed' WHERE id = %s",
                    (status_id,),
                )

    def test_delete_rejected(self, db_conn, test_node_id):
        """DELETE should be rejected by the trigger."""
        status_id = _insert_test_status(db_conn, test_node_id)

        import psycopg2
        with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
            with db_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM mindmap_node_status WHERE id = %s",
                    (status_id,),
                )
