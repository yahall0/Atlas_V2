# ATLAS Platform — Operations Runbook

| Document Attribute | Value |
|---|---|
| Document ID | ATLAS-OPS-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted |
| Issue Date | 2026-04-19 |
| Document Owner | Platform Engineering Lead |
| Audience | Platform Engineering, GSDC Operations, Security Office, on-call responders |

---

## 1. Purpose and scope
This runbook governs the day-to-day operations of the ATLAS Platform in staging and production. It covers routine procedures, service-level targets, monitoring, incident response, backup and restore, capacity management, and change management. It is updated quarterly and on every material change.

## 2. Service catalogue

| Service | Runtime | Port | Dependency |
|---|---|---|---|
| `atlas-api` | FastAPI + Uvicorn | 8000 | db, redis, mongodb |
| `atlas-frontend` | Next.js (`next start`) | 3000 | atlas-api |
| `atlas-db` | PostgreSQL 15 + pgvector | 5432 | — |
| `atlas-redis` | Redis 7 | 6379 | — |
| `atlas-mongodb` | MongoDB 7 | 27017 | — |
| `atlas-prometheus` | Prometheus | 9090 | scrapes atlas-api |
| `atlas-grafana` | Grafana | 3001 | atlas-prometheus |
| `atlas-mlflow` | MLflow tracking server | 5000 | storage backend |
| `atlas-labelstudio` | Label Studio (annotation) | 8080 | atlas-db |

## 3. Environments

| Environment | Host | URL | Purpose |
|---|---|---|---|
| `dev` | Developer workstations | `http://localhost:3000` | Individual development |
| `int` | Continuous integration | ephemeral | Automated testing |
| `staging` | GSDC staging cluster | `https://atlas-staging.<domain>` | Pre-production validation |
| `prod` | GSDC production cluster | `https://atlas.<domain>` | Live operations |

## 4. Service level objectives (SLO)

| # | SLI | Target | Measurement window |
|---|---|---|---|
| SLO-01 | Monthly availability | ≥ 99.5 % | Rolling 30 days |
| SLO-02 | API read latency p95 | ≤ 500 ms | Rolling 7 days |
| SLO-03 | API write latency p95 | ≤ 1000 ms | Rolling 7 days |
| SLO-04 | FIR ingestion (typed PDF) p95 | ≤ 8 s | Rolling 7 days |
| SLO-05 | Gap analysis p95 | ≤ 10 s | Rolling 7 days |
| SLO-06 | Error rate (5xx) | ≤ 0.5 % | Rolling 24 hours |
| SLO-07 | Audit chain verification failures | 0 | Immediate |

**Error budget** is consumed when SLOs are missed; exhaustion freezes feature deployments.

## 5. Deployment

### 5.1 Change-advisory gates

| Gate | Required approver | Evidence |
|---|---|---|
| G1 Design | Architecture Review Board | ADR or design note |
| G2 Code review | Peer reviewer | Pull request approval |
| G3 Security review | Security Office (for sensitive changes) | Security sign-off |
| G4 Staging validation | QA Lead | Test evidence |
| G5 Production release | Platform Engineering Lead | Release record |

### 5.2 Promotion path
`dev` → `int` (automated on PR) → `staging` (manual trigger) → `production` (manual trigger with G5).

### 5.3 Production release procedure
1. Confirm error-budget headroom and absence of open P1 incidents.
2. Announce maintenance window to DGP-Modernisation and district liaisons.
3. Take pre-release backup (see §7).
4. Deploy new image tags via GitOps pipeline.
5. Run Alembic migrations: `alembic upgrade head`.
6. Wait for readiness probes to report healthy on all replicas.
7. Smoke test: `GET /api/v1/health` and three canary user journeys (login, FIR read, chargesheet read).
8. Post-release: monitor dashboards for 30 minutes; close release record.

### 5.4 Rollback procedure
1. Re-deploy prior image tag.
2. If the migration is not backwards-compatible, restore from pre-release backup (requires change-manager authorisation).
3. Verify audit chain integrity post-rollback.

## 6. Monitoring and alerting

