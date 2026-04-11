"""Add audit_log_chargesheet and recommendation_actions tables.

Revision ID: 008
Revises: 007
Create Date: 2026-04-11

Tamper-evident audit chain with SHA-256 hash linking for chargesheet reviews.
"""

from __future__ import annotations

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Audit log - append-only hash chain
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log_chargesheet (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chargesheet_id  UUID NOT NULL REFERENCES chargesheets(id) ON DELETE CASCADE,
            user_id         TEXT NOT NULL,
            action          VARCHAR(64) NOT NULL,
            detail_json     JSONB,
            ip_address      VARCHAR(45),
            user_agent      TEXT,
            previous_hash   VARCHAR(64) NOT NULL,
            entry_hash      VARCHAR(64) NOT NULL UNIQUE,
            created_at      TIMESTAMP NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_cs_created "
        "ON audit_log_chargesheet (chargesheet_id, created_at);"
    )

    # Recommendation actions
    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendation_actions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chargesheet_id      UUID REFERENCES chargesheets(id) ON DELETE CASCADE,
            recommendation_id   VARCHAR(128),
            recommendation_type VARCHAR(32),
            source_rule         VARCHAR(32),
            action_taken        VARCHAR(16) NOT NULL,
            original_text       TEXT,
            modified_text       TEXT,
            reason              TEXT,
            reviewer_id         TEXT,
            audit_entry_id      UUID REFERENCES audit_log_chargesheet(id),
            created_at          TIMESTAMP DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rec_actions_cs "
        "ON recommendation_actions (chargesheet_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendation_actions;")
    op.execute("DROP TABLE IF EXISTS audit_log_chargesheet;")
