# ADR-D18: Gold-standard ratification workflow — AI curation + SME panel

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Programme Director, ML Engineering Lead, Platform Engineering Lead, SME Panel Chair
**Related:** [ADR-D15](ADR-D15-subclause-precision.md), [ADR-D16](ADR-D16-recommender-pipeline.md), [ADR-D17](ADR-D17-phase2-pipeline.md)

---

## Context

Every quality lever in the section recommender — embedder selection, reranker fine-tuning, structured-fact extraction, feedback-driven re-ranking, special-act ingestion priority — is judged against the gold-standard set. Until that set is reviewed and ratified by qualified legal experts, the metrics it produces are partly self-referential and cannot trustworthily guide engineering decisions.

The gold standard's 60 entries entered the repository as `model_generated_awaiting_sme`. Going directly from there to SME ratification would consume an estimated 12–16 hours of senior-counsel time on first-pass labelling work that could be done with adequate quality by a deeply-instructed AI curator. Senior-counsel time is the scarcest resource on the programme.

## Decision

The platform SHALL maintain a three-stage lifecycle for every gold-standard FIR entry, with the first stage now defaulted, the second stage performed by a deeply-instructed AI curator with full visibility into the diff, and the third stage owned by the legal SME panel.

### Lifecycle

```
model_generated_awaiting_sme
        │
        │  (AI curation pass — scripts/curate_gold.py)
        │  - rigorous re-read of every entry
        │  - sub-clause-precision upgrade
        │  - over-charge removal
        │  - missing-companion addition
        │  - per-entry curator-note + diff hash recorded
        ▼
ai_curated_pending_sme
        │
        │  (SME panel review — scripts/ratify_gold.py)
        │  - calibration cases first (5 entries)
        │  - one entry at a time, four actions
        │      Accept   → sme_ratified
        │      Modify   → sme_revised  (full new label list captured)
        │      Reject   → withdrawn    (reason required)
        │      Defer    → stays ai_curated_pending_sme
        │  - every action audit-chained
        ▼
sme_ratified  ─or─  sme_revised  ─or─  withdrawn
```

### Authority and limits

| Stage | Authority of the labels | Used for |
|---|---|---|
| `model_generated_awaiting_sme` | None — bootstrapping only | Initial pipeline wiring, smoke tests |
| `ai_curated_pending_sme` | Provisional — qualified-AI judgment | Engineering iteration, regression detection |
| `sme_ratified` | Authoritative — programme metric of record | All quality reporting, quality-gate decisions, model release |

The eval harness reports separately for each filter (`--status sme_ratified`). Engineering decisions that affect production deployment SHALL be made on ratified-only metrics. Iterative engineering improvements MAY use the ai-curated metrics as a faster-cycle proxy, but their reported numbers SHALL be marked "indicative" until ratified.

### What the AI curator did (this iteration)

A single rigorous pass over all 60 entries produced:

| Outcome | Count | Notes |
|---|---|---|
| Accepted as-is (vouched) | 45 | Original labels held up under sub-clause-precision review |
| Revised | 15 | Sub-clause sharpening, over-charge removal, missing-companion addition, redundancy removal |
| Withdrawn | 0 | All entries are within scope |

Representative revisions (full diff in the ratification ledger):

| Entry | Change | Reason |
|---|---|---|
| GS_0005 (dacoity) | `BNS 310` → `BNS 310(2)` | Sub-clause precision (operative punishment limb) |
| GS_0011 (affray) | Removed `BNS 3(5)` | Common intention does not attach in mutual fights |
| GS_0024 (child kidnap) | Removed `BNS 139` | Over-charging (no murder intent) |
| GS_0038 (mob assault) | Added `BNS 189`; removed `BNS 3(5)` | Unlawful-assembly chain completed; `190` makes `3(5)` redundant |
| GS_0049 (attempt to murder by fire) | `BNS 109` → `BNS 109(1)` | Sub-clause precision |
| GS_0054 (mischief vehicle) | `BNS 324(4)` → `BNS 324(5)` | Damage of ₹1,25,000 exceeds the ₹1,00,000 threshold of (4) |

Every revision carries a curator-note. The SME panel sees both the revision and the rationale and can override.

### Tooling

| Tool | Purpose |
|---|---|
| `backend/app/legal_sections/ratification.py` | Status enum, transition helper, label-hash, diff, ledger emit, audit-chain hook |
| `scripts/curate_gold.py` | One-shot AI-curation pass; idempotent; safe to re-run |
| `scripts/ratify_gold.py` | Interactive SME CLI; resume-friendly; persists after every decision |
| `docs/sme/GOLD_RATIFICATION_PROTOCOL.md` | The reviewer-facing protocol document with calibration cases and the four-action key |
| `backend/app/legal_sections/data/ratification_ledger.jsonl` | Append-only event log of every status transition with diff hashes |

### Audit and replay

Every transition writes:
- a ratification-ledger event: `{fir_id, actor, previous_status, new_status, action, previous_labels_hash, new_labels_hash, diff, notes, timestamp}`
- a platform audit-chain entry: `GOLD_RATIFIED_<ACTION>` with the full event payload

The lineage of any gold-standard entry is reconstructible from the ledger alone. Defects identified after ratification SHALL be remediated through the same CLI (`Modify` action moves an entry to `sme_revised`); the JSONL is never edited by hand.

## Consequences

### Positive
- Senior-counsel time is conserved for finalisation, not first-draft labelling. Estimated saving: 8–10 hours of panel time.
- The SME panel sees a coherent, sub-clause-precise starting point with rationale, accelerating throughput from ~12 minutes per entry (cold start) to ~4–6 minutes (review-and-confirm).
- Engineering iteration is unblocked: the `ai_curated_pending_sme` lane gives the eval harness usable numbers within hours, not weeks.
- The ratified-only lane preserves authority where it must rest — with the SME panel.

### Negative
- The `ai_curated_pending_sme` numbers risk being treated as authoritative by impatient stakeholders. Mitigated by explicit "indicative" labelling on all reports.
- AI-curator errors propagate to the SME panel as a subtle anchor effect. Mitigated by surfacing the original `model_generated` labels in the per-entry diff (the SME sees both the original and the curator's revision).

### Operational
- The CLI is resume-friendly. SME sessions of any length are safe.
- Backups: the gold-standard JSONL is in version control. Every ratification commit captures the previous state.
- Calibration: panel reviewers SHALL ratify the five calibration entries before working through the rest, and resolve disagreements before continuing.

## Quality gate

The eval harness is updated to filter by status:
```
python scripts/eval_recommender.py --status sme_ratified
python scripts/eval_recommender.py --status ai_curated_pending_sme
```

Release decisions SHALL use the `sme_ratified` lane. Engineering iteration MAY use the `ai_curated_pending_sme` lane for faster cycles. CI publishes both numbers nightly.

## Implementation references

| Concern | Path |
|---|---|
| Lifecycle module | `backend/app/legal_sections/ratification.py` |
| Curation script | `scripts/curate_gold.py` |
| Ratification CLI | `scripts/ratify_gold.py` |
| Protocol document | `docs/sme/GOLD_RATIFICATION_PROTOCOL.md` |
| Gold-standard data | `backend/app/legal_sections/data/gold_standard.jsonl` |
| Ratification ledger | `backend/app/legal_sections/data/ratification_ledger.jsonl` |
