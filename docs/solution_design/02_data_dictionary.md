# ATLAS Platform — Data Dictionary

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-DD-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted |
| Issue Date | 2026-04-19 |
| Document Owner | Data Architecture Lead |
| Companion to | [Solution Design Document](01_solution_design_document.md) |

---

## 1. Purpose
This document is the authoritative data dictionary for the ATLAS Platform. It defines every persistent entity, its columns, semantics, lawful basis (where applicable), and lifecycle. It is the reference of record for engineers building integrations, analysts producing reports, and security officers conducting access reviews.

## 2. Conventions

| Convention | Meaning |
|---|---|
| Notation | Tables in `snake_case`; column types use PostgreSQL idiom |
| Identifiers | All primary keys are UUIDv4 unless explicitly stated as `BIGSERIAL` |
| Time zones | All timestamps stored in UTC; presentation tier converts to IST (UTC+5:30) |
| Nullability | "NN" indicates `NOT NULL`; otherwise nullable |
| Sensitivity | C=Confidential · P=Personal · S=Sensitive Personal · O=Operational · R=Reference |
| Retention | Period after which the row may be archived or anonymised |

## 3. Entity index

| # | Table | Purpose | Section |
|---|---|---|---|
| 3.1 | `firs` | First Information Reports | §4 |
| 3.2 | `complainants` | Persons who lodged the FIR | §5 |
| 3.3 | `accused` | Persons named as accused | §6 |
| 3.4 | `property_details` | Stolen / seized property line items | §7 |
| 3.5 | `users` | Identity store | §8 |
| 3.6 | `audit_log` | Tamper-evident audit chain | §9 |
| 3.7 | `ocr_jobs` | OCR processing ledger | §10 |
| 3.8 | `chargesheets` | Prosecutorial filings | §11 |
| 3.9 | `validation_reports` | Legal validation findings | §12 |
| 3.10 | `evidence_gap_reports` | Evidence gap reports (legacy table) | §13 |
| 3.11 | `chargesheet_mindmaps` | Investigation guidance trees | §14 |
| 3.12 | `chargesheet_mindmap_nodes` | Mindmap nodes (recursive) | §15 |
| 3.13 | `chargesheet_gap_reports`, `chargesheet_gaps` | Aggregated gap analysis | §16 |
| 3.14 | `legal_kb_*` | Knowledge base — judgments, offences, references | §17 |
| 3.15 | `legal_sections`, `legal_section_chunks` | Statutory section corpus and embeddings | §18 |

---

## 4. Table — `firs`

**Purpose**: authoritative record of a First Information Report.
**Lawful basis**: Section 173 BNSS, 2023 (registration of FIR).
**Retention**: minimum seven (7) years from final disposal of any related case, indefinite under legal hold.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate primary key (`gen_random_uuid()`) |
| `fir_number` | TEXT | | O | Official FIR registration number |
| `police_station` | TEXT | | O | Registering station |
| `district` | TEXT | | O | District in which the FIR was registered |
| `fir_date` | DATE | | O | Date of FIR registration |
| `occurrence_start` | TIMESTAMP | | O | Earliest known time of occurrence |
| `occurrence_end` | TIMESTAMP | | O | Latest known time of occurrence |
| `primary_act` | TEXT | | O | Principal act invoked (`IPC` / `BNS` / special act code) |
| `primary_sections` | TEXT[] | | O | Sections invoked at registration |
| `sections_flagged` | TEXT[] | | O | Sections flagged for review (e.g. by NLP) |
| `complainant_name` | TEXT | | P | Free-text name as written on FIR |
| `accused_name` | TEXT | | P | Free-text accused name as written on FIR |
| `gpf_no` | TEXT | | O | General Police Force number of registering officer |
| `occurrence_from`, `occurrence_to` | DATE | | O | Date window of occurrence |
| `time_from`, `time_to` | TEXT | | O | Time window (free-text) |
| `info_received_date`, `info_received_time` | DATE/TEXT | | O | Time information was received at the station |
| `info_type` | TEXT | | O | Oral or written |
| `place_distance_km` | TEXT | | O | Distance of place of occurrence from PS |
| `place_address` | TEXT | | P | Place of occurrence |
| `complainant_father_name` | TEXT | | P | Complainant's father's / guardian's name |
| `complainant_age` | SMALLINT | | P | Complainant age |
| `complainant_nationality` | TEXT | | P | Complainant nationality |
| `complainant_occupation` | TEXT | | P | Complainant occupation |
| `io_name`, `io_rank`, `io_number` | TEXT | | O | Investigating officer details |
| `officer_name` | TEXT | | O | Signing officer (where distinct from IO) |
| `dispatch_date`, `dispatch_time` | DATE/TEXT | | O | Date and time when copy was dispatched to court |
| `stolen_property` | JSONB | | O | Array of `{ description, value }` |
| `completeness_pct` | NUMERIC(4,1) | | O | Confidence of extraction completeness (0–100) |
| `narrative` | TEXT | NN | C | Free-text narrative of the offence |
| `raw_text` | TEXT | NN | C | Verbatim OCR / extracted text of source PDF |
| `source_system` | TEXT | | O | Origin (`manual`, `pdf_upload`, `eGujCop`, etc.) |
| `created_at` | TIMESTAMP | | O | Insertion time |
| `status` | TEXT | | O | Workflow status (`pending`, `classified`, `chargesheeted`, `closed`) |
| `nlp_metadata` | JSONB | | O | Container for NLP outputs |
| `nlp_classification` | TEXT | | O | Primary classifier output (offence label) |
| `nlp_confidence` | NUMERIC(5,4) | | O | Classifier confidence in [0,1] |
| `nlp_classified_at` | TIMESTAMP | | O | When classification ran |
| `nlp_classified_by` | TEXT | | O | Identifier of classifier (model + version) |
| `nlp_model_version` | TEXT | | O | Version tag of the model used |

