# ADR-D20: Compendium pipeline wiring — mindmap, gap-aggregator, FIR auto-trigger

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Platform Engineering Lead, ML Engineering Lead, Programme Director
**Related:** [ADR-D13](ADR-D13-chargesheet-mindmap.md), [ADR-D16](ADR-D16-recommender-pipeline.md), [ADR-D17](ADR-D17-phase2-pipeline.md), [ADR-D19](ADR-D19-io-scenarios-kb.md)

---

## Context

ADR-D19 ingested the Delhi Police Academy *Compendium of Scenarios for Investigating Officers, 2024* into a structured knowledge base (`io_scenarios.jsonl`, 20 scenarios with full procedural trees, evidence catalogues, forms, deadlines, and actor roles). The KB was built and tested but not yet plumbed into the three live surfaces that an Investigating Officer actually touches:

1. The **mindmap engine** (`backend/app/mindmap/generator.py`) was still loading model-generated JSON templates.
2. The **chargesheet gap analyser** (`backend/app/chargesheet/gap_aggregator.py`) had no awareness of the Compendium-required forms, evidence, or statutory deadlines.
3. The **FIR ingestion routes** (`backend/app/api/v1/firs.py POST /firs` and `backend/app/api/v1/ingest.py POST /ingest`) accepted uploads and persisted them, but did not invoke the section recommender — so no recommendations existed to feed downstream surfaces.

This ADR records the three plumbing decisions that close the loop end-to-end: an uploaded FIR now flows through recommender → Compendium-scenario lookup → mindmap + checklist, all stored against the FIR record.

## Decision

### Task 1 — Mindmap engine routing

A new module `backend/app/mindmap/playbook_generator.py` builds mindmaps from the Compendium scenarios. The existing `backend/app/mindmap/generator.py:generate_mindmap()` is patched to **prefer the playbook path** when the FIR's recommended citations match a Compendium scenario, and fall back to the model-generated template path otherwise.

* `has_playbook_for(citations)` — cheap predicate the generator uses to decide.
* `generate_playbook_mindmap(fir_id, citations, conn=None)` — builds the mindmap; persists to the existing `chargesheet_mindmaps` and `chargesheet_mindmap_nodes` tables when `conn` is supplied; returns an in-memory tree when not (test/preview mode).
* When **multiple** Compendium scenarios match the citation set (e.g. assault + dacoity), a synthetic root wraps all matching scenarios as siblings.
* **Failure mode:** the playbook path is best-effort. Any exception logs and falls through to the existing template path, so the mindmap surface never breaks.

The `generated_by_model_version` column carries the marker `playbook-v1+delhi-pa-compendium-2024` so playbook-derived mindmaps are auditable and distinguishable from template-derived ones.

### Task 2 — Gap aggregator augmentation

`backend/app/chargesheet/gap_aggregator.py` gains a new gap source — the Compendium playbook — joining the existing five (T54 legal validator, T55 evidence ML, mindmap-divergence, completeness rules, KB-driven 3-layer).

The new helper `_playbook_driven_gaps(cs, fir)`:

1. Resolves the FIR's recommended sub-clause-precise citations.
2. Looks up matching Compendium scenarios.
3. Aggregates the required forms, evidence and deadlines via `scenario_adapter.checklist_for_scenarios(...)`.
4. Cross-references each item against the chargesheet's text and structured fields.
5. Emits gap entries for items not detectably present, classified into three categories:

| Category | Severity | Confidence | Use |
|---|---|---|---|
| `playbook_form_missing` | high | 0.85 | Required form (RUKKA, FSL Form, MLC, Site Plan, Sample Seal, Road Certificate, IIF-III, …) not detected |
| `playbook_evidence_missing` | medium | 0.55 | Compendium-flagged evidence step likely not addressed |
| `playbook_deadline_reminder` | low | 1.00 | Statutory clock applicable (24 hours / 72 hours / 90 days) — informational |

Each form-gap carries a `playbook_reference` array citing the originating Compendium scenario(s) with page numbers. The recommendation ledger and the audit chain inherit this provenance.

The aggregator's `partial_sources` field includes `playbook_compendium` when the playbook source is empty — so observability still distinguishes "no playbook applicable" from "playbook errored".

### Task 3 — Auto-trigger on FIR ingestion

A new module `backend/app/legal_sections/auto_trigger.py` runs the section recommender + Compendium-scenario lookup against a freshly-ingested FIR and persists the result to `firs.nlp_metadata`.

* The `POST /api/v1/firs` and `POST /api/v1/ingest` endpoints both schedule `_trigger_recommender_in_background(fir_record)` as a FastAPI `BackgroundTasks` job. The HTTP response goes out first; the recommender runs after.
* The retriever is **lazy-cached at process scope** (one initialisation per worker, not per request).
* Persistence layout:

