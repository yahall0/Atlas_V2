-- This file is automatically executed by PostgreSQL on first container startup
-- via /docker-entrypoint-initdb.d
--
-- To reset the database and re-run this schema:
--   docker-compose down -v
--   docker-compose up --build
--
-- NOTE: scripts in /docker-entrypoint-initdb.d only run on the FIRST container
-- initialisation. Removing the named volume is required to trigger them again.

-- ATLAS FIR Database Schema
-- Sprint 1 T3 (hardened)
-- pgcrypto is required for gen_random_uuid() in PostgreSQL < 13 and some Docker images.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─────────────────────────────────────────────
-- Core FIR table
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS firs (
    -- Primary identifiers
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_number          TEXT,
    police_station      TEXT,
    district            TEXT,

    -- Dates & time
    fir_date            DATE,
    occurrence_start    TIMESTAMP NULL,
    occurrence_end      TIMESTAMP NULL,

    -- Legal classification
    primary_act         TEXT,
    primary_sections    TEXT[],
    sections_flagged    TEXT[],

    -- Participants (extracted from OCR; nested tables hold structured versions)
    complainant_name    TEXT,
    accused_name        TEXT,

    -- Investigating officer
    gpf_no              TEXT,

    -- Occurrence window (full four-corner: date_from, date_to, time_from, time_to)
    occurrence_from     DATE,
    occurrence_to       DATE,
    time_from           TEXT,
    time_to             TEXT,

    -- Information received at PS
    info_received_date  DATE,
    info_received_time  TEXT,

    -- Type of information (oral / written)
    info_type           TEXT,

    -- Place of occurrence
    place_distance_km   TEXT,
    place_address       TEXT,

    -- Extended complainant details
    complainant_father_name  TEXT,
    complainant_age          SMALLINT,
    complainant_nationality   TEXT,
    complainant_occupation    TEXT,

    -- Investigating / signing officer details
    io_name             TEXT,
    io_rank             TEXT,
    io_number           TEXT,
    officer_name        TEXT,

    -- Court dispatch
    dispatch_date       DATE,
    dispatch_time       TEXT,

    -- Stolen / seized property (JSON array of {description, value})
    stolen_property     JSONB,

    -- Extraction completeness score (0-100)
    completeness_pct    NUMERIC(4,1),

    -- Narrative (CRITICAL — required for NLP pipeline)
    narrative           TEXT NOT NULL,
    raw_text            TEXT NOT NULL,

    -- Metadata
    source_system       TEXT DEFAULT 'manual',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Sprint 2: NLP pipeline columns
    status              TEXT DEFAULT 'pending',
    nlp_metadata        JSONB DEFAULT '{}',
    nlp_classification  TEXT,
    nlp_confidence      NUMERIC(5,4),
    nlp_classified_at   TIMESTAMP,
    nlp_classified_by   TEXT,
    nlp_model_version   TEXT
);

CREATE INDEX IF NOT EXISTS idx_fir_number  ON firs (fir_number);
CREATE INDEX IF NOT EXISTS idx_created_at  ON firs (created_at);

-- ─────────────────────────────────────────────
-- Complainants
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS complainants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id      UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    name        TEXT,
    father_name TEXT,
    age         SMALLINT,
    address     TEXT
);

CREATE INDEX IF NOT EXISTS idx_complainants_fir_id ON complainants (fir_id);

-- ─────────────────────────────────────────────
-- Accused
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accused (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id  UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    name    TEXT,
    age     SMALLINT,
    address TEXT
);

CREATE INDEX IF NOT EXISTS idx_accused_fir_id ON accused (fir_id);

-- ─────────────────────────────────────────────
-- Property details (future-proof)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS property_details (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id      UUID NOT NULL REFERENCES firs (id) ON DELETE CASCADE,
    description TEXT,
    value       NUMERIC(15, 2)
);

CREATE INDEX IF NOT EXISTS idx_property_details_fir_id ON property_details (fir_id);

-- ─────────────────────────────────────────────
-- Users table
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'READONLY',
    district TEXT,
    police_station TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ─────────────────────────────────────────────
-- Audit log (append-only, tamper-evident hash chain)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details JSONB,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- ─────────────────────────────────────────────
-- OCR processing jobs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ocr_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending',
    filename TEXT,
    uploaded_by UUID,
    fir_id UUID REFERENCES firs(id),
    result_summary JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status ON ocr_jobs(status);

-- ─────────────────────────────────────────────
-- Charge-sheets
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chargesheets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fir_id          UUID REFERENCES firs(id) ON DELETE SET NULL,
    filing_date     DATE,
    court_name      TEXT,
    accused_json    JSONB DEFAULT '[]',
    charges_json    JSONB DEFAULT '[]',
    evidence_json   JSONB DEFAULT '[]',
    witnesses_json  JSONB DEFAULT '[]',
    io_name         TEXT,
    raw_text        TEXT NOT NULL DEFAULT '',
    parsed_json     JSONB DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','parsed','reviewed','flagged')),
    reviewer_notes  TEXT,
    uploaded_by     TEXT,
    district        TEXT,
    police_station  TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chargesheets_fir_id ON chargesheets(fir_id);
CREATE INDEX IF NOT EXISTS idx_chargesheets_status ON chargesheets(status);
CREATE INDEX IF NOT EXISTS idx_chargesheets_district ON chargesheets(district);
CREATE INDEX IF NOT EXISTS idx_chargesheets_created_at ON chargesheets(created_at);

-- ─────────────────────────────────────────────
-- Validation reports
-- ─────────────────────────────────────────────
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
CREATE INDEX IF NOT EXISTS idx_validation_reports_cs_id ON validation_reports(chargesheet_id);
CREATE INDEX IF NOT EXISTS idx_validation_reports_status ON validation_reports(overall_status);

-- ─────────────────────────────────────────────
-- Evidence gap reports
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence_gap_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chargesheet_id  UUID NOT NULL REFERENCES chargesheets(id) ON DELETE CASCADE,
    fir_id          UUID REFERENCES firs(id) ON DELETE SET NULL,
    crime_category  VARCHAR(64),
    gaps_json       JSONB NOT NULL DEFAULT '[]',
    present_json    JSONB NOT NULL DEFAULT '[]',
    coverage_pct    NUMERIC(5,1) DEFAULT 0.0,
    total_gaps      INTEGER DEFAULT 0,
    analyzed_by     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_gap_cs_id ON evidence_gap_reports(chargesheet_id);
