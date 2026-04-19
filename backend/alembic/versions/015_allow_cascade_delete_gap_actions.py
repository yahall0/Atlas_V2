"""Allow cascaded delete of chargesheet_gap_actions when its parent is deleted.

Revision ID: 015
Revises: 014
Create Date: 2026-04-19

Migration 010 installed an append-only trigger on
``chargesheet_gap_actions`` that rejects every UPDATE / DELETE.  That
guard is the right default — gap-action rows are part of the
audit/feedback ledger and must not be silently mutated.

But it also blocks the cascade path
``chargesheets -> chargesheet_gap_reports -> chargesheet_gap_actions``
that fires when an admin deletes a chargesheet.  Mirroring migration
014 (which carved out the same escape hatch for
``mindmap_node_status``), this migration teaches the trigger to
permit DELETE *only* when the session has set the shared
``atlas.allow_status_delete`` GUC to ``on``.  The DELETE-chargesheet
endpoint sets this GUC within its transaction; everywhere else the
original append-only invariant holds.
"""
from __future__ import annotations

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_gap_action_mutation() RETURNS TRIGGER AS $$
        BEGIN
          -- Narrow escape hatch: cascading delete from chargesheets sets
          -- atlas.allow_status_delete='on' for the transaction.  Outside
          -- that window the table stays append-only.
          IF TG_OP = 'DELETE'
             AND current_setting('atlas.allow_status_delete', true) = 'on' THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION 'chargesheet_gap_actions is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_gap_action_mutation() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'chargesheet_gap_actions is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
