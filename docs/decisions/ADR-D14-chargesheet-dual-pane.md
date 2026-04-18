# ADR-D14: Chargesheet Dual-Pane Gap Analysis — Aggregation, Provenance, Append-only Actions, Triple-Export Model

**Status:** Accepted  
**Date:** 2026-04-18  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Task:** T56-E

## Context

Gujarat Police Investigating Officers preparing chargesheets face a recurrent problem: critical gaps (missing evidence, incorrect legal sections, absent witness bayans, procedural omissions) are discovered only after the chargesheet is filed in court, leading to supplementary chargesheets, judicial criticism, and in some cases, acquittals on procedural grounds.

ATLAS already produces several independent analyses of chargesheet quality:

1. **T54 Legal Validator** — rule-based checks for section applicability, mandatory legal provisions, and cross-section consistency.
2. **T55 Evidence Gap Classifier** — ML-based identification of missing evidence categories given the offence type and investigation record.
3. **T53-M Mindmap** — template-driven investigation guidance with status tracking; divergence between "addressed" mindmap nodes and actual chargesheet content indicates work that was planned but not reflected.
4. **Completeness Rules** — static JSON rules checking for mandatory fields (witness schedule, accused particulars, seizure memos, IO identification, charges, filing date).

Each of these produces useful output individually, but IOs currently must navigate to separate screens, mentally merge findings, and decide what to fix. There is no unified view, no combined severity ranking, and no audit trail of which gaps were addressed, dismissed, or escalated.

The Chargesheet Dual-Pane Gap Analysis feature (T56-E) addresses this by:

- Presenting a split-screen view: chargesheet document on the left, aggregated gap list on the right.
- Aggregating all gap sources server-side into a single ranked report.
- Providing append-only, hash-chained actions on each gap for audit integrity.
- Offering three distinct export formats for different audiences (court, internal, supervisor).

## Decision

### 1. Backend aggregation over frontend composition

Gap aggregation happens entirely on the server side. The frontend receives a single `GapReportResponse` containing all gaps from all sources, already deduplicated, severity-ranked, and enriched with remediation steps.

**Rationale:**

- **Audit integrity:** A server-side snapshot is immutable once persisted. If aggregation happened client-side, different clients could produce different views of the same data, undermining auditability.
- **Snapshot immutability:** Each report is a point-in-time snapshot. The aggregator reads from T54, T55, mindmap, and completeness sources at generation time. Subsequent changes to upstream data do not retroactively alter existing reports; a reanalysis creates a new version.
- **Performance:** Aggregation involves database queries against 4-5 tables, deduplication logic, and severity sorting. Doing this server-side avoids multiple round-trips from the browser and keeps the frontend thin.
- **RBAC uniformity:** Access control decisions (district scoping, role-based visibility) are enforced in a single place (the API layer) rather than being reimplemented in each frontend component.

### 2. Multi-source gap provenance

Every gap in the report carries a `source` field identifying its origin:

| Source value | Origin |
|---|---|
| `T54_legal_validator` | Rule-based legal validation engine |
| `T55_evidence_ml` | ML evidence gap classifier |
| `mindmap_diff` | Divergence between mindmap "addressed" nodes and chargesheet content |
| `completeness_rules` | Static JSON completeness checks |
| `manual_review` | Gaps added manually by a supervisor (Phase 2) |

**Rationale:**

- **Transparency:** IOs can see why a gap was flagged and assess whether the source is relevant to their case. A legal gap from T54 (rule-based, high confidence) carries different weight than an evidence gap from T55 (ML, variable confidence).
- **Trust:** Distinguishing AI-generated gaps (T55, mindmap_diff) from deterministic checks (T54, completeness_rules) allows IOs to calibrate their response. AI-sourced gaps carry `requires_disclaimer: true`.
- **Debugging:** When a gap appears incorrect, knowing its source allows developers to trace the issue to the correct subsystem.

### 3. Append-only action trail

Gap actions (accept, modify, dismiss, defer, escalate) are stored in the `chargesheet_gap_actions` table, which is append-only:

- Each action entry contains `hash_prev` (the SHA-256 hash of the preceding entry) and `hash_self` (the SHA-256 hash of the current entry), forming a per-gap hash chain.
- A PostgreSQL trigger (`reject_gap_action_mutation`) rejects all `UPDATE` and `DELETE` operations on the table.
- The hash chain uses the same algorithm as the mindmap status chain (ADR-D13): `SHA-256(gap_id|user_id|action|note|timestamp|previous_hash)`.

**Rationale:**

- **Evidentiary integrity:** The action trail may be presented in court to demonstrate that the IO reviewed and addressed each identified gap. Any retroactive alteration breaks the hash chain and is detectable.
- **Accountability:** Each entry records the `user_id` of the officer who took the action, creating individual accountability.
- **Non-repudiation:** An IO cannot claim they never saw a critical gap if the action trail shows they dismissed it with a note.