### 6.1 Dashboards
- **Platform health** — request rate, latency, error rate by endpoint.
- **Ingestion** — OCR job queue depth, failure rate, median duration.
- **ML** — classifier confidence distribution, drift indicators.
- **Security** — failed-login rate, RBAC denials, audit-chain status.
- **Infrastructure** — CPU, memory, disk, replication lag.

### 6.2 Alerts (selected)

| Alert | Condition | Severity | Action |
|---|---|---|---|
| API 5xx rate elevated | > 1 % for 5 minutes | P2 | Page on-call engineer |
| DB replication lag | > 60 seconds for 10 minutes | P2 | Page DBA |
| Audit-chain break detected | Any occurrence | P1 | Page Security + DBA |
| OCR queue depth | > 500 for 15 minutes | P3 | Ticket to platform eng. |
| Login-failure spike | > 20/minute sustained | P2 | Page Security |
| Disk utilisation | > 85 % | P2 | Page platform eng. |
| Certificate expiring | ≤ 30 days | P3 | Ticket to platform eng. |

### 6.3 Severity and response targets

| Severity | Examples | Acknowledge | Restore |
|---|---|---|---|
| P1 | Full outage, audit break, data-integrity risk | 15 min | 4 h |
| P2 | Degraded service, partial outage | 30 min | 8 h |
| P3 | Non-urgent ops issues | Next business day | 5 days |

## 7. Backup and restore

### 7.1 Backup schedule

| Asset | Method | Frequency | Retention |
|---|---|---|---|
| PostgreSQL base backup | `pg_basebackup` | Daily 02:00 IST | 30 days rolling |
| PostgreSQL WAL | Continuous archiving | Continuous | 30 days rolling |
| MongoDB | `mongodump` snapshot | Daily 02:30 IST | 30 days rolling |
| Raw document store | Content-hash-addressed, immutable | On write (by design) | Coterminous with case |
| Configuration / secrets | Secrets vault snapshot | On change | Vendor-defined |
| Model artefacts (MLflow) | Volume snapshot | On release | 12 months |

All backups are encrypted with keys held in the GSDC backup vault. Weekly snapshots are copied off-site to a secondary GSDC facility.

### 7.2 Restore procedures

**PostgreSQL point-in-time recovery (PITR)** — target RPO 15 minutes:
1. Identify target timestamp.
2. Stop application.
3. Restore most recent base backup to scratch cluster.
4. Replay WAL up to target timestamp.
5. Validate data integrity (row counts, audit-chain verification).
6. Promote and reconnect application.
7. Reconcile any work lost during the window — IO manual re-entry if required.

**MongoDB restore** — target RPO 24 hours (documents are immutable so primary RPO applies to structured metadata only).

**DR rehearsal** — half-yearly, full-system restore to the secondary GSDC facility; recorded in the DR log.

## 8. Key and secret rotation

| Secret | Rotation | Procedure | Downtime |
|---|---|---|---|
| TLS certificates | 12 months (or on compromise) | Renew via GSDC PKI, hot-reload in nginx | None |
| JWT signing key | 90 days | Dual-key overlap: new key active for issuance, old key active for validation for 24 hours | None |
| DB passwords | 180 days | Rotate; update secrets vault; rolling app restart | None (rolling) |
| Column encryption keys | 90 days | Re-encrypt in background; retain old key until migration complete | None |
| Admin credentials | On personnel change | HR-triggered; audit entry | None |

## 9. Capacity management

### 9.1 Sizing baseline (production)

| Tier | Initial | Scale-up trigger |
|---|---|---|
| API | 4 nodes × (4 vCPU / 8 GB) | Sustained CPU > 70 % for 30 minutes |
| DB primary | 1 node × (8 vCPU / 32 GB) | Sustained CPU > 70 % or free space < 20 % |
| DB standby | 1 node mirror of primary | n/a |
| Redis | 1 node × (2 vCPU / 4 GB) + sentinel | Memory > 75 % |
| MongoDB | 3-node replica set × (4 vCPU / 16 GB) | Disk > 70 % |
| Observability | 1 node × (4 vCPU / 8 GB) | Retention change |

### 9.2 Growth projection
- FIR corpus: ~800,000/year; assume 20 KB structured + 1 MB raw average → ~850 GB/year pending compression.
- Audit log: ~20 writes/FIR → 16 M rows/year.

## 10. Database administration

### 10.1 Roles (least-privilege)

