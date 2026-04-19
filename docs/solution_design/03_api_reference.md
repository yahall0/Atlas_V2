# ATLAS Platform — API Reference

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-API-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted |
| Issue Date | 2026-04-19 |
| Document Owner | Platform Engineering Lead |
| Companion to | [Solution Design Document](01_solution_design_document.md), [Data Dictionary](02_data_dictionary.md) |

---

## 1. General

### 1.1 Base URL
- Production : `https://atlas.<gsdc-domain>/api/v1`
- Staging    : `https://atlas-staging.<gsdc-domain>/api/v1`
- Local      : `http://localhost:8000/api/v1`

### 1.2 Versioning
- All endpoints are under `/api/v1`. Breaking changes will be introduced as `/api/v2` and dual-supported for one major release cycle (six months minimum).

### 1.3 Authentication
- All endpoints (except `/auth/login` and `/health`) require a JSON Web Token in the `Authorization: Bearer <token>` header.
- Tokens are issued by `/auth/login` and refreshed via `/auth/refresh`.
- Algorithm: HS256. Access-token TTL: 30 minutes. Refresh-token TTL: 24 hours.

### 1.4 Authorisation (RBAC summary)

| Role | Scope | Typical capability |
|---|---|---|
| ADMIN | Statewide | Full administrative access, user management, KB publication |
| SP | District | Read all in district; sign off SP-level approvals |
| DYSP | Sub-division | Read all in sub-division; sign off DYSP-level approvals |
| SHO | Police station | Read/write all in station; endorse chargesheets |
| IO | Police station (own cases) | Read/write own cases |
| READONLY | Configurable | Read access only |

### 1.5 Conventions
- Content type: `application/json` unless explicitly noted (uploads are `multipart/form-data`; PDF exports are `application/pdf`).
- Identifiers: UUIDv4 in canonical hyphenated form.
- Time: ISO 8601 UTC, e.g. `2026-04-19T10:15:30Z`.
- Pagination: `?limit=<int>&offset=<int>`. Defaults `limit=20`, max `limit=100`.
- Filtering: query parameters; multi-valued filters are comma-separated.

### 1.6 Error envelope

