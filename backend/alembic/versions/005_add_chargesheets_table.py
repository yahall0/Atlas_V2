"""Add chargesheets table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-11

Stores parsed charge-sheet documents with JSONB columns for accused,
charges, evidence, and witnesses.
"""

from __future__ import annotations

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS chargesheets (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            fir_id          UUID REFERENCES firs(id) ON DELETE SET NULL,
            filing_date     DATE,
            court_name      TEXT,

            accused_json    JSONB DEFAULT '[]',
            charges_json    JSONB DEFAULT '[]',
            evidence_json   JSONB DEFAULT '[]',
            witnesses_json  JSONB DEFAULT '[]',

            io_name         TEXT,
            raw_text        TEXT NOT NULL DEFAULT '',
            parsed_json     JSONB DEFAULT '{}',

            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','parsed','reviewed','flagged')),
            reviewer_notes  TEXT,
            uploaded_by     TEXT,
            district        TEXT,
            police_station  TEXT,

            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chargesheets_fir_id "
        "ON chargesheets (fir_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chargesheets_status "
        "ON chargesheets (status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chargesheets_district "
        "ON chargesheets (district);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chargesheets_created_at "
        "ON chargesheets (created_at);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chargesheets;")