### 4. Triple export model

Three separate PDF export endpoints serve three distinct audiences:

| Export | Audience | Content | AI annotations |
|---|---|---|---|
| **Clean PDF** | Court | Chargesheet content only, formatted per court requirements | None whatsoever |
| **Review Report** | Internal (IO, SHO) | Gap analysis with severity, remediation, action status | Full, with watermark "INTERNAL REVIEW -- NOT FOR COURT SUBMISSION" |
| **Redline** | Supervisor (DYSP, SP) | Chargesheet text with inline markup showing where gaps apply | Full, with watermark "REDLINE -- SUPERVISOR REVIEW" |

**Rationale:**

- **Court safety:** The Clean PDF must never contain AI annotations, disclaimers, or gap analysis. Submitting AI-generated commentary to the court could create procedural complications and undermine the chargesheet's evidentiary value. The Clean PDF is restricted to `_EXPORT_ROLES` (excludes READONLY) and logs every export event.
- **Internal utility:** The Review Report gives the IO and SHO a complete picture of what the AI found, what was addressed, and what remains open. The watermark prevents accidental court submission.
- **Supervisor workflow:** The Redline gives supervisors a quick visual of where the chargesheet has issues, supporting their review responsibility without requiring them to navigate the ATLAS UI.

### 5. Severity-ranked presentation

Gaps are sorted by severity (critical > high > medium > low > advisory) and then by confidence score (descending) within each severity tier. They are **not** grouped by source.

**Rationale:**

- IOs care about impact, not about which subsystem found the gap. A critical evidence gap from T55 is more urgent than a medium legal finding from T54, regardless of source.
- Source is still visible as a metadata field, but it does not drive display order.

### 6. Feature flag

The dual-pane gap analysis feature is gated behind the environment variable `ATLAS_CHARGESHEET_DUAL_PANE_ENABLED` (default: `false`).

**Rationale:**

- The feature depends on multiple upstream modules (T54, T55, T53-M) being production-ready. The feature flag allows deployment of the code without activation until all dependencies and the Nodal Officer sign-off are confirmed.
- Consistent with the feature flag pattern established in ADR-D13 (`ATLAS_MINDMAP_ENABLED`).

### 7. Graceful degradation

If any source (T54, T55, or mindmap) is unavailable at analysis time, the report is still generated using the remaining available sources. The response includes a `partial_sources` array listing which sources were unavailable, and the `generator_version` field is appended with `+partial(...)`.

**Rationale:**

- A chargesheet review should not be blocked because one upstream module has not yet run or encountered an error. Completeness rules (static JSON checks) are always available as a baseline.
- The `partial_sources` field allows the UI to display a warning banner (e.g., "Evidence gap analysis was not available for this report").
- Reanalysis after the missing source becomes available will produce a new, more complete report version.

## Consequences

### Positive

- IOs receive a single, severity-ranked view of all chargesheet gaps, reducing the cognitive load of navigating multiple analysis screens.
- Every action on every gap is permanently recorded with cryptographic tamper evidence, suitable for court proceedings and internal affairs investigations.
- Three export formats ensure that the right content reaches the right audience without risk of AI annotations appearing in court filings.
- Multi-source provenance builds trust by clearly distinguishing deterministic checks from AI-generated suggestions.
- Graceful degradation ensures the feature remains useful even when upstream modules are partially available.
- Feature flag allows safe, staged rollout aligned with operational readiness.

### Negative / Risks

- **Backend complexity:** The aggregator must query 4-5 tables, deduplicate across sources, and maintain hash chains. This adds complexity to the codebase and requires thorough integration testing.
- **Partial report ambiguity:** When sources are unavailable, IOs may be unaware of gaps that would have been detected if all sources were running. The `partial_sources` warning mitigates this but relies on the IO reading the banner.
- **Export maintenance:** Three separate HTML renderers must be maintained. Changes to the chargesheet data model require updates to all three renderers.
- **Deduplication imperfection:** The deduplication algorithm uses `(category, key1, key2)` tuples to identify overlapping gaps. Gaps that are semantically identical but described differently across sources may not be deduplicated. This is accepted as a tolerable false-positive rate; IOs can dismiss duplicates.
- **Hash chain recovery:** If a hash chain is corrupted (e.g., due to a bug in an early version), there is no built-in mechanism to "reset" the chain. The entire action history for that gap becomes unverifiable. Mitigation: extensive unit tests for the hash computation and trigger enforcement.

## Related ADRs

- **ADR-D01** — Modular monolith architecture (deployment model, single-repo constraint)
- **ADR-D03** — RBAC matrix (role definitions, district scoping, PII masking policy)
- **ADR-D13** — Chargesheet mindmap (template-driven guidance, append-only hash chain pattern, feature flag pattern)