**Indexes**: `idx_fir_number` (`fir_number`), `idx_created_at` (`created_at`).

---

## 5. Table — `complainants`

**Purpose**: structured store of complainants associated with an FIR (one FIR may have multiple complainants).
**Lawful basis**: Section 173 BNSS.
**Retention**: coterminous with parent FIR.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `fir_id` | UUID | NN | O | FK → `firs.id`, cascade delete |
| `name` | TEXT | | P | Complainant name |
| `father_name` | TEXT | | P | Complainant's father's / guardian's name |
| `age` | SMALLINT | | P | Age in years |
| `address` | TEXT | | P | Residence address |

**Indexes**: `idx_complainants_fir_id` (`fir_id`).

---

## 6. Table — `accused`

**Purpose**: structured store of accused persons associated with an FIR.
**Retention**: coterminous with parent FIR; remains under legal hold until final disposal.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `fir_id` | UUID | NN | O | FK → `firs.id`, cascade delete |
| `name` | TEXT | | P | Accused name |
| `age` | SMALLINT | | P | Age in years |
| `address` | TEXT | | P | Residence address |

**Indexes**: `idx_accused_fir_id` (`fir_id`).

---

## 7. Table — `property_details`

**Purpose**: line-item store of stolen or seized property attached to an FIR.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `fir_id` | UUID | NN | O | FK → `firs.id`, cascade delete |
| `description` | TEXT | | O | Free-text description |
| `value` | NUMERIC(15,2) | | O | Estimated monetary value |

**Indexes**: `idx_property_details_fir_id` (`fir_id`).

---

## 8. Table — `users`

**Purpose**: identity store for platform users.
**Lawful basis**: legitimate interest of the data controller for access management.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `username` | TEXT | NN unique | P | Login identifier |
| `password_hash` | TEXT | NN | S | bcrypt-hashed password (cost 12) |
| `full_name` | TEXT | | P | User full name |
| `role` | TEXT | NN | O | One of `ADMIN`, `SP`, `DYSP`, `SHO`, `IO`, `READONLY` |
| `district` | TEXT | | O | District scoping (NULL for state-wide roles) |
| `police_station` | TEXT | | O | Station scoping (NULL for district-wide roles) |
| `is_active` | BOOLEAN | | O | Soft-delete flag |
| `created_at` | TIMESTAMP | | O | Creation time |

**Indexes**: `idx_users_username` (`username`).

---

## 9. Table — `audit_log`

**Purpose**: append-only, hash-chained log of every state-changing action.
**Integrity guarantees**:
- Append-only enforced by DB trigger (no `UPDATE` or `DELETE` permitted).
- `entry_hash = SHA256(previous_hash || canonical_json(entry))` — verifiable end-to-end.
- DBA role is split: a separate read-only role exists for the audit log to limit privileged abuse.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | BIGSERIAL | NN | O | Monotonic identifier |
| `user_id` | UUID | | O | Acting user (NULL for system actions) |
| `action` | TEXT | NN | O | Verb-noun action code (e.g. `FIR_CREATED`) |
| `resource_type` | TEXT | NN | O | Aggregate kind (e.g. `FIR`, `CHARGESHEET`) |
| `resource_id` | TEXT | | O | Target identifier (string form) |
| `details` | JSONB | | O | Structured action payload (PII-redacted) |
| `ip_address` | TEXT | | O | Source IP (IPv4 or IPv6) |
| `created_at` | TIMESTAMP | | O | Action time |

