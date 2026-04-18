# ADR-D13: Chargesheet Mindmap — Template-driven advisory tree with ML supplementation

**Status:** Accepted  
**Date:** 2026-04-18  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Task:** T53-M

## Context

Gujarat Police requires Investigating Officers (IOs) to receive structured investigation guidance immediately upon FIR ingestion. This guidance must be:

1. **Case-type-aware** — different offence categories (theft, assault, cybercrime, etc.) demand different investigation steps, evidence types, and legal considerations.
2. **Advisory, not prescriptive** — the mindmap provides recommendations; the IO retains full discretion over the investigation.
3. **Integrated with the existing FIR pipeline** — must consume outputs from T46 (chargesheet ingestion), T47 (field extraction), T48 (completeness checking), T28 (BNS/IPC classifier), and T55 (evidence gap analysis).
4. **Auditable** — all generated nodes, status changes, and AI suggestions must maintain a tamper-evident trail for potential evidentiary value in court proceedings.

## Decision

### 1. Template-driven approach over pure ML

Static JSON templates are maintained per case category. Each template defines a tree of investigation nodes (evidence to collect, witnesses to examine, forensic steps, legal provisions to verify). ML-generated suggestions supplement the template but **never override** template-defined nodes.

**Rationale:** Legal accuracy requires that templates be reviewed and vetted by legal experts and senior officers. A pure ML approach would require continuous monitoring for legal correctness and could produce hallucinated or outdated guidance. Templates provide a predictable, verifiable baseline; ML adds case-specific detail on top.

### 2. Append-only status audit trail

Node status changes (e.g., `pending` -> `in_progress` -> `completed` -> `not_applicable`) are stored in an append-only audit table. Each row includes a SHA-256 hash of the previous row's hash concatenated with the current row's payload, forming a hash chain.

- `UPDATE` and `DELETE` operations on the audit table are rejected by a database trigger.
- This ensures tamper evidence: any retroactive modification breaks the hash chain and is detectable during verification.
- The hash chain can be independently verified by court-appointed technical auditors.

### 3. Disclaimer policy

All AI-generated content carries advisory disclaimers to ensure no IO mistakes ML output for binding legal instruction:

- **Node-level indicators:** Nodes originating from ML suggestions display an inline disclaimer icon and tooltip distinguishing them from template-sourced nodes.
- **Panel-level banner:** A non-dismissable banner is displayed at the top of the mindmap panel stating that all content is advisory and does not constitute legal direction.
- **Export watermark:** Any exported or printed mindmap includes a footer disclaimer.

### 4. Regeneration vs. editing

Existing mindmaps are **never edited in place**. When regeneration is triggered (e.g., after new evidence is ingested or the case category is reclassified), a new version of the mindmap is created. The previous version is retained and remains accessible.

**Rationale:** This preserves the audit trail — every version represents a point-in-time snapshot. IOs and supervisors can compare versions to understand how guidance evolved as the investigation progressed.

### 5. Feature flag

The feature is gated behind the `ATLAS_MINDMAP_ENABLED` environment variable (default: `false`). Templates must be formally signed off by the Nodal Officer before the flag is enabled in any production deployment.

**Rationale:** Deploying advisory legal content without explicit sign-off from the designated authority creates liability risk. The feature flag ensures the system is technically ready but only activated after procedural approval.

## Consequences

### Positive

- Predictable, auditable, legally vetted investigation guidance out of the box via templates.
- ML supplements enhance templates with case-specific suggestions without risk of overriding legal correctness.
- Full append-only audit trail with SHA-256 hash chain verification provides tamper evidence suitable for court proceedings.
- Version-based regeneration preserves complete history of guidance evolution.
- Feature flag prevents premature deployment of unreviewed content.

### Negative / Risks

- Template maintenance requires manual updates when laws change (e.g., BNS amendments, new Supreme Court directives). A review cadence must be established.
- Regeneration creates new versions rather than editing in place, which may initially confuse users accustomed to in-place editing. Mitigated by UI cues showing version history.
- ML supplementation quality depends on the underlying classifier (T28) and evidence gap analyser (T55); low-confidence upstream outputs reduce suggestion relevance.

## Related ADRs

- **ADR-D01** — Modular monolith architecture (deployment model)
- **ADR-D03** — RBAC matrix (role-based access to mindmap features)
- **ADR-D06** — Multilingual pipeline (language handling for template matching and ML inference)
