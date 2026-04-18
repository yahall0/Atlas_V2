"""Add legal knowledge-base tables.

Revision ID: 011
Revises: 010
Create Date: 2026-04-18

Legal KB: offences, knowledge nodes, judgments, judgment chunks,
judgment insights, KB versions, and an append-only audit log.
"""

from __future__ import annotations

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector extension ──────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ── legal_kb_offences ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_offences (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category_id         TEXT NOT NULL,
            offence_code        TEXT UNIQUE NOT NULL,
            bns_section         TEXT,
            bns_subsection      TEXT,
            display_name_en     TEXT NOT NULL,
            display_name_gu     TEXT,
            short_description_md TEXT,
            punishment          TEXT,
            cognizable          BOOLEAN,
            bailable            BOOLEAN,
            triable_by          TEXT,
            compoundable        TEXT,
            schedule_reference  TEXT,
            related_offence_codes TEXT[] DEFAULT '{}',
            special_acts        TEXT[] DEFAULT '{}',
            kb_version          TEXT NOT NULL DEFAULT '1.0.0',
            created_at          TIMESTAMP NOT NULL DEFAULT now(),
            updated_at          TIMESTAMP NOT NULL DEFAULT now(),
            review_status       TEXT NOT NULL DEFAULT 'draft'
                                CHECK (review_status IN (
                                    'draft','reviewed','approved','deprecated'
                                )),
            reviewed_by         UUID,
            reviewed_at         TIMESTAMP,
            embedding           vector(768)
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_offences_category "
        "ON legal_kb_offences (category_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_offences_bns "
        "ON legal_kb_offences (bns_section, bns_subsection);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_offences_embedding "
        "ON legal_kb_offences USING hnsw (embedding vector_cosine_ops);"
    )

    # ── legal_kb_knowledge_nodes ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_knowledge_nodes (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            offence_id              UUID NOT NULL REFERENCES legal_kb_offences(id) ON DELETE CASCADE,
            branch_type             TEXT NOT NULL
                                    CHECK (branch_type IN (
                                        'legal_section','immediate_action','panchnama',
                                        'evidence','witness_bayan','forensic',
                                        'gap_historical','procedural_safeguard'
                                    )),
            tier                    TEXT NOT NULL
                                    CHECK (tier IN ('canonical','judgment_derived')),
            priority                TEXT NOT NULL DEFAULT 'medium'
                                    CHECK (priority IN (
                                        'critical','high','medium','low','advisory'
                                    )),
            title_en                TEXT NOT NULL,
            title_gu                TEXT,
            description_md          TEXT,
            legal_basis_citations   JSONB DEFAULT '[]'::jsonb,
            procedural_metadata     JSONB DEFAULT '{}'::jsonb,
            requires_disclaimer     BOOLEAN NOT NULL DEFAULT false,
            display_order           INTEGER NOT NULL DEFAULT 0,
            kb_version              TEXT NOT NULL DEFAULT '1.0.0',
            created_at              TIMESTAMP NOT NULL DEFAULT now(),
            updated_at              TIMESTAMP NOT NULL DEFAULT now(),
            created_by              UUID,
            approved_by             UUID,
            approval_status         TEXT NOT NULL DEFAULT 'proposed'
                                    CHECK (approval_status IN (
                                        'proposed','approved','contested','deprecated'
                                    )),
            contested_by_insight_ids UUID[] DEFAULT '{}',
            embedding               vector(768)
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_nodes_offence "
        "ON legal_kb_knowledge_nodes (offence_id, branch_type, approval_status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_nodes_embedding "
        "ON legal_kb_knowledge_nodes USING hnsw (embedding vector_cosine_ops);"
    )

    # ── legal_kb_judgments ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_judgments (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            citation            TEXT UNIQUE NOT NULL,
            case_name           TEXT,
            court               TEXT NOT NULL
                                CHECK (court IN (
                                    'supreme_court','gujarat_hc','other_hc','district'
                                )),
            jurisdiction        TEXT,
            judgment_date       DATE,
            bench               TEXT,
            binding_authority   INTEGER NOT NULL DEFAULT 40,
            source_file_ref     TEXT,
            source_url          TEXT,
            full_text           TEXT,
            summary_md          TEXT,
            related_bns_sections  TEXT[] DEFAULT '{}',
            related_offence_codes TEXT[] DEFAULT '{}',
            ingested_at         TIMESTAMP NOT NULL DEFAULT now(),
            ingested_by         UUID,
            review_status       TEXT NOT NULL DEFAULT 'ingested'
                                CHECK (review_status IN (
                                    'ingested','extracted','reviewed','approved','rejected'
                                )),
            reviewed_by         UUID,
            reviewed_at         TIMESTAMP,
            embedding           vector(768)
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_judgments_court_date "
        "ON legal_kb_judgments (court, judgment_date DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_judgments_authority "
        "ON legal_kb_judgments (binding_authority DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_judgments_embedding "
        "ON legal_kb_judgments USING hnsw (embedding vector_cosine_ops);"
    )

    # ── legal_kb_judgment_chunks ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_judgment_chunks (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            judgment_id     UUID NOT NULL REFERENCES legal_kb_judgments(id) ON DELETE CASCADE,
            chunk_index     INTEGER NOT NULL,
            chunk_text      TEXT NOT NULL,
            chunk_type      TEXT NOT NULL DEFAULT 'other'
                            CHECK (chunk_type IN (
                                'facts','ratio','obiter','operative','other'
                            )),
            embedding       vector(768),
            created_at      TIMESTAMP NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_chunks_judgment "
        "ON legal_kb_judgment_chunks (judgment_id, chunk_index);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding "
        "ON legal_kb_judgment_chunks USING hnsw (embedding vector_cosine_ops);"
    )

    # ── legal_kb_judgment_insights ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_judgment_insights (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            judgment_id                 UUID NOT NULL REFERENCES legal_kb_judgments(id) ON DELETE CASCADE,
            target_offence_id           UUID REFERENCES legal_kb_offences(id) ON DELETE SET NULL,
            target_knowledge_node_id    UUID REFERENCES legal_kb_knowledge_nodes(id) ON DELETE SET NULL,
            insight_type                TEXT NOT NULL
                                        CHECK (insight_type IN (
                                            'new_procedural_requirement',
                                            'evidentiary_standard_clarification',
                                            'rights_safeguard',
                                            'acquittal_pattern',
                                            'contradicts_existing_node',
                                            'reinforces_existing_node',
                                            'general'
                                        )),
            branch_type                 TEXT,
            title_en                    TEXT NOT NULL,
            description_md              TEXT,
            extracted_quote             TEXT,
            extracted_quote_paragraph   INTEGER,
            extraction_confidence       NUMERIC(4,3) DEFAULT 0.0,
            extraction_model_version    TEXT,
            proposed_action             TEXT
                                        CHECK (proposed_action IN (
                                            'add_new_node','update_node',
                                            'flag_contested','deprecate_node',
                                            'reinforce_only'
                                        )),
            review_status               TEXT NOT NULL DEFAULT 'pending'
                                        CHECK (review_status IN (
                                            'pending','approved','rejected','needs_revision'
                                        )),
            review_notes                TEXT,
            reviewed_by                 UUID,
            reviewed_at                 TIMESTAMP,
            applied_at                  TIMESTAMP,
            applied_as_node_id          UUID,
            kb_version_before           TEXT,
            kb_version_after            TEXT,
            created_at                  TIMESTAMP NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_insights_judgment "
        "ON legal_kb_judgment_insights (judgment_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_insights_offence "
        "ON legal_kb_judgment_insights (target_offence_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_kb_insights_review "
        "ON legal_kb_judgment_insights (review_status, created_at DESC);"
    )

    # ── legal_kb_versions ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_versions (
            version                     TEXT PRIMARY KEY,
            released_at                 TIMESTAMP NOT NULL DEFAULT now(),
            released_by                 UUID,
            changelog_md                TEXT,
            offences_added              INTEGER DEFAULT 0,
            offences_modified           INTEGER DEFAULT 0,
            nodes_added                 INTEGER DEFAULT 0,
            nodes_modified              INTEGER DEFAULT 0,
            nodes_deprecated            INTEGER DEFAULT 0,
            judgment_insights_applied   INTEGER DEFAULT 0,
            approved_by                 UUID
        );
    """)

    # ── legal_kb_audit_log (append-only) ────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_kb_audit_log (
            id              BIGSERIAL PRIMARY KEY,
            actor_user_id   UUID,
            action          TEXT NOT NULL,
            target_type     TEXT,
            target_id       UUID,
            before_state    JSONB,
            after_state     JSONB,
            timestamp       TIMESTAMP NOT NULL DEFAULT now(),
            hash_prev       VARCHAR(64) NOT NULL,
            hash_self       VARCHAR(64) NOT NULL
        );
    """)

    # ── Append-only trigger (reject UPDATE / DELETE) ────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_kb_audit_mutation() RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'legal_kb_audit_log is append-only: % operations prohibited', TG_OP;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_kb_audit_no_update
          BEFORE UPDATE ON legal_kb_audit_log
          FOR EACH ROW EXECUTE FUNCTION reject_kb_audit_mutation();
    """)
    op.execute("""
        CREATE TRIGGER trg_kb_audit_no_delete
          BEFORE DELETE ON legal_kb_audit_log
          FOR EACH ROW EXECUTE FUNCTION reject_kb_audit_mutation();
    """)


def downgrade() -> None:
    # Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_kb_audit_no_delete ON legal_kb_audit_log;")
    op.execute("DROP TRIGGER IF EXISTS trg_kb_audit_no_update ON legal_kb_audit_log;")
    # Function
    op.execute("DROP FUNCTION IF EXISTS reject_kb_audit_mutation();")
    # Tables (reverse creation order)
    op.execute("DROP TABLE IF EXISTS legal_kb_audit_log;")
    op.execute("DROP TABLE IF EXISTS legal_kb_versions;")
    op.execute("DROP TABLE IF EXISTS legal_kb_judgment_insights;")
    op.execute("DROP TABLE IF EXISTS legal_kb_judgment_chunks;")
    op.execute("DROP TABLE IF EXISTS legal_kb_judgments;")
    op.execute("DROP TABLE IF EXISTS legal_kb_knowledge_nodes;")
    op.execute("DROP TABLE IF EXISTS legal_kb_offences;")
    # NOTE: Do NOT drop the vector extension.
