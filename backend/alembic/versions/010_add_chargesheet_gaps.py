"""Add chargesheet gap analysis tables.

Revision ID: 010
Revises: 009
Create Date: 2026-04-18

Gap reports, individual gaps, and append-only gap actions.
"""

from __future__ import annotations

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── chargesheet_gap_reports ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS chargesheet_gap_reports (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chargesheet_id          UUID NOT NULL REFERENCES chargesheets(id) ON DELETE CASCADE,
            generated_at            TIMESTAMP NOT NULL DEFAULT now(),
            generator_version       VARCHAR(128) NOT NULL,
            gap_count               INTEGER NOT NULL DEFAULT 0,
            critical_count          INTEGER NOT NULL DEFAULT 0,
            high_count              INTEGER NOT NULL DEFAULT 0,
            medium_count            INTEGER NOT NULL DEFAULT 0,
            low_count               INTEGER NOT NULL DEFAULT 0,
            advisory_count          INTEGER NOT NULL DEFAULT 0,
            generation_duration_ms  INTEGER
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_gap_reports_cs "
        "ON chargesheet_gap_reports (chargesheet_id, generated_at DESC);"
    )

    # ── chargesheet_gaps ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS chargesheet_gaps (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            report_id               UUID NOT NULL REFERENCES chargesheet_gap_reports(id) ON DELETE CASCADE,
            category                VARCHAR(32) NOT NULL
                                    CHECK (category IN (
                                        'legal','evidence','witness',
                                        'procedural','mindmap_divergence','completeness'
                                    )),
            severity                VARCHAR(16) NOT NULL
                                    CHECK (severity IN (
                                        'critical','high','medium','low','advisory'
                                    )),
            source                  VARCHAR(32) NOT NULL
                                    CHECK (source IN (
                                        'T54_legal_validator','T55_evidence_ml',
                                        'mindmap_diff','completeness_rules','manual_review'
                                    )),
            requires_disclaimer     BOOLEAN NOT NULL DEFAULT false,
            title                   VARCHAR(512) NOT NULL,
            description_md          TEXT,
            location                JSONB,
            legal_refs              JSONB DEFAULT '[]'::jsonb,
            remediation             JSONB DEFAULT '{}'::jsonb,
            related_mindmap_node_id UUID,
            confidence              NUMERIC(4,3) NOT NULL DEFAULT 0.0,
            tags                    TEXT[] DEFAULT '{}',
            display_order           INTEGER NOT NULL DEFAULT 0
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_gaps_report "
        "ON chargesheet_gaps (report_id, severity, display_order);"
    )

    # ── chargesheet_gap_actions (append-only) ────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS chargesheet_gap_actions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            gap_id              UUID NOT NULL REFERENCES chargesheet_gaps(id) ON DELETE CASCADE,
            user_id             TEXT NOT NULL,
            action              VARCHAR(16) NOT NULL
                                CHECK (action IN (
                                    'accepted','modified','dismissed',
                                    'deferred','escalated'
                                )),
            note                TEXT,
            modification_diff   TEXT,
            evidence_ref        TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT now(),
            hash_prev           VARCHAR(64) NOT NULL,
            hash_self           VARCHAR(64) NOT NULL
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_gap_actions_lookup "
        "ON chargesheet_gap_actions (gap_id, created_at DESC);"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_gap_actions_hash_self "
        "ON chargesheet_gap_actions (hash_self);"
    )

    # ── Append-only trigger (reject UPDATE / DELETE) ─────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_gap_action_mutation() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'chargesheet_gap_actions is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_gap_actions_no_update
          BEFORE UPDATE ON chargesheet_gap_actions
          FOR EACH ROW EXECUTE FUNCTION reject_gap_action_mutation();
    """)
    op.execute("""
        CREATE TRIGGER trg_gap_actions_no_delete
          BEFORE DELETE ON chargesheet_gap_actions
          FOR EACH ROW EXECUTE FUNCTION reject_gap_action_mutation();
    """)


def downgrade() -> None:
    # Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_gap_actions_no_delete ON chargesheet_gap_actions;")
    op.execute("DROP TRIGGER IF EXISTS trg_gap_actions_no_update ON chargesheet_gap_actions;")
    # Function
    op.execute("DROP FUNCTION IF EXISTS reject_gap_action_mutation();")
    # Tables (reverse creation order)
    op.execute("DROP TABLE IF EXISTS chargesheet_gap_actions;")
    op.execute("DROP TABLE IF EXISTS chargesheet_gaps;")
    op.execute("DROP TABLE IF EXISTS chargesheet_gap_reports;")
