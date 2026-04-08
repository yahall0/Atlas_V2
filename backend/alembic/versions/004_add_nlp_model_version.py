"""Sprint 3 — add nlp_model_version column to firs.

Revision ID: 004
Revises: 003
Create Date: 2026-04-14

Records which model checkpoint produced each NLP classification result,
enabling traceability when the checkpoint is updated.
"""

from __future__ import annotations

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE firs
            ADD COLUMN IF NOT EXISTS nlp_model_version TEXT;
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_firs_nlp_model_version "
        "ON firs (nlp_model_version);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_firs_nlp_model_version;")
    op.execute("""
        ALTER TABLE firs
            DROP COLUMN IF EXISTS nlp_model_version;
    """)
