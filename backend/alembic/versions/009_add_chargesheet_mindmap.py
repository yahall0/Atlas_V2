"""Add chargesheet mindmap tables.

Revision ID: 009
Revises: 008
Create Date: 2026-04-18

Chargesheet mindmap with append-only node status tracking.
"""

from __future__ import annotations

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── chargesheet_mindmaps ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS chargesheet_mindmaps (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            fir_id                  UUID NOT NULL REFERENCES firs(id) ON DELETE CASCADE,
            case_category           VARCHAR(64) NOT NULL,
            template_version        VARCHAR(32) NOT NULL,
            generated_at            TIMESTAMP NOT NULL DEFAULT now(),
            generated_by_model_version VARCHAR(128),
            root_node_id            UUID,
            status                  VARCHAR(32) NOT NULL DEFAULT 'active'
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mindmap_fir_id "
        "ON chargesheet_mindmaps (fir_id);"
    )

    # ── mindmap_nodes ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS mindmap_nodes (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            mindmap_id      UUID NOT NULL REFERENCES chargesheet_mindmaps(id) ON DELETE CASCADE,
            parent_id       UUID REFERENCES mindmap_nodes(id) ON DELETE SET NULL,
            node_type       VARCHAR(32) NOT NULL
                            CHECK (node_type IN (
                                'legal_section','immediate_action','evidence',
                                'interrogation','panchnama','forensic',
                                'witness_bayan','gap_from_fir','custom'
                            )),
            title           VARCHAR(512) NOT NULL,
            description_md  TEXT,
            source          VARCHAR(32) NOT NULL
                            CHECK (source IN (
                                'static_template','ml_suggestion',
                                'completeness_engine','io_custom'
                            )),
            bns_section     VARCHAR(32),
            ipc_section     VARCHAR(32),
            crpc_section    VARCHAR(32),
            priority        VARCHAR(16) NOT NULL DEFAULT 'recommended'
                            CHECK (priority IN ('critical','recommended','optional')),
            requires_disclaimer BOOLEAN NOT NULL DEFAULT false,
            display_order   INTEGER NOT NULL DEFAULT 0,
            metadata        JSONB DEFAULT '{}'::jsonb
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mindmap_nodes_mindmap_id "
        "ON mindmap_nodes (mindmap_id);"
    )

    # ── mindmap_node_status (append-only) ────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS mindmap_node_status (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            node_id      UUID NOT NULL REFERENCES mindmap_nodes(id) ON DELETE CASCADE,
            user_id      TEXT NOT NULL,
            status       VARCHAR(32) NOT NULL
                         CHECK (status IN (
                             'open','in_progress','addressed',
                             'not_applicable','disputed'
                         )),
            note         TEXT,
            evidence_ref TEXT,
            updated_at   TIMESTAMP NOT NULL DEFAULT now(),
            hash_prev    VARCHAR(64) NOT NULL,
            hash_self    VARCHAR(64) NOT NULL
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mindmap_node_status_lookup "
        "ON mindmap_node_status (node_id, updated_at DESC);"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mindmap_node_status_hash_self "
        "ON mindmap_node_status (hash_self);"
    )

    # ── Append-only trigger (reject UPDATE / DELETE) ─────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_mindmap_status_mutation() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'mindmap_node_status is append-only: % operations are prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_mindmap_status_no_update
          BEFORE UPDATE ON mindmap_node_status
          FOR EACH ROW EXECUTE FUNCTION reject_mindmap_status_mutation();
    """)
    op.execute("""
        CREATE TRIGGER trg_mindmap_status_no_delete
          BEFORE DELETE ON mindmap_node_status
          FOR EACH ROW EXECUTE FUNCTION reject_mindmap_status_mutation();
    """)


def downgrade() -> None:
    # Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_mindmap_status_no_delete ON mindmap_node_status;")
    op.execute("DROP TRIGGER IF EXISTS trg_mindmap_status_no_update ON mindmap_node_status;")
    # Function
    op.execute("DROP FUNCTION IF EXISTS reject_mindmap_status_mutation();")
    # Tables (reverse creation order)
    op.execute("DROP TABLE IF EXISTS mindmap_node_status;")
    op.execute("DROP TABLE IF EXISTS mindmap_nodes;")
    op.execute("DROP TABLE IF EXISTS chargesheet_mindmaps;")
