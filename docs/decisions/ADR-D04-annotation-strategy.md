# ADR-D04: FIR Annotation Strategy

**Status:** Accepted  
**Date:** 2026-04-08  
**Deciders:** Amit (Lead), Aditya (Backend/ML), Prishav (Frontend/NLP)  
**Sprint Gate:** Sprint 2

## Context

To fine-tune IndicBERT for FIR classification (ADR-D02) and NER, a labelled corpus is required. Key constraints:

- **Data sensitivity:** FIR data is Confidential police data; annotation tool must be self-hosted on-premise.
- **Annotation types needed:**
  1. Text classification — crime category label per FIR narrative (11 categories).
  2. Named Entity Recognition — PERSON, LOCATION, POLICE_STATION, DATE_TIME, IPC_SECTION, BNS_SECTION, VEHICLE, WEAPON.
- **Team size:** 2 annotators (domain experts from Gujarat Police).
- **Target volume:** 200 gold-standard annotated FIRs for Sprint 2 kick-off; 500 for Sprint 3 fine-tuning.
- **Budget:** Zero licensing cost.

## Candidates Evaluated

| Tool | Self-hosted | Free | GUI | Pre-annotation | Notes |
|---|---|---|---|---|---|
| Label Studio (OSS) | ✅ | ✅ | ✅ | ✅ | Docker image available |
| Doccano | ✅ | ✅ | ✅ | ❌ | NER only; no classification |
| Prodigy (Explosion) | ✅ | ❌ | ✅ | ✅ | Commercial licence required |
| BRAT | ✅ | ✅ | ⚠ dated | ❌ | No classification support |
| Manual CSV | ✅ | ✅ | ❌ | ❌ | No inter-annotator tooling |

## Decision

**Selected: Label Studio (Open-Source, self-hosted via Docker)**

Rationale:
1. Supports both classification (single-choice labels) and NER (span labels) in a single tool.
2. Zero-cost Docker image — deploys inside existing `docker-compose.yml`.
3. Export to JSON/CSV/CONLL compatible with HuggingFace `datasets.load_dataset("json")`.
4. Built-in inter-annotator agreement tracking via overlapping task assignment.
5. `label-studio-sdk` Python package enables programmatic project setup and task import.

## Annotation Workflow

```
FIR PDFs → batch_import_firs.py → ATLAS DB
       ↓
create_gold_standard.py (stratified 200-FIR sample)
       ↓
setup_labelstudio.py → Label Studio projects (FIR_NER + FIR_Category)
       ↓
Annotators label via Label Studio UI
       ↓
Export JSON → HuggingFace Dataset → app/ml/train.py
```

### Quality Controls
- Minimum 10% of tasks double-annotated for inter-annotator agreement (Cohen's κ ≥ 0.7 required to proceed).
- Disputed labels resolved by lead annotator during adjudication pass.
- Annotation guidelines document committed to `docs/training/annotation_guidelines.md`.

## Consequences

### Positive
- All annotation stays on-premise; no data leaves Gujarat Police infrastructure.
- Programmatic task import allows iterative active-learning loops in Sprint 3+.

### Negative / Risks
- Label Studio requires a PostgreSQL DB for production mode; shares existing `atlas_db` (acceptable at pilot scale).
- Annotators need 2--3 hour onboarding session on Label Studio UI.

## Sprint 2 Acceptance Criteria

- [ ] Label Studio accessible on `http://localhost:8080` via `docker compose up`.
- [ ] `scripts/setup_labelstudio.py` creates `FIR_NER` and `FIR_Category` projects without error.
- [ ] `scripts/create_gold_standard.py` produces a `gold_standard.jsonl` with 200 stratified FIR tasks.
- [ ] At least 1 annotator trained and able to label a test task in Label Studio UI.
