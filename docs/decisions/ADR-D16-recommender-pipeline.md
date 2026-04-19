# ADR-D16: Section recommender pipeline, conflict guard, and gold-standard evaluation

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Platform Engineering Lead, ML Engineering Lead, Programme Director, Public Prosecutor (advisory), District SP (advisory)
**Supersedes:** none
**Related:** [ADR-D15](ADR-D15-subclause-precision.md) — sub-clause precision contract

---

## Context

ADR-D15 established that recommendations must be at sub-clause precision. To honour that contract end-to-end the platform requires:

1. A **chunker** that decomposes each section into addressable retrieval units (one per sub-clause where present, plus header / illustrations / explanations / exceptions).
2. An **embedder** abstraction so the production target (`BAAI/bge-m3`, multilingual dense + sparse + multi-vector) can be substituted into a working development pipeline that is fully offline and deterministic.
3. A **retriever** that returns top-K chunks for a given FIR narrative, with optional act filtering driven by the date-of-occurrence rule.
4. A **recommender service** that aggregates retrieved chunks back to addressable units, applies a confidence floor and a borderline flag, and emits the `SectionRecommendation` shape defined in `backend/app/legal_sections/schemas.py`.
5. A **conflict guard** that rejects over-charges, requires companion sections (e.g. common intention when there are ≥ 2 accused), and flags incompatible-section pairs (e.g. murder + culpable homicide as primary).
6. A **gold-standard set + evaluation harness** so the system's accuracy is measurable and any regression is detected automatically.

Without (5) the tool produces "AI suggestions"; without (6) "best in the world" is unmeasurable. Both are non-negotiable.

## Decision

The platform SHALL implement the section-recommendation pipeline as the chained stages below. Each stage is a separate Python module under `backend/app/legal_sections/` and is independently testable.

### Stages

```
FIR narrative + occurrence_date + accused_count
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  act_for(occurrence_date)                                      │
│    occurrence ≥ 2024-07-01 → BNS                              │
│    otherwise                → IPC                             │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Retriever.retrieve(query, k=60, act_filter=...)              │
│    InMemoryRetriever (dev) | PgvectorRetriever (production)   │
│    Embedder: TfidfEmbedder (dev) | Bge3Embedder (production)  │
│    Embedding-time text = "<section_title>. <chunk_text>"      │
│    L2-normalised cosine similarity                            │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Aggregate by addressable_id (max-pool)                       │
│    Sub-clause hits outrank header / section_body chunks       │
│    on the same parent (×0.85 demotion).                       │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Confidence floor (default 0.20 raw cosine)                   │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Conflict guard — conflicts.evaluate(citations, context)      │
│    INC-* incompatible pairs    → warn (attach to entries)     │
│    REQ-* required companions    → block-add missing companion │
│    OVR-* over-charging guards   → block-drop offending entry  │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  Borderline flag — top-2 within 10% confidence                │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  RecommendationResponse                                       │
│    sub-clause-precise canonical citations (ADR-D15)           │
│    rationale_quote = verbatim sub-clause text                 │
│    conflict_findings array — visible to IO and audit          │
└────────────────────────────────────────────────────────────────┘
```

### Conflict guard rule families (binding)

| Family | Purpose | Examples |
|---|---|---|
| **INC** — Incompatible pairs | Two sections cannot be primary on the same incident without alternative pleading | INC-001 (BNS 101 vs 105), INC-002 (IPC 302 vs 304), INC-003 (BNS 303 vs 316), INC-004 (BNS 309 vs 310) |
| **REQ** — Required companions | A condition over the FIR or accused-count requires an additional section | REQ-001 (≥2 accused → BNS 3(5) / IPC 34); REQ-002 (lock broken + theft → BNS 331(3)); REQ-003 (receptacle broken + theft → BNS 334(1)) |
| **OVR** — Over-charging guards | A section's gating facts must appear in the FIR | OVR-001 (BNS 305(a) requires dwelling-context words); OVR-003 (BNS 117(2) requires MLC / grievous-hurt indicators); OVR-006 (BNS 310 requires ≥5 accused) |

Adding a rule is a one-file change (`backend/app/legal_sections/conflicts.py`) with peer review by the legal panel. The full rule set is reviewed quarterly.

### Embedder substitution

Two backends implement the `Embedder` protocol:

* **`TfidfEmbedder`** — pure-Python, no dependencies. Used for development, unit tests, the eval harness, and any deployment that lacks the heavy ML dependency. Deterministic.
* **`Bge3Embedder`** — `BAAI/bge-m3`. Lazy-loaded. Activated by `ATLAS_EMBEDDER=bge-m3` (or by `get_embedder("bge-m3")`). This is the production target.

