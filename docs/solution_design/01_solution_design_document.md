# ATLAS Platform — Solution Design Document

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-SDD-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted — Internal & Authorised External Reviewers |
| Issue Date | 2026-04-19 |
| Last Reviewed | 2026-04-19 |
| Document Owner | Platform Engineering Lead |
| Approver | Programme Director |
| Distribution | Engineering, Architecture Review Board, Security Office, Programme Management |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context and Drivers](#2-business-context-and-drivers)
3. [Scope](#3-scope)
4. [Glossary and Acronyms](#4-glossary-and-acronyms)
5. [Solution Overview](#5-solution-overview)
6. [Functional Architecture](#6-functional-architecture)
7. [Technical Architecture](#7-technical-architecture)
8. [Data Architecture](#8-data-architecture)
9. [Module Catalogue](#9-module-catalogue)
10. [Integration Architecture](#10-integration-architecture)
11. [Non-Functional Requirements](#11-non-functional-requirements)
12. [Security and Compliance Posture](#12-security-and-compliance-posture)
13. [Operations and Service Management](#13-operations-and-service-management)
14. [Quality Assurance and Testing](#14-quality-assurance-and-testing)
15. [Risk Register](#15-risk-register)
16. [Roadmap and Release Plan](#16-roadmap-and-release-plan)
17. [Governance Model](#17-governance-model)
18. [Assumptions, Dependencies and Constraints](#18-assumptions-dependencies-and-constraints)
19. [Appendices](#19-appendices)

---

## 1. Executive Summary

### 1.1 Purpose
The ATLAS Platform (*Advanced Technology for Law-enforcement Analytics and Surveillance*) is a purpose-built case-management and decision-support system commissioned to assist Investigating Officers (IOs), Station House Officers (SHOs), Deputy Superintendents of Police (DySPs) and Superintendents of Police (SPs) of the Gujarat Police in the lawful and procedurally correct preparation of First Information Reports (FIRs) and chargesheets under the Bharatiya Nyaya Sanhita, 2023 (BNS) and the legacy Indian Penal Code, 1860 (IPC).

### 1.2 Solution snapshot
ATLAS is delivered as a modular monolith comprising a FastAPI-based service backend, a Next.js 14 web application, and a managed data tier built on PostgreSQL 15 (with `pgvector`), Redis 7 and MongoDB 7. The platform is deployed on-premises within the Gujarat State Data Centre (GSDC). All natural-language processing, document classification, and decision-support inference is performed locally on hardened CPU-only infrastructure; no information ever leaves the operator boundary.

### 1.3 Strategic outcomes
The platform delivers four measurable outcomes that align with the State's law-enforcement modernisation programme:

| # | Outcome | Indicator |
|---|---|---|
| O-1 | Reduction in average FIR-to-chargesheet preparation cycle time | Benchmark vs. baseline (Q3 2026) |
| O-2 | Increase in evidentiary completeness of chargesheets at first submission | % chargesheets with zero critical evidence gaps at submission |
| O-3 | Standardisation of investigation procedure across the State's districts | % FIRs with mindmap completion ≥ 90 % at filing |
| O-4 | Tamper-evident audit trail meeting BSA, 2023 admissibility tests | 100 % of investigative actions captured in hash-chained audit log |

### 1.4 Implementation status
As at the issue date of this document, the platform has completed five of eight planned delivery sprints. Core services in production include: authentication and role-based access control (RBAC), FIR ingestion, chargesheet ingestion, mindmap generation, evidence-gap analysis, legal knowledge base and audit-chain. Remaining work is described in §16 (Roadmap).

---

## 2. Business Context and Drivers

### 2.1 Operating environment
The Gujarat Police operates across 33 districts and over 600 police stations, processing in excess of 800,000 FIRs annually. Two structural changes have created acute demand for digital decision-support tooling:

1. **Statutory transition.** With effect from 1 July 2024, the Indian Penal Code, 1860 stands superseded by the Bharatiya Nyaya Sanhita, 2023 (Act 45 of 2023) for offences committed on or after that date. IOs must therefore concurrently apply two legal frameworks until the legacy IPC caseload is exhausted.

2. **Evidentiary regime.** The Bharatiya Sakshya Adhiniyam, 2023 (BSA) modernises evidentiary rules, places greater weight on electronic records, and imposes new chain-of-custody and certification requirements.

### 2.2 Stakeholder map

| Stakeholder | Interest | Engagement Cadence |
|---|---|---|
| Director General of Police, Gujarat | Strategic outcomes, statewide rollout | Quarterly steering |
| Inspector General – Modernisation | Programme delivery, vendor governance | Monthly |
| District Superintendents of Police | District rollout, training, adoption | Monthly per district |
| Investigating Officers (end users) | Daily usability, accuracy of suggestions | Continuous via in-product feedback |
| Public Prosecutors (downstream) | Chargesheet completeness and admissibility | Quarterly user-group |
| Gujarat State Data Centre | Hosting, network, compliance | Monthly operations review |
| Office of the Advocate General | Legal-doctrine review of recommendations | Ad-hoc, before each model release |

### 2.3 Business drivers (BD)

| ID | Driver | Description |
|---|---|---|
| BD-01 | Procedural standardisation | Convergence of investigative procedure across districts to reduce variance in case quality |
| BD-02 | Evidentiary discipline | Reduction of chargesheets returned by prosecution due to evidentiary gaps |
| BD-03 | Statutory dual-running | Concurrent support for IPC and BNS across the transition window |
| BD-04 | Vernacular accessibility | Accommodation of Gujarati-language casework alongside English |
| BD-05 | Data sovereignty | All operational data, models and inference must remain within the State data-centre perimeter |
| BD-06 | Audit and traceability | Tamper-evident audit log to support evidentiary challenges in court |

---

## 3. Scope

### 3.1 In scope (MVP through Sprint 8)

| # | Capability | Module | Status |
|---|---|---|---|
| S-01 | FIR ingestion from PDF (typed and scanned) | `ingestion` | Live |
| S-02 | FIR field-level extraction (38 fields) | `ingestion.fir_parser` | Live |
| S-03 | Multilingual classification (Gujarati + English) | `ml.legal_nlp_filter` | Live |
| S-04 | Chargesheet ingestion and field extraction | `ingestion.chargesheet_parser` | Live |
| S-05 | Statutory-section recommendation (IPC and BNS) | `legal_sections` | Sprint 6 (in flight) |
| S-06 | Investigation mindmap generation by case category | `mindmap` | Live |
| S-07 | Evidence-gap detection (rule + semantic + ML) | `chargesheet.gap_*` | Live |
| S-08 | Legal knowledge base (judgments, offences, references) | `mindmap.kb` | Live |
| S-09 | Tamper-evident audit chain | `audit_chain` | Live |
| S-10 | Role-based access control with district scoping | `core.rbac` | Live |
| S-11 | Dual-pane chargesheet review interface | `frontend/chargesheet/[id]` | Live |
| S-12 | Conviction-probability indicator | `ml.conviction_predictor` | Sprint 7 (planned) |
| S-13 | Chargesheet version control | `chargesheet.versioning` | Sprint 7 (planned) |
| S-14 | Operational dashboards and Prometheus/Grafana telemetry | `infrastructure/grafana` | Live |

### 3.2 Out of scope (current programme)

| # | Item | Rationale |
|---|---|---|
| OS-01 | Direct integration with court case-management systems (e-Courts, ICJS) beyond export feeds | Awaiting MoU between MHA and DoJ |
| OS-02 | Case-prediction / outcome forecasting beyond the conviction-probability indicator | Requires a multi-year longitudinal dataset that is not yet available |
| OS-03 | Public-facing complainant portal | Distinct programme under PMO Modernisation |
| OS-04 | Mobile native applications (iOS/Android) | Web-responsive interface is sufficient for tablet usage in field |
| OS-05 | Forensic laboratory information management | Out of programme charter |

### 3.3 Boundary diagram

```
                          ┌────────────────────────────┐
                          │  ATLAS Platform            │
   FIRs (PDF) ──────────▶ │  - Ingestion              │
   Chargesheets (PDF) ──▶ │  - NLP / classification    │
   IO inputs (web UI) ──▶ │  - Mindmap & gap analysis  │
                          │  - Knowledge base          │ ──▶ Reports
                          │  - Audit chain             │ ──▶ Audit exports
                          │                            │ ──▶ Read-only feeds to
                          │  PostgreSQL │ Redis │ Mongo│      ICJS / e-Prison
                          └────────────────────────────┘      (one-way, future)
```

---

## 4. Glossary and Acronyms

| Term | Definition |
|---|---|
| ATLAS | Advanced Technology for Law-enforcement Analytics and Surveillance |
| BNS | Bharatiya Nyaya Sanhita, 2023 (Act 45 of 2023) |
| BNSS | Bharatiya Nagarik Suraksha Sanhita, 2023 (replaces CrPC) |
| BSA | Bharatiya Sakshya Adhiniyam, 2023 (replaces Indian Evidence Act, 1872) |
| CCTNS | Crime and Criminal Tracking Network and Systems |
| CrPC | Code of Criminal Procedure, 1973 |
| DPDP | Digital Personal Data Protection Act, 2023 |
| DySP | Deputy Superintendent of Police |
| FIR | First Information Report |
| GSDC | Gujarat State Data Centre |
| ICJS | Inter-operable Criminal Justice System |
| IO | Investigating Officer |
| IPC | Indian Penal Code, 1860 |
| KB | Knowledge Base |
| NLP | Natural Language Processing |
| OCR | Optical Character Recognition |
| RBAC | Role-Based Access Control |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| SHO | Station House Officer |
| SLA | Service Level Agreement |
| SLO | Service Level Objective |
| SOP | Standard Operating Procedure |
| SP | Superintendent of Police |
| TLS | Transport Layer Security |

---

## 5. Solution Overview

### 5.1 Solution principles

| # | Principle | Implication |
|---|---|---|
| P-01 | Data sovereignty | All processing within GSDC perimeter; no outbound calls at runtime |
| P-02 | Procedural correctness over speed | Latency budgets relaxed where they preserve legal accuracy |
| P-03 | Explainability of every recommendation | Each suggestion links to source statute, illustration or precedent |
| P-04 | Tamper-evidence | Every action that could affect a case is captured in a hash-chained log |
| P-05 | Human-in-the-loop | The system advises; the IO decides — no automated final filings |
| P-06 | Bilingual parity | Equivalent functional behaviour for Gujarati and English casework |
| P-07 | On-premise economy | Designed to run on commodity CPU servers without GPU acceleration |
| P-08 | Modular monolith | One repository, one deployable unit, internal module boundaries |

### 5.2 Logical capability map

```
┌───────────────────────────────────────────────────────────────────────┐
│                     ATLAS Capability Map                               │
├──────────────────┬──────────────────┬──────────────────┬───────────────┤
│  INGEST          │  ANALYSE         │  ASSIST          │  GOVERN       │
├──────────────────┼──────────────────┼──────────────────┼───────────────┤
│ • PDF ingestion  │ • NLP            │ • Mindmap        │ • RBAC        │
│ • OCR            │   classification │   generation     │ • Audit chain │
│ • FIR parsing    │ • Section        │ • Gap analysis   │ • Compliance  │
│ • Chargesheet    │   recommendation │ • Recommendation │ • Telemetry   │
│   parsing        │ • Legal KB       │   review         │ • Backup &    │
│ • Bulk import    │   retrieval      │ • Coverage       │   restore     │
│                  │ • Conviction-    │   meter          │               │
│                  │   probability    │                  │               │
└──────────────────┴──────────────────┴──────────────────┴───────────────┘
```

### 5.3 Personas

| Code | Persona | Primary Tasks | Key Concerns |
|---|---|---|---|
| U-IO | Investigating Officer | Register FIR, collect evidence, draft chargesheet | Time pressure, vernacular ease, statutory accuracy |
| U-SHO | Station House Officer | Review IO output, sign off chargesheets | Procedural compliance, station-level workload |
| U-DYSP | Deputy Superintendent | Sub-divisional supervision, exception review | Aggregate quality metrics, escalations |
| U-SP | Superintendent | Divisional/district oversight | Outcome KPIs, audit posture, public accountability |
| U-ADM | Platform Administrator | User management, configuration, model lifecycle | System health, uptime, security |
| U-RO | Read-only / observer | Analytics, training, internal audit | Read access without modification |

### 5.4 Top-level user journeys

**UJ-01 — Register a new FIR**: IO uploads scanned/typed PDF → system performs OCR (if scanned), parses 38 fields, classifies offences → IO reviews and confirms → record persisted with audit entry.

**UJ-02 — Prepare and review a chargesheet**: IO uploads draft chargesheet → system extracts accused, charges, evidence and witnesses → produces gap report and statutory-section recommendations → IO reviews in dual-pane interface, accepting or modifying each suggestion → SHO endorses.

**UJ-03 — Generate investigation mindmap**: System infers case category from classified FIR → loads category template → produces investigation-step tree → IO updates node status as activities are completed.

**UJ-04 — Audit-trail extraction**: SP requests audit export for a specific case → system produces hash-chained log with cryptographic verification → exported as evidentiary attachment.

---

## 6. Functional Architecture

### 6.1 Functional decomposition

```
┌───────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION TIER                            │
│  Next.js 14 (App Router, TypeScript) │ shadcn/ui │ ReactFlow         │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ HTTPS / REST (JSON, JWT bearer)
┌──────────────────────────────▼────────────────────────────────────────┐
│                          APPLICATION TIER                             │
│   FastAPI (Python 3.11)                                               │
│   ┌──────────┬───────────┬─────────────┬───────────┬──────────────┐  │
│   │  Auth &  │ Ingestion │  NLP / ML   │  Mindmap  │  Gap         │  │
│   │  RBAC    │ Pipeline  │  Pipeline   │  Engine   │  Aggregator  │  │
│   └──────────┴───────────┴─────────────┴───────────┴──────────────┘  │
│   ┌──────────┬───────────┬─────────────┬───────────┬──────────────┐  │
│   │ Audit    │ Knowledge │ Validation  │ Review    │ Dashboard    │  │
│   │ Chain    │ Base      │ Engine      │ Workflow  │ Aggregator   │  │
│   └──────────┴───────────┴─────────────┴───────────┴──────────────┘  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ SQLAlchemy 2.0 / pgvector / async drivers
┌──────────────────────────────▼────────────────────────────────────────┐
│                            DATA TIER                                  │
│   PostgreSQL 15 + pgvector  │  Redis 7  │  MongoDB 7 (raw documents) │
└───────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                       OBSERVABILITY TIER                              │
│   Prometheus  │  Grafana  │  structlog (JSON, ECS-compatible)        │
│   MLflow (model registry)  │  Label Studio (annotation)              │
└───────────────────────────────────────────────────────────────────────┘
```

### 6.2 Functional requirements (selected)

| ID | Requirement | Priority | Verified by |
|---|---|---|---|
| FR-01 | The system shall ingest FIR PDFs (typed or scanned) up to 25 MB and 100 pages | Must | UAT-01, INT-12 |
| FR-02 | The system shall extract a minimum of 38 named FIR fields with field-level confidence scores | Must | INT-04 |
| FR-03 | The system shall classify FIR narratives into IPC and BNS offences with multi-label output | Must | ML-EVAL-01 |
| FR-04 | The system shall generate an investigation mindmap from one of nine case categories | Must | INT-22 |
| FR-05 | The system shall produce an evidence-gap report categorised by severity (critical / high / medium / low) | Must | INT-30 |
| FR-06 | The system shall provide a hash-chained, append-only audit log for every state-changing action | Must | SEC-AUD-01 |
| FR-07 | The system shall enforce district-level data scoping for IO and SHO roles | Must | SEC-RBAC-01 |
| FR-08 | The system shall support Gujarati and English text in all narrative fields | Must | I18N-01 |
| FR-09 | The system shall provide a dual-pane review interface for chargesheet recommendations | Must | UAT-09 |
| FR-10 | The system shall recommend statutory sections from IPC (1860) and BNS (2023) based on FIR narrative | Must | ML-EVAL-02 |
| FR-11 | The system shall maintain a versioned legal knowledge base with publish/draft workflow | Must | INT-40 |
| FR-12 | The system shall expose Prometheus metrics on `/metrics` for all request paths | Must | OPS-MON-01 |
| FR-13 | The system shall persist raw uploaded documents in immutable storage for evidentiary integrity | Must | SEC-DAT-02 |
| FR-14 | The system shall produce, on demand, a verifiable audit-chain export per case | Must | SEC-AUD-02 |
| FR-15 | The system shall support concurrent users without session collision (MVCC isolation) | Must | PERF-LOAD-01 |

---

## 7. Technical Architecture

### 7.1 Component view

| Layer | Component | Technology | Version |
|---|---|---|---|
| Presentation | Web application | Next.js (App Router) | 14.2.x |
| Presentation | Component library | shadcn/ui + Base UI | current |
| Presentation | Visualisation | ReactFlow | 11.x |
| Presentation | Client-side cache | TanStack React Query | 5.x |
| Application | API gateway and service | FastAPI + Uvicorn | 0.110.x |
| Application | ORM | SQLAlchemy | 2.0.x |
| Application | Migrations | Alembic | latest stable |
| Application | Authentication | python-jose (JWT, HS256) + bcrypt | latest |
| ML / NLP | Multilingual classifier | MuRIL-base-cased (HuggingFace) | local cache |
| ML / NLP | Zero-shot fallback | mDeBERTa-v3-base-MNLI-XNLI | local cache |
| ML / NLP | Language detection | FastText `lid.176.bin` | n/a |
| ML / NLP | Evidence-gap classifier | scikit-learn pipeline | 1.4.x |
| ML / NLP | OCR (scanned documents) | Tesseract via `pytesseract` | 5.x |
| ML / NLP | Tracking and registry | MLflow | 2.10+ |
| ML / NLP | Annotation | Label Studio | latest stable |
| Data | Primary OLTP | PostgreSQL with `pgvector` | 15 |
| Data | Cache and queue | Redis | 7 |
| Data | Document store (raw) | MongoDB | 7 |
| Observability | Metrics | Prometheus | 2.50 |
| Observability | Dashboards | Grafana | 10.3 |
| Observability | Logging | structlog (JSON, ECS-compatible) | latest |

### 7.2 Deployment topology — production

```
                ┌────────────────────────────────────────────────┐
                │          Gujarat State Data Centre (GSDC)      │
                │                                                │
   Police     ──┼──▶ TLS termination ──▶ Reverse proxy (nginx) ──┼─┐
   stations     │                                                │ │
   (browser)    │   ┌───────────────────────────────────────┐   │ │
                │   │           Application Cluster         │◀──┼─┘
                │   │  ┌──────────┐  ┌──────────┐           │   │
                │   │  │ API node │  │ API node │  (n=2-4) │   │
                │   │  └────┬─────┘  └────┬─────┘           │   │
                │   └───────┼─────────────┼─────────────────┘   │
                │           │             │                     │
                │   ┌───────▼─────────────▼──────────────────┐  │
                │   │            Data Cluster                │  │
                │   │  Postgres (primary + standby)          │  │
                │   │  Redis (single + sentinel)             │  │
                │   │  MongoDB (replica set)                 │  │
                │   └───────────────────────────────────────┘  │
                │                                              │
                │   ┌───────────────────────────────────────┐  │
                │   │  Observability                        │  │
                │   │  Prometheus │ Grafana │ Log shipper  │  │
                │   └───────────────────────────────────────┘  │
                └──────────────────────────────────────────────┘
```

### 7.3 Environment matrix

| Environment | Purpose | Sizing (initial) | Data |
|---|---|---|---|
| `dev` | Developer workstations | Docker Compose, 1 node each | Synthetic |
| `int` | Continuous integration | Docker Compose ephemeral | Synthetic |
| `staging` | Pre-production validation | 2 API nodes, 1 DB primary + 1 standby | Anonymised production extract (≤ 90 days) |
| `prod` | Live operations | 4 API nodes, 1 DB primary + 1 standby, Redis sentinel, Mongo 3-node RS | Authoritative |

---

## 8. Data Architecture

### 8.1 Conceptual data model

The platform is organised around five aggregate roots:

1. **FIR** — the originating record of an offence, with associated complainants and accused persons.
2. **Chargesheet** — the prosecutorial filing, linked to one FIR, comprising charges, accused persons, evidence and witnesses.
3. **Mindmap** — an investigation guidance tree, derived from FIR + case category, with hierarchical nodes.
4. **Gap report** — an analysis of the chargesheet identifying missing or weak evidence elements.
5. **Audit chain** — the immutable, hash-linked record of every state-changing action across the platform.

### 8.2 Storage strategy

| Data class | Store | Rationale | Retention |
|---|---|---|---|
| Structured case data | PostgreSQL | Relational integrity, MVCC, mature backups | Per BNSS evidentiary timelines (min. 7 years) |
| Vector embeddings | PostgreSQL `pgvector` | Co-located with structured data; avoids dual-source-of-truth | Coterminous with parent record |
| Cache & ephemeral state | Redis | Sub-millisecond reads | TTL-based, no persistence required |
| Raw documents (PDF, OCR text) | MongoDB GridFS | Flexible schema, large object support | Coterminous with case (immutable) |
| Audit log | PostgreSQL (append-only with DB trigger) | ACID guarantees, evidentiary admissibility | Indefinite (legal hold) |
| Model artefacts | MLflow store on local volume | Versioning, reproducibility | Per model-lifecycle policy |

### 8.3 Logical schema (summary)

A complete data dictionary is maintained as a separate deliverable at [02_data_dictionary.md](02_data_dictionary.md). Key entities are summarised below; refer to that document for column-level details.

| Table | Cardinality | Primary purpose |
|---|---|---|
| `firs` | 1 : N (complainants, accused) | Authoritative FIR record |
| `complainants` | N : 1 (firs) | Persons who lodged the FIR |
| `accused` | N : 1 (firs) | Persons named as accused in the FIR |
| `chargesheets` | 1 : 1 (firs, optional) | Prosecutorial filing |
| `validation_reports` | N : 1 (chargesheets) | Legal-validation findings |
| `evidence_gap_reports` | N : 1 (chargesheets) | Evidence-gap analysis output |
| `chargesheet_mindmaps` | 1 : 1 (firs) | Investigation guidance tree |
| `chargesheet_mindmap_nodes` | N : 1 (mindmaps), self-referential | Tree nodes |
| `chargesheet_gap_reports`, `chargesheet_gaps` | 1 : N | Aggregated gap-analysis reports |
| `legal_kb_*` | reference data | Knowledge base — judgments, offences, references, evidence guidelines |
| `legal_sections`, `legal_section_chunks` | reference data + RAG store | IPC/BNS section text and embedding chunks |
| `audit_log` | append-only | Tamper-evident log |
| `users` | reference | Identity store |
| `ocr_jobs` | N : 1 (firs) | OCR job ledger |

### 8.4 Data classification

| Class | Examples | Handling |
|---|---|---|
| Personal — sensitive | Aadhaar, mobile, address, biometrics | Auto-redacted in logs; encrypted at rest; role-restricted |
| Personal — basic | Name, age, gender | Encrypted at rest; role-restricted |
| Operational | FIR number, sections, status flags | Encrypted at rest |
| Reference / public | IPC/BNS text, KB judgments (post-publication) | No restriction beyond integrity |
| Diagnostic | Logs, metrics | PII-stripped; structured JSON |

---

## 9. Module Catalogue

### 9.1 Authentication and Access Control (`backend/app/core`)
- **Responsibilities**: JWT issuance and validation, password hashing, RBAC enforcement, district-scoping middleware.
- **Key components**: [security.py](backend/app/core/security.py), [rbac.py](backend/app/core/rbac.py), [pii.py](backend/app/core/pii.py).
- **Roles**: ADMIN, SP, DYSP, SHO, IO, READONLY (definitive matrix in [04_security_and_compliance.md](04_security_and_compliance.md)).
- **Standards**: HS256 JWTs with 30-minute access tokens; rotating refresh tokens; bcrypt cost factor 12.

### 9.2 Ingestion Pipeline (`backend/app/ingestion`)
- **Responsibilities**: PDF parsing (typed and scanned), field extraction, validation, persistence.
- **Key components**: [pipeline.py](backend/app/ingestion/pipeline.py), [pdf_parser.py](backend/app/ingestion/pdf_parser.py), [fir_parser.py](backend/app/ingestion/fir_parser.py), [chargesheet_parser.py](backend/app/ingestion/chargesheet_parser.py).
- **Output contract**: validated `FIRCreate` / `ChargeSheetParsed` Pydantic models.

### 9.3 NLP / Machine-Learning Pipeline (`backend/app/ml`, `backend/app/nlp`)
- **Responsibilities**: language detection, multilingual classification, evidence-gap inference, bias monitoring.
- **Key components**: [legal_nlp_filter.py](backend/app/ml/legal_nlp_filter.py), [evidence_gap_model.py](backend/app/ml/evidence_gap_model.py), [evidence_taxonomy.py](backend/app/ml/evidence_taxonomy.py), [train.py](backend/app/ml/train.py), [evaluate.py](backend/app/ml/evaluate.py), [bias_report.py](backend/app/ml/bias_report.py).
- **Models**: MuRIL-base-cased (primary), mDeBERTa-v3-base-MNLI-XNLI (zero-shot fallback), FastText `lid.176.bin`, scikit-learn evidence classifier.

### 9.4 Mindmap Engine (`backend/app/mindmap`)
- **Responsibilities**: case-category inference, template loading, mindmap generation, node-status updates.
- **Templates**: nine case categories (`murder`, `rape`, `ndps`, `dowry`, `cyber_crime`, `pocso`, `theft`, `accident`, `missing_persons`).
- **Key components**: [generator.py](backend/app/mindmap/generator.py), [registry.py](backend/app/mindmap/registry.py), [routes.py](backend/app/mindmap/routes.py).
- **Reference**: [docs/integration/mindmap-backend-integration.md](../integration/mindmap-backend-integration.md).

### 9.5 Evidence Gap Aggregator (`backend/app/chargesheet`)
- **Responsibilities**: combine rule-based, semantic and ML-based gap signals; deduplicate; rank by severity.
- **Tiers**:
  - *Tier 1 — rule*: completeness rules per case category.
  - *Tier 2 — semantic*: TF–IDF similarity over curated evidence phrases.
  - *Tier 3 — machine-learned*: scikit-learn classifier (suggestion-grade).
- **Reference**: [docs/integration/chargesheet-gap-backend-integration.md](../integration/chargesheet-gap-backend-integration.md).

### 9.6 Legal Sections RAG (`backend/app/legal_sections`)
- **Responsibilities**: verbatim canonical IPC and BNS text; embedding store; retrieval-augmented section recommendation.
- **Status**: Sprint 6. Source data extracted and verified ([data/](backend/app/legal_sections/data/) — 585 IPC sections, 358 BNS sections, 99.7 % coverage). Implementation plan in [README.md](backend/app/legal_sections/README.md).

### 9.7 Knowledge Base (`backend/app/mindmap/kb`)
- **Responsibilities**: judgments, offence taxonomy, legal references, evidence guidelines; semantic search via pgvector.
- **Workflow**: ingest → extract insights → review → publish (versioned).

### 9.8 Audit Chain (`backend/app/audit_chain.py`, `backend/app/models/audit.py`)
- **Responsibilities**: append-only hash-chained log of every state-changing action.
- **Algorithm**: `entry_hash = SHA256(previous_hash || canonical_json(entry))`.
- **Properties**: append-only enforced by DB trigger; export verifiable end-to-end.

### 9.9 Frontend (`frontend/src`)
- **Responsibilities**: web user interface, authentication-aware navigation, dual-pane review workflow, mindmap rendering.
- **Notable pages**: `/dashboard/fir/[firId]`, `/dashboard/chargesheet/[id]`, `/dashboard/kb`.
- **Reference**: [docs/decisions/ADR-D14-chargesheet-dual-pane.md](../decisions/ADR-D14-chargesheet-dual-pane.md).

---

## 10. Integration Architecture

### 10.1 Internal integration

All inter-module communication occurs in-process within the FastAPI service. Module boundaries are enforced by package layout and explicit Pydantic-typed function signatures rather than network hops, in keeping with the modular-monolith decision recorded in [ADR-D01](../decisions/ADR-D01-architecture.md).

### 10.2 External integration (current and planned)

| Endpoint Partner | Direction | Mode | Status |
|---|---|---|---|
| eGujCop FIR feed | Inbound | Scheduled batch (CSV/JSON over SFTP) | Planned — Sprint 8 |
| ICJS / e-Courts | Outbound (read-only export) | API or feed | Planned — post-MoU |
| e-Prison | Outbound (read-only export) | API | Planned — post-MoU |
| NCRB CCTNS | Bi-directional | API | Planned — Phase 2 |
| Email / SMS notifications | Outbound | SMTP / SMS gateway | Planned — Sprint 7 |

### 10.3 Integration patterns

- All inbound feeds are validated against a strict JSON schema before persistence; rejected records are routed to a quarantine table with reason codes.
- All outbound exports are produced into an export bucket and pulled by the partner system; ATLAS does not initiate outbound calls to external services in production runtime.
- API responses use HTTP status codes and a uniform error envelope: `{ "error": { "code": str, "message": str, "trace_id": str } }`.

---

## 11. Non-Functional Requirements

### 11.1 Performance and capacity

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-01 | API median response time, read endpoints | ≤ 250 ms |
| NFR-PERF-02 | API median response time, write endpoints | ≤ 500 ms |
| NFR-PERF-03 | FIR ingestion (typed PDF, ≤ 10 pages) end-to-end | ≤ 8 s p95 |
| NFR-PERF-04 | FIR ingestion (scanned PDF, ≤ 10 pages) end-to-end | ≤ 30 s p95 |
| NFR-PERF-05 | Mindmap generation | ≤ 3 s p95 |
| NFR-PERF-06 | Gap analysis | ≤ 10 s p95 |
| NFR-PERF-07 | Concurrent active users (statewide steady state) | 1,500 |
| NFR-PERF-08 | Concurrent active users (peak) | 4,500 |
| NFR-PERF-09 | FIR throughput (sustained) | 100 / minute |

### 11.2 Availability and resilience

| ID | Requirement | Target |
|---|---|---|
| NFR-AVAIL-01 | Service availability | 99.5 % monthly |
| NFR-AVAIL-02 | Recovery Time Objective (RTO) | ≤ 4 hours |
| NFR-AVAIL-03 | Recovery Point Objective (RPO) | ≤ 15 minutes |
| NFR-AVAIL-04 | Planned-maintenance window | Tuesday 02:00–05:00 IST |

### 11.3 Scalability
- Application tier scales horizontally; sessions are stateless (JWT bearer).
- Database tier scales vertically; partition strategy for `firs`, `audit_log` and `chargesheets` by district + year is planned for Phase 2.
- ML inference is co-located with the API tier; if throughput exceeds targets, an inference service can be split out without API changes.

### 11.4 Maintainability
- Strict module boundaries with public APIs declared via `__all__` and Pydantic-typed signatures.
- Static analysis (`flake8`, `mypy` planned) and pre-commit hooks (gitleaks, trailing-whitespace).
- Required automated test coverage: ≥ 70 % at module level, 100 % at audit-chain.

### 11.5 Usability and accessibility
- WCAG 2.1 AA target for all public-facing screens.
- Bilingual labels (Gujarati and English) on all primary navigation.
- Tablet-friendly layouts at ≥ 1024 px.

### 11.6 Localisation
- Server-side language detection (FastText) for narrative inputs.
- Numeric normalisation for Gujarati numerals to Latin digits during ingestion.

---

## 12. Security and Compliance Posture

A complete control catalogue is maintained at [04_security_and_compliance.md](04_security_and_compliance.md). The summary below captures the design intent.

### 12.1 Confidentiality
- TLS 1.3 in transit (terminated at reverse proxy), AES-256 at rest (full-disk and DB-level for sensitive columns).
- Role-restricted PII columns; auto-redaction in application logs.
- JWT signing keys rotated every 90 days; bcrypt password hashing.

### 12.2 Integrity
- Append-only `audit_log` enforced by DB trigger.
- Hash-chained audit entries (`entry_hash = SHA256(previous_hash || canonical_json(entry))`) provide cryptographic detection of tampering.
- Raw documents stored immutably in MongoDB GridFS with content-hash addressing.

### 12.3 Availability
- Active-passive PostgreSQL with streaming replication.
- Container-orchestrated restart policy for all application services.
- Daily encrypted backups to GSDC's backup vault, weekly off-site snapshot.

### 12.4 Statutory and regulatory
- Digital Personal Data Protection Act, 2023 — see §12.4 of [04_security_and_compliance.md](04_security_and_compliance.md).
- Bharatiya Sakshya Adhiniyam, 2023 — admissibility considerations addressed by the audit-chain design.
- IT Act, 2000 (as amended) — reasonable security practices documented and audited.

---

## 13. Operations and Service Management

The full operations runbook is at [05_operations_runbook.md](05_operations_runbook.md). Highlights:

| Function | Cadence | Owner |
|---|---|---|
| Daily backup verification | Daily | GSDC Operations |
| Patch review (OS, container base images) | Monthly | Platform Engineering |
| Security scan (gitleaks, dependency scan) | Per pull request + nightly | Platform Engineering |
| Disaster-recovery drill | Half-yearly | GSDC Operations + Platform Engineering |
| Model re-evaluation (NLP) | Quarterly | ML Engineering |
| Capacity review | Quarterly | Architecture Review Board |

---

## 14. Quality Assurance and Testing

### 14.1 Test pyramid

| Level | Scope | Tooling |
|---|---|---|
| Unit | Pure functions, parsers, validators | `pytest` |
| Integration | DB-backed flows, audit-chain integrity | `pytest` + ephemeral PostgreSQL |
| Contract | API request/response schemas | `pytest` + `httpx` |
| End-to-end | UI flows | Planned: Playwright |
| ML evaluation | Classifier accuracy, calibration, bias | `pytest` + custom harness |
| Performance | Latency and throughput | k6 (planned) |
| Security | SAST, dependency scan, secrets | `gitleaks`, `flake8`, dependency scan |

### 14.2 ML evaluation policy
- Each model release is accompanied by a model card capturing dataset, fairness analysis, calibration curve and error taxonomy.
- A holdout set of at least 200 hand-labelled FIRs forms the gold standard.
- Top-1 accuracy and top-5 hit-rate are tracked per model release.

### 14.3 Acceptance criteria (illustrative)
- AC-01 : All unit and integration tests pass on the release branch with ≥ 70 % coverage.
- AC-02 : ML evaluation report shows no regression > 2 % vs. previous release at the 95 % CI.
- AC-03 : Security scan shows zero High or Critical findings in the release artefact.
- AC-04 : Operations rehearsal completed for any change touching backup, restore or migration paths.

---

## 15. Risk Register

Severity is recorded as a function of likelihood (L) × impact (I); both rated 1–5.

| ID | Risk | L | I | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R-01 | Misclassification of statutory section leads to defective chargesheet | 3 | 5 | 15 | Human-in-the-loop review; explainability of every recommendation; SME sign-off on model release | ML Engineering |
| R-02 | Audit log tampering challenges evidentiary integrity in court | 1 | 5 | 5 | Hash-chain + DB trigger + read-only DBA role for audit table | Security Office |
| R-03 | Vernacular OCR errors cascade into wrong field extraction | 3 | 4 | 12 | Confidence flags surfaced to IO; manual override for low-confidence fields | Platform Engineering |
| R-04 | Model drift after deployment due to changing case patterns | 3 | 3 | 9 | Quarterly re-evaluation; drift monitoring on classifier confidence distribution | ML Engineering |
| R-05 | DB outage at GSDC | 2 | 5 | 10 | Streaming replication + half-yearly DR drill | GSDC Operations |
| R-06 | Privilege misuse by authorised user | 2 | 5 | 10 | RBAC + district scoping + every action logged + quarterly access review | Security Office |
| R-07 | Statutory updates (BNS amendments) outpace KB ingestion | 3 | 4 | 12 | Versioned KB; expedited ingestion SLA for gazetted amendments | Programme Management |
| R-08 | Capacity exhaustion at peak (e.g. statewide incident) | 2 | 4 | 8 | Horizontal API scale-out; rate-limit at reverse proxy; queue-based ingestion | Platform Engineering |
| R-09 | Loss of vendor / open-source library support | 2 | 3 | 6 | Pinned dependency versions; quarterly review of EoL items | Platform Engineering |
| R-10 | Unauthorised exfiltration of case data | 1 | 5 | 5 | No outbound runtime calls; egress firewall; immutable raw store; DLP planned | Security Office |

---

## 16. Roadmap and Release Plan

### 16.1 Release timeline (current programme)

| Sprint | Theme | Indicative window | Status |
|---|---|---|---|
| 1 | Foundations (CI/CD, infra, RBAC, schema) | Q4 2025 | Complete |
| 2 | FIR ingestion, classification baseline | Q4 2025 | Complete |
| 3 | Chargesheet ingestion, validation | Q1 2026 | Complete |
| 4 | Mindmap engine, gap analysis | Q1 2026 | Complete |
| 5 | KB integration, dual-pane review, audit chain | Q2 2026 | Complete |
| 6 | Statutory-section RAG, KB-driven recommendations | Q2 2026 | In flight |
| 7 | Conviction-probability indicator, version control | Q3 2026 | Planned |
| 8 | External integrations (eGujCop, export feeds), production hardening | Q3 2026 | Planned |

### 16.2 Phase 2 candidates (post-Sprint 8)
- Multi-acts coverage (NDPS, POCSO, IT Act, MV Act, Dowry Prohibition).
- Native mobile interfaces.
- Advanced analytics dashboard for senior leadership.
- ICJS-grade interoperability.

---

## 17. Governance Model

### 17.1 RACI (high level)

| Activity | Programme | Architecture | Platform Eng. | ML Eng. | Security | GSDC Ops |
|---|---|---|---|---|---|---|
| Solution architecture | A | R | C | C | C | I |
| Application development | I | C | R/A | C | C | I |
| ML model development | I | C | C | R/A | C | I |
| Security architecture | A | C | C | C | R | I |
| Infrastructure operations | I | C | C | I | C | R/A |
| Release management | A | C | R | C | C | C |
| Incident response | A | C | R | C | C | R |

R: Responsible · A: Accountable · C: Consulted · I: Informed

### 17.2 Change management
- Material changes to architecture, security or data-handling require Architecture Review Board approval.
- All production deployments pass through staging with an explicit go/no-go review captured in the release record.
- Migrations are forward-only and accompanied by a verified rollback plan (data-restore drill on staging).

### 17.3 Architecture Decision Records
ADRs are stored at [docs/decisions/](../decisions/) and referenced from this document where they make a load-bearing choice. The minimum content of an ADR is *Status, Date, Deciders, Context, Decision, Consequences*.

---

## 18. Assumptions, Dependencies and Constraints

### 18.1 Assumptions

| ID | Assumption |
|---|---|
| A-01 | GSDC will provide hardened virtualised hosts meeting baseline CPU/RAM specifications |
| A-02 | Network connectivity from each police station to GSDC is at least 10 Mbps, ≤ 80 ms RTT |
| A-03 | District training will precede each phased district rollout |
| A-04 | Legal SMEs will be available for model evaluation and KB curation at the cadence stated in §13 |

### 18.2 Dependencies

| ID | Dependency | Type |
|---|---|---|
| D-01 | GSDC certificate authority for TLS issuance | External |
| D-02 | MHA / DoJ MoU for ICJS export linkage | External |
| D-03 | Gazetted publication of BNS amendments | External |
| D-04 | Annotated training data from legal SMEs | Internal |

### 18.3 Constraints

| ID | Constraint |
|---|---|
| C-01 | No outbound runtime internet calls in production |
| C-02 | All inference performed on CPU; no GPU dependency in MVP |
| C-03 | Gujarati and English are the only supported languages in MVP |
| C-04 | Audit log is immutable and may not be purged |

---

## 19. Appendices

### 19.1 Reference documents

| Reference | Title | Location |
|---|---|---|
| ADR-D01 | Modular monolith architecture | [decisions/ADR-D01-architecture.md](../decisions/ADR-D01-architecture.md) |
| ADR-D02 | Model selection | [decisions/ADR-D02-model-selection.md](../decisions/ADR-D02-model-selection.md) |
| ADR-D03 | RBAC matrix | [decisions/ADR-D03-rbac-matrix.md](../decisions/ADR-D03-rbac-matrix.md) |
| ADR-D04 | Annotation strategy | [decisions/ADR-D04-annotation-strategy.md](../decisions/ADR-D04-annotation-strategy.md) |
| ADR-D05 | Evaluation strategy | [decisions/ADR-D05-evaluation-strategy.md](../decisions/ADR-D05-evaluation-strategy.md) |
| ADR-D06 | Multilingual pipeline | [decisions/ADR-D06-multilingual-pipeline.md](../decisions/ADR-D06-multilingual-pipeline.md) |
| ADR-D13 | Chargesheet mindmap | [decisions/ADR-D13-chargesheet-mindmap.md](../decisions/ADR-D13-chargesheet-mindmap.md) |
| ADR-D14 | Chargesheet dual-pane review | [decisions/ADR-D14-chargesheet-dual-pane.md](../decisions/ADR-D14-chargesheet-dual-pane.md) |
| ADR-D15 | Sub-clause precision in legal section recommendations | [decisions/ADR-D15-subclause-precision.md](../decisions/ADR-D15-subclause-precision.md) |
| ADR-D16 | Section recommender pipeline, conflict guard and gold-standard evaluation | [decisions/ADR-D16-recommender-pipeline.md](../decisions/ADR-D16-recommender-pipeline.md) |
| ADR-D17 | Phase-2 production wiring — embedder, reranker, persistence, feedback, route, special-acts framework | [decisions/ADR-D17-phase2-pipeline.md](../decisions/ADR-D17-phase2-pipeline.md) |
| ADR-D18 | Gold-standard ratification workflow — AI curation + SME panel | [decisions/ADR-D18-gold-ratification.md](../decisions/ADR-D18-gold-ratification.md) |
| ADR-D19 | IO Scenarios Knowledge Base — Delhi Police Academy Compendium | [decisions/ADR-D19-io-scenarios-kb.md](../decisions/ADR-D19-io-scenarios-kb.md) |
| ADR-D20 | Compendium pipeline wiring — mindmap, gap-aggregator, FIR auto-trigger | [decisions/ADR-D20-compendium-pipeline-wiring.md](../decisions/ADR-D20-compendium-pipeline-wiring.md) |
| INT-01 | Mindmap backend integration | [integration/mindmap-backend-integration.md](../integration/mindmap-backend-integration.md) |
| INT-02 | Chargesheet gap backend integration | [integration/chargesheet-gap-backend-integration.md](../integration/chargesheet-gap-backend-integration.md) |
| R-01 | FIR legal standards | [R01-fir-legal-standards.md](../R01-fir-legal-standards.md) |

### 19.2 Acceptance and sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Programme Director | | | |
| Architecture Review Board chair | | | |
| Security Office | | | |
| Platform Engineering Lead | | | |
| ML Engineering Lead | | | |

---

*End of Solution Design Document.*
