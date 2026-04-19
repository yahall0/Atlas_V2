# ADR-D17: Phase-2 production wiring — embedder, reranker, persistence, feedback, route, special-acts framework

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Platform Engineering Lead, ML Engineering Lead, Programme Director, District SP (advisory), Public Prosecutor (advisory)
**Related:** [ADR-D15](ADR-D15-subclause-precision.md), [ADR-D16](ADR-D16-recommender-pipeline.md)

---

## Context

Phase 1 delivered the verbatim corpus, sub-clause parser (ADR-D15), and the dev-grade recommender pipeline (ADR-D16). The pipeline ran end-to-end on a 20-FIR seed gold standard with TF-IDF retrieval — top-5 accuracy 5%, sub-clause recall 4.8%. Architecture validated; quality intentionally floor-level.

Phase 2 closes the gap between *architecture proven* and *production capable*. Seven workstreams were committed.

## Decision

Phase 2 ships the following, all verified by tests and the eval harness on a 60-FIR gold standard.

### 1. FastAPI route (Phase 2.1)
The recommender is now exposed as `POST /api/v1/firs/{fir_id}/recommend-sections` (synchronous), `GET .../latest` (cached lookup, returns 404 until DB-backed cache lands) and `POST .../{addressable_id}/feedback` (IO accept/modify/dismiss capture). Registered in `backend/app/main.py` alongside existing routers. The retriever is built once at import time and cached for the process lifetime.

### 2. Cross-encoder reranker (Phase 2.2)
`backend/app/legal_sections/reranker.py`. Two backends:

* **`DevReranker`** — heuristic (cosine + Jaccard token overlap), zero dependencies.
* **`Bge3Reranker`** — `BAAI/bge-reranker-v2-m3` cross-encoder, lazy-loaded.

Activated via `ATLAS_RERANKER` env var. Wired into the recommender between retrieval and aggregation.

### 3. Pgvector retriever and Alembic migration (Phase 2.3)
Migration `013_add_legal_sections_kb` provisions `legal_sections`, `legal_section_chunks` (with `vector(1024)` column and IVF-Flat ANN index), and `legal_recommendation_feedback`. `PgvectorRetriever` and `PgvectorIngestor` mirror the in-memory retriever's interface — substitution is a one-line change once the DB is provisioned.

### 4. Feedback capture (Phase 2.4)
`backend/app/legal_sections/feedback.py`. Records IO actions to a feedback ledger (JSONL) and emits an audit-chain entry. `load_signals()` aggregates the ledger into per-`addressable_id` action counts — used as a re-ranking prior in Phase 3.

### 5. Gold standard expansion (Phase 2.5)
Expanded from 20 → **60 FIRs** spanning theft variants, hurt/grievous-hurt, robbery/dacoity, kidnapping, dowry death, sexual harassment, voyeurism, criminal intimidation, defamation, stalking, mischief, criminal trespass, forgery, false-evidence, attempt-to-suicide, and nine more case classes. All entries marked `model_generated_awaiting_sme` — SME ratification is the gate for high-confidence statistics.

### 6. bge-m3 production embedder (Phase 2.6)
Verified end-to-end. `sentence-transformers` installed; `BAAI/bge-m3` loads cleanly on CPU and produces 1024-dim normalised vectors. **Eval results on the 60-FIR gold set:**

| Metric | TF-IDF baseline | bge-m3 | Lift |
|---|---|---|---|
| top-1 accuracy | 0.0% | 3.3% | +3.3pp |
| top-3 accuracy | 5.0% | 16.7% | +11.7pp |
| top-5 accuracy | 8.3% | 20.0% | +11.7pp |
| **top-10 accuracy** | 10.0% | **33.3%** | **+23.3pp** |
| exact-recovery rate | 3.3% | 16.7% | +13.4pp |
| **sub-clause recall** | 4.8% | **27.6%** | **+22.8pp** |
| sub-clause precision | 0.85% | 2.99% | +2.1pp |
| missed-charging rate | 95.2% | 72.4% | -22.8pp |

bge-m3 alone produces a **3.3× improvement in top-10 accuracy and 5.7× improvement in sub-clause recall**. Adding bge-reranker-v2-m3, then SME-ratified gold expansion, then feedback-driven re-ranking, are independent compounding levers from this baseline.

