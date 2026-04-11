"""Add validation_reports table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-11

Stores legal cross-reference validation reports for charge-sheets.
"""

from __future__ import annotations

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS validation_reports (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chargesheet_id  UUID NOT NULL REFERENCES chargesheets(id) ON DELETE CASCADE,
            fir_id          UUID REFERENCES firs(id) ON DELETE SET NULL,
            findings_json   JSONB NOT NULL DEFAULT '[]',
            summary_json    JSONB NOT NULL DEFAULT '{}',
            overall_status  TEXT NOT NULL DEFAULT 'pass'
                            CHECK (overall_status IN ('pass','warnings','errors','critical')),
            validated_by    TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_validation_reports_cs_id "
        "ON validation_reports (chargesheet_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_validation_reports_status "
        "ON validation_reports (overall_status);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS validation_reports;")
