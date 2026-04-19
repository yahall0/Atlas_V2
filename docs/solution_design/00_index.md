# ATLAS Platform — Solution Documentation

| Document Attribute | Value |
|---|---|
| Suite ID | ATLAS-SUITE-001 |
| Version | 1.0 |
| Status | Issued for Review |
| Classification | Restricted — Internal & Authorised External Reviewers |
| Issue Date | 2026-04-19 |
| Document Owner | Programme Management Office |

---

## 1. Purpose
This index governs the ATLAS Platform solution documentation suite. Every artefact in this suite is authoritative for its scope and is the reference of record for all engineering, operations, security and assurance activities.

## 2. Reading order

| Audience | Recommended order |
|---|---|
| Programme leadership | §1, §3 of [SDD](01_solution_design_document.md); [§15 Risk Register](01_solution_design_document.md#15-risk-register); [§16 Roadmap](01_solution_design_document.md#16-roadmap-and-release-plan) |
| Architecture Review Board | Full [SDD](01_solution_design_document.md); [Security and Compliance](04_security_and_compliance.md) |
| Engineering | [SDD](01_solution_design_document.md) → [Data Dictionary](02_data_dictionary.md) → [API Reference](03_api_reference.md) → [Operations Runbook](05_operations_runbook.md) |
| Security and Audit | [Security and Compliance](04_security_and_compliance.md); §9 of [SDD](01_solution_design_document.md); audit-relevant sections of [Operations Runbook](05_operations_runbook.md) |
| Operations / SRE | [Operations Runbook](05_operations_runbook.md); §13 of [SDD](01_solution_design_document.md) |

## 3. Document inventory

| # | Document | Status | Description |
|---|---|---|---|
| 01 | [Solution Design Document](01_solution_design_document.md) | Issued for Review | Master design — business context, architecture, modules, NFRs, risks, governance |
| 02 | [Data Dictionary](02_data_dictionary.md) | Issued for Review | Authoritative table-by-table data definitions, sensitivity, retention |
| 03 | [API Reference](03_api_reference.md) | Issued for Review | Complete REST endpoint catalogue with conventions, payloads, errors |
| 04 | [Security and Compliance](04_security_and_compliance.md) | Issued for Review | Control catalogue, statutory mappings (DPDP / BSA / IT Act), audit chain |
| 05 | [Operations Runbook](05_operations_runbook.md) | Issued for Review | SLOs, deployment, monitoring, incident response, backup and restore |

## 4. Companion artefacts (existing)

| Artefact | Path | Owner |
|---|---|---|
| Architecture Decision Records | [docs/decisions/](../decisions/) | Architecture Review Board |
| Mindmap integration guide | [docs/integration/mindmap-backend-integration.md](../integration/mindmap-backend-integration.md) | Platform Engineering |
| Chargesheet gap integration guide | [docs/integration/chargesheet-gap-backend-integration.md](../integration/chargesheet-gap-backend-integration.md) | Platform Engineering |
| FIR legal standards reference | [docs/R01-fir-legal-standards.md](../R01-fir-legal-standards.md) | Programme Management |
| Legal sections corpus | [backend/app/legal_sections/](../../backend/app/legal_sections/) | Platform Engineering |

## 5. Naming and version control

- Documents are stored as plain Markdown in `docs/solution_design/`.
- Filenames follow `NN_kebab-case.md` to preserve reading order.
- Each document carries a header table with Document ID, version, status, classification, issue date and owner.
- Material changes increment the document version (semver applied: major for structural, minor for content, patch for typographical).
- All updates pass through the Pull Request process with peer review and, for security-relevant changes, Security Office sign-off.

## 6. Status definitions

| Status | Meaning |
|---|---|
| Draft | Author working copy; not for distribution |
| Issued for Review | Released for stakeholder review; comments welcome |
| Approved | Signed off by named approver; in force |
| Superseded | Replaced by a later version |
| Retired | No longer in force |

## 7. Distribution and access

The suite is restricted. Access is granted by the Programme Management Office on need-to-know basis. External recipients must execute the standard non-disclosure agreement before distribution.

## 8. Amendment record

| Version | Date | Author | Description |
|---|---|---|---|
| 1.0 | 2026-04-19 | Platform Engineering | Initial issue of consolidated documentation suite |

---

*End of Index.*
