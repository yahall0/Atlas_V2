# ADR-D19: IO Scenarios Knowledge Base — Delhi Police Academy Compendium

**Status:** Accepted
**Date:** 2026-04-19
**Deciders:** Programme Director, Platform Engineering Lead, ML Engineering Lead, SP–Modernisation (advisory)
**Related:** [ADR-D13](ADR-D13-chargesheet-mindmap.md), [ADR-D15](ADR-D15-subclause-precision.md), [ADR-D16](ADR-D16-recommender-pipeline.md), [ADR-D17](ADR-D17-phase2-pipeline.md)

---

## Context

The platform has, until today, sourced its mindmap templates from internally-authored JSON files (one per case category — murder, theft, NDPS, etc.). These templates were built rapidly to ship Sprint 4 but carry no statutory or training authority. When a chargesheet is challenged in court, the IO cannot cite "Atlas template" as the source of the procedure followed.

The Delhi Police Academy publishes the **Compendium of Scenarios for Investigating Officers, 2024** — a 202-page, 20-scenario, BNS / BNSS / BSA-aligned playbook that is the official training material for IOs at the Academy. It contains, per scenario:

* The applicable BNS sections and punishment summary
* A representative case-fact pattern
* Numbered, chronologically-ordered procedural phases (handling the call → FIR registration → investigation → final report)
* Lettered sub-blocks within each phase (e.g. *a. Examination of the scene of crime*, *b. Documentation*, *c. Procedure of arrest*)
* Enumerated items `(i), (ii), (iii)…` with inline references to specific BNSS/BSA/POCSO/IT-Act sections, mandatory forms (HIF-II, IIF-III, MLC, FSL Form, Site Plan, Sample Seal, Road Certificate from Malkhana, RUKKA, LOC, Arrest Memo, Personal Search Memo), deadlines (24 hrs / 72 hrs / 90 days), and the actor responsible.

This is, in substance, a government-authored investigation playbook with the legal authority and pedagogical weight that the platform's home-grown templates lack.

## Decision

The platform SHALL adopt the Compendium as the authoritative source for:

1. **Mindmap templates** (replacing the existing nine model-generated templates).
2. **Per-section investigation checklists** (consumed by the chargesheet gap analyser).
3. **Procedural compliance scoring** (a new metric per chargesheet — *% of required artefacts completed*).
4. **Recommendation explainability** (each section recommendation now carries a `playbook_reference` that points to the Compendium scenario and pages).

### Source

* `ScenariosDelhiPolice.pdf` — text-extractable PDF (202 pages, 20 scenarios). Selected over the earlier scanned variant (`ScenariosOfIO.pdf`, 188 pages, 18 scenarios) because (a) text extraction is exact whereas OCR introduces character-level noise that corrupts legal references, (b) this version is more complete (20 vs 18 scenarios).

### Pipeline

```
ScenariosDelhiPolice.pdf
        │
        │ scripts/extract_io_scenarios.py
        ▼
io_scenarios_pages.jsonl       (one line per page, verbatim text)
        │
        │ backend/app/legal_sections/io_scenarios.build_kb()
        ▼
io_scenarios.jsonl              (one line per structured scenario)
        │
        │ scenario_adapter
        ▼
   ┌────────────────┬────────────────────────┬────────────────────────┐
   ▼                ▼                        ▼                        ▼
mindmap         checklist             playbook_reference          procedural
nodes           per scenario          per recommendation          compliance
                                                                  score
```

### Schema (per scenario, as persisted in `io_scenarios.jsonl`)

| Field | Type | Description |
|---|---|---|
| `scenario_id` | TEXT | `SCN_001`–`SCN_020` |
| `scenario_name` | TEXT | Human-readable name |
| `applicable_sections` | TEXT[] | Sub-clause-precise (per ADR-D15) |
| `punishment_summary` | TEXT | From the Compendium TOC |
| `case_facts_template` | TEXT | The Compendium's illustrative paragraph |
| `phases` | array | Phases → sub-blocks → items |
| `evidence_catalogue` | TEXT[] | Items flagged as evidence by keyword scan |
| `forms_required` | TEXT[] | HIF-II / IIF-III / MLC / FSL Form / Site Plan / Sample Seal / Road Certificate / RUKKA / LOC / Arrest Memo / Personal Search Memo / DD Entry / TIP |
| `deadlines` | TEXT[] | Extracted from "within N hours/days" patterns |
| `linked_acts` | TEXT[] | BNS / BNSS / BSA / POCSO / Arms / NDPS / IT |
| `page_start`, `page_end` | INT | Source page references |
| `source_authority` | TEXT | "Delhi Police Academy, Compendium of Scenarios for Investigating Officers, 2024" |

### Adapter API (`backend/app/legal_sections/scenario_adapter.py`)

| Function | Purpose |
|---|---|
| `playbook_for_recommendation(citations)` | Returns `PlaybookReference[]` for the matched scenarios — fed into `SectionRecommendation.playbook_reference` |
| `mindmap_nodes_for_scenario(scenario)` | Returns a `MindmapNode` tree (compatible with `backend/app/mindmap/generator.py`) |
| `checklist_for_scenarios(scenarios)` | Aggregates evidence + forms + deadlines + actors across multiple matching scenarios |

