"""Initial schema — all Sprint 1 tables.

Revision ID: 001
Revises:
Create Date: 2026-04-08

Wraps the hand-written init_schema.sql so it is version-controlled and
reproducible via ``alembic upgrade head``.
"""

from __future__ import annotations

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS firs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_number          TEXT,
    police_station      TEXT,
    district            TEXT,
    fir_date            DATE,
    occurrence_start    TIMESTAMP NULL,
    occurrence_end      TIMESTAMP NULL,
    primary_act         TEXT,
    primary_sections    TEXT[],
    sections_flagged    TEXT[],
    complainant_name    TEXT,
    accused_name        TEXT,
    gpf_no              TEXT,
    occurrence_from     DATE,
    occurrence_to       DATE,
    time_from           TEXT,
    time_to             TEXT,
    info_received_date  DATE,
    info_received_time  TEXT,
    info_type           TEXT,
    place_distance_km   TEXT,
    place_address       TEXT,
    complainant_father_name  TEXT,
    complainant_age          SMALLINT,
    complainant_nationality  TEXT,
    complainant_occupation   TEXT,
    io_name             TEXT,
    io_rank             TEXT,
    io_number           TEXT,
    officer_name        TEXT,
    dispatch_date       DATE,
    dispatch_time       TEXT,
    stolen_property     JSONB,
    completeness_pct    NUMERIC(4,1),
    narrative           TEXT NOT NULL,
    raw_text            TEXT NOT NULL,
    source_system       TEXT DEFAULT 'manual',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fir_number ON firs (fir_number);
CREATE INDEX IF NOT EXISTS idx_created_at ON firs (created_at);
CREATE INDEX IF NOT EXISTS idx_firs_district ON firs (district);

CREATE TABLE IF NOT EXISTS complainants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id      UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    name        TEXT,
    father_name TEXT,
    age         SMALLINT,
    address     TEXT
);
CREATE INDEX IF NOT EXISTS idx_complainants_fir_id ON complainants (fir_id);

CREATE TABLE IF NOT EXISTS accused (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id  UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    name    TEXT,
    age     SMALLINT,
    address TEXT
);
CREATE INDEX IF NOT EXISTS idx_accused_fir_id ON accused (fir_id);

CREATE TABLE IF NOT EXISTS property_details (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id      UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    description TEXT,
    value       NUMERIC(15, 2)
);
CREATE INDEX IF NOT EXISTS idx_property_details_fir_id ON property_details (fir_id);

CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    full_name      TEXT,
    role           TEXT NOT NULL DEFAULT 'READONLY',
    district       TEXT,
    police_station TEXT,
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

CREATE TABLE IF NOT EXISTS audit_log (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    details       JSONB,
    ip_address    TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at);

CREATE TABLE IF NOT EXISTS ocr_jobs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status         TEXT DEFAULT 'pending',
    filename       TEXT,
    uploaded_by    UUID,
    fir_id         UUID REFERENCES firs (id),
    result_summary JSONB,
    error_message  TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at   TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status ON ocr_jobs (status);
"""

_DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ocr_jobs CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS property_details CASCADE;
DROP TABLE IF EXISTS accused CASCADE;
DROP TABLE IF EXISTS complainants CASCADE;
DROP TABLE IF EXISTS firs CASCADE;
"""


def upgrade() -> None:
    op.execute(_UPGRADE_SQL)


def downgrade() -> None:
    op.execute(_DOWNGRADE_SQL)
