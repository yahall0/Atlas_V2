"""Sprint 2 — add nlp_classification columns to firs.

Revision ID: 003
Revises: 002
Create Date: 2026-04-08
"""

from __future__ import annotations

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE firs
            ADD COLUMN IF NOT EXISTS nlp_classification  TEXT,
            ADD COLUMN IF NOT EXISTS nlp_confidence      NUMERIC(4, 3),
            ADD COLUMN IF NOT EXISTS nlp_classified_at   TIMESTAMP,
            ADD COLUMN IF NOT EXISTS nlp_classified_by   TEXT;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_firs_nlp_class ON firs (nlp_classification);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_firs_nlp_class;")
    op.execute("""
        ALTER TABLE firs
            DROP COLUMN IF EXISTS nlp_classified_by,
            DROP COLUMN IF EXISTS nlp_classified_at,
            DROP COLUMN IF EXISTS nlp_confidence,
            DROP COLUMN IF EXISTS nlp_classification;
    """)
