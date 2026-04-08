# ADR-D03: RBAC Matrix and Data Access Control

**Status:** Accepted  
**Date:** 2026-04-08  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Sprint Gate:** Sprint 2

## Context

The ATLAS Platform handles sensitive police FIR data subject to:
- **BNS §73 / Section 228A CrPC** — prohibition on disclosing victim identity in sexual offence cases.
- **Gujarat Police data classification policy** — FIR data classified as Confidential.
- **Operational need** — Investigating Officers (IO) need full access to their cases; higher officers need district/state aggregates.

Six user roles exist in the system:

| Role | Description |
|---|---|
| `IO` | Investigating Officer — files FIRs, sees own district cases |
| `SHO` | Station House Officer — supervises IOs, same district scope |
| `DYSP` | Deputy Superintendent — multi-station oversight |
| `SP` | Superintendent of Police — district-wide command |
| `ADMIN` | System administrator — full access, user management |
| `READONLY` | Auditor / analyst — read-only, fully masked PII |

## Decision

### 1. District Scoping

IO and SHO roles are **district-scoped**: all list/read queries automatically filter on `firs.district = user.district`. DYSP, SP, ADMIN, and READONLY roles receive unscoped results.

### 2. PII Masking Matrix

| Field | ADMIN / SP | IO / SHO | DYSP | READONLY |
|---|---|---|---|---|
| Aadhaar number | Visible | `[AADHAAR]` | `[AADHAAR]` | `[AADHAAR]` |
| Phone number | Visible | `[PHONE-XXXX]` (last 4) | `[PHONE-XXXX]` | `[PHONE-XXXX]` |
| Complainant name | Full | Full | First + last initial | First + last initial |
| Victim name (§376+) | `[VICTIM-PROTECTED]` | `[VICTIM-PROTECTED]` | `[VICTIM-PROTECTED]` | `[VICTIM-PROTECTED]` |
| Place address (§376+) | `[ADDRESS-PROTECTED]` | `[ADDRESS-PROTECTED]` | `[ADDRESS-PROTECTED]` | `[ADDRESS-PROTECTED]` |

**Victim identity masking is unconditional for all roles** when `primary_sections` contains any BNS §63-99 or legacy IPC §376 family section.

### 3. Write Permissions

| Endpoint | Required Role(s) |
|---|---|
| `POST /firs` | IO, SHO, ADMIN |
| `PATCH /firs/{id}/classification` | SHO, DYSP, SP, ADMIN |
| `POST /predict/classify` (with `fir_id`) | SHO, DYSP, SP, ADMIN |
| `POST /predict/classify` (no `fir_id`) | IO, SHO, DYSP, SP, ADMIN |
| `GET /firs`, `GET /firs/{id}` | All authenticated roles |
| `GET /dashboard/stats` | All authenticated roles |

### 4. Audit Logging

All write operations (FIR create, classification patch) are inserted into `audit_log` with `user_id`, `action`, `resource_type`, `resource_id`, and `details`.

## Consequences

### Positive
- Clear, auditable access boundary between ranks.
- Victim identity protection is code-enforced, not relying on caller discipline.

### Negative / Risks
- Guest / unauthenticated access returns 403 — all dashboards require login.
- If a FIR has both a BNS §376 section and a theft section, full victim masking still applies; this is by design.

## Sprint 2 Acceptance Criteria

- [ ] `PATCH /firs/{id}/classification` rejects IO callers with HTTP 403.
- [ ] FIRs with `primary_sections=["376"]` return `complainant_name="[VICTIM-PROTECTED]"` for all roles.
- [ ] `GET /dashboard/stats` returns HTTP 403 for unauthenticated requests.
- [ ] Audit log row created for each `PATCH /firs/{id}/classification` call.
