"""Sprint 2 — add status and nlp_metadata to firs.

Revision ID: 002
Revises: 001
Create Date: 2026-04-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE firs
            ADD COLUMN IF NOT EXISTS status       TEXT    DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS nlp_metadata JSONB   DEFAULT '{}';
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_firs_status ON firs (status);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_firs_status;")
    op.execute("""
        ALTER TABLE firs
            DROP COLUMN IF EXISTS nlp_metadata,
            DROP COLUMN IF EXISTS status;
    """)