| Role | Purpose | Notes |
|---|---|---|
| `atlas_app` | Application runtime user | Read/write on operational tables; no privileges on `audit_log` DDL |
| `atlas_migrator` | Migration runner | Schema DDL; used only by Alembic on release |
| `atlas_readonly` | Analytics / dashboards | Read on operational tables only |
| `atlas_audit_reader` | Read `audit_log` | Separate role, assigned to Security/Audit |
| `atlas_dba_break_glass` | Administrative intervention | Dual-control; every session logged; see §11 |

### 10.2 Migrations
- Forward-only, peer-reviewed.
- `alembic upgrade head` run during release; failure aborts the release.
- Destructive migrations require a documented rollback plan and a verified restore on staging.

## 11. Break-glass access
- Break-glass DBA access is granted by the duty Security Officer for a bounded window.
- Session is recorded; actions are reconciled against the approved ticket within 24 hours.
- The audit-chain verification must be run before and after every break-glass session.

## 12. On-call and escalation

| Rotation | Composition | Primary coverage |
|---|---|---|
| Platform primary | Platform engineers | 24/7 |
| Platform secondary | Platform engineering lead | Escalation |
| ML primary | ML engineers | Business hours; extended for release weeks |
| Security primary | Security officers | 24/7 |
| Database primary | Database administrator | 24/7 |

Escalation: primary → secondary → Platform Engineering Lead → Programme Director.

## 13. Operational runbooks (common procedures)

The procedures below are indicative; full step-by-step scripts are maintained in the runbook repository.

### 13.1 OCR queue is backing up
1. Check `atlas-api` logs for Tesseract failures.
2. Inspect `ocr_jobs` for `status = 'failed'` and triage by `error_message`.
3. If a transient DB outage occurred, retry failed jobs.
4. If the backlog exceeds the 15-minute SLO, scale the worker replica count.

### 13.2 Unusual login-failure volume
1. Correlate against source IP ranges.
2. If concentrated, firewall-block the offending range and notify Security.
3. Check for credential-stuffing indicators (uniform spread across multiple usernames).

### 13.3 Audit-chain verification failure
1. Page Security **and** DBA.
2. Freeze any changes to `audit_log`.
3. Run the verification script to identify the first broken index.
4. Compare against the most recent pre-incident backup.
5. File incident report; notify DGP and Public Prosecutor (see [Security §8.4](04_security_and_compliance.md#84-statutory-reporting-timelines)).

### 13.4 High-priority data correction
- Never `UPDATE`/`DELETE` directly on production.
- Use the application's administrative endpoint or an approved correction script; every change must append to the audit chain.

## 14. Model lifecycle management

| Stage | Artefacts | Ownership |
|---|---|---|
| Training | Dataset, config, training script | ML Engineering |
| Evaluation | Model card, metrics, bias report | ML Engineering |
| Approval | Review minutes | ML Engineering + Security (for release) |
| Deployment | Tagged model in MLflow registry; version stamp in `nlp_model_version` | Platform Engineering |
| Monitoring | Drift dashboards, confidence distributions | ML Engineering |
| Retirement | Archived with model card | ML Engineering |

## 15. Change and release calendar

- Regular release window: Tuesday 22:00–00:00 IST (outside station peak hours).
- Emergency change: authorised by Platform Engineering Lead with post-hoc ARB ratification within five business days.
- Freeze: 24 hours before and 24 hours after each district-rollout "go-live".

## 16. Documentation and tooling

| Artefact | Location |
|---|---|
| This runbook | `docs/solution_design/05_operations_runbook.md` |
| SDD | `docs/solution_design/01_solution_design_document.md` |
| Data dictionary | `docs/solution_design/02_data_dictionary.md` |
| API reference | `docs/solution_design/03_api_reference.md` |
| Security and compliance | `docs/solution_design/04_security_and_compliance.md` |
| Architecture Decision Records | `docs/decisions/ADR-D*.md` |
| Integration guides | `docs/integration/*.md` |
| Runbook scripts | `scripts/` |

## 17. Review and approval

- This document is reviewed quarterly and on every material operational change.
- Any update requires sign-off by: Platform Engineering Lead, Security Officer, GSDC Operations Manager.

---

*End of Operations Runbook.*