**Indexes**: `idx_audit_created` (`created_at`).

**Retention**: indefinite. Subject to legal-hold rules.

---

## 10. Table — `ocr_jobs`

**Purpose**: ledger of OCR processing jobs.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `status` | TEXT | | O | One of `pending`, `running`, `complete`, `failed` |
| `filename` | TEXT | | O | Source filename |
| `uploaded_by` | UUID | | O | FK → `users.id` |
| `fir_id` | UUID | | O | FK → `firs.id` (set after parse) |
| `result_summary` | JSONB | | O | Summary of OCR results (page count, confidence) |
| `error_message` | TEXT | | O | Captured failure reason |
| `created_at` | TIMESTAMP | | O | Submission time |
| `completed_at` | TIMESTAMP | | O | Completion time |

**Indexes**: `idx_ocr_jobs_status` (`status`).

---

## 11. Table — `chargesheets`

**Purpose**: prosecutorial filing arising from one or more FIRs.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `fir_id` | UUID | | O | FK → `firs.id` |
| `filing_date` | DATE | | O | Date of filing |
| `court_name` | TEXT | | O | Filing court |
| `status` | TEXT | | O | `pending`, `reviewed`, `flagged`, `submitted` |
| `accused_json` | JSONB | | P | Array of accused records as parsed |
| `charges_json` | JSONB | | O | Array of charges (section, act, description, confidence) |
| `evidence_json` | JSONB | | O | Array of evidence (type, description, status) |
| `witnesses_json` | JSONB | | P | Array of witnesses |
| `io_name` | TEXT | | O | Investigating officer name |
| `raw_text` | TEXT | | C | Verbatim source document text |
| `parsed_json` | JSONB | | O | Full parser output (audit trail) |
| `reviewer_notes` | TEXT | | O | Reviewer remarks captured during dual-pane review |
| `uploaded_by` | UUID | | O | FK → `users.id` |
| `district` | TEXT | | O | District (denormalised for RBAC scoping) |
| `police_station` | TEXT | | O | Police station (denormalised) |
| `created_at`, `updated_at` | TIMESTAMP | | O | Audit timestamps |

---

## 12. Table — `validation_reports`

**Purpose**: legal validation findings produced by the validation engine (IPC/BNS cross-reference, mandatory-fields, etc.).

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `chargesheet_id` | UUID | NN | O | FK → `chargesheets.id` |
| `validated_at` | TIMESTAMP | | O | Time of validation |
| `findings_json` | JSONB | | O | Findings array |
| `overall_assessment` | TEXT | | O | `pass`, `pass_with_observations`, `fail` |
| `created_by` | TEXT | | O | Identifier of the validation engine version |
| `status` | TEXT | | O | Lifecycle status |

---

## 13. Table — `evidence_gap_reports` (legacy)

**Status**: legacy single-tier report, retained for historical data. New analyses are written to `chargesheet_gap_reports` (§16).

| Column | Type | NN | Description |
|---|---|---|---|
| `id` | UUID | NN | Surrogate PK |
| `chargesheet_id` | UUID | NN | FK → `chargesheets.id` |
| `generated_at` | TIMESTAMP | | Generation time |
| `generated_by` | TEXT | | Generator identifier |
| `gaps_json` | JSONB | | Array of gap entries |
| `evidence_categories` | TEXT[] | | Categories considered |

---

## 14. Table — `chargesheet_mindmaps`

**Purpose**: investigation guidance tree per FIR.

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `fir_id` | UUID | NN | O | FK → `firs.id` |
| `case_category` | TEXT | NN | O | One of nine supported categories |
| `template_version` | TEXT | NN | O | Template hash or semver |
| `generated_at` | TIMESTAMP | | O | Generation time |
| `generated_by_model_version` | TEXT | | O | Model identifier used for category inference |
| `status` | TEXT | | O | `active`, `superseded` |
| `root_node_id` | UUID | | O | FK → `chargesheet_mindmap_nodes.id` |

---

## 15. Table — `chargesheet_mindmap_nodes`

**Purpose**: hierarchical nodes of a mindmap (self-referential tree).