Switching from TF-IDF to bge-m3 is a single environment-variable change. No interface change is required.

### Gold-standard set

* **Location:** `backend/app/legal_sections/data/gold_standard.jsonl`.
* **Schema:** `{fir_id, narrative, occurrence_date_iso, accused_count, expected_citations[], rationale_facts[], source, status, sme_ratified_by, sme_ratified_at, hash}`.
* **Status lifecycle:** `model_generated_awaiting_sme` → `sme_ratified` → (if a defect later found) `withdrawn`.
* **Initial seed:** 20 FIRs across the most common case patterns (theft, dwelling theft, snatching, dacoity, criminal breach of trust, cheating, defamation, stalking, cruelty, affray, harassment, trespass, vehicle theft, temple theft, armed robbery, OTP fraud, forgery, public-servant misconduct, road accident, common-intention assault). Each entry annotates the expected canonical citations at sub-clause precision so the eval harness measures against the ADR-D15 contract.
* **SME ratification process:** the legal panel reviews each `model_generated_awaiting_sme` entry, edits as required, and transitions to `sme_ratified`. Until ratified, eval-harness numbers should be read as indicative.

### Evaluation harness

`scripts/eval_recommender.py` reads the gold set, runs the recommender against every entry, and reports:

| Metric | Definition |
|---|---|
| top-1 / top-3 / top-5 / top-10 accuracy | At least one expected citation in the top-K returned set |
| exact_recovery_rate | All expected citations present in the returned set |
| sub-clause recall | Σ recovered ÷ Σ expected (citation-level) |
| sub-clause precision | Σ recovered ÷ Σ recommended (citation-level) |
| over-charging rate | Σ recommended-not-expected ÷ Σ recommended |
| missed-charging rate | Σ expected-not-recovered ÷ Σ expected |

The harness writes a per-FIR breakdown to `data/eval_report.json`. CI MAY publish this report and gate releases on regressions.

### Quality gate (release-blocking)

Before any release that touches the corpus, parser, chunker, embedder, retriever, recommender or conflict rules:

* `python scripts/verify_legal_sections.py` → exit 0
* `pytest backend/tests/legal_sections/` → all green (currently 45/45)
* `python scripts/eval_recommender.py` → no regression in any of `top5_accuracy`, `subclause_recall`, `over_charging_rate` against the previous report

## Consequences

### Positive
* End-to-end pipeline exists and is testable without GPU or external services.
* Production substitution is a one-line change (`ATLAS_EMBEDDER=bge-m3`).
* Conflict guard prevents the "wrongly suggested" failure mode that was identified in user evaluation: incompatible pairs flagged, required companions auto-added, over-charges dropped.
* Gold-standard infrastructure makes the system's accuracy measurable and improvement trackable.

### Negative
* TF-IDF baseline numbers are weak. The architecture is sound but the recall gap to bge-m3 will be visible until production embedder is wired.
* 20-FIR seed is below the 200+ needed for high-confidence statistics. SME ratification + expansion is a continuing workstream.

### Operational
* Embedder factory honours `ATLAS_EMBEDDER` env var. Production deployment SHALL set this to `bge-m3` and ensure the model files are pre-fetched into the container layer (no outbound network at runtime — see programme constraint C-01).
* The gold-standard JSONL is **versioned in the repository**. Any change passes through PR with legal-panel sign-off.

## Implementation references

| Concern | Path |
|---|---|
| Chunker | `backend/app/legal_sections/chunker.py` |
| Embedder | `backend/app/legal_sections/embedder.py` |
| Retriever | `backend/app/legal_sections/retriever.py` |
| Conflict guard | `backend/app/legal_sections/conflicts.py` |
| Recommender | `backend/app/legal_sections/recommender.py` |
| Schemas | `backend/app/legal_sections/schemas.py` |
| Gold standard | `backend/app/legal_sections/data/gold_standard.jsonl` |
| Eval harness | `scripts/eval_recommender.py` |
| Tests | `backend/tests/legal_sections/test_*.py` (45 cases) |

## Roadmap (Phase 2)

* Wire `Bge3Embedder` into staging.
* Add a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) between retrieval and aggregation.
* Add sparse retrieval (Postgres tsvector) and fuse via RRF (utility already shipped in `retriever.py`).
* Implement the `PgvectorRetriever` mirror of the in-memory retriever; persist embeddings on extraction.
* Expand the gold standard to 200+ entries with SME ratification.
* Wire feedback capture: when an IO or court accepts / modifies / dismisses a recommendation, log to `audit_log` with the original recommendation and use the signal in re-ranking.