```jsonc
firs.nlp_metadata = {
  "recommended_sections": [
    { "canonical_citation": "BNS 305(a)", "section_id": "BNS_305",
      "act": "BNS", "section_number": "305",
      "sub_clause_label": "(a)", "addressable_id": "BNS_305_a",
      "confidence": 0.92, "rationale_quote": "..." },
    /* ... */
  ],
  "compendium_scenarios": [
    { "scenario_id": "SCN_016", "scenario_name": "Housebreaking by night",
      "page_start": 147, "page_end": 154,
      "applicable_sections": ["BNS 331(3)"] }
  ],
  "recommender_act_basis": "BNS",
  "recommender_run_at": "2026-04-19T14:00:00Z",
  /* ... existing keys preserved ... */
}
```

* **Failure mode:** every error is logged, never raised. The FIR record remains usable; the recommender can be invoked manually via `POST /api/v1/firs/{id}/recommend-sections`.
* **Idempotency:** the auto-trigger always overwrites the `recommended_sections` and `compendium_scenarios` keys; other `nlp_metadata` keys are preserved by deep-merge.

## End-to-end flow (after this wiring)

```
PDF upload  →  POST /api/v1/ingest (or POST /api/v1/firs)
              │
              │ persist + return 201
              │
              ▼
              [BackgroundTasks: auto_trigger]
              │
              │ run_recommender_for_fir(...)
              │ ├─ retriever.retrieve()  → top-K chunks
              │ ├─ recommender.recommend() → sub-clause-precise citations
              │ └─ find_scenarios_for_sections() → Compendium scenarios
              │
              │ persist to firs.nlp_metadata
              │
              ▼
   ┌──────────┴──────────────────────────────────┐
   │                                              │
   ▼                                              ▼
mindmap engine                          chargesheet gap analyser
generator.generate_mindmap()             aggregate_gaps()
  └─ if has_playbook_for(citations):       └─ _playbook_driven_gaps(...)
       playbook_generator.generate_*()         emits form / evidence /
       (Compendium-derived tree)               deadline gaps with
                                               playbook_reference
```

Net effect: every FIR upload now produces, automatically, a sub-clause-precise recommendation, a Compendium-grounded mindmap, and a checklist-driven gap report — all auditable to a Delhi Police Academy page reference.

## Quality gate

```
pytest backend/tests/legal_sections/         →  78 passed
pytest backend/tests/legal_sections/test_phase3_wiring.py  →  14 passed
verify_legal_sections.py                     →  OVERALL: PASS
```

## Consequences

### Positive
* The IO never has to know the Compendium exists — the mindmap and the checklist surface its content automatically.
* Each chargesheet gap can be defended in court with a Delhi Police Academy page citation.
* Scaling new offences / scenarios is purely data work: add to `SCENARIOS` list in `io_scenarios.py`, re-run `build_kb()`. Engineering does not change.
* The auto-trigger creates a trail of recommended sections per FIR, which becomes the dataset for the structured-fact extractor's training set in Phase 4.

### Negative
* Recommender quality (top-10 ≈ 35 % on bge-m3) directly governs how often the playbook path is invoked. Until SME-ratification + structured-fact extractor lift recall, ~65 % of FIRs will still hit the legacy template fallback.
* The auto-trigger adds 5–30 s of CPU work per FIR upload (post-response, in background). On a multi-worker deployment this is invisible to the user; on a single-worker dev box it can backlog.
* `_playbook_driven_gaps` is keyword-based (does the chargesheet text contain "RUKKA"?). False negatives possible (the IO completed it but used a different word) and false positives (the word appears in narrative without the actual form being filed). SME pass over the 20 scenarios will tighten the keyword list.

### Operational
* The retriever cache is per-process. With 4 API workers the model loads 4 times at startup (~10 s each). Acceptable; can be moved to a shared in-memory store later.
* Background tasks rely on FastAPI's in-process `BackgroundTasks`. For high-throughput deployment, migrate to Redis-Queue / Celery (out of scope here).

## Implementation references

| Concern | Path |
|---|---|
| Playbook mindmap generator | `backend/app/mindmap/playbook_generator.py` |
| Mindmap router patch | `backend/app/mindmap/generator.py` (`_recommended_citations_from_fir`, `generate_mindmap`) |
| Gap-aggregator playbook source | `backend/app/chargesheet/gap_aggregator.py` (`_playbook_driven_gaps`) |
| Auto-trigger module | `backend/app/legal_sections/auto_trigger.py` |
| FIR endpoint wiring | `backend/app/api/v1/firs.py` (`_trigger_recommender_in_background`) |
| Ingest endpoint wiring | `backend/app/api/v1/ingest.py` |
| Tests (14 new, 78 total) | `backend/tests/legal_sections/test_phase3_wiring.py` |

## Roadmap

* Phase 4: SME-ratify the 60-FIR gold standard so playbook coverage can be measured against authoritative labels.
* Phase 4: build the structured-fact extractor (Sarvam-1) so the recommender's recall lifts past the floor — directly increasing playbook-route hit-rate.
* Phase 4: wire `playbook_reference` into the `SectionRecommendation` Pydantic schema and surface in the recommender API response (this ADR persists it on the FIR record but doesn't yet return it inline on every recommend call).
* Phase 5: replace in-process `BackgroundTasks` with a job queue when concurrent FIR uploads exceed ~30/min per worker.
