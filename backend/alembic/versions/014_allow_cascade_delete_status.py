"""Allow cascaded delete of mindmap_node_status when a FIR is deleted.

Revision ID: 014
Revises: 013
Create Date: 2026-04-18

Background
----------
Migration 009 installed an append-only trigger on ``mindmap_node_status``
that rejects every UPDATE / DELETE.  That guard is the right default —
the table is the audit chain and must not be mutated.

But it also blocks the cascade path
``firs -> chargesheet_mindmaps -> mindmap_nodes -> mindmap_node_status``
that fires when an admin deletes a FIR or chargesheet.  We need a narrow,
explicit escape hatch: the trigger now permits DELETE *only* when the
session has set the ``atlas.allow_status_delete`` GUC to ``on``.  The
DELETE-FIR / DELETE-chargesheet endpoints set this within the
transaction, so cascade succeeds; everywhere else the original
append-only invariant holds.
"""
from __future__ import annotations

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_mindmap_status_mutation() RETURNS TRIGGER AS $$
        BEGIN
          -- Narrow escape hatch: cascading delete of the parent FIR /
          -- chargesheet sets atlas.allow_status_delete='on' for the
          -- transaction.  Outside that window the table stays append-only.
          IF TG_OP = 'DELETE'
             AND current_setting('atlas.allow_status_delete', true) = 'on' THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'mindmap_node_status is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_mindmap_status_mutation() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'mindmap_node_status is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