| Column | Type | NN | Sensitivity | Description |
|---|---|---|---|---|
| `id` | UUID | NN | O | Surrogate PK |
| `mindmap_id` | UUID | NN | O | FK → `chargesheet_mindmaps.id` |
| `parent_id` | UUID | | O | FK → `chargesheet_mindmap_nodes.id` (nullable for root) |
| `node_type` | TEXT | NN | O | `legal_section`, `immediate_action`, `evidence`, `interrogation`, `forensic`, `witness`, `panchnama`, `suggested_section` |
| `title` | TEXT | NN | O | Human-readable node title |
| `description_md` | TEXT | | O | Markdown description |
| `source` | TEXT | | O | Origin (`template`, `kb`, `nlp`, `user`) |
| `priority` | TEXT | | O | `critical`, `recommended`, `optional` |
| `display_order` | INT | | O | Sibling ordering hint |
| `bns_section`, `ipc_section`, `crpc_section` | TEXT | | O | Linked statutory sections |
| `metadata` | JSONB | | O | Free-form metadata (e.g. `legal_cases`, `confidence`) |

---

## 16. Tables — `chargesheet_gap_reports` and `chargesheet_gaps`

### 16.1 `chargesheet_gap_reports`

| Column | Type | NN | Description |
|---|---|---|---|
| `id` | UUID | NN | Surrogate PK |
| `chargesheet_id` | UUID | NN | FK → `chargesheets.id` |
| `generated_at` | TIMESTAMP | | Generation time |
| `generated_by` | TEXT | | Generator identifier |
| `case_category` | TEXT | | Inferred category at generation time |
| `gaps` | JSONB | | Array of gap entries |
| `readiness` | JSONB | | Overall coverage metrics (e.g. `{ critical_pct, overall_pct }`) |

### 16.2 `chargesheet_gaps`

| Column | Type | NN | Description |
|---|---|---|---|
| `id` | UUID | NN | Surrogate PK |
| `report_id` | UUID | NN | FK → `chargesheet_gap_reports.id` |
| `category` | TEXT | NN | Evidence category (e.g. `post_mortem_report`) |
| `severity` | TEXT | NN | `critical`, `high`, `medium`, `low` |
| `tier` | TEXT | NN | `rule`, `semantic`, `ml` |
| `description` | TEXT | NN | Human-readable description |
| `legal_refs` | JSONB | | Array of statutory references |
| `remediation` | JSONB | | Suggested remediation steps |
| `location` | JSONB | | Source span / pointer |
| `confidence` | NUMERIC(5,4) | | Confidence in [0,1] |
| `source` | TEXT | | Originating module |

---

## 17. Tables — `legal_kb_*`

**Purpose**: curated legal knowledge base. Composed of judgments, offences, evidence guidelines and references. Versioned and reviewed before publication.

The KB is described in detail in [docs/integration/mindmap-backend-integration.md](../integration/mindmap-backend-integration.md). The principal tables are:

| Table | Purpose |
|---|---|
| `legal_kb_offences` | Offence taxonomy (BNS / IPC / special acts) |
| `legal_kb_judgments` | Judgments and binding precedents |
| `legal_kb_judgment_insights` | Extracted holdings, ratio decidendi, doctrines |
| `legal_kb_references` | Citations and cross-references |
| `legal_kb_evidence_guidelines` | Per-offence evidentiary expectations |
| `legal_kb_versions` | Versioning ledger |

---

## 18. Tables — `legal_sections` and `legal_section_chunks`

**Purpose**: canonical IPC and BNS section corpus and embedding chunks for retrieval-augmented section recommendation.

### 18.1 `legal_sections`

| Column | Type | NN | Description |
|---|---|---|---|
| `id` | TEXT | NN | Composite key (e.g. `IPC_302`, `BNS_103`) |
| `act` | TEXT | NN | `IPC` or `BNS` |
| `section_number` | TEXT | NN | Section number including letter suffix where applicable |
| `section_title` | TEXT | | Verbatim section title |
| `chapter_number` | TEXT | | Roman numeral |
| `chapter_title` | TEXT | | Chapter title |
| `full_text` | TEXT | NN | Verbatim section text |
| `sub_clauses` | JSONB | | Structural decomposition into addressable sub-units (see §18.3 and ADR-D15) |
| `cognizable` | BOOLEAN | | From CrPC/BNSS First Schedule (nullable until enriched) |
| `bailable` | BOOLEAN | | From CrPC/BNSS First Schedule |
| `triable_by` | TEXT | | From CrPC/BNSS First Schedule |
| `compoundable` | BOOLEAN | | From CrPC/BNSS First Schedule |
| `cross_references` | TEXT[] | | Sections cited within the body |
| `metadata` | JSONB | | Auxiliary attributes |
| `created_at` | TIMESTAMP | | Insertion time |

### 18.2 `legal_section_chunks`

