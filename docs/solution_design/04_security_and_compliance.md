# ATLAS Platform — Security and Compliance

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-SEC-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted |
| Issue Date | 2026-04-19 |
| Document Owner | Security Officer |
| Companion to | [Solution Design Document](01_solution_design_document.md) |

---

## 1. Purpose
This document sets out the security architecture, control catalogue, and compliance posture of the ATLAS Platform. It is the reference of record for the Security Office, internal audit, and external assessors.

## 2. Scope
- All ATLAS application services and infrastructure deployed within the Gujarat State Data Centre (GSDC).
- All persistent and transient data handled by the platform.
- All identities (human and service) that access the platform.

## 3. Statutory and regulatory context

| Reference | Title | Applicability |
|---|---|---|
| DPDP Act | Digital Personal Data Protection Act, 2023 | Personal data of complainants, accused, witnesses |
| BSA | Bharatiya Sakshya Adhiniyam, 2023 | Admissibility of records in criminal proceedings |
| BNSS | Bharatiya Nagarik Suraksha Sanhita, 2023 | Procedural compliance for FIR/chargesheet workflow |
| IT Act | Information Technology Act, 2000 (with amendments) | "Reasonable security practices and procedures" obligations |
| CERT-In | Indian Computer Emergency Response Team Directions, 2022 | Incident reporting timelines, log retention |
| ISO/IEC 27001:2022 | Reference framework | Aligned (not yet certified) |

## 4. Security architecture

### 4.1 Trust boundaries