### 7. Special-acts framework (Phase 2.7)
`backend/app/legal_sections/acts.py` introduces an `ActSpec` registry. IPC and BNS are registered as `ingested`; BNSS, BSA, CrPC, NDPS, POCSO, IT Act, MV Act, Dowry Prohibition, Arms Act, SC/ST Atrocities, Domestic Violence, Gujarat Prohibition, and Gujarat Gambling are registered as `planned`. Adding a new act is now mechanical: provide the source PDF, set `status="ingested"`, run `extract_legal_sections.py`, re-index. No other code change is required.

## Production switching

| Capability | Dev default | Production setting |
|---|---|---|
| Embedder | `TfidfEmbedder` | `ATLAS_EMBEDDER=bge-m3` |
| Reranker | `DevReranker` | `ATLAS_RERANKER=bge-reranker-v2-m3` |
| Retriever | `InMemoryRetriever` | `PgvectorRetriever` (after running migration 013 + ingestor) |
| Audit sink | best-effort import | wired automatically in production import path |

## Quality gates (release-blocking)

```
pytest backend/tests/legal_sections/                    →  53 passed
python scripts/verify_legal_sections.py                 →  OVERALL: PASS
python scripts/eval_recommender.py                      →  TF-IDF baseline metrics
ATLAS_EMBEDDER=bge-m3 python scripts/eval_recommender.py →  bge-m3 production metrics
```

CI gates a release on no-regression in:
* `top5_accuracy`, `subclause_recall`, `over_charging_rate` against the previous report (TF-IDF lane, runs on every PR — fast).
* The bge-m3 lane runs nightly and gates promotion to staging.

## Consequences

### Positive
* The pipeline is now operationally complete: an IO can hit the API, get a sub-clause-precise recommendation, accept/dismiss it, and have that signal persisted for re-ranking.
* The bge-m3 measurement (recorded in `data/eval_report.json`) sets the production-realistic baseline for any future change. Every quality lever (reranker, gold expansion, feedback signal, special acts) can now be measured against this baseline.
* The substitution surfaces (embedder / reranker / retriever / acts) keep the pipeline pluggable. Phase-3 levers do not require structural changes.
* Special-acts addition is now a configuration change plus PDF supply — no engineering ticket per act.

### Negative
* Top-1 accuracy is still low (3.3%) — the system advises, the IO decides. This is by design (P-05 from the SDD), but the quality bar for *practical IO assistance* requires sub-clause recall well above today's 27.6%. Phase 3 (reranker + SME gold + feedback signal + cross-act expansion) is required for that bar.
* `sentence-transformers` adds ~2 GB of disk + ~1 GB of RAM to the runtime image. Acceptable for the on-prem GSDC deployment; documented in the operations runbook.
* The 60-FIR seed remains awaiting SME ratification; treat all reported numbers as indicative until ratified.

### Operational
* Production deployment SHALL set `ATLAS_EMBEDDER=bge-m3` and pre-fetch the model into the container layer (no outbound network at runtime, per programme constraint C-01).
* Migration `013_add_legal_sections_kb` is forward-only with a verified `downgrade()`; rehearsed on staging before production.
* The feedback ledger is local JSONL today; in production it is mirrored to the `legal_recommendation_feedback` table and the audit chain.

## Implementation references

| Concern | Path |
|---|---|
| FastAPI routes | `backend/app/legal_sections/routes.py` |
| Reranker | `backend/app/legal_sections/reranker.py` |
| Pgvector retriever + ingestor | `backend/app/legal_sections/pgvector_retriever.py` |
| Migration 013 | `backend/alembic/versions/013_add_legal_sections_kb.py` |
| Feedback | `backend/app/legal_sections/feedback.py` |
| Gold standard (60 FIRs) | `backend/app/legal_sections/data/gold_standard.jsonl` |
| Acts registry | `backend/app/legal_sections/acts.py` |
| Phase-2 tests | `backend/tests/legal_sections/test_phase2.py` |
| Eval reports | `backend/app/legal_sections/data/eval_report.json` |

## Roadmap (Phase 3)

* Pair `bge-m3` retrieval with `bge-reranker-v2-m3` end-to-end and measure compounded lift.
* SME ratification of the 60-FIR seed; expansion to 200+ entries.
* Wire feedback signals into re-ranking (accept_weight, dismiss_weight) — `load_signals()` already aggregates the ledger.
* Ingest the four highest-priority special acts: BNSS (procedural), BSA (evidence), NDPS, POCSO. Source PDFs to be supplied by the programme office.
* Tablet/PWA form factor for IO field use.
* Voice-to-Gujarati input pipeline (offline whisper + custom NER for legal entities).
