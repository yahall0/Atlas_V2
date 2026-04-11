"""Add evidence_gap_reports table.

Revision ID: 007
Revises: 006
Create Date: 2026-04-11

Stores evidence gap analysis reports for charge-sheets.
"""

from __future__ import annotations

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_gap_reports (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chargesheet_id  UUID NOT NULL REFERENCES chargesheets(id) ON DELETE CASCADE,
            fir_id          UUID REFERENCES firs(id) ON DELETE SET NULL,
            crime_category  VARCHAR(64),
            gaps_json       JSONB NOT NULL DEFAULT '[]',
            present_json    JSONB NOT NULL DEFAULT '[]',
            coverage_pct    NUMERIC(5,1) DEFAULT 0.0,
            total_gaps      INTEGER DEFAULT 0,
            analyzed_by     TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_gap_cs_id "
        "ON evidence_gap_reports (chargesheet_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_gap_reports;")