```
┌────────────────────── Untrusted (police-station LAN) ──────────────────────┐
│  Browser │ Tablet │ Desk PC                                               │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ TLS 1.3 (mutual where supported)
┌──────────────────────────────▼─────────── DMZ (GSDC) ───────────────────────┐
│  Reverse proxy / WAF                                                       │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ Internal mTLS (service-to-service)
┌──────────────────────────────▼─────────── Application zone ─────────────────┐
│  ATLAS API · Worker nodes                                                  │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ Authenticated, encrypted DB protocol
┌──────────────────────────────▼─────────── Data zone ────────────────────────┐
│  PostgreSQL · Redis · MongoDB · Backup vault                              │
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Authentication
- Password-based login over TLS, bcrypt with cost factor 12.
- Successful login issues a JWT access token (HS256, 30-minute TTL) and a refresh token (24-hour TTL, rotating).
- Failed-login throttling: 5 failures / 5 minutes triggers a 15-minute lockout.
- Future: integration with the State Single Sign-On directory (SAML 2.0).

### 4.3 Authorisation
- RBAC enforced at the API and the data layer.
- District scoping enforced as a query filter for `IO` and `SHO`.
- Sensitive endpoints (KB publication, user management) restricted to `ADMIN`.
- Quarterly access reviews are mandatory and recorded.

### 4.4 RBAC matrix (definitive)

| Capability | ADMIN | SP | DYSP | SHO | IO | READONLY |
|---|---|---|---|---|---|---|
| Create FIR | ✓ | | | ✓ | ✓ | |
| Read FIR (own scope) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Override classification | ✓ | ✓ | ✓ | ✓ | | |
| Upload chargesheet | ✓ | | | ✓ | ✓ | |
| Read chargesheet (scope) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Endorse chargesheet | ✓ | | | ✓ | | |
| Generate / regenerate mindmap | ✓ | | | ✓ | ✓ | |
| Update node status | ✓ | | | ✓ | ✓ | |
| Run / re-run gap analysis | ✓ | | | ✓ | ✓ | |
| Act on a gap (accept/modify/dismiss) | ✓ | | | ✓ | ✓ | |
| Create / edit KB content | ✓ | | | | | |
| Publish KB version | ✓ | | | | | |
| User management | ✓ | | | | | |
| Audit-log read | ✓ | ✓ | ✓ | | | |
| Metrics read | ✓ | | | | | |
| Bulk export | ✓ | ✓ | | | | |

### 4.5 Cryptography

| Use | Algorithm | Key length | Custodian |
|---|---|---|---|
| TLS in transit | TLS 1.3 | RSA 2048 / ECDSA P-256 | GSDC PKI |
| Token signing | HS256 | 256-bit | Application secrets vault |
| Disk-at-rest | AES-256-XTS | 256-bit | GSDC storage layer |
| Column-level (sensitive PII) | AES-256-GCM (`pgcrypto`) | 256-bit | Application key, rotated 90 days |
| Audit chain | SHA-256 | n/a (hash) | Application |
| Password hashing | bcrypt cost 12 | n/a | Application |

Key rotation procedure: see [Operations Runbook §8](05_operations_runbook.md#8-key-and-secret-rotation).

### 4.6 Personal data handling
- **Lawful basis**: Section 7(b) DPDP Act (compliance with law) for accused/witness PII; legitimate use for users.
- **Data minimisation**: only fields prescribed by BNSS form Part-I/II are captured.
- **Storage limitation**: minimum seven (7) years post-disposal; subject to legal hold.
- **Auto-redaction in logs**: a single function `core.pii.redact()` is applied to every structured log payload, replacing identifiers with format-preserving placeholders (e.g. `<AADHAAR:****1234>`).

### 4.7 Tamper-evident audit chain
- Every state-changing action writes one record to `audit_log`.
- Record hash: `entry_hash = SHA256(previous_hash || canonical_json(entry))`.
- Properties:
  - **Append-only**: a database trigger rejects `UPDATE` and `DELETE`.
  - **Cryptographic continuity**: removing or altering any record breaks the chain at the affected point and all subsequent records.
  - **Verifiable export**: per-case export contains the chain segment and a verification routine.
- Standard actions logged include but are not limited to:
  `LOGIN_SUCCESS`, `LOGIN_FAILED`, `FIR_CREATED`, `FIR_CLASSIFICATION_OVERRIDDEN`, `CHARGESHEET_UPLOADED`, `CHARGESHEET_REVIEWED`, `CHARGESHEET_FLAGGED`, `MINDMAP_GENERATED`, `MINDMAP_NODE_STATUS_UPDATED`, `GAP_REPORT_GENERATED`, `GAP_ACTION_TAKEN`, `KB_PUBLISHED`, `USER_CREATED`, `USER_DEACTIVATED`, `MODEL_DEPLOYED`.

## 5. Network security

| Control | Implementation |
|---|---|
| Network segmentation | Three zones — DMZ, Application, Data — enforced by GSDC firewall |
| Egress restriction | Outbound network access denied at runtime; allow-list only for backup vault and monitoring |
| Reverse proxy | nginx with WAF rules (OWASP CRS), rate-limit, request-size cap |
| Service-to-service | mTLS where supported, internal-only addresses |
| Inbound from stations | TLS 1.3 only; HSTS; client IP whitelisting at firewall |

## 6. Application security

| Domain | Control |
|---|---|
| Input validation | Pydantic schemas at all API boundaries; rejection on validation failure |
| Output encoding | All responses are JSON; no template rendering on the API tier |
| File uploads | MIME-sniffed (not just suffix-checked); virus-scanned by GSDC scanner; PDF only |
| Object access | All read/write goes through CRUD layer enforcing RBAC + scoping |
| Secrets | Kept in environment variables sourced from GSDC secrets vault; never in source control |
| Dependency scanning | Pre-commit + nightly; PRs blocked on High/Critical findings |
| Static analysis | flake8 (current), mypy (planned), bandit (planned) |
| Container hardening | Multi-stage build; runtime user is non-root; no shell in production image |

## 7. Cryptographic key management

| Key type | Storage | Rotation | Backup |
|---|---|---|---|
| TLS keys | GSDC PKI | 12 months | Sealed offline copy |
| JWT signing key | Secrets vault, bound to running pod | 90 days | Two-of-three custodian split |
| Column encryption keys | Secrets vault, application reads at boot | 90 days | Two-of-three custodian split |
| Backup encryption keys | Backup vault | 12 months | Custodian split |

## 8. Logging, monitoring and incident response

### 8.1 Logging
- Structured JSON logs (ECS schema) emitted to `stdout` and shipped to GSDC log aggregator.
- Log levels: DEBUG (dev only), INFO (default), WARNING, ERROR.
- Required fields per record: `timestamp`, `service`, `trace_id`, `user.id` (if available), `event`, `outcome`.
- PII redaction applied unconditionally.

### 8.2 Monitoring (security signals)
- Failed-login spikes, privilege-escalation attempts, audit-chain verification failures, unusual export volumes.
- Alerts routed to Security Office via on-call rotation.

### 8.3 Incident response
1. **Detect**: alert raised by monitoring or reported by user.
2. **Contain**: revoke affected tokens; restrict network if necessary.
3. **Eradicate**: patch root cause; redeploy.
4. **Recover**: validate audit chain; restore from clean backup if needed.
5. **Post-incident**: file CERT-In notification within statutory timelines (6 hours for prescribed incidents); root-cause review within 5 business days; remediation tracked.

### 8.4 Statutory reporting timelines

| Incident class | Notify | Within |
|---|---|---|
| Cyber incident under CERT-In Direction 2022 | CERT-In | 6 hours |
| Personal data breach affecting principals | Data Protection Board | 72 hours (best practice) |
| Loss of evidentiary integrity (audit chain) | DGP, Public Prosecutor | Immediately |

## 9. Compliance posture

### 9.1 Mapping to ISO/IEC 27001:2022 (selected Annex A)

| Control | Implementation in ATLAS |
|---|---|
| A.5.1 Policies for information security | Programme charter + this document |
| A.5.10 Acceptable use | Operations runbook §13 |
| A.5.15 Access control | RBAC, district scoping |
| A.5.18 Access rights | Quarterly access review |
| A.5.23 Cloud services security | N/A (on-premise) |
| A.5.30 ICT readiness for business continuity | DR drills, RTO/RPO targets |
| A.6.1 Screening | HR-led, recorded |
| A.7.4 Physical security monitoring | GSDC |
| A.8.1 User endpoint devices | Browser-only access; no client install |
| A.8.5 Secure authentication | JWT + bcrypt + lockout |
| A.8.9 Configuration management | IaC (Docker Compose), reviewed |
| A.8.12 Data leakage prevention | Egress restriction; immutable raw store |
| A.8.15 Logging | Structured JSON, ECS, retained |
| A.8.16 Monitoring activities | Prometheus + alerting |
| A.8.24 Use of cryptography | Documented in §4.5 |
| A.8.28 Secure coding | Static analysis, peer review |
| A.8.32 Change management | ARB sign-off, staging gate |

### 9.2 DPDP Act mapping (selected)

| DPDP requirement | ATLAS control |
|---|---|
| Notice and consent (where applicable) | UI screens for end users; legal basis recorded for principals |
| Lawful processing | Section 7(b) compliance with law for case principals |
| Data minimisation | Capture limited to BNSS-prescribed fields |
| Storage limitation | Retention schedule + legal hold |
| Accuracy and rectification | Manual override workflow; audit-trailed |
| Security safeguards | Controls in §4–§8 |
| Data principal rights | Dedicated request-handling SOP outside platform |
| Breach notification | §8.4 |

## 10. Threat model (summary)

The Operational Threat Model is maintained separately as a STRIDE matrix; the headline threats and mitigations are reproduced below.

| Threat | Vector | Mitigation |
|---|---|---|
| Spoofing of authenticated user | Credential theft | bcrypt, lockout, future SSO/MFA |
| Tampering with audit log | Privileged DB access | Append-only trigger + hash chain + split DBA role |
| Tampering with raw documents | Storage write | Immutable GridFS with content-hash addressing |
| Repudiation of an action | Lack of audit | Every state change logged with actor and outcome |
| Information disclosure (PII) | Excess access | RBAC + district scoping + log redaction |
| Denial of service | Floods, large uploads | Rate limit, request-size cap, async ingestion |
| Elevation of privilege | Application bug | Static analysis, peer review, principle of least privilege |
| Misclassification by ML model | Erroneous suggestion | Human-in-the-loop, explainability, model evaluation |
| Supply-chain compromise | Malicious dependency | Lockfiles, dependency scanning, internal mirror |
| Insider misuse | Authorised user | Quarterly access review, behavioural monitoring |

## 11. Compliance assertions and evidence

For each control in §4–§9, the Security Office maintains an evidence binder with the artefact references below. The binder is made available during internal and external audit.

| Domain | Evidence references |
|---|---|
| Access control | RBAC matrix, quarterly review minutes, sample audit-log queries |
| Cryptography | Key rotation log, certificate inventory, KMS audit |
| Logging and monitoring | Log retention configuration, alert rules, sample dashboards |
| Incident response | Drill records, post-incident reviews, CERT-In submissions |
| Backup and recovery | Backup verification reports, DR drill records |
| Change management | ARB minutes, deployment records, rollback drills |

---

*End of Security and Compliance.*
