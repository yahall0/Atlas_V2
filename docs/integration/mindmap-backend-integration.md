# Chargesheet Mindmap -- Backend Integration Guide

> **Module**: T53-M (Chargesheet Mindmap)
> **Last updated**: 2026-04-18
> **Status**: Phase 1 -- Production-ready
> **Audience**: Backend developers, DevOps, QA engineers

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Database Schema Reference](#2-database-schema-reference)
3. [Template Authoring Guide](#3-template-authoring-guide)
4. [API Reference](#4-api-reference)
5. [Integration with Existing Modules](#5-integration-with-existing-modules)
6. [Observability](#6-observability)
7. [Failure Modes & Recovery](#7-failure-modes--recovery)
8. [Testing](#8-testing)
9. [Security & Compliance](#9-security--compliance)
10. [Deployment Notes](#10-deployment-notes)

---

## 1. Architecture Overview

### 1.1 Project Layout

```
backend/
  app/
    mindmap/
      __init__.py          # Module marker
      schemas.py           # Pydantic v2 models (request/response + template validation)
      registry.py          # Template registry -- loads & validates JSON at startup
      generator.py         # Core generation logic, hash-chain, DB operations
      routes.py            # FastAPI router (9 endpoints)
      metrics.py           # Prometheus counters/histograms + structlog helpers
      templates/
        murder.json        # Case-category template (IPC 302/304 family)
        theft.json         # IPC 378-381, 411, 457
        rape.json          # IPC 376 family
        dowry.json         # IPC 498A, 304B
        ndps.json          # NDPS Act
        cyber_crime.json   # IT Act + IPC
        pocso.json         # POCSO Act
        accident.json      # IPC 304A, MV Act
        missing_persons.json
  alembic/
    versions/
      009_add_chargesheet_mindmap.py   # Migration (depends on 001-008)
  tests/
    mindmap/
      test_template_registry.py
      test_mindmap_generator.py
      test_mindmap_append_only.py      # DB integration -- trigger verification
      test_mindmap_hash_chain.py
      test_mindmap_rbac.py
      test_fir_to_mindmap_e2e.py
```

### 1.2 End-to-End Sequence

The mindmap is generated from the convergence of several upstream task outputs. When an officer requests a mindmap for a FIR, the system reads classification, completeness, and evidence-gap data that were produced by earlier pipeline stages.

```mermaid
sequenceDiagram
    participant Officer as IO / SHO
    participant API as Mindmap API
    participant T46 as T46 FIR Ingestion
    participant T47 as T47 Extraction
    participant T48 as T48 Completeness
    participant T28 as T28 NLP Classifier
    participant T55 as T55 Evidence Gap
    participant Gen as Mindmap Generator
    participant DB as PostgreSQL

    Officer->>API: POST /api/v1/fir/{fir_id}/mindmap
    API->>DB: SELECT * FROM firs WHERE id = fir_id
    Note over T46,T47: FIR already ingested & extracted<br/>by upstream pipeline

    API->>Gen: generate_mindmap(fir_id)
    Gen->>DB: Read fir record (T47 extraction output)
    Gen->>Gen: _get_case_category(fir)<br/>reads nlp_classification + nlp_confidence (T28)
    Gen->>Gen: _get_completeness_gaps(fir)<br/>reads completeness_pct (T48)
    Gen->>DB: SELECT FROM evidence_gap_reports (T55)
    Gen->>Gen: load_template(case_category)
    Gen->>DB: INSERT chargesheet_mindmaps
    Gen->>DB: INSERT mindmap_nodes (template + gaps + ML suggestions)
    Gen->>DB: UPDATE root_node_id
    Gen-->>API: MindmapResponse
    API-->>Officer: 201 Created + JSON tree
```

### 1.3 Data Flow Diagram

```mermaid
flowchart LR
    subgraph "Upstream Pipeline (pre-existing)"
        FIR_PDF["FIR PDF Upload"]
        T46["T46: Ingestion"]
        T47["T47: Extraction"]
        T48["T48: Completeness"]
        T28["T28: NLP Classifier"]
        T55["T55: Evidence Gap"]
    end

    subgraph "Mindmap Module (T53-M)"
        REG["Template Registry<br/>(registry.py)"]
        GEN["Generator<br/>(generator.py)"]
        ROUTES["Routes<br/>(routes.py)"]
        METRICS["Metrics<br/>(metrics.py)"]
    end

    subgraph "Data Stores"
        FIRS_TABLE["firs table<br/>(READ)"]
        EGR_TABLE["evidence_gap_reports<br/>(READ)"]
        MM_TABLE["chargesheet_mindmaps<br/>(READ/WRITE)"]
        NODE_TABLE["mindmap_nodes<br/>(READ/WRITE)"]
        STATUS_TABLE["mindmap_node_status<br/>(APPEND-ONLY)"]
        TEMPLATES["templates/*.json<br/>(READ at startup)"]
    end

    FIR_PDF --> T46 --> T47 --> FIRS_TABLE
    T47 --> T28 --> FIRS_TABLE
    T47 --> T48 --> FIRS_TABLE
    T55 --> EGR_TABLE

    TEMPLATES --> REG
    FIRS_TABLE --> GEN
    EGR_TABLE --> GEN
    REG --> GEN
    GEN --> MM_TABLE
    GEN --> NODE_TABLE
    GEN --> STATUS_TABLE
    ROUTES --> GEN
    ROUTES --> METRICS
```

### 1.4 Dependency Matrix

| Dependency | Type | Required | Fallback |
|---|---|---|---|
| PostgreSQL (psycopg2) | Runtime | Yes | None -- server will not start |
| T47 extraction (firs table) | Data | Yes | 404 if FIR not found |
| T28 NLP classifier (nlp_classification, nlp_confidence) | Data | No | Falls back to `generic` template, flags `uncertain` |
| T48 completeness (completeness_pct) | Data | No | No "FIR Gaps" branch in mindmap |
| T55 evidence gap (evidence_gap_reports) | Data | No | No "ML-Suggested Evidence Gaps" branch, logs warning |
| Template JSON files | Startup | Yes | Server startup aborts with RuntimeError |
| structlog | Runtime | Yes | Standard logging fallback |
| prometheus_client | Runtime | No | Metrics silently disabled |
| WeasyPrint | Runtime (PDF export) | No | Falls back to HTML export |

---

## 2. Database Schema Reference

### 2.1 Entity Relationship Diagram

```mermaid
erDiagram
    firs ||--o{ chargesheet_mindmaps : "1 FIR has 0..N mindmap versions"
    chargesheet_mindmaps ||--|{ mindmap_nodes : "1 mindmap has 1..N nodes"
    mindmap_nodes ||--o{ mindmap_node_status : "1 node has 0..N status entries"
    mindmap_nodes ||--o{ mindmap_nodes : "parent-child (self-ref)"

    chargesheet_mindmaps {
        UUID id PK "gen_random_uuid()"
        UUID fir_id FK "NOT NULL, references firs(id)"
        VARCHAR64 case_category "NOT NULL"
        VARCHAR32 template_version "NOT NULL"
        TIMESTAMP generated_at "NOT NULL, DEFAULT now()"
        VARCHAR128 generated_by_model_version "nullable"
        UUID root_node_id "nullable, set after nodes inserted"
        VARCHAR32 status "NOT NULL, DEFAULT 'active'"
    }

    mindmap_nodes {
        UUID id PK "gen_random_uuid()"
        UUID mindmap_id FK "NOT NULL, references chargesheet_mindmaps(id)"
        UUID parent_id FK "nullable, self-ref, ON DELETE SET NULL"
        VARCHAR32 node_type "NOT NULL, CHECK constraint"
        VARCHAR512 title "NOT NULL"
        TEXT description_md "nullable, Markdown"
        VARCHAR32 source "NOT NULL, CHECK constraint"
        VARCHAR32 bns_section "nullable"
        VARCHAR32 ipc_section "nullable"
        VARCHAR32 crpc_section "nullable"
        VARCHAR16 priority "NOT NULL, DEFAULT 'recommended'"
        BOOLEAN requires_disclaimer "NOT NULL, DEFAULT false"
        INTEGER display_order "NOT NULL, DEFAULT 0"
        JSONB metadata "DEFAULT '{}'::jsonb"
    }

    mindmap_node_status {
        UUID id PK "gen_random_uuid()"
        UUID node_id FK "NOT NULL, references mindmap_nodes(id)"
        TEXT user_id "NOT NULL"
        VARCHAR32 status "NOT NULL, CHECK constraint"
        TEXT note "nullable"
        TEXT evidence_ref "nullable"
        TIMESTAMP updated_at "NOT NULL, DEFAULT now()"
        VARCHAR64 hash_prev "NOT NULL"
        VARCHAR64 hash_self "NOT NULL, UNIQUE"
    }
```

### 2.2 Full DDL

```sql
-- ── chargesheet_mindmaps ──────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_mindmap_fir_id
    ON chargesheet_mindmaps (fir_id);

-- ── mindmap_nodes ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mindmap_nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mindmap_id      UUID NOT NULL
                    REFERENCES chargesheet_mindmaps(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_mindmap_nodes_mindmap_id
    ON mindmap_nodes (mindmap_id);

-- ── mindmap_node_status (append-only) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS mindmap_node_status (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id      UUID NOT NULL
                 REFERENCES mindmap_nodes(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_mindmap_node_status_lookup
    ON mindmap_node_status (node_id, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mindmap_node_status_hash_self
    ON mindmap_node_status (hash_self);
```

### 2.3 Column Descriptions

#### `chargesheet_mindmaps`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `fir_id` | Foreign key to `firs.id`. Multiple mindmap versions can exist per FIR. Cascading delete. |
| `case_category` | NLP-derived case category string (e.g., `murder`, `theft`, `cyber_crime`, `generic`). |
| `template_version` | Semver string of the template used at generation time. Enables audit of which template version produced a given mindmap. |
| `generated_at` | UTC timestamp of generation. |
| `generated_by_model_version` | Identifies the generation pipeline version. Current value: `template-v1+completeness`. Appends `+uncertain` when classifier confidence is below 0.7. |
| `root_node_id` | UUID of the root node in `mindmap_nodes`. Set after node insertion completes. |
| `status` | `active` or `superseded`. Only one `active` mindmap per FIR at a time. Regeneration marks the old one `superseded`. |

#### `mindmap_nodes`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `mindmap_id` | FK to owning mindmap. Cascading delete. |
| `parent_id` | Self-referential FK for tree structure. `NULL` for the root node. `ON DELETE SET NULL` so orphaned subtrees do not cascade-delete. |
| `node_type` | One of: `legal_section`, `immediate_action`, `evidence`, `interrogation`, `panchnama`, `forensic`, `witness_bayan`, `gap_from_fir`, `custom`. Enforced by CHECK constraint. |
| `title` | Human-readable node title. Max 512 chars. |
| `description_md` | Markdown-formatted description with investigative guidance. |
| `source` | Origin of the node: `static_template` (from JSON), `ml_suggestion` (from T55), `completeness_engine` (from T48 gap detection), `io_custom` (manually added by IO). |
| `bns_section` | Bharatiya Nyaya Sanhita section reference (e.g., `103(1)`). Nullable. |
| `ipc_section` | Indian Penal Code section reference (e.g., `302`). Nullable. |
| `crpc_section` | Code of Criminal Procedure section reference. Nullable. |
| `priority` | `critical`, `recommended`, or `optional`. Drives UI styling and sort weight. |
| `requires_disclaimer` | If `true`, the UI must render the advisory disclaimer alongside this node. Set for ML-suggested and completeness-gap nodes. |
| `display_order` | Integer controlling render order within a parent. Assigned sequentially at generation time. |
| `metadata` | JSONB bag for extensible data. For `io_custom` nodes, stores `{"created_by": "<user_id>"}`. |

#### `mindmap_node_status`

| Column | Description |
|---|---|
| `id` | Primary key, auto-generated UUIDv4. |
| `node_id` | FK to the node this status entry belongs to. Cascading delete. |
| `user_id` | Username (from JWT `sub` claim) of the officer who made this status change. |
| `status` | New status value. One of: `open`, `in_progress`, `addressed`, `not_applicable`, `disputed`. |
| `note` | Optional free-text note explaining the status change. |
| `evidence_ref` | Optional reference to evidence (file ID, exhibit number, etc.). |
| `updated_at` | UTC timestamp of this status entry. |
| `hash_prev` | SHA-256 hash of the preceding entry in this node's chain, or `"GENESIS"` for the first entry. |
| `hash_self` | SHA-256 hash of this entry. Globally unique (enforced by unique index). |

### 2.4 Indices and Rationale

| Index | Columns | Rationale |
|---|---|---|
| `idx_mindmap_fir_id` | `chargesheet_mindmaps(fir_id)` | Fast lookup of all mindmap versions for a given FIR. Used by every API endpoint. |
| `idx_mindmap_nodes_mindmap_id` | `mindmap_nodes(mindmap_id)` | Fetching all nodes for a mindmap. Typically 20-80 nodes per mindmap. |
| `idx_mindmap_node_status_lookup` | `mindmap_node_status(node_id, updated_at DESC)` | Composite index for fetching the latest status entry for a node. The `DESC` order enables `LIMIT 1` to return the most recent entry without a sort. |
| `idx_mindmap_node_status_hash_self` | `mindmap_node_status(hash_self)` UNIQUE | Guarantees hash uniqueness across all status entries. Prevents duplicate insertions and provides a fast lookup path for chain verification. |

### 2.5 Append-Only Trigger

The `mindmap_node_status` table is designed as an append-only audit log. A PostgreSQL trigger function rejects any `UPDATE` or `DELETE` operations at the database level, regardless of which application or user issues the statement.

```sql
CREATE OR REPLACE FUNCTION reject_mindmap_status_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION
    'mindmap_node_status is append-only: % operations are prohibited',
    TG_OP;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_mindmap_status_no_update
  BEFORE UPDATE ON mindmap_node_status
  FOR EACH ROW EXECUTE FUNCTION reject_mindmap_status_mutation();

CREATE TRIGGER trg_mindmap_status_no_delete
  BEFORE DELETE ON mindmap_node_status
  FOR EACH ROW EXECUTE FUNCTION reject_mindmap_status_mutation();
```

This trigger fires `BEFORE` the mutation, so the operation is rejected before any row modification occurs. The only way to bypass this is to `DROP TRIGGER` (which requires superuser privileges and would appear in PostgreSQL audit logs).

### 2.6 Hash-Chain Algorithm Specification

Each node's status history forms an independent hash chain. The chain provides tamper-evident auditability: if any entry is modified, inserted, or deleted, the chain verification will fail.

**Hash computation:**

```
Input string = f"{node_id}|{user_id}|{status}|{note}|{evidence_ref}|{timestamp}|{previous_hash}"
Hash         = SHA-256( input_string.encode("utf-8") )
Output       = lowercase hex digest (64 characters)
```

**Genesis rule:** The first status entry for any node uses `"GENESIS"` as the `previous_hash` value.

**Chain verification algorithm (pseudocode):**

```python
def verify_chain(entries: List[StatusEntry]) -> (bool, Optional[int]):
    """Walk chain from oldest to newest, recomputing each hash.
    Returns (is_valid, first_break_index_or_None).
    """
    expected_prev = "GENESIS"

    for i, entry in enumerate(entries):
        # Check backward link
        if entry.hash_prev != expected_prev:
            return False, i

        # Recompute hash from fields
        recomputed = sha256(
            f"{entry.node_id}|{entry.user_id}|{entry.status}|"
            f"{entry.note}|{entry.evidence_ref}|"
            f"{entry.timestamp}|{entry.hash_prev}"
        )

        if recomputed != entry.hash_self:
            return False, i

        expected_prev = entry.hash_self

    return True, None
```

**Conflict detection:** When updating a node's status via the API, the client must supply `hash_prev` -- the hash of the most recent status entry the client is aware of. The server compares this against the actual latest `hash_self` in the database. If they differ, another user has updated the node since the client last read it, and a `409 Conflict` is returned. This provides optimistic concurrency control.

### 2.7 Node Status State Machine

```mermaid
stateDiagram-v2
    [*] --> open : Node created (no status entry yet)

    open --> in_progress : IO begins work
    open --> addressed : IO marks complete
    open --> not_applicable : IO/SHO deems irrelevant
    open --> disputed : Officer disputes relevance

    in_progress --> addressed : IO completes task
    in_progress --> open : IO reverts to open
    in_progress --> not_applicable : Deemed irrelevant during work
    in_progress --> disputed : Officer disputes

    addressed --> disputed : Supervisor challenges
    addressed --> open : Reopened after review

    not_applicable --> open : Reconsidered
    not_applicable --> disputed : Officer disputes

    disputed --> open : Resolved, reset to open
    disputed --> addressed : Resolved, marked complete
    disputed --> not_applicable : Resolved, confirmed irrelevant
```

> **Note**: The state machine is not enforced at the database level. All transitions are allowed by the CHECK constraint. The diagram above describes the *expected* workflow. Any `NodeStatus` value can transition to any other `NodeStatus` value. The append-only chain records every transition with full provenance.

---

## 3. Template Authoring Guide

### 3.1 JSON Schema for Template Files

Each template file in `backend/app/mindmap/templates/` must conform to the `TemplateTree` Pydantic model. The effective JSON schema is:

```json
{
  "case_category": "string (unique identifier, e.g. 'murder')",
  "template_version": "string (semver, e.g. '1.0.0')",
  "description": "string (human-readable description of the template)",
  "branches": [
    {
      "node_type": "enum: legal_section | immediate_action | evidence | interrogation | panchnama | forensic | witness_bayan | gap_from_fir | custom",
      "title": "string (required, branch heading)",
      "description_md": "string (Markdown, optional, defaults to '')",
      "priority": "enum: critical | recommended | optional (default: recommended)",
      "requires_disclaimer": "boolean (default: false)",
      "children": [
        {
          "node_type": "enum (same as above)",
          "title": "string (required)",
          "description_md": "string (Markdown, optional)",
          "ipc_section": "string or null (e.g. '302')",
          "bns_section": "string or null (e.g. '103(1)')",
          "crpc_section": "string or null",
          "priority": "enum: critical | recommended | optional (default: recommended)",
          "requires_disclaimer": "boolean (default: false)"
        }
      ]
    }
  ]
}
```

**Constraints:**
- `case_category` must be unique across all template files. If two files share the same `case_category`, the second one loaded (alphabetical order) will overwrite the first.
- `template_version` should follow semantic versioning (`MAJOR.MINOR.PATCH`).
- At least one `branches` entry is recommended (the generic fallback has zero branches but is hardcoded, not loaded from a file).
- The `children` array is optional per branch; branches can be leaf nodes.

### 3.2 Annotated Template Example

```json
{
  // Unique category key -- matches T28 classifier output labels
  "case_category": "theft",

  // Semver -- bump MAJOR for structural changes, MINOR for new nodes,
  // PATCH for text corrections
  "template_version": "1.0.0",

  // Displayed in admin UI and PDF export header
  "description": "Chargesheet mindmap template for theft and property crime cases under IPC 378-381, 411, 457 and corresponding BNS provisions",

  "branches": [
    {
      // Branch-level node_type groups the children
      "node_type": "legal_section",
      "title": "Applicable Legal Sections",
      "description_md": "Legal sections applicable to theft...",
      "priority": "critical",
      "requires_disclaimer": false,

      "children": [
        {
          "node_type": "legal_section",
          "title": "IPC 379 / BNS 303(2) -- Theft",
          "description_md": "IPC 378 defines theft; IPC 379 prescribes punishment...",

          // Cross-reference both old (IPC) and new (BNS) section numbers
          "ipc_section": "379",
          "bns_section": "303(2)",

          // critical = must-have for chargesheet
          "priority": "critical",
          "requires_disclaimer": false
        }
        // ... more children
      ]
    }
    // ... more branches (immediate_action, evidence, etc.)
  ]
}
```

### 3.3 Template Change Process

Template changes affect the investigative guidance provided to police officers across Gujarat. The following process applies:

1. **Proposal**: Gujarat Police Nodal Officer submits a change request as a GitHub issue describing the proposed modification, the case category affected, and the legal basis.

2. **Branch**: Developer creates a feature branch: `template/<category>-v<version>` (e.g., `template/murder-v1.1.0`).

3. **Edit**: Modify the JSON file. Run `python -c "from app.mindmap.registry import reload_templates; reload_templates()"` locally to validate.

4. **Version bump rules**:
   - **PATCH** (1.0.0 -> 1.0.1): Text corrections, typo fixes, description improvements. No structural changes.
   - **MINOR** (1.0.0 -> 1.1.0): Adding new child nodes, adding new branches, changing priorities.
   - **MAJOR** (1.0.0 -> 2.0.0): Removing branches or nodes, restructuring the tree, changing `case_category` value.

5. **Pull request**: PR must include:
   - Updated `template_version` in the JSON file.
   - Passing `pytest backend/tests/mindmap/test_template_registry.py -v`.
   - Approval from at least one developer **and** the Nodal Officer (or their delegate).

6. **Review gates**: CI pipeline validates all templates via Pydantic at test time. A malformed template will fail the test suite and block merge.

7. **Deployment**: After merge, the next deployment will load the new template. Existing mindmaps are not affected -- they retain the template version recorded at generation time. New mindmaps (and regenerated ones) will use the updated template.

### 3.4 Startup Validation

Templates are validated by Pydantic (`TemplateTree.model_validate()`) at server startup via the `_load_all()` function in `registry.py`. If any template file:

- Is not valid JSON: startup fails with `RuntimeError`.
- Does not conform to the Pydantic schema: startup fails with `RuntimeError`.
- The templates directory does not exist or is empty: startup fails with `RuntimeError`.

This is a deliberate fail-fast design. A server with invalid templates must not serve requests because it could generate incorrect investigative guidance.

---

## 4. API Reference

All endpoints are mounted under the prefix `/api/v1`. Authentication is via JWT Bearer token in the `Authorization` header. District-scoped roles (IO, SHO) can only access FIRs within their assigned district.

### 4.1 POST /api/v1/fir/{fir_id}/mindmap

**Generate or fetch chargesheet mindmap (idempotent).**

If a mindmap already exists for this FIR with the current template version, returns the existing one. Otherwise, generates a new mindmap.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/fir/{fir_id}/mindmap` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Path Parameters:**

| Name | Type | Description |
|---|---|---|
| `fir_id` | UUID | FIR identifier |

**Request Body:** None

**Response Body:** `MindmapResponse`

```json
{
  "id": "uuid",
  "fir_id": "uuid",
  "case_category": "murder",
  "template_version": "1.0.0",
  "generated_at": "2026-04-18T10:30:00",
  "generated_by_model_version": "template-v1+completeness",
  "root_node_id": "uuid",
  "status": "active",
  "disclaimer": "Advisory -- AI-generated suggestions. Investigating Officer retains full discretion. Not a substitute for legal judgment.",
  "nodes": [
    {
      "id": "uuid",
      "mindmap_id": "uuid",
      "parent_id": null,
      "node_type": "evidence",
      "title": "Chargesheet Mindmap",
      "description_md": "Root node for chargesheet investigation guidance",
      "source": "static_template",
      "bns_section": null,
      "ipc_section": null,
      "crpc_section": null,
      "priority": "critical",
      "requires_disclaimer": false,
      "display_order": 0,
      "metadata": {},
      "current_status": null,
      "children": [ "...nested nodes..." ]
    }
  ]
}
```

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | FIR not found (ValueError) |
| 401 | Missing or invalid JWT |
| 403 | Role not in (IO, SHO, DYSP, SP, ADMIN), or district scope violation |
| 404 | FIR does not exist |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json"
```

---

### 4.2 GET /api/v1/fir/{fir_id}/mindmap

**Get the latest active mindmap for a FIR.**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/fir/{fir_id}/mindmap` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Path Parameters:**

| Name | Type | Description |
|---|---|---|
| `fir_id` | UUID | FIR identifier |

**Request Body:** None

**Response Body:** `MindmapResponse` (same schema as POST)

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | FIR not found, or no mindmap generated yet |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.3 GET /api/v1/fir/{fir_id}/mindmap/versions

**List all mindmap versions for a FIR.**

Returns summary information for every mindmap version (both active and superseded).

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/fir/{fir_id}/mindmap/versions` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `List[MindmapVersionSummary]`

```json
[
  {
    "id": "uuid",
    "case_category": "murder",
    "template_version": "1.0.0",
    "generated_at": "2026-04-18T10:30:00",
    "status": "active",
    "node_count": 42
  },
  {
    "id": "uuid-older",
    "case_category": "murder",
    "template_version": "1.0.0",
    "generated_at": "2026-04-15T08:00:00",
    "status": "superseded",
    "node_count": 38
  }
]
```

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | FIR not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/versions" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.4 GET /api/v1/fir/{fir_id}/mindmap/versions/{mindmap_id}

**Get a specific historical mindmap version.**

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/fir/{fir_id}/mindmap/versions/{mindmap_id}` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Path Parameters:**

| Name | Type | Description |
|---|---|---|
| `fir_id` | UUID | FIR identifier |
| `mindmap_id` | UUID | Specific mindmap version ID |

**Response Body:** `MindmapResponse`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | FIR not found, or mindmap_id does not exist or does not belong to this FIR |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/versions/660e8400-e29b-41d4-a716-446655440001" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.5 PATCH /api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/status

**Update node status (append-only).**

Appends a new status entry to the node's hash chain. The client must supply `hash_prev` (the `hash_self` of the most recent status entry the client knows about, or `"GENESIS"` if this is the first status update for the node).

| Property | Value |
|---|---|
| Method | `PATCH` |
| Path | `/api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/status` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `200 OK` |

**Path Parameters:**

| Name | Type | Description |
|---|---|---|
| `fir_id` | UUID | FIR identifier |
| `node_id` | UUID | Node identifier |

**Request Body:** `NodeStatusUpdate`

```json
{
  "status": "in_progress",
  "note": "Started collecting CCTV footage from nearby shops",
  "evidence_ref": "exhibit-cctv-001",
  "hash_prev": "GENESIS"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | enum | Yes | One of: `open`, `in_progress`, `addressed`, `not_applicable`, `disputed` |
| `note` | string | No | Free-text note explaining the status change |
| `evidence_ref` | string | No | Reference to evidence (file ID, exhibit number) |
| `hash_prev` | string | Yes | Hash of the most recent status entry the client knows about. Use `"GENESIS"` for the first status update on a node. |

**Response Body:** `NodeStatusResponse`

```json
{
  "id": "uuid",
  "node_id": "uuid",
  "user_id": "inspector_sharma",
  "status": "in_progress",
  "note": "Started collecting CCTV footage from nearby shops",
  "evidence_ref": "exhibit-cctv-001",
  "updated_at": "2026-04-18T10:45:00",
  "hash_prev": "GENESIS",
  "hash_self": "a1b2c3d4e5f6..."
}
```

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Node not found, or invalid request body |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | FIR not found |
| 409 | Hash chain conflict -- `hash_prev` does not match the latest `hash_self` in the database. Another user has updated this node since the client last read it. |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X PATCH "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/nodes/770e8400-e29b-41d4-a716-446655440002/status" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "addressed",
    "note": "CCTV footage collected and preserved",
    "evidence_ref": "exhibit-cctv-001",
    "hash_prev": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
  }'
```

---

### 4.6 GET /api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/history

**Get the full status chain for a node.**

Returns all status entries in chronological order (oldest first), enabling the client to display a complete audit trail and verify chain integrity.

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/history` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response Body:** `List[NodeStatusResponse]`

```json
[
  {
    "id": "uuid-1",
    "node_id": "uuid-node",
    "user_id": "inspector_sharma",
    "status": "open",
    "note": null,
    "evidence_ref": null,
    "updated_at": "2026-04-18T10:30:00",
    "hash_prev": "GENESIS",
    "hash_self": "abc123..."
  },
  {
    "id": "uuid-2",
    "node_id": "uuid-node",
    "user_id": "inspector_sharma",
    "status": "in_progress",
    "note": "Started CCTV collection",
    "evidence_ref": null,
    "updated_at": "2026-04-18T14:00:00",
    "hash_prev": "abc123...",
    "hash_self": "def456..."
  }
]
```

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | FIR not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/nodes/770e8400-e29b-41d4-a716-446655440002/history" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

---

### 4.7 POST /api/v1/fir/{fir_id}/mindmap/nodes

**Add a custom node to the active mindmap.**

Allows an Investigating Officer to add investigation-specific nodes beyond the template. The node is attached to the root if no `parent_id` is provided.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/fir/{fir_id}/mindmap/nodes` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Request Body:** `CustomNodeCreate`

```json
{
  "parent_id": "uuid-of-parent-node-or-null",
  "node_type": "custom",
  "title": "Obtain mobile CDR for accused",
  "description_md": "Request CDR from Jio for the period 01-Apr to 15-Apr 2026",
  "priority": "recommended"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `parent_id` | UUID | No | root node | Parent node to attach to. If null, attaches to the root node. |
| `node_type` | enum | No | `custom` | Node type. Typically `custom` for IO-added nodes. |
| `title` | string | Yes | -- | Node title (1-512 characters). |
| `description_md` | string | No | `""` | Markdown description. |
| `priority` | enum | No | `optional` | One of: `critical`, `recommended`, `optional`. |

**Response Body:** `MindmapNodeResponse`

```json
{
  "id": "uuid-new-node",
  "mindmap_id": "uuid-mindmap",
  "parent_id": "uuid-root",
  "node_type": "custom",
  "title": "Obtain mobile CDR for accused",
  "description_md": "Request CDR from Jio for the period 01-Apr to 15-Apr 2026",
  "source": "io_custom",
  "bns_section": null,
  "ipc_section": null,
  "crpc_section": null,
  "priority": "recommended",
  "requires_disclaimer": false,
  "display_order": 43,
  "metadata": {"created_by": "inspector_sharma"},
  "current_status": null,
  "children": []
}
```

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Invalid request body, or mindmap not found |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | FIR not found, or no mindmap exists yet (must generate first) |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/nodes" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Obtain mobile CDR for accused",
    "description_md": "Request CDR from Jio for 01-Apr to 15-Apr 2026",
    "priority": "recommended"
  }'
```

---

### 4.8 POST /api/v1/fir/{fir_id}/mindmap/regenerate

**Force regeneration of the mindmap (creates a new version).**

Marks the current active mindmap as `superseded` and generates a fresh one. Useful when upstream data has changed (e.g., FIR re-classified, new evidence gaps detected). The old mindmap and all its status history are retained.

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/api/v1/fir/{fir_id}/mindmap/regenerate` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN |
| Success Code | `201 Created` |

**Request Body:** `RegenerateRequest`

```json
{
  "justification": "FIR reclassified from theft to robbery after further investigation. Need updated template."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `justification` | string | Yes | Reason for regeneration. 5-2000 characters. Logged for audit. |

**Response Body:** `MindmapResponse` (the newly generated mindmap)

**Error Codes:**

| Code | Condition |
|---|---|
| 400 | Invalid request body, or FIR not found |
| 401 | Missing or invalid JWT |
| 403 | Role not in write roles, or district scope violation |
| 404 | FIR not found |
| 500 | Internal server error |

**Sample curl:**

```bash
curl -X POST "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/regenerate" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"justification": "FIR reclassified from theft to robbery after Section 161 statements"}'
```

---

### 4.9 GET /api/v1/fir/{fir_id}/mindmap/export/pdf

**Export the active mindmap as a PDF checklist.**

Renders the mindmap tree as an HTML checklist and converts to PDF using WeasyPrint. If WeasyPrint is not installed, falls back to returning an HTML file.

| Property | Value |
|---|---|
| Method | `GET` |
| Path | `/api/v1/fir/{fir_id}/mindmap/export/pdf` |
| Auth | Bearer JWT |
| Roles | IO, SHO, DYSP, SP, ADMIN, READONLY |
| Success Code | `200 OK` |

**Response:**
- Content-Type: `application/pdf` (or `text/html` if WeasyPrint unavailable)
- Content-Disposition: `attachment; filename="mindmap_{fir_id}.pdf"`

**Error Codes:**

| Code | Condition |
|---|---|
| 401 | Missing or invalid JWT |
| 403 | District scope violation |
| 404 | FIR not found, or no mindmap to export |
| 500 | Internal server error |

**Sample curl:**

```bash
curl "https://atlas.example.com/api/v1/fir/550e8400-e29b-41d4-a716-446655440000/mindmap/export/pdf" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -o mindmap_report.pdf
```

---

## 5. Integration with Existing Modules

### 5.1 T28 -- NLP Case Classifier

**Integration point:** The `firs` table columns `nlp_classification` (VARCHAR) and `nlp_confidence` (FLOAT).

**How it works:**
1. T28 classifies each FIR narrative into a case category (e.g., `murder`, `theft`, `cyber_crime`).
2. The mindmap generator reads these two fields from the FIR record via `_get_case_category()`.
3. If `nlp_confidence >= 0.7`, the classification is accepted as confident. The matching template is used directly.
4. If `nlp_confidence < 0.7`, the classification is accepted but flagged as `uncertain`. The `generated_by_model_version` field is appended with `+uncertain`. The UI should surface a warning to the officer.
5. If `nlp_classification` is `NULL`, the system falls back to the `generic` template (which has zero branches, producing only gap and ML-suggestion nodes if available).

**Relevant code:** `backend/app/mindmap/generator.py`, function `_get_case_category()`.

### 5.2 T48 -- FIR Completeness Engine

**Integration point:** The `firs` table column `completeness_pct` (INTEGER, 0-100) and individual field presence checks.

**How it works:**
1. If `completeness_pct < 100`, the generator scans for specific missing fields: `fir_number`, `complainant_name`, `accused_name`, `place_address`, `occurrence_from`/`occurrence_start`, `primary_sections`, `io_name`, `district`.
2. For each missing field, a `gap_from_fir` node is created under a "FIR Gaps" branch with `priority: critical` and `requires_disclaimer: true`.
3. If `completeness_pct` is `NULL` or `100`, no gap branch is generated.
4. If the T48 module has not run or the field is unavailable, the mindmap is still generated -- the "FIR Gaps" branch is simply absent.

**Relevant code:** `backend/app/mindmap/generator.py`, function `_get_completeness_gaps()`.

### 5.3 T55 -- ML Evidence Gap Classifier

**Integration point:** The `evidence_gap_reports` table, queried by `fir_id`.

**How it works:**
1. The generator queries `evidence_gap_reports` for the most recent report matching the FIR ID.
2. The `report_data` (or `gaps`) JSONB column is parsed. Each gap entry should contain `title`, `description` (or `detail`), and `priority`.
3. Gap entries are inserted as child nodes under an "ML-Suggested Evidence Gaps" branch with `source: ml_suggestion` and `requires_disclaimer: true`.
4. If the query fails or no report exists, the generator logs a warning and proceeds without ML suggestions. This is graceful degradation -- not a fatal error.

**Relevant code:** `backend/app/mindmap/generator.py`, function `_get_evidence_gaps()`.

### 5.4 T56 -- Chargesheet Review (Future Phase 2)

**Status:** Not implemented. Planned for Phase 2.

**Intended integration:** The chargesheet review module (T56) will consume the mindmap's node status data to assess chargesheet readiness. Specifically:
- Percentage of `critical` nodes in `addressed` status.
- Unresolved `disputed` nodes as blockers.
- Custom nodes added by IO as supplementary evidence of thoroughness.

**No code changes are needed in the mindmap module for T56 integration** -- it will read from `chargesheet_mindmaps`, `mindmap_nodes`, and `mindmap_node_status` tables directly.

---

## 6. Observability

### 6.1 Structured Log Events

All log events use `structlog` with structured key-value fields. The event names are designed for machine parsing in log aggregation systems (ELK, Loki, CloudWatch).

| Event Name | Level | Trigger | Key Fields |
|---|---|---|---|
| `mindmap.generated` | INFO | New mindmap created | `fir_id`, `mindmap_id`, `case_category`, `user` |
| `mindmap.regenerated` | INFO | Mindmap regenerated | `fir_id`, `mindmap_id`, `justification`, `user` |
| `mindmap.node_status_changed` | INFO | Node status updated | `node_id`, `new_status`, `user` |
| `mindmap.custom_node_added` | INFO | Custom node created | `mindmap_id`, `node_id`, `user` |
| `mindmap.hash_chain_violation` | ERROR | Hash mismatch detected | `event=hash_chain_violation`, `severity=CRITICAL` |
| `mindmap.generate_error` | ERROR | Generation failure | `fir_id`, `error` |
| `mindmap.export_error` | ERROR | PDF export failure | `error` |

### 6.2 Prometheus Metrics

Defined in `backend/app/mindmap/metrics.py`. If `prometheus_client` is not installed, all metric operations are silently skipped.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `atlas_mindmap_generated_total` | Counter | `case_category` | Total number of mindmaps generated, bucketed by case category. |
| `atlas_mindmap_generation_duration_seconds` | Histogram | (none) | Time taken to generate a mindmap. Buckets: 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0 seconds. |
| `atlas_mindmap_node_status_changes_total` | Counter | `from_status`, `to_status` | Total node status transitions, bucketed by source and target status. |
| `atlas_mindmap_hash_chain_violations_total` | Counter | (none) | Hash chain violations detected. **Should always be 0.** Any non-zero value indicates data tampering or a bug. |

### 6.3 PromQL Examples

**Generation rate over time:**

```promql
rate(atlas_mindmap_generated_total[5m])
```

**Generation rate by case category:**

```promql
sum by (case_category) (rate(atlas_mindmap_generated_total[1h]))
```

**95th percentile generation latency:**

```promql
histogram_quantile(0.95, rate(atlas_mindmap_generation_duration_seconds_bucket[5m]))
```

**Status change activity:**

```promql
sum by (to_status) (rate(atlas_mindmap_node_status_changes_total[1h]))
```

**Hash chain violation alert query:**

```promql
atlas_mindmap_hash_chain_violations_total > 0
```

### 6.4 Suggested Grafana Panels

| Panel | Type | Query | Description |
|---|---|---|---|
| Mindmaps Generated | Time series | `rate(atlas_mindmap_generated_total[5m])` | Generation throughput over time |
| Generation by Category | Pie chart | `sum by (case_category) (atlas_mindmap_generated_total)` | Distribution of generated mindmaps across case categories |
| Generation Latency (p50/p95/p99) | Time series | `histogram_quantile(0.5/0.95/0.99, ...)` | Latency percentiles to detect degradation |
| Node Status Changes | Stacked bar | `sum by (to_status) (rate(atlas_mindmap_node_status_changes_total[1h]))` | Officer activity patterns |
| Hash Chain Violations | Stat panel | `atlas_mindmap_hash_chain_violations_total` | Must always show 0. Red threshold at 1. |
| Most Active Case Categories | Table | `topk(5, sum by (case_category) (atlas_mindmap_generated_total))` | Which case types generate the most mindmaps |

### 6.5 Alert Rules

```yaml
# Prometheus alerting rule
groups:
  - name: atlas_mindmap
    rules:
      - alert: MindmapHashChainViolation
        expr: atlas_mindmap_hash_chain_violations_total > 0
        for: 0m
        labels:
          severity: critical
          team: atlas-backend
        annotations:
          summary: "Hash chain violation detected in mindmap node status"
          description: >
            A hash chain violation has been detected, indicating potential
            data tampering in the mindmap_node_status table. This requires
            immediate investigation. Check ERROR logs for
            'mindmap.hash_chain_violation' events.
          runbook: "https://wiki.internal/atlas/runbooks/hash-chain-violation"

      - alert: MindmapGenerationSlow
        expr: histogram_quantile(0.95, rate(atlas_mindmap_generation_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
          team: atlas-backend
        annotations:
          summary: "Mindmap generation p95 latency exceeds 5 seconds"
```

---

## 7. Failure Modes & Recovery

### 7.1 T47 Extraction Missing (FIR record not found)

**Symptom:** `POST /api/v1/fir/{fir_id}/mindmap` returns `404 Not Found`.

**Cause:** The FIR has not been ingested or extracted yet. The `firs` table has no row for this `fir_id`.

**Recovery:**
1. Verify the FIR was uploaded and T46/T47 pipeline completed.
2. Check the ingestion logs for errors.
3. Re-upload the FIR if necessary.
4. The mindmap endpoint will succeed once the FIR record exists.

### 7.2 T48 Completeness Unavailable

**Symptom:** The generated mindmap has no "FIR Gaps" branch, even though the FIR is clearly incomplete.

**Cause:** `completeness_pct` is `NULL` in the FIR record, meaning T48 has not run.

**Impact:** The mindmap is still generated using the template and any available ML suggestions, but the completeness-driven gap nodes are absent.

**Recovery:** Run the T48 completeness analysis on the FIR, then regenerate the mindmap via `POST /api/v1/fir/{fir_id}/mindmap/regenerate`.

**Log:** No explicit warning is logged for this case (absence of data is not an error condition).

### 7.3 T28 Classifier Confidence Below 0.7

**Symptom:** The mindmap is generated but `generated_by_model_version` contains `+uncertain`. The UI should display a warning banner.

**Cause:** The NLP classifier was not confident enough in its categorization. The FIR narrative may be ambiguous, too short, or describe an uncommon offence.

**Impact:** The mindmap still uses the best-guess template. Officers should verify the case category and regenerate with the correct classification if needed.

**Recovery:** No immediate recovery needed. If the classification is wrong:
1. Correct the `nlp_classification` field (via the classifier admin interface or manual override).
2. Regenerate the mindmap.

### 7.4 Hash-Chain Violation (409 Conflict)

**Symptom:** `PATCH /api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/status` returns `409 Conflict` with message `"Hash chain conflict: expected <hash>, got <hash>. Another user may have updated this node."`.

**Cause:** Two officers attempted to update the same node concurrently. The first update succeeded, but the second used a stale `hash_prev`.

**Impact:** The update is rejected. No data corruption occurs.

**Recovery:**
1. Client should `GET .../nodes/{node_id}/history` to retrieve the latest status chain.
2. Read the latest `hash_self` from the most recent entry.
3. Retry the PATCH with the correct `hash_prev`.

**Monitoring:** Each violation increments `atlas_mindmap_hash_chain_violations_total` and logs an ERROR-level `mindmap.hash_chain_violation` event. If violations are frequent, investigate whether there is a systematic issue (race condition in the UI, misuse of the API).

**Escalation:** If the violation counter is non-zero and the cause is not a benign concurrent-update race, page the on-call engineer. A non-concurrent violation implies data tampering.

### 7.5 Template Registry Load Failure

**Symptom:** Server fails to start. Error message: `"Template directory not found"`, `"No template JSON files found"`, or `"Invalid mindmap template <filename>: <validation error>"`.

**Cause:** Template files are missing, corrupted, or do not conform to the Pydantic schema.

**Impact:** The server process will not start. No mindmap requests can be served.

**Recovery:**
1. Check the `backend/app/mindmap/templates/` directory.
2. Verify all JSON files are valid JSON and conform to the `TemplateTree` schema.
3. Run: `python -c "from app.mindmap.registry import reload_templates; reload_templates()"` locally to identify the specific validation error.
4. Fix the template and redeploy.

**Prevention:** The CI pipeline runs `test_template_registry.py` on every PR. Template changes that break validation will be caught before merge.

---

## 8. Testing

### 8.1 Test Files

| File | Type | DB Required | Description |
|---|---|---|---|
| `test_template_registry.py` | Unit | No | Validates all 9 templates load, conform to schema, have branches. Tests fallback to generic template. |
| `test_mindmap_generator.py` | Unit | No | Tests case category logic, completeness gap extraction, hash chain computation, dedup logic. |
| `test_mindmap_hash_chain.py` | Unit | No | Builds and verifies 10-entry hash chains. Tests tamper detection for modified hash, status, note, prev_hash, and forged insertions. |
| `test_mindmap_rbac.py` | Integration | No (mocked) | Tests RBAC enforcement: READONLY cannot write, IO can write, unauthenticated is rejected. Uses FastAPI TestClient with dependency overrides. |
| `test_mindmap_append_only.py` | DB Integration | Yes | Tests the PostgreSQL trigger: INSERT allowed, UPDATE rejected, DELETE rejected. Requires `DATABASE_URL` env var. Marked with `@pytest.mark.db`. |
| `test_fir_to_mindmap_e2e.py` | Integration | No | End-to-end pipeline: FIR data -> case classification -> template selection -> gap generation. Tests all 9 case categories. Marked with `@pytest.mark.db`. |

### 8.2 Fixtures

- **Template reload**: Most test classes use `reload_templates()` in an `autouse` fixture to ensure a clean registry state.
- **Mock auth tokens**: `_mock_token(role, district)` in `test_mindmap_rbac.py` creates mock JWT payloads for each role.
- **DB fixtures**: `test_mindmap_append_only.py` uses a `db_conn` fixture that connects via `DATABASE_URL`, creates test FIR/mindmap/node records, and rolls back on teardown.

### 8.3 How to Run

```bash
# Run all mindmap tests (unit tests only, no DB required)
pytest backend/tests/mindmap/ -v --cov=backend/app/mindmap --cov-fail-under=80

# Run only unit tests (skip DB-dependent tests)
pytest backend/tests/mindmap/ -v -m "not db"

# Run with DB integration tests (requires DATABASE_URL)
DATABASE_URL=postgresql://user:pass@localhost:5432/atlas_test \
  pytest backend/tests/mindmap/ -v --cov=backend/app/mindmap --cov-fail-under=80

# Run a specific test class
pytest backend/tests/mindmap/test_mindmap_hash_chain.py::TestHashChainIntegrity -v

# Run with verbose coverage report
pytest backend/tests/mindmap/ -v \
  --cov=backend/app/mindmap \
  --cov-report=term-missing \
  --cov-fail-under=80
```

**Coverage target:** Minimum 80% line coverage on `backend/app/mindmap/`. Current tests cover:
- Template loading and validation (all 9 categories).
- Case category determination (threshold boundary, fallback).
- Completeness gap detection (8 field checks).
- Hash chain computation and tamper detection (7 scenarios).
- RBAC enforcement (8 endpoint/role combinations).
- Append-only trigger (INSERT, UPDATE, DELETE).
- End-to-end pipeline (4 scenarios + 9 parameterized).

---

## 9. Security & Compliance

### 9.1 RBAC Matrix

| Endpoint | IO | SHO | DYSP | SP | ADMIN | READONLY |
|---|---|---|---|---|---|---|
| POST /mindmap (generate) | Yes | Yes | Yes | Yes | Yes | **No** |
| GET /mindmap (latest) | Yes | Yes | Yes | Yes | Yes | Yes |
| GET /mindmap/versions | Yes | Yes | Yes | Yes | Yes | Yes |
| GET /mindmap/versions/{id} | Yes | Yes | Yes | Yes | Yes | Yes |
| PATCH /nodes/{id}/status | Yes | Yes | Yes | Yes | Yes | **No** |
| GET /nodes/{id}/history | Yes | Yes | Yes | Yes | Yes | Yes |
| POST /nodes (custom) | Yes | Yes | Yes | Yes | Yes | **No** |
| POST /regenerate | Yes | Yes | Yes | Yes | Yes | **No** |
| GET /export/pdf | Yes | Yes | Yes | Yes | Yes | Yes |

**District scoping:** IO and SHO roles are district-scoped. They can only access FIRs where `fir.district == user.district`. This is enforced by `_check_district_scope()` in `routes.py`. DYSP, SP, ADMIN, and READONLY have cross-district access.

**Authentication:** All endpoints require a valid JWT Bearer token. Requests without a token receive `401 Unauthorized`.

**Authorization enforcement:** Role checks use FastAPI dependency injection via `require_role(*roles)`. The role check occurs before any database query, preventing information leakage through timing differences.

### 9.2 PII Considerations

Mindmap nodes may reference Personally Identifiable Information (PII) from the FIR:
- Complainant names (in gap detection messages like "Complainant Name not recorded").
- Accused names.
- Addresses and locations.

**READONLY role PII redaction:** The READONLY role is intended for researchers and auditors. A future enhancement (not yet implemented) will apply PII-redacted projections for READONLY users, stripping names and addresses from node descriptions. Until then, READONLY users see the same data as other roles.

**Implementation note:** PII redaction should be implemented as a response transformer in the route layer, not in the generator. The database should retain full-fidelity data for evidentiary purposes.

### 9.3 Audit Trail Evidentiary Value

The hash-chain design of `mindmap_node_status` provides cryptographic evidence of the sequence and integrity of status changes. This is relevant for:

- **Court proceedings:** The hash chain can demonstrate that investigation steps were completed in a specific order and that the audit trail has not been tampered with.
- **Internal affairs investigations:** The append-only design (enforced by a DB trigger that rejects UPDATE and DELETE) ensures that officers cannot retroactively alter their status updates.
- **Supervisory review:** The `user_id` field on each status entry provides accountability for who marked each task as complete.

**Chain verification:** Any party can independently verify the chain by walking entries from oldest to newest, recomputing each SHA-256 hash, and confirming that `hash_self` matches. The algorithm is documented in Section 2.6.

### 9.4 DPDP Act Compliance

Under the Digital Personal Data Protection Act, 2023:

- **Data minimization:** Mindmap nodes contain investigative guidance, not raw personal data. PII references are incidental (e.g., gap messages mention which fields are missing). A researcher projection should expose only node types, statuses, priorities, and timestamps -- not descriptions or titles that may contain names.
- **Purpose limitation:** Mindmap data is generated solely for chargesheet preparation assistance. It must not be repurposed for profiling, predictive policing, or officer performance scoring without explicit authorization.
- **Right to erasure:** FIR deletion cascades to mindmap data via `ON DELETE CASCADE` foreign keys. However, the append-only audit trail in `mindmap_node_status` is designed for evidentiary integrity and should be retained for the statutory period even if the FIR is archived.

---

## 10. Deployment Notes

### 10.1 Migration Ordering

The mindmap migration is `009_add_chargesheet_mindmap.py` with `down_revision = "008"`. It must run after all prior migrations (001 through 008).

```bash
# Run migrations
cd backend
alembic upgrade head

# Verify the migration was applied
alembic current
# Expected output: 009 (head)

# To verify tables exist
psql $DATABASE_URL -c "\dt mindmap*"
# Should show: chargesheet_mindmaps, mindmap_nodes, mindmap_node_status
```

**Rollback:**

```bash
alembic downgrade 008
```

This drops all three mindmap tables, their triggers, and the trigger function. All mindmap data will be lost.

### 10.2 Feature Flag

The mindmap feature is controlled by the environment variable `ATLAS_MINDMAP_ENABLED`.

| Variable | Type | Default | Description |
|---|---|---|---|
| `ATLAS_MINDMAP_ENABLED` | boolean | `true` | Set to `false` to disable the mindmap UI panel and API endpoints. |

**Production rollout process:**
1. Run the migration (`alembic upgrade head`).
2. Deploy with `ATLAS_MINDMAP_ENABLED=false` (keeps the feature hidden until Nodal Officer sign-off).
3. QA team tests endpoints directly via curl/Postman.
4. Obtain Nodal Officer sign-off on template content and UI.
5. Set `ATLAS_MINDMAP_ENABLED=true` and redeploy (or update the environment variable without redeployment if the application reads it dynamically).

### 10.3 Rollback Procedure

If an issue is discovered after enabling the feature:

1. **Set `ATLAS_MINDMAP_ENABLED=false`.** This hides the UI panel and disables the API endpoints. No data is deleted.
2. **Existing mindmaps are retained** in the database. They will be visible again if the feature is re-enabled.
3. **No migration rollback is needed** for a feature-flag rollback. Only roll back the migration if you need to remove the tables entirely.
4. **Status history is preserved.** The append-only hash chain in `mindmap_node_status` remains intact regardless of the feature flag state.

### 10.4 Environment Variables Summary

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | -- | PostgreSQL connection string |
| `ATLAS_MINDMAP_ENABLED` | No | `true` | Feature flag for mindmap module |
| `JWT_SECRET_KEY` | Yes | -- | Secret for JWT token validation |

### 10.5 Pre-deployment Checklist

- [ ] Migrations 001-008 are already applied.
- [ ] `alembic upgrade head` runs cleanly (applies migration 009).
- [ ] All 9 template JSON files are present in `backend/app/mindmap/templates/`.
- [ ] Server starts without template validation errors.
- [ ] `pytest backend/tests/mindmap/ -v` passes with 80%+ coverage.
- [ ] `ATLAS_MINDMAP_ENABLED=false` is set for initial production deployment.
- [ ] Prometheus scrape config includes the ATLAS backend target (if using metrics).
- [ ] Grafana dashboard for mindmap metrics is provisioned.
- [ ] Alert rule for `atlas_mindmap_hash_chain_violations_total > 0` is active.
- [ ] Nodal Officer has reviewed and approved template content for all 9 case categories.