All errors follow the structure below.

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "trace_id": "string",
    "details": { "field": ["message"] }
  }
}
```

### 1.7 Standard HTTP status codes

| Code | Meaning | Example |
|---|---|---|
| 200 | OK | Successful read |
| 201 | Created | Successful resource creation |
| 202 | Accepted | Asynchronous job accepted (e.g. ingestion) |
| 204 | No Content | Successful delete / void update |
| 400 | Bad Request | Validation failure |
| 401 | Unauthorised | Missing or invalid token |
| 403 | Forbidden | Authenticated but not permitted |
| 404 | Not Found | Resource not found or out of scope |
| 409 | Conflict | Workflow violation (e.g. closed case) |
| 422 | Unprocessable Entity | Business-rule validation failure |
| 429 | Too Many Requests | Rate-limit triggered |
| 500 | Internal Server Error | Unhandled server fault |
| 503 | Service Unavailable | Dependency outage |

### 1.8 Rate limits
- Default: 60 requests/minute per JWT subject.
- Ingestion endpoints: 10 requests/minute per JWT subject.
- Bulk-import endpoints: 1 request/minute per JWT subject.
- Limits are returned via `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` response headers.

### 1.9 Health and observability
- `GET /api/v1/health` — liveness/readiness, no auth required.
- `GET /metrics` — Prometheus exposition format, restricted to monitoring service IPs.

---

## 2. Endpoint catalogue (summary)

| # | Method | Path | Purpose |
|---|---|---|---|
| 2.1 | POST | `/auth/login` | Issue JWT pair |
| 2.2 | POST | `/auth/refresh` | Refresh access token |
| 2.3 | GET | `/auth/me` | Current user profile |
| 2.4 | GET | `/health` | Liveness/readiness |
| 2.5 | POST | `/firs` | Create FIR |
| 2.6 | GET | `/firs/{fir_id}` | Retrieve FIR |
| 2.7 | GET | `/firs` | List FIRs |
| 2.8 | PATCH | `/firs/{fir_id}/classification` | Manually set classification |
| 2.9 | POST | `/ingest` | Upload FIR PDF for ingestion |
| 2.10 | POST | `/chargesheet/upload` | Upload chargesheet PDF |
| 2.11 | GET | `/chargesheet/{cs_id}` | Retrieve chargesheet |
| 2.12 | GET | `/chargesheet/` | List chargesheets |
| 2.13 | PATCH | `/chargesheet/{cs_id}/review` | Set review status |
| 2.14 | POST | `/validate` | Run validation against a chargesheet |
| 2.15 | GET | `/validate/{validation_id}` | Get validation report |
| 2.16 | POST | `/evidence/analyze` | Run evidence analysis |
| 2.17 | GET | `/evidence/{report_id}` | Get evidence report |
| 2.18 | POST | `/predict` | Predict classification for raw narrative |
| 2.19 | POST | `/review/...` | Reviewer-workflow endpoints |
| 2.20 | POST | `/fir/{fir_id}/mindmap` | Generate mindmap |
| 2.21 | GET | `/fir/{fir_id}/mindmap` | Get latest mindmap |
| 2.22 | GET | `/fir/{fir_id}/mindmap/versions` | List mindmap versions |
| 2.23 | GET | `/fir/{fir_id}/mindmap/versions/{mindmap_id}` | Get specific version |
| 2.24 | PATCH | `/fir/{fir_id}/mindmap/nodes/{node_id}/status` | Update node status |
| 2.25 | GET | `/fir/{fir_id}/mindmap/nodes/{node_id}/history` | Node status history |
| 2.26 | POST | `/fir/{fir_id}/mindmap/nodes` | Add custom node |
| 2.27 | POST | `/fir/{fir_id}/mindmap/regenerate` | Regenerate mindmap |
| 2.28 | GET | `/fir/{fir_id}/mindmap/export/pdf` | Export mindmap as PDF |
| 2.29 | POST | `/chargesheet/{cs_id}/gaps/analyze` | Run gap analysis |
| 2.30 | GET | `/chargesheet/{cs_id}/gaps/report` | Latest gap report |
| 2.31 | GET | `/chargesheet/{cs_id}/gaps/reports` | List versions |
| 2.32 | GET | `/chargesheet/{cs_id}/gaps/reports/{report_id}` | Get specific version |
| 2.33 | POST | `/chargesheet/{cs_id}/gaps/reanalyze` | Re-run gap analysis |
| 2.34 | PATCH | `/chargesheet/{cs_id}/gaps/{gap_id}/action` | Act on a gap |
| 2.35 | GET | `/chargesheet/{cs_id}/gaps/{gap_id}/history` | Gap action history |
| 2.36 | POST | `/chargesheet/{cs_id}/gaps/{gap_id}/apply-suggestion` | Apply suggested remediation |
| 2.37 | GET | `/dashboard/stats` | Dashboard aggregates |
| 2.38 | GET | `/kb/offences` | List offences |
| 2.39 | GET | `/kb/offences/{offence_id}` | Get offence |
| 2.40 | POST | `/kb/offences` | Create offence |
| 2.41 | PUT | `/kb/offences/{offence_id}` | Update offence |
| 2.42 | PATCH | `/kb/offences/{offence_id}/review` | Move through review states |
| 2.43 | POST | `/kb/offences/{offence_id}/nodes` | Add knowledge node |
| 2.44 | PUT | `/kb/nodes/{node_id}` | Update knowledge node |
| 2.45 | DELETE | `/kb/nodes/{node_id}` | Deprecate knowledge node |
| 2.46 | POST | `/kb/query` | Knowledge bundle query |
| 2.47 | GET | `/kb/judgments` | List judgments |
| 2.48 | GET | `/kb/judgments/{judgment_id}` | Get judgment |
| 2.49 | POST | `/kb/judgments` | Ingest a judgment |
| 2.50 | POST | `/kb/judgments/{judgment_id}/extract` | Extract insights |
| 2.51 | GET | `/kb/insights/pending` | List pending insights |
| 2.52 | PATCH | `/kb/insights/{insight_id}/review` | Review an insight |
| 2.53 | GET | `/kb/versions` | List KB versions |
| 2.54 | GET | `/kb/stats` | KB statistics |
| 2.55 | POST | `/firs/{fir_id}/recommend-sections` | Recommend statutory sections (Sprint 6) |

---

## 3. Authentication endpoints

### 3.1 `POST /auth/login`
**Purpose**: issue an access token and refresh token.
**Authorisation**: none.

Request:
```json
{ "username": "io.amreli.001", "password": "********" }
```

Response `200`:
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Errors: `401` invalid credentials.

### 3.2 `POST /auth/refresh`
**Purpose**: exchange a refresh token for a new access token.

Request: `{ "refresh_token": "<jwt>" }` → Response `200`: same shape as login.

### 3.3 `GET /auth/me`
**Purpose**: return the authenticated principal.

Response `200`:
```json
{
  "username": "io.amreli.001",
  "role": "IO",
  "district": "Amreli",
  "police_station": "City"
}
```

---

## 4. FIR endpoints

### 4.1 `POST /firs` — Create FIR
**Authorisation**: IO, SHO, ADMIN. District-scoped for IO/SHO.

Request body (subset):
```json
{
  "fir_number": "11192050250010",
  "district": "Amdavad",
  "police_station": "Vadaj",
  "fir_date": "2025-01-01",
  "primary_act": "BNS",
  "primary_sections": ["303", "317"],
  "complainant_name": "Dinaben Dinak",
  "narrative": "...",
  "raw_text": "..."
}
```
Response `201`: `FIRResponse` (see [Data Dictionary §4](02_data_dictionary.md#4-table--firs)).

### 4.2 `GET /firs/{fir_id}`
Returns full FIR record. `404` if outside caller's RBAC scope.

### 4.3 `GET /firs`
Query parameters:
- `district` — filter (RBAC-scoped users may not exceed their scope)
- `police_station`
- `status` — pending | classified | chargesheeted | closed
- `from`, `to` — ISO dates filtering by `fir_date`
- `limit`, `offset`

### 4.4 `PATCH /firs/{fir_id}/classification`
Manual override of NLP classification. Body: `{ "classification": "BNS_103", "rationale": "..." }`.
Audit entry: `FIR_CLASSIFICATION_OVERRIDDEN`.

### 4.5 `POST /ingest`
**Multipart upload**. Field `file` = PDF (≤ 25 MB, ≤ 100 pages).

Response `202`:
```json
{ "ocr_job_id": "uuid", "fir_id": null, "status": "pending" }
```
Polling: `GET /ingest/{ocr_job_id}` (when implemented) or via job status broadcast.

---

## 5. Chargesheet endpoints

### 5.1 `POST /chargesheet/upload`
**Multipart upload**. Field `file` = PDF.

Response `202`: `ChargeSheetResponse` with `status = pending` and parsed sections populated incrementally.

### 5.2 `GET /chargesheet/{cs_id}`
Returns full chargesheet record.

### 5.3 `GET /chargesheet/`
Filters: `status`, `district`, `police_station`, `fir_id`, `from`, `to`, `limit`, `offset`.

### 5.4 `PATCH /chargesheet/{cs_id}/review`
Set or update review status.
Body:
```json
{ "status": "reviewed", "reviewer_notes": "Sections 303, 317 confirmed; evidence list complete." }
```
Audit entry: `CHARGESHEET_REVIEWED` (or `_FLAGGED`).

---

## 6. Validation endpoints

### 6.1 `POST /validate`
Body: `{ "chargesheet_id": "uuid" }`.
Response `201`: `ValidationReport` with `findings_json` and `overall_assessment`.

### 6.2 `GET /validate/{validation_id}`
Returns the persisted validation report.

---

## 7. Evidence endpoints

### 7.1 `POST /evidence/analyze`
Body: `{ "chargesheet_id": "uuid" }`.
Response `201`: `EvidenceReport`.

### 7.2 `GET /evidence/{report_id}`
Returns the persisted evidence report.

---

## 8. Prediction endpoints

### 8.1 `POST /predict`
Body: `{ "narrative": "free-text Gujarati or English narrative" }`.
Response `200`:
```json
{
  "language": "gu",
  "primary_classification": "BNS_303",
  "secondary_classifications": ["BNS_317"],
  "confidence": 0.91,
  "model_version": "v3.0.1"
}
```

---

## 9. Mindmap endpoints

All mindmap endpoints are scoped to a parent FIR. Updates are append-only — no overwriting of historical state.

### 9.1 `POST /fir/{fir_id}/mindmap`
Generate a fresh mindmap. Response `201`: `MindmapResponse` (recursive tree).

### 9.2 `GET /fir/{fir_id}/mindmap`
Latest mindmap for the FIR.

### 9.3 `GET /fir/{fir_id}/mindmap/versions`
List versions: `[{ id, generated_at, status, template_version }]`.

### 9.4 `GET /fir/{fir_id}/mindmap/versions/{mindmap_id}`
Specific version.

### 9.5 `PATCH /fir/{fir_id}/mindmap/nodes/{node_id}/status`
Body:
```json
{ "status": "addressed", "notes": "PM report received and tagged as evidence E-12." }
```
Status one of: `open`, `in_progress`, `addressed`, `not_applicable`, `disputed`.
Append-only: history retained.

### 9.6 `GET /fir/{fir_id}/mindmap/nodes/{node_id}/history`
Returns array of status transitions with actor and timestamp.

### 9.7 `POST /fir/{fir_id}/mindmap/nodes`
Add a custom node. Body must include `parent_id`, `node_type`, `title`.

### 9.8 `POST /fir/{fir_id}/mindmap/regenerate`
Regenerate (creates a new version; previous remains accessible).

### 9.9 `GET /fir/{fir_id}/mindmap/export/pdf`
Returns a printable PDF checklist. Content-type: `application/pdf`.

---

## 10. Gap-analysis endpoints

All gap-analysis endpoints follow the pattern of *append-only history*; previous reports and prior actions remain visible.

### 10.1 `POST /chargesheet/{chargesheet_id}/gaps/analyze`
Trigger gap analysis. Response `201`: `GapReportResponse`.

### 10.2 `GET /chargesheet/{chargesheet_id}/gaps/report`
Latest gap report.

### 10.3 `GET /chargesheet/{chargesheet_id}/gaps/reports`
List gap-report versions.

### 10.4 `GET /chargesheet/{chargesheet_id}/gaps/reports/{report_id}`
Specific gap report.

### 10.5 `POST /chargesheet/{chargesheet_id}/gaps/reanalyze`
Run a fresh analysis (new version).

### 10.6 `PATCH /chargesheet/{chargesheet_id}/gaps/{gap_id}/action`
Body:
```json
{ "action": "accept", "notes": "Witness W-3 statement scheduled for 2026-04-25." }
```
Action one of: `accept`, `modify`, `dismiss`, `request_more_info`.

### 10.7 `GET /chargesheet/{chargesheet_id}/gaps/{gap_id}/history`
Action history.

### 10.8 `POST /chargesheet/{chargesheet_id}/gaps/{gap_id}/apply-suggestion`
Apply the system-generated remediation. Body: optional `{ "comment": "..." }`.

---

## 11. Knowledge Base endpoints

### 11.1 Offences
- `GET /kb/offences` — list
- `GET /kb/offences/{offence_id}` — detail
- `POST /kb/offences` — create
- `PUT /kb/offences/{offence_id}` — update
- `PATCH /kb/offences/{offence_id}/review` — transition through `draft → in_review → published → deprecated`

### 11.2 Knowledge nodes
- `POST /kb/offences/{offence_id}/nodes`
- `PUT /kb/nodes/{node_id}`
- `DELETE /kb/nodes/{node_id}` (deprecate; not destructive)

### 11.3 Judgments
- `GET /kb/judgments`
- `GET /kb/judgments/{judgment_id}`
- `POST /kb/judgments` — ingest (upload metadata + body)
- `POST /kb/judgments/{judgment_id}/extract` — extract holdings/insights

### 11.4 Insights and lifecycle
- `GET /kb/insights/pending`
- `PATCH /kb/insights/{insight_id}/review`
- `GET /kb/versions`
- `GET /kb/stats`
- `POST /kb/query` — bundle query for a given offence/case context

---

## 12. Section Recommendation (Sprint 6)

### 12.1 `POST /firs/{fir_id}/recommend-sections`
Trigger statutory-section recommendation for an FIR.

The recommendation contract honours the **sub-clause precision requirement**
defined in [ADR-D15](../decisions/ADR-D15-subclause-precision.md). Every
returned recommendation cites the smallest applicable addressable unit of
the statute. Where a section contains enumerated alternatives or numbered
sub-sections, the recommender SHALL identify the matching sub-clause(s) and
emit:

* `sub_clause_label` — the marker (e.g. `(a)`, `(2)`, `Provided that`, `First`)
* `canonical_citation` — court-ready form (e.g. `BNS 305(a)`)
* `addressable_id` — URL-safe identifier (e.g. `BNS_305_a`)
* `rationale_quote` — verbatim text of the sub-clause, not the umbrella header

Multiple sub-clauses of the same parent section MAY be returned as separate
entries when more than one alternative applies.

Response `200`:
```json
{
  "fir_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "act_basis": "BNS",
  "occurrence_start": "2025-03-16T11:00:00+05:30",
  "commission_window": { "from": "11:00", "to": "afternoon (pre-sunset)" },
  "model_version": "atlas-rag-v1.0.0",
  "generated_at": "2026-04-19T10:30:00Z",
  "recommendations": [
    {
      "section_id": "BNS_305",
      "act": "BNS",
      "section_number": "305",
      "section_title": "Theft in a dwelling house, or means of transportation or place of worship, etc.",
      "sub_clause_label": "(a)",
      "canonical_citation": "BNS 305(a)",
      "addressable_id": "BNS_305_a",
      "confidence": 0.97,
      "rationale_quote": "(a) in any building, tent or vessel used as a human dwelling or used for the custody of property; or",
      "matching_fir_facts": [
        "theft committed inside the complainant's residence",
        "house was used as a human dwelling and for custody of property (gold, silver, cash)"
      ],
      "related_sections": ["BNS_303"],
      "borderline_with": []
    },
    {
      "section_id": "BNS_331",
      "act": "BNS",
      "section_number": "331",
      "section_title": "Punishment for house-trespass or house-breaking",
      "sub_clause_label": "(3)",
      "canonical_citation": "BNS 331(3)",
      "addressable_id": "BNS_331_3",
      "confidence": 0.92,
      "rationale_quote": "(3) Whoever commits lurking house-trespass or house-breaking, in order to the committing of any offence punishable with imprisonment, shall be punished … if the offence intended to be committed is theft, the term of the imprisonment may be extended to seven years.",
      "matching_fir_facts": [
        "lock of the front door was broken to gain entry",
        "intended offence was theft"
      ],
      "related_sections": ["BNS_330", "BNS_332"],
      "borderline_with": []
    }
  ]
}
```

#### 12.1.1 Sub-clause emission rules (binding)

| Rule | Statement |
|---|---|
| RC-01 | If the matched section contains zero addressable sub-clauses, `sub_clause_label` SHALL be `null` and `canonical_citation` SHALL be the section header form (e.g. `BNS 379`). |
| RC-02 | If the matched section contains addressable sub-clauses, the recommender SHALL identify the smallest matching unit. Returning the umbrella section is a defect. |
| RC-03 | When more than one sibling sub-clause matches, each SHALL be emitted as a separate recommendation entry. The parent `section_id` is shared; `canonical_citation` differs. |
| RC-04 | `rationale_quote` SHALL be the verbatim text of the cited sub-clause, including the marker (e.g. `(a) in any building...`). It SHALL NOT be the umbrella section header. |
| RC-05 | Provisos are first-class addressable units. They SHALL be emitted with `canonical_citation = "<section> Proviso"` (or `"Provided that"` form per the source). |
| RC-06 | The IO interface SHALL render `canonical_citation` verbatim in the chargeable list and in any document export. |

### 12.2 `GET /firs/{fir_id}/recommend-sections/latest`
Returns the latest cached recommendation for the FIR.

---

## 13. Dashboard

### 13.1 `GET /dashboard/stats`
Returns aggregate counts and KPIs for the caller's RBAC scope.

```json
{
  "fir_count": 12453,
  "chargesheet_count": 8921,
  "pending_review": 142,
  "average_cycle_time_days": 22.3,
  "evidence_coverage_pct": 78.4
}
```

---

## 14. Audit-export endpoints (planned)

The platform is committed to providing a verifiable audit-chain export per case. The endpoint specification will be appended to this document on completion of Sprint 7.

---

## 15. Notes for integrators

- **Idempotency**: clients should send `Idempotency-Key` headers on all `POST /firs`, `POST /chargesheet/upload`, `POST /ingest` requests. Server retains the first response for 24 h.
- **Backwards compatibility**: additive fields will be introduced without a major-version bump. Removing or renaming fields requires `/api/v2`.
- **Localisation**: all natural-language fields are stored verbatim. Clients should not transliterate or translate before storage.

---

*End of API Reference.*
