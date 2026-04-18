# Chargesheet Gap Analysis -- Backend Integration Guide

> **Module**: T56-E (Chargesheet Dual-Pane Gap Analysis)
> **Last updated**: 2026-04-18
> **Status**: Phase 1 -- Production-ready
> **Audience**: Backend developers, DevOps, QA engineers

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Database Schema Reference](#2-database-schema-reference)
3. [Gap Source Specifications](#3-gap-source-specifications)
4. [API Reference](#4-api-reference)
5. [Action Semantics](#5-action-semantics)
6. [Export Specifications](#6-export-specifications)
7. [Mindmap Integration](#7-mindmap-integration)
8. [Failure Modes & Recovery](#8-failure-modes--recovery)
9. [Observability](#9-observability)
10. [Security & Compliance](#10-security--compliance)
11. [Performance Tuning](#11-performance-tuning)
12. [Testing](#12-testing)
13. [Deployment](#13-deployment)
14. [Phase 2 Hooks](#14-phase-2-hooks)

---

## 1. Architecture Overview

### 1.1 Project Layout

```
backend/
  app/
    chargesheet/
      __init__.py              # Module marker
      gap_schemas.py           # Pydantic v2 models (request/response)
      gap_aggregator.py        # Core aggregation: fetch, convert, dedup, persist
      gap_routes.py            # FastAPI router (10 endpoints)
      gap_metrics.py           # Prometheus counters/histograms + structlog helpers
      completeness_rules/
        generic.json           # Base rules applied to all case categories
        murder.json            # IPC 302/304 / BNS 103 family
        ndps.json              # NDPS Act
        sexual_offences.json   # IPC 376 / BNS 63-99 family
  alembic/
    versions/
      010_add_chargesheet_gaps.py  # Migration (depends on 009)
  tests/
    chargesheet/
      test_gap_aggregator.py
      test_gap_routes.py
      test_gap_hash_chain.py
      test_gap_append_only.py      # DB integration -- trigger verification
      test_gap_exports.py
```

### 1.2 End-to-End Sequence

When an IO or SHO requests a gap analysis for a chargesheet, the system aggregates outputs from four upstream sources into a unified report. Each source is fetched independently; failures in any single source do not block the report.

```mermaid
sequenceDiagram
    participant IO as IO / SHO
    participant API as Gap Analysis API
    participant T53 as T53 CS Ingestion
    participant T54 as T54 Legal Validator
    participant T55 as T55 Evidence Gap ML
    participant MM as T53-M Mindmap
    participant CR as Completeness Rules
    participant AGG as Gap Aggregator
    participant DB as PostgreSQL

    IO->>API: POST /api/v1/chargesheet/{cs_id}/gaps/analyze
    API->>DB: SELECT * FROM chargesheets WHERE id = cs_id
    Note over T53: Chargesheet already ingested<br/>by upstream pipeline

    API->>AGG: aggregate_gaps(cs_id)

    par Fetch all sources
        AGG->>DB: SELECT FROM validation_reports (T54)
        AGG->>DB: SELECT FROM evidence_gap_reports (T55)
        AGG->>DB: SELECT FROM chargesheet_mindmaps + mindmap_nodes (T53-M)
        AGG->>CR: Load generic.json + {category}.json
    end

    AGG->>AGG: _convert_legal_findings(T54)
    AGG->>AGG: _convert_evidence_gaps(T55)
    AGG->>AGG: _compute_mindmap_divergences(MM)
    AGG->>AGG: _run_completeness_rules(CR)
    AGG->>AGG: _deduplicate(all_gaps)
    AGG->>AGG: Sort by severity, then confidence

    AGG->>DB: INSERT chargesheet_gap_reports
    AGG->>DB: INSERT chargesheet_gaps (N rows)
    AGG-->>API: GapReportResponse
    API-->>IO: 201 Created + JSON
```

### 1.3 Data Flow Diagram

```mermaid
flowchart LR
    subgraph "Upstream Pipeline (pre-existing)"
        CS_PDF["Chargesheet PDF Upload"]
        T53["T53: CS Ingestion"]
        T54["T54: Legal Validator"]
        T55["T55: Evidence Gap ML"]
        T53M["T53-M: Mindmap"]
    end

    subgraph "Gap Analysis Module (T56-E)"
        AGG["Gap Aggregator<br/>(gap_aggregator.py)"]
        ROUTES["Gap Routes<br/>(gap_routes.py)"]
        SCHEMAS["Gap Schemas<br/>(gap_schemas.py)"]
        METRICS["Gap Metrics<br/>(gap_metrics.py)"]
        RULES["Completeness Rules<br/>(*.json)"]
    end

    subgraph "Data Stores"
        CS_TABLE["chargesheets<br/>(READ)"]
        FIR_TABLE["firs<br/>(READ)"]
        VR_TABLE["validation_reports<br/>(READ, T54)"]
        EGR_TABLE["evidence_gap_reports<br/>(READ, T55)"]
        MM_TABLE["chargesheet_mindmaps<br/>(READ)"]
        MN_TABLE["mindmap_nodes<br/>(READ)"]
        GR_TABLE["chargesheet_gap_reports<br/>(READ/WRITE)"]
        G_TABLE["chargesheet_gaps<br/>(READ/WRITE)"]
        GA_TABLE["chargesheet_gap_actions<br/>(APPEND-ONLY)"]
    end

    CS_PDF --> T53 --> CS_TABLE
    T54 --> VR_TABLE
    T55 --> EGR_TABLE
    T53M --> MM_TABLE
    T53M --> MN_TABLE

    CS_TABLE --> AGG
    FIR_TABLE --> AGG
    VR_TABLE --> AGG
    EGR_TABLE --> AGG
    MM_TABLE --> AGG
    MN_TABLE --> AGG
    RULES --> AGG

    AGG --> GR_TABLE
    AGG --> G_TABLE
    ROUTES --> AGG
    ROUTES --> GA_TABLE
    ROUTES --> METRICS
```

### 1.4 Dependency Matrix

| Dependency | Type | Required | Fallback |
|---|---|---|---|
| PostgreSQL (psycopg2) | Runtime | Yes | None -- server will not start |
| Chargesheet record (chargesheets table) | Data | Yes | 404 if chargesheet not found |
| T54 Legal Validator (validation_reports) | Data | No | Report generated without legal findings; `partial_sources` includes `T54_legal_validator` |
| T55 Evidence Gap ML (evidence_gap_reports) | Data | No | Report generated without evidence gaps; `partial_sources` includes `T55_evidence_ml` |
| T53-M Mindmap (chargesheet_mindmaps, mindmap_nodes) | Data | No | Report generated without mindmap divergences; `partial_sources` includes `mindmap_diff` |
| Completeness rules JSON files | Startup | Partial | Generic rules always available; category-specific rules may be absent |
| structlog | Runtime | Yes | Standard logging fallback |
| prometheus_client | Runtime | No | Metrics silently disabled |
| WeasyPrint | Runtime (PDF export) | No | Falls back to HTML export |

### 1.5 Decision Rationale

See **ADR-D14** for the full architectural decision record. Key decisions summarized:

1. **Server-side aggregation** (not client-side composition) -- audit integrity, snapshot immutability, RBAC uniformity.
2. **Multi-source provenance** -- every gap carries its origin for transparency.
3. **Append-only action trail** with SHA-256 hash chain -- evidentiary integrity.
4. **Triple export model** -- court, internal, supervisor audiences require different documents.
5. **Severity-ranked presentation** -- gaps sorted by impact, not by source.

---

## 2. Database Schema Reference

### 2.1 Entity Relationship Diagram

```mermaid
erDiagram
    chargesheets ||--o{ chargesheet_gap_reports : "1 CS has 0..N report versions"
    chargesheet_gap_reports ||--|{ chargesheet_gaps : "1 report has 1..N gaps"
    chargesheet_gaps ||--o{ chargesheet_gap_actions : "1 gap has 0..N actions"
    chargesheet_gaps }o--o| mindmap_nodes : "optional link to mindmap node"

    chargesheet_gap_reports {
        UUID id PK "gen_random_uuid()"
        UUID chargesheet_id FK "NOT NULL, references chargesheets(id)"
        TIMESTAMP generated_at "NOT NULL, DEFAULT now()"
        VARCHAR128 generator_version "NOT NULL"
        INTEGER gap_count "NOT NULL, DEFAULT 0"
        INTEGER critical_count "NOT NULL, DEFAULT 0"
        INTEGER high_count "NOT NULL, DEFAULT 0"
        INTEGER medium_count "NOT NULL, DEFAULT 0"
        INTEGER low_count "NOT NULL, DEFAULT 0"
        INTEGER advisory_count "NOT NULL, DEFAULT 0"
        INTEGER generation_duration_ms "nullable"
    }

    chargesheet_gaps {
        UUID id PK "gen_random_uuid()"
        UUID report_id FK "NOT NULL, references chargesheet_gap_reports(id)"
        VARCHAR32 category "NOT NULL, CHECK constraint"
        VARCHAR16 severity "NOT NULL, CHECK constraint"
        VARCHAR32 source "NOT NULL, CHECK constraint"
        BOOLEAN requires_disclaimer "NOT NULL, DEFAULT false"
        VARCHAR512 title "NOT NULL"
        TEXT description_md "nullable"
        JSONB location "nullable, page/offset/bbox"
        JSONB legal_refs "DEFAULT '[]'::jsonb"
        JSONB remediation "DEFAULT '{}'::jsonb"
        UUID related_mindmap_node_id "nullable"
        NUMERIC confidence "NOT NULL, DEFAULT 0.0"
        TEXT_ARRAY tags "DEFAULT '{}'"
        INTEGER display_order "NOT NULL, DEFAULT 0"
    }

    chargesheet_gap_actions {
        UUID id PK "gen_random_uuid()"
        UUID gap_id FK "NOT NULL, references chargesheet_gaps(id)"
        TEXT user_id "NOT NULL"
        VARCHAR16 action "NOT NULL, CHECK constraint"
        TEXT note "nullable"
        TEXT modification_diff "nullable"
        TEXT evidence_ref "nullable"
        TIMESTAMP created_at "NOT NULL, DEFAULT now()"
        VARCHAR64 hash_prev "NOT NULL"
        VARCHAR64 hash_self "NOT NULL, UNIQUE"
    }
```

### 2.2 Full DDL

```sql
-- ── chargesheet_gap_reports ──────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_gap_reports_cs
    ON chargesheet_gap_reports (chargesheet_id, generated_at DESC);

-- ── chargesheet_gaps ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chargesheet_gaps (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id               UUID NOT NULL
                            REFERENCES chargesheet_gap_reports(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_gaps_report
    ON chargesheet_gaps (report_id, severity, display_order);

-- ── chargesheet_gap_actions (append-only) ────────────────────────────────
CREATE TABLE IF NOT EXISTS chargesheet_gap_actions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gap_id              UUID NOT NULL
                        REFERENCES chargesheet_gaps(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_gap_actions_lookup
    ON chargesheet_gap_actions (gap_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gap_actions_hash_self
    ON chargesheet_gap_actions (hash_self);
```

### 2.3 Column Descriptions

#### `chargesheet_gap_reports`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `chargesheet_id` | Foreign key to `chargesheets.id`. Multiple report versions can exist per chargesheet. Cascading delete. |
| `generated_at` | UTC timestamp of report generation. |
| `generator_version` | Version string of the aggregator. Current: `gap-aggregator-v1`. Appends `+partial(...)` when sources are unavailable. |
| `gap_count` | Total number of gaps in this report. |
| `critical_count` | Number of gaps with severity `critical`. |
| `high_count` | Number of gaps with severity `high`. |
| `medium_count` | Number of gaps with severity `medium`. |
| `low_count` | Number of gaps with severity `low`. |
| `advisory_count` | Number of gaps with severity `advisory`. |
| `generation_duration_ms` | Wall-clock time to generate the report, in milliseconds. Used for performance monitoring. |

#### `chargesheet_gaps`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `report_id` | FK to owning report. Cascading delete. |
| `category` | Gap category. One of: `legal`, `evidence`, `witness`, `procedural`, `mindmap_divergence`, `completeness`. |
| `severity` | Gap severity. One of: `critical`, `high`, `medium`, `low`, `advisory`. Drives sort order and UI styling. |
| `source` | Origin of the gap. One of: `T54_legal_validator`, `T55_evidence_ml`, `mindmap_diff`, `completeness_rules`, `manual_review`. |
| `requires_disclaimer` | If `true`, the UI must render an AI advisory disclaimer alongside this gap. Set for ML-sourced and mindmap-diff gaps. |
| `title` | Human-readable gap title. Max 512 chars. |
| `description_md` | Markdown-formatted description with detailed explanation. |
| `location` | JSONB object with chargesheet document coordinates: `page_num`, `char_offset_start`, `char_offset_end`, `bbox` (array `[x1, y1, x2, y2]`). Nullable. |
| `legal_refs` | JSONB array of legal references. Each entry: `{"framework": "BNS|IPC|CrPC|BNSS|BSA", "section": "302", "deep_link": "..."}`. |
| `remediation` | JSONB object with remediation guidance: `summary`, `steps` (array), `suggested_language` (nullable), `sop_refs` (array), `estimated_effort` (minutes/hours/requires_investigation). |
| `related_mindmap_node_id` | UUID of the related mindmap node, if this gap originated from a mindmap divergence. Nullable. |
| `confidence` | Numeric confidence score (0.000 to 1.000). For completeness rules, always 1.0. For ML sources, reflects model confidence. |
| `tags` | PostgreSQL text array for flexible categorization (e.g., rule IDs, tier labels). |
| `display_order` | Integer controlling render order. Assigned sequentially after severity+confidence sorting. |

#### `chargesheet_gap_actions`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `gap_id` | FK to the gap this action belongs to. Cascading delete. |
| `user_id` | Username (from JWT `sub` claim) of the officer who took this action. |
| `action` | Action type. One of: `accepted`, `modified`, `dismissed`, `deferred`, `escalated`. |
| `note` | Optional free-text note explaining the action. |
| `modification_diff` | For `modified` actions: the text change or suggested language that was applied. |
| `evidence_ref` | Optional reference to evidence (file ID, exhibit number). |
| `created_at` | UTC timestamp of this action entry. |
| `hash_prev` | SHA-256 hash of the preceding entry in this gap's chain, or `"GENESIS"` for the first entry. |
| `hash_self` | SHA-256 hash of this entry. Globally unique (enforced by unique index). |

### 2.4 Indices and Rationale

| Index | Columns | Rationale |
|---|---|---|
| `idx_gap_reports_cs` | `chargesheet_gap_reports(chargesheet_id, generated_at DESC)` | Fast lookup of the latest report for a chargesheet. Composite with DESC enables `LIMIT 1` without sort. |
| `idx_gaps_report` | `chargesheet_gaps(report_id, severity, display_order)` | Fetching all gaps for a report, pre-sorted by severity and display order. Typically 5-50 gaps per report. |
| `idx_gap_actions_lookup` | `chargesheet_gap_actions(gap_id, created_at DESC)` | Fetching the latest action for a gap. DESC order enables `LIMIT 1` for current action lookup. |
| `idx_gap_actions_hash_self` | `chargesheet_gap_actions(hash_self)` UNIQUE | Guarantees hash uniqueness across all action entries. Prevents duplicate insertions. |

### 2.5 Append-Only Trigger

The `chargesheet_gap_actions` table is append-only. A PostgreSQL trigger function rejects any `UPDATE` or `DELETE` operations at the database level.

```sql
CREATE OR REPLACE FUNCTION reject_gap_action_mutation() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION
    'chargesheet_gap_actions is append-only: % operations are prohibited',
    TG_OP;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_gap_actions_no_update
  BEFORE UPDATE ON chargesheet_gap_actions
  FOR EACH ROW EXECUTE FUNCTION reject_gap_action_mutation();

CREATE TRIGGER trg_gap_actions_no_delete
  BEFORE DELETE ON chargesheet_gap_actions
  FOR EACH ROW EXECUTE FUNCTION reject_gap_action_mutation();
```

This trigger fires `BEFORE` the mutation, so the operation is rejected before any row modification occurs. The only way to bypass this is to `DROP TRIGGER` (which requires superuser privileges and would appear in PostgreSQL audit logs).

### 2.6 Hash-Chain Algorithm Specification

Each gap's action history forms an independent hash chain. The chain provides tamper-evident auditability.

**Hash computation:**

```
Input string = f"{gap_id}|{user_id}|{action}|{note}|{timestamp}|{previous_hash}"
Hash         = SHA-256( input_string.encode("utf-8") )
Output       = lowercase hex digest (64 characters)
```

**Genesis rule:** The first action entry for any gap uses `"GENESIS"` as the `previous_hash` value.

**Chain verification algorithm:**

```python
def verify_action_chain(entries: List[ActionEntry]) -> (bool, Optional[int]):
    """Walk chain from oldest to newest, recomputing each hash.
    Returns (is_valid, first_break_index_or_None).
    """
    expected_prev = "GENESIS"

    for i, entry in enumerate(entries):
        if entry.hash_prev != expected_prev:
            return False, i

        recomputed = sha256(
            f"{entry.gap_id}|{entry.user_id}|{entry.action}|"
            f"{entry.note}|{entry.created_at.isoformat()}|"
            f"{entry.hash_prev}"
        )

        if recomputed != entry.hash_self:
            return False, i

        expected_prev = entry.hash_self

    return True, None
```

**Conflict detection:** When acting on a gap via the API, the client must supply `hash_prev` -- the hash of the most recent action entry the client is aware of (or `"GENESIS"` for the first action). The server compares this against the actual latest `hash_self` in the database. If they differ, another user has acted on this gap since the client last read it, and a `409 Conflict` is returned. This provides optimistic concurrency control.

---

## 3. Gap Source Specifications

### 3.1 T54 Legal Validator Output Schema

T54 writes to the `validation_reports` table. The aggregator reads the most recent report for the chargesheet.

**Source table:** `validation_reports`

**Query:** `SELECT * FROM validation_reports WHERE chargesheet_id = %s ORDER BY created_at DESC LIMIT 1`

**Expected `report_data` (JSONB) structure:**

```json
{
  "findings": [
    {
      "rule_id": "LEGAL_001",
      "severity": "CRITICAL",
      "section": "302",
      "description": "IPC 302 charged but no post-mortem report referenced",
      "recommendation": "Include post-mortem report reference in evidence schedule",
      "confidence": 0.95
    }
  ]
}
```

**Severity mapping:**

| T54 severity | Gap severity |
|---|---|
| `CRITICAL` | `critical` |
| `ERROR` | `high` |
| `WARNING` | `medium` |

**Converted gap fields:**

- `category`: `"legal"`
- `source`: `"T54_legal_validator"`
- `requires_disclaimer`: `false` (rule-based, deterministic)
- `confidence`: from T54 finding, default `0.9`

### 3.2 T55 Evidence Gap ML Output Schema

T55 writes to the `evidence_gap_reports` table. The aggregator reads the most recent report for the chargesheet.

**Source table:** `evidence_gap_reports`

**Query:** `SELECT * FROM evidence_gap_reports WHERE chargesheet_id = %s ORDER BY created_at DESC LIMIT 1`

**Expected `gaps_json` (JSONB) structure:**

```json
[
  {
    "category": "Documentary Evidence",
    "severity": "critical",
    "recommendation": "CCTV footage from adjacent premises not collected",
    "legal_basis": "Section 65B, Indian Evidence Act",
    "confidence": 0.82,
    "tier": "primary"
  }
]
```

**Severity mapping:**

| T55 severity | Gap severity |
|---|---|
| `critical` | `critical` |
| `important` | `high` |
| `suggested` | `medium` |

**Converted gap fields:**

- `category`: `"evidence"`
- `source`: `"T55_evidence_ml"`
- `requires_disclaimer`: `true` (ML-generated)
- `confidence`: from T55 gap entry, default `0.7`

### 3.3 Mindmap Diff Algorithm

The mindmap diff identifies mindmap nodes marked as "addressed" by the IO during investigation that have no corresponding artifact in the chargesheet.

**Algorithm:**

1. Fetch the latest active mindmap for the linked FIR (`chargesheet.fir_id` -> `chargesheet_mindmaps.fir_id`).
2. Fetch all nodes and their current status (latest `mindmap_node_status` entry per node).
3. For each node where `current_status == "addressed"`:
   a. Check whether the node's content is reflected in the chargesheet based on `node_type`:
      - `panchnama`: keyword search in `raw_text` for "panchnama", "panchnam", or first 20 chars of title.
      - `evidence`: fuzzy match against `evidence_json` descriptions using first 3 significant words of title.
      - `witness_bayan`: presence check against `witnesses_json` (any witness present = matched).
      - `forensic`: keyword search for "forensic", "fsl", "dna", "ballistic" in `raw_text`.
      - `legal_section`: exact match of `bns_section` or `ipc_section` against `charges_json[].section`.
      - Other types: first 15 chars of title in `raw_text`.
   b. If not matched, create a `mindmap_divergence` gap with `confidence = max(0.1, 1.0 - match_confidence)`.

**Converted gap fields:**

- `category`: `"mindmap_divergence"`
- `source`: `"mindmap_diff"`
- `requires_disclaimer`: `true` (heuristic matching, not deterministic)
- `related_mindmap_node_id`: UUID of the divergent mindmap node

### 3.4 Completeness Rules JSON Schema

Static rules are stored in `backend/app/chargesheet/completeness_rules/`. The aggregator loads `generic.json` (always) plus `{case_category}.json` (if available).

**Rule JSON schema:**

```json
{
  "case_category": "string (e.g., 'generic', 'murder')",
  "version": "string (semver)",
  "rules": [
    {
      "id": "string (unique rule ID, e.g., 'COMP_001')",
      "title": "string (human-readable title)",
      "description": "string (detailed explanation)",
      "severity": "enum: critical | high | medium | low | advisory",
      "category": "enum: legal | evidence | witness | procedural | completeness",
      "check_type": "enum: field_present | text_contains",
      "check_config": {
        "field": "string (chargesheet column name, for field_present)",
        "allow_null": "boolean (default true, for field_present)",
        "min_entries": "integer (minimum array length, for field_present)",
        "keywords": "array of strings (for text_contains)",
        "min_matches": "integer (minimum keyword matches, for text_contains)"
      },
      "remediation": {
        "summary": "string",
        "steps": ["string"],
        "estimated_effort": "enum: minutes | hours | requires_investigation"
      }
    }
  ]
}
```

**Available check types:**

| Check type | Behavior |
|---|---|
| `field_present` | Checks whether a chargesheet column exists, is non-null (if `allow_null: false`), and/or meets a minimum entry count (for JSON arrays). |
| `text_contains` | Searches `raw_text` for specified keywords; fails if fewer than `min_matches` keywords are found. |

**Converted gap fields:**

- `source`: `"completeness_rules"`
- `requires_disclaimer`: `false` (deterministic, rule-based)
- `confidence`: `1.0` (static rules are binary pass/fail)

### 3.5 Deduplication Algorithm

After all sources are collected, the aggregator deduplicates using a `(category, key1, key2)` tuple:

- **Legal findings:** `("legal", section, rule_id)`
- **Evidence gaps:** `("evidence", evidence_category, "")`
- **Mindmap divergences:** `("mindmap_divergence", node_id, "")`
- **Completeness rules:** `(rule_category, rule_id, "")`

When two gaps share a dedup key:
1. The higher severity is retained.
2. Tags are merged (union).
3. A `combined_sources` array is added listing both contributing sources.

---

## 4. API Reference

All endpoints are mounted under the prefix `/api/v1`. Authentication is via JWT Bearer token in the `Authorization` header. District-scoped roles (IO, SHO) can only access chargesheets within their assigned district.

### 4.1 POST /api/v1/chargesheet/{chargesheet_id}/gaps/analyze

**Generate gap analysis report (idempotent).**

If a report already exists for this chargesheet, returns the existing one. Otherwise, aggregates all sources and generates a new report.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/analyze` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Path Parameters:**

| Name | Type | Description |
|---|---|---|
| `chargesheet_id` | UUID | Chargesheet identifier |

**Request Body:** None

**Response Body:** `GapReportResponse`

```json
{
  "id": "uuid",
  "chargesheet_id": "uuid",
  "generated_at": "2026-04-18T10:30:00",
  "generator_version": "gap-aggregator-v1",
  "gap_count": 12,
  "critical_count": 3,
  "high_count": 4,
  "medium_count": 3,
  "low_count": 1,
  "advisory_count": 1,
  "generation_duration_ms": 450,
  "gaps": [
    {
      "id": "uuid",
      "report_id": "uuid",
      "category": "legal",
      "severity": "critical",
      "source": "T54_legal_validator",
      "requires_disclaimer": false,
      "title": "IPC 302 charged but no post-mortem report referenced",
      "description_md": "Section 302 IPC requires...",
      "location": {"page_num": 3, "char_offset_start": 1200, "char_offset_end": 1350},
      "legal_refs": [{"framework": "IPC", "section": "302"}],
      "remediation": {
        "summary": "Include post-mortem report in evidence schedule",
        "steps": ["Obtain PMR from civil surgeon", "Add to evidence list"],
        "suggested_language": null,
        "estimated_effort": "minutes"
      },
      "related_mindmap_node_id": null,
      "confidence": 0.95,
      "tags": ["LEGAL_001"],
      "display_order": 0,
      "current_action": null
    }
  ],
  "disclaimer": "Advisory -- AI-assisted review. Investigating Officer retains full legal responsibility. Not a substitute for legal judgment or supervisor review.",
  "partial_sources": []
}
```

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Invalid chargesheet_id or chargesheet data error |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/analyze" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json"
```

---

### 4.2 GET /api/v1/chargesheet/{chargesheet_id}/gaps/report

**Get the latest gap analysis report.**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/report` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `GapReportResponse` (same schema as POST analyze)

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | Chargesheet not found, or no report generated yet |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/report" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.3 GET /api/v1/chargesheet/{chargesheet_id}/gaps/reports

**List all gap report versions for a chargesheet.**

Returns summary information for every report version.

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/reports` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `List[GapReportSummary]`

```json
[
  {
    "id": "uuid",
    "chargesheet_id": "uuid",
    "generated_at": "2026-04-18T10:30:00",
    "generator_version": "gap-aggregator-v1",
    "gap_count": 12,
    "critical_count": 3,
    "high_count": 4
  }
]
```

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/reports" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.4 GET /api/v1/chargesheet/{chargesheet_id}/gaps/reports/{report_id}

**Get a specific historical report version.**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/reports/{report_id}` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `GapReportResponse`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | Chargesheet or report not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/reports/660e8400-e29b-41d4-a716-446655440001" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.5 POST /api/v1/chargesheet/{chargesheet_id}/gaps/reanalyze

**Force reanalysis (creates a new report version).**

Generates a fresh report by re-reading all upstream sources. Previous reports are retained for audit purposes.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/reanalyze` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Request Body:** `ReanalyzeRequest`

```json
{
  "justification": "New witness statements recorded after initial analysis"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `justification` | string | Yes | Reason for reanalysis. 5-2000 characters. Logged for audit. |

**Response Body:** `GapReportResponse`

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Invalid request body |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/reanalyze" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"justification": "New witness statements recorded after initial analysis"}'
```

---

### 4.6 PATCH /api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/action

**Act on a gap (append-only).**

Appends a new action entry to the gap's hash chain. The client must supply `hash_prev`.

| Property | Value |
|---|---|
| Method | `PATCH` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/action` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `200 OK` |

**Request Body:** `GapActionRequest`

```json
{
  "action": "accepted",
  "note": "Agreed -- will add post-mortem report to evidence schedule",
  "modification_diff": null,
  "evidence_ref": "exhibit-pmr-001",
  "hash_prev": "GENESIS"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `action` | enum | Yes | One of: `accepted`, `modified`, `dismissed`, `deferred`, `escalated` |
| `note` | string | No | Free-text note explaining the action |
| `modification_diff` | string | No | For `modified` actions: the text change applied |
| `evidence_ref` | string | No | Reference to evidence (file ID, exhibit number) |
| `hash_prev` | string | Yes | Hash of the most recent action entry. Use `"GENESIS"` for the first action. |

**Response Body:** `GapActionResponse`

```json
{
  "id": "uuid",
  "gap_id": "uuid",
  "user_id": "inspector_sharma",
  "action": "accepted",
  "note": "Agreed -- will add post-mortem report to evidence schedule",
  "modification_diff": null,
  "evidence_ref": "exhibit-pmr-001",
  "created_at": "2026-04-18T10:45:00",
  "hash_prev": "GENESIS",
  "hash_self": "a1b2c3d4e5f6..."
}
```

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Gap not found, or invalid request body |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | Chargesheet not found |
| 409 | Hash chain conflict -- `hash_prev` does not match the latest `hash_self` in the database |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X PATCH "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/770e8400-e29b-41d4-a716-446655440002/action" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "accepted",
    "note": "Post-mortem report added to evidence schedule",
    "evidence_ref": "exhibit-pmr-001",
    "hash_prev": "GENESIS"
  }'
```

---

### 4.7 GET /api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/history

**Get the full action chain for a gap.**

Returns all action entries in chronological order (oldest first).

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/history` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `List[GapActionResponse]`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/770e8400-e29b-41d4-a716-446655440002/history" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.8 POST /api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/apply-suggestion

**Apply AI-suggested language to the chargesheet.**

Reads `remediation.suggested_language` from the gap and records a `modified` action with the suggested text as the `modification_diff`.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/{gap_id}/apply-suggestion` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Request Body:** `ApplySuggestionRequest`

```json
{
  "confirm": true
}
```

**Response Body:** `GapActionResponse`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | Chargesheet or gap not found |
| 409 | Hash chain conflict (concurrent action) |
| 422 | No `suggested_language` available for this gap |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/770e8400-e29b-41d4-a716-446655440002/apply-suggestion" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

---

### 4.9 GET /api/v1/chargesheet/{chargesheet_id}/gaps/export/clean-pdf

**Export clean, court-ready PDF.**

Renders the chargesheet content as a formal PDF with zero AI annotations, zero gap analysis, zero disclaimers. This is the document intended for court filing.

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/export/clean-pdf` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `200 OK` |

**Response:**
- Content-Type: `application/pdf` (or `text/html` if WeasyPrint unavailable)
- Content-Disposition: `attachment; filename="chargesheet_{cs_id}.pdf"`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation or READONLY role |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/export/clean-pdf" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -o chargesheet_clean.pdf
```

---

### 4.10 GET /api/v1/chargesheet/{chargesheet_id}/gaps/export/review-report

**Export AI review report PDF (internal use).**

Contains the full gap analysis with severity indicators, remediation steps, and action status. Watermarked "INTERNAL REVIEW -- NOT FOR COURT SUBMISSION".

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/export/review-report` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `200 OK` |

**Response:**
- Content-Type: `application/pdf` (or `text/html` if WeasyPrint unavailable)
- Content-Disposition: `attachment; filename="review_{cs_id}.pdf"`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation or READONLY role |
| 404 | Chargesheet not found, or no gap report |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/export/review-report" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -o review_report.pdf
```

---

### 4.11 GET /api/v1/chargesheet/{chargesheet_id}/gaps/export/redline

**Export redline diff PDF (supervisor review).**

Shows the chargesheet text with inline markup indicating where gaps apply. Watermarked "REDLINE -- SUPERVISOR REVIEW".

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/chargesheet/{chargesheet_id}/gaps/export/redline` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `200 OK` |

**Response:**
- Content-Type: `application/pdf` (or `text/html` if WeasyPrint unavailable)
- Content-Disposition: `attachment; filename="redline_{cs_id}.pdf"`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation or READONLY role |
| 404 | Chargesheet not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/chargesheet/550e8400-e29b-41d4-a716-446655440000/gaps/export/redline" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -o redline.pdf
```

---

## 5. Action Semantics

Each action type has a specific legal and procedural meaning. These semantics must be communicated to IOs via training materials and UI labels.

### 5.1 Action Type Definitions

| Action | Legal meaning | When to use | Recorded data |
|---|---|---|---|
| **accepted** | IO agrees with the identified gap and will address it. | The gap is valid and the IO plans to fix the chargesheet accordingly. | `note` (optional explanation) |
| **modified** | IO has corrected the chargesheet to address this gap. | After making the actual change to the chargesheet content. | `modification_diff` (the change made), `evidence_ref` (supporting evidence) |
| **dismissed** | IO disagrees with the gap and provides reasoning. | The gap is a false positive, not applicable to this case, or based on incorrect analysis. | `note` (required -- must explain why the gap is not valid) |
| **deferred** | IO acknowledges the gap but postpones action. | The gap requires further investigation, awaiting lab results, witness availability, or supervisor guidance. | `note` (reason for deferral, expected resolution timeline) |
| **escalated** | IO sends the gap to their supervisor for guidance. | The gap involves a legal question beyond the IO's authority, a policy decision, or requires senior officer input. | `note` (question or context for the supervisor) |

### 5.2 Action Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> open : Gap created (no action yet)

    open --> accepted : IO agrees with gap
    open --> modified : IO fixes chargesheet
    open --> dismissed : IO explains why not applicable
    open --> deferred : IO postpones action
    open --> escalated : IO sends to supervisor

    accepted --> modified : IO completes the fix
    accepted --> dismissed : IO reconsiders after review
    accepted --> deferred : Awaiting resources
    accepted --> escalated : Needs supervisor input

    modified --> accepted : Supervisor confirms fix
    modified --> dismissed : Fix deemed unnecessary after review
    modified --> escalated : Supervisor wants further changes

    dismissed --> accepted : Supervisor overrides dismissal
    dismissed --> escalated : Dismissal questioned by supervisor

    deferred --> accepted : IO resumes and agrees
    deferred --> modified : IO completes deferred fix
    deferred --> dismissed : Deferred gap deemed irrelevant
    deferred --> escalated : Deadline approaching, needs guidance

    escalated --> accepted : Supervisor resolves, IO agrees
    escalated --> modified : Supervisor provides fix direction
    escalated --> dismissed : Supervisor confirms not applicable
    escalated --> deferred : Supervisor defers with guidance
```

> **Note:** The state machine is not enforced at the database level. All transitions between action types are permitted. The diagram describes the *expected* workflow. The append-only chain records every transition with full provenance, so any unusual transition sequence is visible in the audit trail.

### 5.3 Supervisor Visibility

When a gap is escalated:
- A structlog event `chargesheet.gap_action_taken` is emitted with `action=escalated`.
- The supervisor (SHO, DYSP, SP) can view all escalated gaps via the report endpoint.
- Phase 2 will add a dedicated supervisor notification and escalation queue.

---

## 6. Export Specifications

### 6.1 Clean PDF (Court Submission)

| Property | Value |
|---|---|
| **Purpose** | Court filing under Section 173 CrPC / 193 BNSS |
| **Audience** | Magistrate, court clerk, defence counsel |
| **AI content** | Absolutely none. Zero gap analysis, zero disclaimers, zero AI annotations. |
| **Watermark** | None |
| **Format** | Formal chargesheet layout: case details, charges table, accused particulars, evidence schedule |
| **Auth restriction** | READONLY role excluded (cannot generate court documents) |
| **Logging** | Every export logs `chargesheet.exported` with `export_type=clean-pdf` and `user` |

**Content sections:**
1. Header: "CHARGESHEET -- Under Section 173 CrPC / 193 BNSS"
2. Case details table: court name, FIR reference, filing date, IO name, district, police station
3. Charges table: section, act, description
4. Accused persons table: name, age, address, role
5. Footer: filing officer identification

### 6.2 Review Report (Internal)

| Property | Value |
|---|---|
| **Purpose** | IO and SHO internal reference during chargesheet preparation |
| **Audience** | IO, SHO, internal reviewers |
| **AI content** | Full gap analysis with severity, source, remediation, action status |
| **Watermark** | "INTERNAL REVIEW -- NOT FOR COURT SUBMISSION" (rotated, semi-transparent, across every page) |
| **Format** | Chargesheet summary + gap-by-gap breakdown with colour-coded severity borders |
| **Disclaimer** | Top banner + bottom banner: "Advisory -- AI-assisted review. Investigating Officer retains full legal responsibility." |

**Content sections:**
1. Chargesheet identification (ID, generation timestamp, version)
2. Summary statistics (total gaps, critical/high/medium/low/advisory counts)
3. Gap-by-gap detail: severity badge, category, title, description, remediation summary, current action status
4. Disclaimer footer

### 6.3 Redline PDF (Supervisor)

| Property | Value |
|---|---|
| **Purpose** | Supervisor review of chargesheet quality |
| **Audience** | DYSP, SP, supervisory officers |
| **AI content** | Chargesheet raw text with inline markup (ins/del styling) indicating where gaps apply |
| **Watermark** | "REDLINE -- SUPERVISOR REVIEW" (rotated, semi-transparent) |
| **Format** | Pre-wrapped chargesheet text with HTML `<ins>` (additions in green) and `<del>` (removals in red) styling |

**Current implementation note:** The redline renderer is a placeholder in Phase 1. It displays the chargesheet raw text with the watermark. Phase 2 will implement true inline diff markup linking gap locations to specific text positions.

---

## 7. Mindmap Integration

### 7.1 Diff Algorithm Details

The mindmap diff is not a generic text diff. It is a semantic comparison between what the IO planned (mindmap nodes marked "addressed") and what actually appears in the chargesheet.

**Query chain:**

1. `chargesheet.fir_id` -> `firs.id` (link chargesheet to its originating FIR)
2. `firs.id` -> `chargesheet_mindmaps.fir_id` WHERE `status = 'active'` (latest active mindmap)
3. `chargesheet_mindmaps.id` -> `mindmap_nodes` (all nodes)
4. For each node: subquery `mindmap_node_status` for latest status

**Match confidence by node type:**

| Node type | Match method | Typical confidence |
|---|---|---|
| `legal_section` | Exact section match against `charges_json` | 0.9 |
| `panchnama` | Keyword search in `raw_text` | 0.7 |
| `evidence` | Fuzzy word match against `evidence_json` | 0.6 |
| `witness_bayan` | Presence check in `witnesses_json` | 0.5 |
| `forensic` | Keyword search (forensic/fsl/dna/ballistic) | 0.6 |
| Other | First 15 chars of title in `raw_text` | 0.4 |

### 7.2 No-Mindmap Handling

If no mindmap exists for the linked FIR (the FIR has not had a mindmap generated, or the FIR link is missing):

1. `partial_sources` includes `"mindmap_diff"`.
2. Zero `mindmap_divergence` gaps are generated.
3. The report is still valid -- completeness rules and T54/T55 gaps are unaffected.
4. The UI should display a banner: "Mindmap analysis was not available for this report."

### 7.3 Multiple Mindmap Versions

The aggregator always reads the **latest active** mindmap (`status = 'active'`, `ORDER BY generated_at DESC LIMIT 1`). Superseded mindmap versions are not consulted.

If the IO regenerates the mindmap and then reanalyzes the chargesheet, the new report will diff against the new mindmap. Previous reports (which diffed against the old mindmap) are retained for audit comparison.

---

## 8. Failure Modes & Recovery

### 8.1 T54 Legal Validator Unavailable

**Symptom:** Gap report is generated with `partial_sources: ["T54_legal_validator"]`. No legal-category gaps from T54 appear.

**Cause:** The `validation_reports` table has no row for this `chargesheet_id`, or the query fails.

**Impact:** Legal validation gaps are absent. Completeness rules may catch some legal issues (e.g., missing charges), but rule-specific checks (e.g., section applicability) are missed.

**Recovery:** Run the T54 legal validator on the chargesheet, then reanalyze via `POST .../gaps/reanalyze`.

**Log:** `WARNING` level: `"Could not fetch T54 legal findings for chargesheet <id>"`

### 8.2 T55 Evidence Gap ML Unavailable

**Symptom:** Gap report is generated with `partial_sources: ["T55_evidence_ml"]`. No evidence-category gaps from T55 appear.

**Cause:** The `evidence_gap_reports` table has no row for this `chargesheet_id`, or the query fails.

**Impact:** ML-based evidence gap detection is absent. Completeness rules may catch basic evidence issues (missing evidence schedule), but nuanced gaps (e.g., "CCTV footage not collected") are missed.

**Recovery:** Run the T55 evidence gap classifier, then reanalyze.

**Log:** `WARNING` level: `"Could not fetch T55 evidence gaps for chargesheet <id>"`

### 8.3 Mindmap Unavailable

**Symptom:** Gap report is generated with `partial_sources: ["mindmap_diff"]`. No `mindmap_divergence` gaps appear.

**Cause:** No active mindmap exists for the linked FIR, the FIR link is missing, or the mindmap query fails.

**Impact:** Divergence analysis (planned vs. actual) is absent. This is the least critical source since it is a supplementary cross-check.

**Recovery:** Generate a mindmap for the FIR, then reanalyze the chargesheet.

**Log:** `WARNING` level: `"Could not fetch mindmap for FIR <id>"`

### 8.4 Partial Report Handling

When any source is unavailable, the report is still generated with available sources. The `generator_version` field reflects the partial state:

```
gap-aggregator-v1+partial(T54_legal_validator,mindmap_diff)
```

The UI should:
1. Display a warning banner listing unavailable sources.
2. Allow reanalysis after the missing sources become available.
3. Show the `partial_sources` array from the response.

### 8.5 Hash Chain Conflict (409)

**Symptom:** `PATCH .../gaps/{gap_id}/action` returns `409 Conflict` with message `"Hash chain conflict: expected <hash>, got <hash>"`.

**Cause:** Two officers attempted to act on the same gap concurrently. The first action succeeded; the second used a stale `hash_prev`.

**Impact:** The action is rejected. No data corruption occurs.

**Recovery:**
1. Client should `GET .../gaps/{gap_id}/history` to retrieve the latest action chain.
2. Read the latest `hash_self` from the most recent entry.
3. Retry the PATCH with the correct `hash_prev`.

### 8.6 Hash Chain Violation (Data Tampering)

**Symptom:** Chain verification (`verify_action_chain()`) returns `(False, break_index)`.

**Cause:** A record in `chargesheet_gap_actions` was modified outside the application (direct SQL, data migration error, or actual tampering).

**Impact:** The integrity of the action trail for that gap is compromised. The entire chain from the break point forward is unverifiable.

**Escalation:** Page on-call engineer immediately. Log event: `chargesheet.hash_chain_violation` at ERROR level with `severity=CRITICAL`.

### 8.7 WeasyPrint Unavailable

**Symptom:** Export endpoints return `text/html` instead of `application/pdf`.

**Cause:** WeasyPrint is not installed (common in development environments without system-level dependencies).

**Impact:** Users receive an HTML file instead of PDF. The content is identical.

**Recovery:** Install WeasyPrint and its system dependencies (`apt install libpango1.0-dev libcairo2-dev` on Debian/Ubuntu).

---

## 9. Observability

### 9.1 Structured Log Events

All log events use `structlog` with structured key-value fields.

| Event Name | Level | Trigger | Key Fields |
|---|---|---|---|
| `chargesheet.gap_report_generated` | INFO | New gap report created | `chargesheet_id`, `report_id`, `gap_count`, `user`, `sources` |
| `chargesheet.gap_report_regenerated` | INFO | Report reanalyzed | `chargesheet_id`, `report_id`, `justification`, `user` |
| `chargesheet.gap_action_taken` | INFO | Action on a gap | `gap_id`, `action`, `user` |
| `chargesheet.suggestion_applied` | INFO | AI suggestion applied | `gap_id`, `chargesheet_id`, `user` |
| `chargesheet.exported` | INFO | PDF/HTML export | `chargesheet_id`, `export_type`, `user` |
| `chargesheet.hash_chain_violation` | ERROR | Hash mismatch detected | `gap_id`, `severity=CRITICAL` |
| `gap.analyze_error` | ERROR | Analysis failure | `error` |
| `gap.get_report_error` | ERROR | Report fetch failure | `error` |

### 9.2 Prometheus Metrics

Defined in `backend/app/chargesheet/gap_metrics.py`. If `prometheus_client` is not installed, all metric operations are silently skipped.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `atlas_chargesheet_gap_reports_total` | Counter | `case_category` | Total gap reports generated |
| `atlas_chargesheet_gap_report_duration_seconds` | Histogram | (none) | Time to generate a gap report. Buckets: 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0s |
| `atlas_chargesheet_gaps_by_severity` | Counter | `severity`, `source` | Gaps created, bucketed by severity and source |
| `atlas_chargesheet_gap_actions_total` | Counter | `action`, `category` | Actions taken on gaps |
| `atlas_chargesheet_suggestions_applied_total` | Counter | (none) | AI suggestions applied to chargesheets |
| `atlas_chargesheet_exports_total` | Counter | `export_type` | Exports generated (clean-pdf, review-report, redline) |

### 9.3 PromQL Examples

**Report generation rate:**

```promql
rate(atlas_chargesheet_gap_reports_total[5m])
```

**95th percentile generation latency:**

```promql
histogram_quantile(0.95, rate(atlas_chargesheet_gap_report_duration_seconds_bucket[5m]))
```

**Gap distribution by severity and source:**

```promql
sum by (severity, source) (rate(atlas_chargesheet_gaps_by_severity[1h]))
```

**Action activity by type:**

```promql
sum by (action) (rate(atlas_chargesheet_gap_actions_total[1h]))
```

**Export volume by type:**

```promql
sum by (export_type) (rate(atlas_chargesheet_exports_total[1h]))
```

**Suggestion adoption rate (suggestions applied / total reports):**

```promql
rate(atlas_chargesheet_suggestions_applied_total[1h])
  / rate(atlas_chargesheet_gap_reports_total[1h])
```

### 9.4 Alert Rules

```yaml
groups:
  - name: atlas_chargesheet_gaps
    rules:
      - alert: ChargesheetGapReportSlow
        expr: histogram_quantile(0.95, rate(atlas_chargesheet_gap_report_duration_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
          team: atlas-backend
        annotations:
          summary: "Chargesheet gap report p95 latency exceeds 10 seconds"

      - alert: ChargesheetGapReportErrors
        expr: rate(atlas_chargesheet_gap_reports_total{case_category="error"}[5m]) > 0
        for: 2m
        labels:
          severity: critical
          team: atlas-backend
        annotations:
          summary: "Gap report generation errors detected"

      - alert: HighCriticalGapRate
        expr: >
          sum(rate(atlas_chargesheet_gaps_by_severity{severity="critical"}[1h]))
          / sum(rate(atlas_chargesheet_gap_reports_total[1h]))
          > 5
        for: 30m
        labels:
          severity: warning
          team: atlas-backend
        annotations:
          summary: "Average critical gaps per report exceeds 5 -- possible rule misconfiguration"
```

---

## 10. Security & Compliance

### 10.1 RBAC Matrix

| Endpoint | IO | SHO | DYSP | SP | ADMIN | READONLY |
|---|---|---|---|---|---|---|
| POST .../gaps/analyze | Yes | Yes | Yes | Yes | Yes | **No** |
| GET .../gaps/report | Yes | Yes | Yes | Yes | Yes | Yes |
| GET .../gaps/reports | Yes | Yes | Yes | Yes | Yes | Yes |
| GET .../gaps/reports/{id} | Yes | Yes | Yes | Yes | Yes | Yes |
| POST .../gaps/reanalyze | Yes | Yes | Yes | Yes | Yes | **No** |
| PATCH .../gaps/{id}/action | Yes | Yes | Yes | Yes | Yes | **No** |
| GET .../gaps/{id}/history | Yes | Yes | Yes | Yes | Yes | Yes |
| POST .../gaps/{id}/apply-suggestion | Yes | Yes | Yes | Yes | Yes | **No** |
| GET .../export/clean-pdf | Yes | Yes | Yes | Yes | Yes | **No** |
| GET .../export/review-report | Yes | Yes | Yes | Yes | Yes | **No** |
| GET .../export/redline | Yes | Yes | Yes | Yes | Yes | **No** |

**District scoping:** IO and SHO roles are district-scoped. They can only access chargesheets where `chargesheet.district == user.district`. Enforced by `_check_scope()` in `gap_routes.py`.

### 10.2 PII Redaction for Researchers

The READONLY role is intended for researchers and auditors. Gap reports may contain PII through:

- Gap titles referencing specific accused names or witness names.
- Remediation text mentioning complainant details.
- Evidence references containing personal information.

**Current state:** READONLY users see the same gap data as other roles (PII not redacted in Phase 1).

**Phase 2 plan:** Implement a response transformer in the route layer that strips PII from gap titles, descriptions, and remediation text for READONLY users. The database retains full-fidelity data.

### 10.3 Clean PDF Authentication Check

The Clean PDF export (`/export/clean-pdf`) has additional security considerations:

- **READONLY role excluded:** Researchers cannot generate court-ready documents. This prevents unauthorized creation of official-looking court filings.
- **Export logging:** Every Clean PDF export is logged with the user identity, creating an audit trail of who generated court documents.
- **No AI content:** The Clean PDF renderer explicitly excludes all AI-generated content. This is enforced architecturally by using a separate rendering function (`_render_clean_html`) that only reads chargesheet data fields, never gap report data.

### 10.4 DPDP Act Compliance

Under the Digital Personal Data Protection Act, 2023:

- **Data minimization:** Gap reports contain investigative guidance, not raw personal data. PII references are incidental.
- **Purpose limitation:** Gap analysis data is generated solely for chargesheet preparation assistance. Must not be repurposed for profiling or performance scoring.
- **Right to erasure:** Chargesheet deletion cascades to gap reports and actions via `ON DELETE CASCADE`. The append-only action trail is retained for the statutory period even if the chargesheet is archived.
- **Audit trail retention:** The hash-chained action trail in `chargesheet_gap_actions` is designed for evidentiary integrity and must be retained per statutory requirements, even if PII is redacted from other tables.

---

## 11. Performance Tuning

### 11.1 Caching Strategy

**Report-level caching:** The `aggregate_gaps()` function is idempotent by default. If a report already exists for a chargesheet, it returns the existing report without re-aggregating. This provides natural read caching -- the first call generates, subsequent calls are fast lookups.

**Template rule caching:** Completeness rules are loaded from disk on each aggregation call. For high-throughput environments, consider caching loaded rules in a module-level dictionary (similar to the mindmap template registry pattern). Current latency impact is negligible (< 1ms for file reads).

### 11.2 N+1 Query Avoidance

The aggregator is designed to avoid N+1 query patterns:

- **Source fetching:** Each of the 4 sources is fetched with a single query (or no query, for completeness rules). No per-gap queries during aggregation.
- **Gap persistence:** All gaps for a report are inserted in a single transaction with individual `INSERT` statements. For reports with > 50 gaps, consider using `execute_batch()` or `COPY` for bulk insertion.
- **Action lookup:** The current action for each gap is fetched via a correlated subquery in the gap SELECT (`SELECT a.action FROM chargesheet_gap_actions a WHERE a.gap_id = g.id ORDER BY a.created_at DESC LIMIT 1`). This is efficient due to the `idx_gap_actions_lookup` index.

### 11.3 PDF Rendering Performance

WeasyPrint PDF rendering is CPU-intensive. Expected rendering times:

| Report size | Rendering time |
|---|---|
| 5-10 gaps | 500ms - 1s |
| 10-30 gaps | 1s - 3s |
| 30-50 gaps | 3s - 5s |

**Mitigation strategies:**
- PDF generation is synchronous in Phase 1. For reports > 30 gaps, consider moving to async task queue (Celery) in Phase 2.
- HTML fallback is always available as a fast alternative when WeasyPrint is slow or unavailable.
- The Clean PDF renders only chargesheet data (no gaps), so it is consistently fast regardless of gap count.

### 11.4 Database Connection Management

The gap routes use `get_connection()` to obtain a psycopg2 connection. The connection pool is managed by the application's `db.session` module. Each request gets a connection from the pool and returns it when the request completes.

**Recommendation:** Ensure the connection pool size (`POOL_SIZE` env var) accounts for concurrent gap analysis requests. Each aggregation holds a connection for the duration of source fetching + persistence (typically 200-500ms).

---

## 12. Testing

### 12.1 Test Files

| File | Type | DB Required | Description |
|---|---|---|---|
| `test_gap_aggregator.py` | Unit | No | Tests source conversion, deduplication, severity sorting, hash computation |
| `test_gap_routes.py` | Integration | No (mocked) | Tests RBAC enforcement, endpoint responses, error handling. Uses FastAPI TestClient. |
| `test_gap_hash_chain.py` | Unit | No | Builds and verifies action hash chains. Tests tamper detection for all mutation types. |
| `test_gap_append_only.py` | DB Integration | Yes | Tests PostgreSQL trigger: INSERT allowed, UPDATE rejected, DELETE rejected. Requires `DATABASE_URL`. Marked `@pytest.mark.db`. |
| `test_gap_exports.py` | Unit | No | Tests HTML rendering for all 3 export types. Validates Clean PDF contains zero AI content. |

### 12.2 Fixtures

**Chargesheet fixtures:** Sample chargesheet records with known data for `charges_json`, `accused_json`, `witnesses_json`, `evidence_json`, `raw_text`.

**Source fixtures:**
- T54: Sample `validation_reports` with 3 legal findings (CRITICAL, ERROR, WARNING).
- T55: Sample `evidence_gap_reports` with 4 evidence gaps across severity tiers.
- Mindmap: Sample `chargesheet_mindmaps` with 10 nodes in various statuses.
- Completeness rules: The actual `generic.json` rules file (10 rules).

**Mock auth tokens:** `_mock_token(role, district)` creates mock JWT payloads for each role.

### 12.3 Running Tests

```bash
# Run all gap analysis tests (unit tests only, no DB required)
pytest backend/tests/chargesheet/ -v --cov=backend/app/chargesheet --cov-fail-under=80

# Run only unit tests (skip DB-dependent tests)
pytest backend/tests/chargesheet/ -v -m "not db"

# Run with DB integration tests (requires DATABASE_URL)
DATABASE_URL=postgresql://user:pass@localhost:5432/atlas_test \
  pytest backend/tests/chargesheet/ -v --cov=backend/app/chargesheet --cov-fail-under=80

# Run a specific test
pytest backend/tests/chargesheet/test_gap_hash_chain.py -v

# Run with verbose coverage report
pytest backend/tests/chargesheet/ -v \
  --cov=backend/app/chargesheet \
  --cov-report=term-missing \
  --cov-fail-under=80
```

**Coverage target:** Minimum 80% line coverage on `backend/app/chargesheet/`.

### 12.4 Load Test Approach

For stress-testing the aggregation pipeline:

```bash
# Generate 100 concurrent gap analysis requests
for i in $(seq 1 100); do
  curl -s -X POST "https://atlas-staging.example.com/api/v1/chargesheet/${CS_IDS[$i]}/gaps/analyze" \
    -H "Authorization: Bearer <TOKEN>" &
done
wait

# Monitor p95 latency during load
watch -n 2 'curl -s http://localhost:9090/api/v1/query \
  --data-urlencode "query=histogram_quantile(0.95, rate(atlas_chargesheet_gap_report_duration_seconds_bucket[1m]))"'
```

**Expected baseline:** p95 < 5s for reports with < 30 gaps. Alert threshold at 10s.

---

## 13. Deployment

### 13.1 Migration Ordering

The gap analysis migration is `010_add_chargesheet_gaps.py` with `down_revision = "009"`. It must run **after** the mindmap migration (009) because the `chargesheet_gaps.related_mindmap_node_id` column references mindmap node UUIDs (soft reference, not FK constraint, but logically dependent).

```bash
# Run migrations
cd backend
alembic upgrade head

# Verify the migration was applied
alembic current
# Expected output: 010 (head)

# Verify tables exist
psql $DATABASE_URL -c "\dt chargesheet_gap*"
# Should show: chargesheet_gap_reports, chargesheet_gaps, chargesheet_gap_actions
```

**Rollback:**

```bash
alembic downgrade 009
```

This drops all three gap analysis tables, their triggers, and the trigger function. All gap analysis data will be lost.

### 13.2 Feature Flag

The dual-pane gap analysis feature is controlled by the environment variable `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED`.

| Variable | Type | Default | Description |
|---|---|---|---|
| `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED` | boolean | `false` | Set to `true` to enable the chargesheet gap analysis UI and API endpoints. |

### 13.3 Production Rollout Process

1. **Run the migration** (`alembic upgrade head`). This creates the tables but does not activate the feature.
2. **Deploy with `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED=false`**. The tables exist but the UI panel is hidden and API endpoints are not active.
3. **QA team tests endpoints** directly via curl/Postman against the staging environment.
4. **Verify upstream dependencies:**
   - T54 legal validator is producing `validation_reports` rows.
   - T55 evidence gap classifier is producing `evidence_gap_reports` rows.
   - T53-M mindmap is generating mindmaps for FIRs.
   - Completeness rules JSON files are present.
5. **Obtain Nodal Officer sign-off** on the gap analysis output quality and export formats.
6. **Set `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED=true`** and redeploy.

### 13.4 Rollback Procedure

If an issue is discovered after enabling the feature:

1. **Set `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED=false`.** This hides the UI and disables endpoints. No data is deleted.
2. **Existing gap reports and actions are retained** in the database.
3. **No migration rollback is needed** for a feature-flag rollback.
4. **Action history is preserved.** The append-only hash chain remains intact.
5. **Only roll back the migration** if you need to remove the tables entirely (`alembic downgrade 009`).

### 13.5 Environment Variables Summary

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string |
| `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED` | No | `false` | Feature flag for gap analysis module |
| `ATLAS_MINDMAP_ENABLED` | No | `true` | Required for mindmap diff source |
| `JWT_SECRET_KEY` | Yes | -- | Secret for JWT token validation |

### 13.6 Pre-deployment Checklist

- [ ] Migrations 001-009 are already applied.
- [ ] `alembic upgrade head` runs cleanly (applies migration 010).
- [ ] Completeness rules JSON files are present in `backend/app/chargesheet/completeness_rules/`.
- [ ] Server starts without validation errors.
- [ ] `pytest backend/tests/chargesheet/ -v` passes with 80%+ coverage.
- [ ] `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED=false` is set for initial production deployment.
- [ ] Prometheus scrape config includes the ATLAS backend target (if using metrics).
- [ ] Export endpoints tested with WeasyPrint (PDF output) and without (HTML fallback).
- [ ] Clean PDF export verified to contain zero AI content.
- [ ] Nodal Officer has reviewed sample gap reports for accuracy.

---

## 14. Phase 2 Hooks

The following features are planned for Phase 2 and have architectural hooks in the current codebase.

### 14.1 Conviction Indicator

**Concept:** A composite score estimating the likelihood that the chargesheet, as currently prepared, would lead to a successful prosecution. Based on:

- Percentage of critical gaps addressed.
- Evidence completeness relative to case category requirements.
- Legal section applicability validation status.

**Hook:** The `GapReportResponse` schema can be extended with a `readiness_score` field. The `ReadinessResponse` and `ReadinessCategory` models are already defined in `gap_schemas.py`.

### 14.2 Automated Remediation

**Concept:** For gaps with `remediation.suggested_language`, allow one-click application of the suggested text directly into the chargesheet document.

**Hook:** The `POST .../gaps/{gap_id}/apply-suggestion` endpoint is already implemented. Phase 2 extends it to actually modify the chargesheet `raw_text` and `charges_json`/`evidence_json` fields, rather than just recording a `modified` action.

### 14.3 Cross-Chargesheet Learning

**Concept:** Aggregate gap patterns across all chargesheets in a district to identify systemic issues (e.g., "IOs in District X consistently miss seizure memo references").

**Hook:** The `chargesheet_gaps` table's `category`, `severity`, and `source` columns, combined with the chargesheet's `district` field, support aggregation queries:

```sql
SELECT district, category, severity, COUNT(*)
FROM chargesheet_gaps g
JOIN chargesheet_gap_reports r ON g.report_id = r.id
JOIN chargesheets c ON r.chargesheet_id = c.id
GROUP BY district, category, severity
ORDER BY COUNT(*) DESC;
```

### 14.4 Supervisor Notification Queue

**Concept:** When a gap is escalated, the supervisor receives an in-app notification and the gap appears in a dedicated "Escalations" tab.

**Hook:** The `escalated` action type is already defined. Phase 2 adds a notification service that watches for `chargesheet.gap_action_taken` events with `action=escalated` and creates notification records.

### 14.5 Manual Gap Addition

**Concept:** Allow supervisors to add gaps manually via a `manual_review` source, creating gaps that do not originate from any automated analysis.

**Hook:** The `manual_review` source value is already included in the `source` CHECK constraint. Phase 2 adds a `POST .../gaps/manual` endpoint for supervisor-created gaps.

### 14.6 Inline Redline Diff

**Concept:** The redline export should show actual inline diffs: text that needs to be added (green underline), text that should be removed (red strikethrough), positioned at the exact locations identified by gap `location` data.

**Hook:** The `location` JSONB field on `chargesheet_gaps` stores page numbers and character offsets. Phase 2 implements a rendering algorithm that applies these locations to the chargesheet `raw_text` to produce true inline markup.
