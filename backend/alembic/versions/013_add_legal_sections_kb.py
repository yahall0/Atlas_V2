"""Legal sections corpus + chunk store + feedback ledger.

Revision ID: 013
Revises: 012
Create Date: 2026-04-19

Persists the IPC and BNS sections corpus (per ADR-D15 sub-clause precision)
and the chunk store used by the section recommender (per ADR-D16). Also
provisions the feedback ledger table that captures IO actions on each
recommendation entry — used as a re-ranking signal.

Tables created:

  * legal_sections           — one row per statutory section (umbrella record)
  * legal_section_chunks     — one row per addressable retrieval chunk
  * legal_recommendation_feedback — IO accept/modify/dismiss feedback ledger

The pgvector extension is required for the dense_embedding column. The
column dimension matches BAAI/bge-m3 (1024). If a different embedder is
configured at deploy time, this column type can be widened or replaced
via a follow-up migration.
"""

from __future__ import annotations

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector is available; idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_sections (
            id                 TEXT PRIMARY KEY,
            act                TEXT NOT NULL CHECK (act IN ('IPC', 'BNS')),
            section_number     TEXT NOT NULL,
            section_title      TEXT,
            chapter_number     TEXT,
            chapter_title      TEXT,
            full_text          TEXT NOT NULL,
            sub_clauses        JSONB NOT NULL DEFAULT '[]'::jsonb,
            illustrations      TEXT[],
            explanations       TEXT[],
            exceptions         TEXT[],
            cross_references   TEXT[],
            cognizable         BOOLEAN,
            bailable           BOOLEAN,
            triable_by         TEXT,
            compoundable       BOOLEAN,
            punishment         TEXT,
            metadata           JSONB DEFAULT '{}'::jsonb,
            source_page_start  INT,
            source_page_end    INT,
            created_at         TIMESTAMPTZ DEFAULT now(),
            updated_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_legal_sections_act_num "
        "ON legal_sections (act, section_number)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_section_chunks (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chunk_id           TEXT UNIQUE NOT NULL,
            section_id         TEXT NOT NULL REFERENCES legal_sections(id) ON DELETE CASCADE,
            act                TEXT NOT NULL CHECK (act IN ('IPC', 'BNS')),
            section_number     TEXT NOT NULL,
            section_title      TEXT,
            chapter_number     TEXT,
            chapter_title      TEXT,
            chunk_type         TEXT NOT NULL CHECK (
                chunk_type IN ('header','section_body','sub_clause','illustration','explanation','exception')
            ),
            chunk_index        INT NOT NULL,
            text               TEXT NOT NULL,
            canonical_citation TEXT NOT NULL,
            addressable_id     TEXT NOT NULL,
            sub_clause_label   TEXT,
            keywords           TEXT[],
            metadata           JSONB DEFAULT '{}'::jsonb,
            dense_embedding    vector(1024),
            created_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_section_chunks_section "
        "ON legal_section_chunks (section_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_section_chunks_act "
        "ON legal_section_chunks (act)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_section_chunks_addressable "
        "ON legal_section_chunks (addressable_id)"
    )
    # IVF-Flat ANN index for dense retrieval. ``lists = 100`` is a sensible
    # starting point for a corpus of ~3,300 chunks; tune at scale.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_section_chunks_dense "
        "ON legal_section_chunks USING ivfflat (dense_embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS legal_recommendation_feedback (
            id                 BIGSERIAL PRIMARY KEY,
            fir_id             TEXT NOT NULL,
            addressable_id     TEXT NOT NULL,
            user_id            UUID,
            action             TEXT NOT NULL CHECK (
                action IN ('accept','modify','dismiss','request_more_info')
            ),
            notes              TEXT,
            audit_action       TEXT NOT NULL,
            created_at         TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_feedback_addressable "
        "ON legal_recommendation_feedback (addressable_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_legal_feedback_fir "
        "ON legal_recommendation_feedback (fir_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS legal_recommendation_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS legal_section_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS legal_sections CASCADE")