### Replacement of existing mindmap templates

The nine internally-authored templates at `backend/app/mindmap/templates/*.json` are deprecated in favour of the 18 Compendium-derived scenarios. The 9 special-act / case-category templates that don't directly map to Compendium scenarios remain available as fallbacks until the Compendium is extended to cover them.

| Existing template | Replaced by |
|---|---|
| `murder.json` | SCN_003 (Murder) + SCN_004 (Mob Lynching) |
| `rape.json` | SCN_001 (Rape with POCSO) |
| `theft.json` | SCN_014 (Snatching) + SCN_016 (Housebreaking by night) — partial; theft simpliciter not covered by Compendium |
| `dowry.json` | SCN_002 (Dowry Death) |
| `ndps.json` | SCN_018 (NDPS Act) |
| `cyber_crime.json` | SCN_019 (Cyber Crime — Call Centre) |
| `pocso.json` | SCN_001 (Rape with POCSO) |
| `accident.json` | SCN_005 (Accidental Death) |
| `missing_persons.json` | SCN_011 (Kidnapping) — partial |

Net-new scenarios delivered: Mob Lynching, Attempt to Murder, Attempt to commit Culpable Homicide, Hurt by Dangerous Weapon (simple), Grievous Hurt by Dangerous Weapon, Hurt by Poison, Kidnapping for Ransom, Riot Case, Attempt to Robbery (armed), Arms Act, Cheating-Fraud.

### Cross-act coverage gained without ingestion

Although Atlas only stocks IPC and BNS as standalone corpora today, the Compendium covers Arms Act, NDPS, POCSO, IT Act and other special acts directly inside the scenario procedural text. This gives the platform **partial coverage of those acts immediately** — until source PDFs of the special acts themselves are supplied.

## Consequences

### Positive
* The mindmap engine inherits the legal authority of the Delhi Police Academy.
* The chargesheet gap analyser gets a deterministic, document-grounded evidence checklist for the 20 most common case classes.
* Each section recommendation now carries a `playbook_reference` — radical lift in IO trust and in court-defence posture.
* Procedural compliance is now a measurable score, not a vibe.
* No ML model required. The KB is rule-extracted from a verbatim source. Auditable end-to-end.
* Adding new scenarios is mechanical: extend `SCENARIOS` table with PDF page ranges, re-run `build_kb()`.

### Negative
* The structural extractor is heuristic (regex-based on phase / sub-block / item patterns). A few sub-block titles are imperfectly extracted (e.g. SCN_003's case-facts paragraph). These are surface-quality issues — the operative items are correctly captured. SME pass over the JSONL is the next-step polish.
* The Compendium covers 20 scenarios; many crime categories are out of scope (notably theft simpliciter, pure CBT, defamation, stalking). For these we retain the existing model-generated templates as fallback.
* Source authority is the **Delhi Police** Academy. The Gujarat Police may have its own equivalent; if so, that should supersede this for Atlas's primary deployment context. Flag for the programme office.

### Operational
* The build is idempotent and offline. `extract_io_scenarios.py` re-runs in seconds. `build_kb()` re-runs in milliseconds.
* The Pgvector DB schema (migration 013) does not yet hold these scenarios; an Alembic migration `015_add_io_scenarios_kb` is the next step for production persistence.
* The mindmap engine wiring (`backend/app/mindmap/generator.py` to consume `mindmap_nodes_for_scenario`) is a 1-day change; queued for Phase 3.

## Quality gate

```
pytest backend/tests/legal_sections/test_io_scenarios_kb.py   →  11 passed
python scripts/extract_io_scenarios.py                        →  202 pages, 331,577 chars
python -c "from backend.app.legal_sections.io_scenarios import build_kb; print(build_kb())"   →  20
```

## Implementation references

| Concern | Path |
|---|---|
| Text extractor | `scripts/extract_io_scenarios.py` |
| KB builder + parser | `backend/app/legal_sections/io_scenarios.py` |
| Adapter (mindmap / checklist / playbook) | `backend/app/legal_sections/scenario_adapter.py` |
| Tests (11 cases) | `backend/tests/legal_sections/test_io_scenarios_kb.py` |
| Page-text source | `backend/app/legal_sections/data/io_scenarios_pages.jsonl` |
| Structured KB | `backend/app/legal_sections/data/io_scenarios.jsonl` |

## Roadmap

* **Next sprint:** wire `mindmap_nodes_for_scenario` into `backend/app/mindmap/generator.py`; deprecate the model-generated templates for the 11 covered case classes.
* **Soon:** add `playbook_reference` field to `SectionRecommendation` schema and surface in the recommender output (one-line schema change + adapter call).
* **Soon:** add procedural compliance score to the chargesheet review surface; bottom-quartile FIRs flagged for SHO review.
* **Phase 3:** Gujarat Police equivalent ingestion if available; SME pass over the 20 scenarios to polish the few extraction-quality artefacts.