| Column | Type | NN | Description |
|---|---|---|---|
| `id` | UUID | NN | Surrogate PK |
| `section_id` | TEXT | NN | FK → `legal_sections.id` |
| `act` | TEXT | NN | Denormalised `IPC` / `BNS` for fast filter |
| `section_number` | TEXT | NN | Denormalised |
| `chunk_type` | TEXT | NN | `header`, `body`, `illustration`, `explanation`, `exception` |
| `chunk_index` | INT | NN | Order within the section |
| `text` | TEXT | NN | Verbatim chunk text |
| `dense_embedding` | vector(1024) | | Dense embedding (model: `BAAI/bge-m3`) |
| `keywords` | TEXT[] | | Extracted keywords for sparse retrieval |
| `metadata` | JSONB | | Auxiliary attributes |
| `source_page` | INT | | Source page in original gazette |
| `created_at` | TIMESTAMP | | Insertion time |

**Indexes**:
- `ix_legal_section_chunks_section` (`section_id`)
- `ix_legal_section_chunks_act` (`act`)
- `ix_legal_section_chunks_dense` USING `ivfflat (dense_embedding vector_cosine_ops)` WITH (lists = 100)

### 18.3 Sub-clause records (`legal_sections.sub_clauses` JSON shape)

Each element of the `sub_clauses` array represents one **addressable sub-unit** of the parent section, per ADR-D15. It is the schema returned by the parser at `backend/app/legal_sections/subclause_parser.py` and the contract relied upon by the recommender, the chunker, and the audit chain.

| Field | Type | Description |
|---|---|---|
| `section_id` | TEXT | Parent section identifier (e.g. `BNS_305`) |
| `label` | TEXT | Raw marker as it appears in the source (e.g. `(a)`, `Provided that`, `First.`) |
| `canonical_label` | TEXT | Normalised marker form (e.g. `(a)`, `Provided that`, `First`) |
| `scheme` | TEXT | One of `num`, `alpha_lower`, `alpha_upper`, `roman_lower`, `roman_upper`, `ordinal`, `proviso` |
| `depth` | INT | Nesting depth — `1` for top-level, `2` for nested, etc. |
| `parent_path` | TEXT[] | Ancestor labels in document order (empty for top-level) |
| `canonical_citation` | TEXT | Court-ready citation (e.g. `BNS 305(a)`, `IPC 376(2)(a)(i)`, `BNS 332 Provided that`) |
| `addressable_id` | TEXT | URL-safe identifier (e.g. `BNS_305_a`, `IPC_376_2_a_i`, `BNS_332_proviso_1`) |
| `text` | TEXT | Verbatim text span of this sub-clause |
| `offset_start` | INT | Character offset within parent `full_text` |
| `offset_end` | INT | Exclusive end offset within parent `full_text` |

**Reference dataset coverage (current extraction):**

| Act | Sections with sub-clauses | Total sub-clauses |
|---|---|---|
| IPC | 98 of 585 | 487 |
| BNS | 151 of 358 | 839 |

Validation gate: `python scripts/verify_legal_sections.py` SHALL exit `0` and the `all_sub_clause_checks_pass` field SHALL be `true` before any release that affects the corpus or the parser.

---

## 19. Reference data files

The reference corpus is shipped as JSONL alongside the application:

| Path | Records | Coverage |
|---|---|---|
| [backend/app/legal_sections/data/ipc_sections.jsonl](../../backend/app/legal_sections/data/ipc_sections.jsonl) | 585 | 99.65 % of body text |
| [backend/app/legal_sections/data/bns_sections.jsonl](../../backend/app/legal_sections/data/bns_sections.jsonl) | 358 | 99.71 % of body text |

Reproduction: `python scripts/extract_legal_sections.py` followed by `python scripts/verify_legal_sections.py` (must report `OVERALL: PASS`).

---

## 20. Data lifecycle

| Phase | Trigger | Action |
|---|---|---|
| Capture | FIR upload, chargesheet upload, manual entry | Validate, persist |
| Enrichment | Background NLP task | Add classification, sections, gap report, mindmap |
| Review | Dual-pane review action | Update status, append audit entry |
| Publication | Endorsement by SHO | Lock record fields, mark immutable for editing |
| Archival | After legal-hold release | Move to cold storage; encrypted at rest |
| Disposal | After retention period | Cryptographic shredding of keys |

## 21. Cross-cutting controls

| Control | Mechanism |
|---|---|
| PII redaction in logs | `core.pii.redact()` applied to all log payloads |
| Row-level access scoping | District-aware filters in CRUD layer for IO/SHO |
| Schema migrations | Alembic — forward-only, peer-reviewed |
| Backup | Daily encrypted PostgreSQL `pg_basebackup` + WAL streaming |
| Restore drill | Half-yearly, recorded in DR log |

---

*End of Data Dictionary.*
