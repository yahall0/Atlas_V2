# ATLAS Sprint 2 — Engineering Task Prompts

**Sprint:** 2 of 8 | **Duration:** 14 calendar days | **Sprint Goal:** NLP foundation operational — IndicBERT inference scaffold live, Gujarati preprocessing pipeline complete, annotation infrastructure up, real FIR data flowing from eGujCop, and RBAC/annotation/multilingual ADRs all signed.
**Team:** Prishiv (Backend/ML/DevOps) + Aditya (Frontend/Data/NLP) + Amit (Lead)
**Date:** Sprint start = 8 April 2026 | Sprint end = 21 April 2026
**Velocity Assumption:** 40 SP total capacity (20 SP per developer)
**Sprint 2 Committed:** 34 SP (T15–T26) + 4 governance + 1 documentation = buffer-safe
**Model Decision (pre-decided):** IndicBERT (ai4bharat) — fine-tuned on FIR data, on-prem
**Annotation Tool (pre-decided):** Label Studio (self-hosted, free)
**Data Status:** Real anonymised eGujCop FIR data obtained
**GPU:** Local GPU available

---

## SPRINT 2 TASK MAP

```
DAY  1    2    3    4    5    6    7    8    9   10   11   12   13   14
     ████T15█                          ADR-D02 Sign-off (1SP)
     ████T16████                       ADR-D03 RBAC Deliberation (2SP)
          ████T17█                     ADR-D04 Annotation Strategy (2SP)
          ████T18████                  ADR-D06 Multilingual Pipeline (2SP)
          ████T19████████              Aditya: Label Studio + Guidelines (3SP)
               ████T20████████         Prishiv: Language Detection Module (3SP)
                    ████T21████████    Prishiv: Gujarati Preprocessing (4SP)
                         ████T22████████████ Prishiv: IndicBERT Scaffold (5SP)
                                   ████T23████ Prishiv: /predict API (3SP)
               ████T24████████          Aditya: Real FIR Batch Import (3SP)
                         ████T25████    Aditya: Dashboard Live Stats (2SP)
                              ████T26████████ Aditya: FIR Browse UI (3SP)
DOC2 █                                         DOC2: Sprint 2 Docs (1SP)
GOV5 █    GOV6 █              GOV7 █          GOV8 █
```

---

---

# T15-PROMPT — ADR-D02 Sign-off: IndicBERT Model Selection

**Assignee:** Prishiv + Aditya | **Story Points:** 1 | **Days:** 1 | **Jira:** ATLAS-T15

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) + Aditya (Frontend/Data/NLP) — 1.5 hours on Day 1

### ENVIRONMENT

Claude.ai / Google Docs for live ADR drafting. No code required.

### EXACT TOOLS

Claude.ai (reference lookup), wiki/docs folder, Jira

### OBJECTIVE

Formalise the pre-agreed IndicBERT model selection decision into a signed ADR-D02 that unblocks T20 (IndicBERT scaffold), T19 (preprocessing pipeline design), and the annotation volume planning in T17.

### INPUTS

- Pre-agreed decision: IndicBERT (ai4bharat/indic-bert) for classification and NER tasks
- R01-fir-legal-standards.md §6 — data quality issues
- ADR-D02 template from D02-PROMPT in ADR-D1-D12.md

### STEPS

**Step 1: Draft the ADR**

```bash
claude "Write ADR-D02 for the ATLAS project. The team has decided:

Model Selection: ai4bharat/indic-bert (IndicBERT) — fine-tuned on ATLAS FIR data

Task allocation:
- Crime-type classification (9 ATLAS categories): IndicBERT fine-tuned classifier
- Named Entity Recognition (persons, places, dates, sections): IndicBERT fine-tuned NER
- Section number extraction (BNS/IPC codes): Rule-based regex + mapping table (no model needed)
- MO code suggestion: Deferred to Sprint 4 — insufficient labelled data in Sprint 2
- Language detection: fastText langdetect (lightweight, proven for Indic scripts)

Rationale for IndicBERT:
- Pre-trained on IndicCorp including Gujarati — best Indic language performance of all on-prem options
- 110M parameters — runs on local GPU and on Gujarat State Data Centre CPU in production
- MIT license — no deployment complications for government use
- Zero ongoing API cost after fine-tuning
- Data residency: fully on-premise — FIR text never leaves Gujarat Police infrastructure

Infrastructure: local GPU for fine-tuning; CPU-viable at inference time (~200ms/FIR)
Fine-tuning plan: Requires 2,000–5,000 labelled FIRs per task (annotation starts Sprint 2 via T17/T18)
Annotation begins: Sprint 2 (T17 — Label Studio setup, T18 — gold standard creation)
Fine-tuning scheduled: Sprint 3–4 (once adequate labels are available)

Open question resolved: Data residency — all model inference stays on-prem (no GPT-4o API calls)
Open question deferred: MO code suggestion — will revisit at Sprint 4 retrospective if labels available

Format this as a proper ADR markdown document with Context, Decision, Consequences (positive/negative/risks), and Sign-off section. Store at: atlas-project/docs/decisions/ADR-D02-model-selection.md"
```

**Step 2: Commit the ADR**

Commit `ADR-D02-model-selection.md` to `docs/decisions/` via `feature/T15-adr-d02-sign-off` branch.

### VALIDATION COMMAND

```bash
# Verify file exists:
Test-Path "D:\sem2\RP\atlas-project\docs\decisions\ADR-D02-model-selection.md"

# Verify it has all required sections:
Select-String -Path "ADR-D02-model-selection.md" -Pattern "Status:|Decision|Consequences|Sign-off"
```

### DONE WHEN

- [ ] ADR-D02-model-selection.md committed to `docs/decisions/`
- [ ] All three members have signed off (or are listed as sign-off pending)
- [ ] Jira stories T20 (IndicBERT), T19 (preprocessing) unblocked via ADR link
- [ ] Sprint 2 backlog annotation volume target set (from fine-tuning requirement)
- [ ] Jira ATLAS-T15 moved to Done

### STORE AT

`atlas-project/docs/decisions/ADR-D02-model-selection.md`

### DORA METRIC

**Lead Time (LT)** — formalising the model decision unblocks T19–T23, turning a 1-hour decision into 5 sprint-days of unblocked engineering.

---
---

# T16-PROMPT — ADR-D03: RBAC Matrix Deliberation (6-Role Permission Matrix)

**Assignee:** Amit (Facilitator) + Prishiv + Aditya | **Story Points:** 2 | **Days:** 1–2 | **Jira:** ATLAS-T16

---

### ROLE + EST TIME

Amit (Facilitator) — 60 minutes Day 1
Prishiv (Backend/ML/DevOps) — 60 minutes Day 1
Aditya (Frontend/Data/NLP) — 60 minutes Day 1

### ENVIRONMENT

Shared screen or meeting room. Claude.ai open for real-time reference. Jira visible.
Sprint 1 already implemented a 6-role RBAC system in `backend/app/core/rbac.py` — this ADR formalises and extends it.

### EXACT TOOLS

Claude.ai, existing `backend/app/core/rbac.py` and `backend/app/core/pii.py` for reference, Google Sheets (permission matrix), ADR template

### OBJECTIVE

Sign ADR-D03 that locks the complete CRUD × Role permission matrix for all ATLAS features, including data masking rules for sensitive fields (BNS Ch.V victim identity). The Sprint 1 RBAC implementation must be validated against this matrix and any gaps closed in Sprint 2.

### INPUTS

- Existing Sprint 1 RBAC: `Role.IO`, `Role.SHO`, `Role.DYSP`, `Role.SP`, `Role.ADMIN`, `Role.READONLY`
- Existing PII masking: `backend/app/core/pii.py` — Aadhaar/phone masking, name truncation for READONLY/DYSP
- D03-PROMPT in `ADR-D1-D12.md` — full permission matrix template
- R01-fir-legal-standards.md §1.1 (officer hierarchy)

### STEPS

**Step 1: Validate Sprint 1 RBAC against the matrix template**

```bash
claude "Review the existing RBAC implementation in backend/app/core/rbac.py and backend/app/core/pii.py against the ATLAS-D03 RBAC matrix template. The 6 roles are: IO, SHO, DYSP, SP, ADMIN, READONLY.

For each of the following feature areas, tell me what permission is currently implemented and what is MISSING:
1. View FIRs at own station vs. cross-station
2. Upload/ingest a new FIR (PDF)
3. Override NLP classification result
4. View victim identity in BNS Ch.V (sexual offence) cases
5. Export data (CSV/PDF)
6. Manage user accounts
7. View audit log
8. View system metrics (Prometheus/Grafana)
9. Configure NLP model parameters
10. View bias audit reports

For each gap, specify: which endpoint needs a guard, which role(s) should have access, and what the exact FastAPI Depends() call should be."
```

**Step 2: Run the deliberation session** (follow D03-PROMPT agenda from ADR-D1-D12.md)

Key decisions to lock in 60 minutes:
- Can IO/SHO see victim identity in rape/POCSO cases by default, or is it masked? (Legal requirement: BNS S.228A equivalent — masked by default for all; unmask requires SHO-level justification recorded in audit log)
- Can NLP classifications be overridden, and by whom?
- Who can export data?

**Step 3: Implement gaps**

```bash
claude "Based on the gap analysis, update backend/app/core/rbac.py and the relevant API route files to implement the missing permission guards identified in Step 1. Specifically:

1. Add a require_role guard to POST /firs (create FIR from JSON) — IO, SHO, ADMIN only
2. Add classification override endpoint PATCH /firs/{fir_id}/classification — SHO, DYSP, SP, ADMIN
3. Add audit log entry for any classification override (who changed, from what, to what, timestamp)
4. Ensure victim_name, victim_address in BNS Ch.V offences are masked for all roles by default in pii.py
5. Document the unmasking procedure in a comment: SHO+ can request unmask via PATCH /firs/{fir_id}/unmask-victim with justification stored in audit_log

Write tests for each new guard in backend/tests/test_fir.py"
```

**Step 4: Commit ADR-D03**

```bash
claude "Write ADR-D03 for ATLAS. Embed the complete permission matrix as a markdown table with these columns: Feature/Action | IO | SHO | DYSP | SP | ADMIN | READONLY. Use C=Create, R=Read, U=Update, D=Delete, -=No Access, R*=Restricted (masked/logged). Include the data masking rules section for BNS Ch.V victim identity."
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend
python -m pytest tests/test_fir.py -v --tb=short

# Verify new guard tests pass:
python -m pytest tests/ -v -k "rbac or classification or override" --tb=short
```

### DONE WHEN

- [ ] Complete CRUD × Role matrix finalised (all 10 feature areas covered)
- [ ] Data masking rules for BNS Ch.V victim identity documented
- [ ] Missing RBAC guards implemented and tested
- [ ] Classification override endpoint implemented with audit log
- [ ] ADR-D03 committed to `docs/decisions/`
- [ ] All tests passing (32+ passing, 0 failed)
- [ ] Jira ATLAS-T16 moved to Done

### STORE AT

`atlas-project/docs/decisions/ADR-D03-rbac-matrix.md`
`Atlas_Platform/backend/app/core/rbac.py` (updated)
`Atlas_Platform/backend/app/core/pii.py` (updated)

### DORA METRIC

**Change Failure Rate (CFR)** — a locked permission matrix prevents security regressions from future feature additions.

---
---

# T17-PROMPT — ADR-D04: Annotation Strategy + Label Studio Deployment

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 2–4 | **Jira:** ATLAS-T17

---

### ROLE + EST TIME

Aditya (Frontend/Data/NLP) — 6 hours across Days 2–4
Amit (Facilitator for the ADR session) — 60 minutes Day 2

### ENVIRONMENT

Claude Code terminal. Docker Desktop for Label Studio. Access to real anonymised eGujCop FIR data.

### EXACT TOOLS

Label Studio (Docker), Python 3.11, pandas, Label Studio SDK, ADR template

### OBJECTIVE

(1) Sign ADR-D04 confirming Label Studio + hybrid annotator strategy. (2) Deploy Label Studio locally with annotation project configured for ATLAS tasks. (3) Write annotation guidelines document. (4) Identify the gold-standard FIR set (200 FIRs) from real data for Prishiv + Aditya to annotate as ground truth.

### INPUTS

- Real anonymised eGujCop FIR data (obtained)
- D04-PROMPT in `ADR-D1-D12.md`
- ADR-D02 (IndicBERT) — defines annotation schema (9 categories for classification; entity types for NER)
- ADR-D06 output (once T18 is done) — defines which preprocessing to apply to FIR text before annotation

### STEPS

**Step 1: Deploy Label Studio**

```bash
# Add Label Studio to Docker Compose:
claude "Add a 'labelstudio' service to D:\sem2\RP\Atlas_Platform\docker-compose.yml:
- Image: heartexlabs/label-studio:latest
- Port: 8080:8080
- Volumes: atlas_labelstudio_data:/label-studio/data
- Environment: LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true, LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files
- Health check: curl -f http://localhost:8080/health || exit 1
- Named volume: atlas_labelstudio_data (add to existing volumes section)
Also add the volume to the volumes section at the bottom of docker-compose.yml"
```

**Step 2: Configure annotation project schema**

```bash
claude "Write a Python script (scripts/setup_labelstudio.py) that uses the Label Studio SDK to:

1. Create a Label Studio project called 'ATLAS-FIR-Classification' with this labelling config:
   - Task type: Text Classification
   - Choices (single): violent_crimes, crimes_against_women_children, property_crimes, financial_economic_crime, cyber_crimes, organised_serious_crimes, public_order_offences, traffic_negligence, missing_persons_misc
   - Text field: narrative (the FIR narrative text)

2. Create a second project called 'ATLAS-FIR-NER' with:
   - Task type: Named Entity Recognition
   - Labels: PERSON_ACCUSED, PERSON_COMPLAINANT, PERSON_WITNESS, LOCATION_OCCURRENCE, LOCATION_ADDRESS, DATE_OCCURRENCE, DATE_FIR, BNS_SECTION, WEAPON, PROPERTY_ITEM
   - Text field: narrative

3. Load the first 200 FIRs from the gold-standard CSV (scripts/gold_standard_firs.csv) as tasks into both projects.
   The CSV format is: fir_id, district, police_station, narrative, sections (comma-separated)

Use environment variable LABEL_STUDIO_TOKEN for auth. Print project URLs on completion.

Requirements: pip install label-studio-sdk pandas"
```

**Step 3: Write annotation guidelines**

```bash
claude "Write annotation guidelines for ATLAS FIR labelling (docs/annotation/guidelines-v1.md). Cover:

1. CLASSIFICATION TASK
   - Decision tree for each of the 9 ATLAS categories (based on ATLAS category × BNS section mapping from R01 §3.1)
   - Golden rules: (a) always classify by PRIMARY offence if multiple sections; (b) if unclear, use 'organised_serious_crimes' as a catch-all only for S.111/S.112 offences
   - Tie-breaking procedure: two annotators disagree → Aditya adjudicates → record in adjudication log

2. NER TASK
   - Entity type definitions with 2 examples each (positive + negative example)
   - How to handle overlapping entities
   - How to handle Gujarati script vs. Romanised Gujarati names
   - Aadhaar numbers: annotate as PERSON_ACCUSED/COMPLAINANT parent entity, NOT as separate entity
   - BNS_SECTION: annotate the full pattern 'BNS Section 303' or 'S.103 BNS' — include both number and prefix

3. QUALITY STANDARDS
   - Minimum inter-annotator agreement: Cohen's κ ≥ 0.80 on classification, token-level F1 ≥ 0.75 on NER
   - Ambiguous cases: mark with 'AMBIGUOUS' label — do not guess
   - Speed target: ~15–20 FIRs/hour for classification, ~8–10 FIRs/hour for NER

4. GOLD STANDARD SET
   - 200 FIRs selected by stratified sampling: ~22 per category (9 × 22 = 198 + 2 extra)
   - Primary annotators: Prishiv + Aditya (both annotate independently)
   - Adjudication: Aditya resolves disagreements, records reasoning
   - Timeline: all 200 labelled by Day 8 of Sprint 2"
```

**Step 4: Create gold standard FIR CSV**

```bash
claude "Write a Python script (scripts/create_gold_standard.py) that:

1. Reads real anonymised eGujCop FIR data from data/raw/egujcop_anonymised.csv (or equivalent)
2. Inspects available fields: district, police_station, sections, narrative text
3. Performs stratified sampling to select 200 FIRs distributed across:
   - All 6 pilot districts (Ahmedabad City, Ahmedabad Rural, Surat City, Vadodara City, Rajkot City, Gandhinagar)
   - All 9 ATLAS crime categories (infer from BNS sections using BNS-to-category mapping dict)
4. Outputs scripts/gold_standard_firs.csv with columns: fir_id, district, police_station, sections, narrative, estimated_category (from section mapping — for annotator reference only, NOT ground truth)
5. Prints sampling statistics: count per district, count per estimated category

BNS-to-category mapping to embed in the script (from R01 §3.1):
- S.100-S.146: violent_crimes
- S.63-S.99: crimes_against_women_children
- S.303-S.334: property_crimes
- S.318, S.336-S.340: financial_economic_crime
- S.111, S.113, S.147-S.158: organised_serious_crimes
- S.189-S.202, S.270-S.296: public_order_offences
- S.106, S.125: traffic_negligence
- S.137-S.140: missing_persons_misc
- cyber + IT Act mentions: cyber_crimes"
```

**Step 5: Sign ADR-D04**

```bash
claude "Write ADR-D04 for ATLAS confirming:
- Tool: Label Studio (self-hosted Docker, port 8080)
- Annotator model: Hybrid — Prishiv + Aditya annotate gold standard (200 FIRs); BITS Pilani students annotate bulk (2,000+ FIRs) in Sprints 3–4; Aditya adjudicates disagreements
- Target volume: 200 gold-standard FIRs by end of Sprint 2; 2,000 bulk FIRs by end of Sprint 4
- Quality threshold: Cohen's κ ≥ 0.80 for classification, F1 ≥ 0.75 for NER
- Projects configured: ATLAS-FIR-Classification and ATLAS-FIR-NER
- Annotation guidelines: docs/annotation/guidelines-v1.md"
```

### VALIDATION COMMAND

```bash
# Verify Label Studio is running:
curl -s http://localhost:8080/health

# Verify projects exist:
python scripts/setup_labelstudio.py --verify

# Verify gold standard CSV:
python -c "import pandas as pd; df = pd.read_csv('scripts/gold_standard_firs.csv'); print(f'Rows: {len(df)}'); print(df['estimated_category'].value_counts())"

# Verify annotation guidelines exist:
Test-Path "D:\sem2\RP\atlas-project\docs\annotation\guidelines-v1.md"
```

### DONE WHEN

- [ ] Label Studio running at `http://localhost:8080` and added to `docker-compose.yml`
- [ ] Both annotation projects created (classification + NER) with correct label schemas
- [ ] 200 gold-standard FIRs loaded as tasks in Label Studio
- [ ] Annotation guidelines committed to `docs/annotation/guidelines-v1.md`
- [ ] `scripts/create_gold_standard.py` and `scripts/setup_labelstudio.py` committed
- [ ] ADR-D04 committed to `docs/decisions/`
- [ ] Jira ATLAS-T17 moved to Done

### STORE AT

`atlas-project/docs/decisions/ADR-D04-annotation-strategy.md`
`atlas-project/docs/annotation/guidelines-v1.md`
`Atlas_Platform/scripts/create_gold_standard.py`
`Atlas_Platform/scripts/setup_labelstudio.py`

### DORA METRIC

**Lead Time (LT)** — annotation infrastructure unblocks the entire fine-tuning → model quality → UAT chain. Delay here cascades to V01 gate.

---
---

# T18-PROMPT — ADR-D06: Multilingual Pipeline Architecture Decision

**Assignee:** Amit (Facilitator) + Both Developers | **Story Points:** 2 | **Days:** 2–3 | **Jira:** ATLAS-T18

---

### ROLE + EST TIME

Amit (Facilitator) — 75 minutes Day 2
Prishiv — 75 minutes Day 2
Aditya — 75 minutes Day 2

### ENVIRONMENT

Meeting room / shared screen. Claude.ai for real-time research. No code in this session — the implementation is T19–T20.

### EXACT TOOLS

Claude.ai, D06-PROMPT from ADR-D1-D12.md, sample FIR texts (5 examples showing 4 text patterns)

### OBJECTIVE

Sign ADR-D06 that locks the multilingual NLP pipeline architecture — specifically how ATLAS handles the 4 FIR text patterns: pure Gujarati, pure English, code-mixed Gujarati-English, and Romanised Gujarati. The decision directly determines T19 (preprocessing) and T20 (IndicBERT input preparation) implementation.

### INPUTS

- D06-PROMPT from ADR-D1-D12.md (4 options: translate-to-English, normalise-to-Gujarati, multilingual-native, detect-and-route)
- ADR-D02 (IndicBERT chosen) — IndicBERT is multilingual-native (trained on IndicCorp), so Option C is strongly favoured
- 5 sample FIR texts from real data showing each text pattern
- IndicNLP library documentation

### RECOMMENDATION FOR SESSION

Given ADR-D02 selected IndicBERT (pre-trained on multilingual IndicCorp including Gujarati + English):

**Recommended decision: Option C (Multilingual-Native) with script normalisation pre-step**

Pipeline:
```
[Raw FIR Text]
  → Stage 1: Language detection (fastText — classify as gu/en/mixed/romanised)
  → Stage 2: Script normalisation (Unicode NFC; Gujarati script U+0A80–U+0AFF validation)
  → Stage 3: Romanised Gujarati → Gujarati script (IndicXlit if detected as romanised)
  → Stage 4: IndicNLP tokenisation (preserves Gujarati word boundaries)
  → Stage 5: IndicBERT tokeniser (SentencePiece subword; handles code-mixed natively)
```

Bring this recommendation into the session and debate — if team agrees, commit. If debate arises on Romanised Gujarati handling, note it as an open risk.

### STEPS

**Step 1: Run the D06 deliberation session** (follow the agenda from D06-PROMPT, 75 minutes)

**Step 2: Document the pipeline decision**

```bash
claude "Write ADR-D06 for ATLAS confirming the multilingual NLP pipeline architecture. The team decided Option C (Multilingual-Native Pipeline) with the following stage-by-stage specification:

Stage 1 - Language Detection:
  Tool: fastText langdetect (lid.176.bin model)
  Output: language tag ('gu', 'en', 'mixed', 'romanised_gu')
  Fallback: if confidence < 0.7, tag as 'mixed'

Stage 2 - Unicode Normalisation:
  Tool: Python unicodedata.normalize('NFC', text)
  Purpose: Gujarati script uses combining diacritics; NFC ensures consistent encoding

Stage 3 - Romanised Gujarati Transliteration (conditional):
  Trigger: only if Stage 1 detects 'romanised_gu'
  Tool: ai4bharat/IndicXlit (xlit Python library)
  Target: Gujarati script (gu)
  Fallback: if IndicXlit fails, pass as-is (IndicBERT handles some Romanised input)

Stage 4 - Tokenisation:
  Tool: IndicNLP (indic_tokenize.trivial_tokenize for Gujarati)
  Purpose: Segment text at word boundaries before subword tokenisation

Stage 5 - IndicBERT Tokeniser:
  Tool: ai4bharat/indic-bert SentencePiece tokeniser (via HuggingFace AutoTokenizer)
  Max tokens: 512 (truncate narratives > 512 tokens from the START to preserve closing text)
  Output: input_ids, attention_mask tensors for IndicBERT

Code-mixing handling: pass as-is to IndicBERT after NFC normalisation. IndicBERT handles English tokens natively via its multilingual vocabulary.

Include a pipeline diagram in ASCII art and a table of tools with pip install commands."
```

### VALIDATION COMMAND

```bash
# Verify ADR-D06 exists:
Test-Path "D:\sem2\RP\atlas-project\docs\decisions\ADR-D06-multilingual-pipeline.md"

# Quick smoke test of tool availability (run after T19 is complete):
python -c "import fasttext; import indicnlp; from transformers import AutoTokenizer; print('All pipeline tools available')"
```

### DONE WHEN

- [ ] Deliberation session ran with all three team members
- [ ] Pipeline option decided (Option C recommended)
- [ ] Stage-by-stage tool selections documented with version numbers
- [ ] ADR-D06 committed to `docs/decisions/`
- [ ] T19 (preprocessing) and T20 (IndicBERT) implementation tasks updated with specific tool choices from this ADR
- [ ] Jira ATLAS-T18 moved to Done

### STORE AT

`atlas-project/docs/decisions/ADR-D06-multilingual-pipeline.md`

### DORA METRIC

**Lead Time (LT)** — pipeline architecture decision directly constrains T19 and T20 implementation scope, preventing rework if tool choices need to change.

---
---

# T19-PROMPT — Language Detection + Script Normalisation Module

**Assignee:** Prishiv | **Story Points:** 3 | **Days:** 3–5 | **Jira:** ATLAS-T19

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) — 8 hours across Days 3–5

### ENVIRONMENT

Claude Code terminal. Python 3.11. Local GPU available (not needed for this task). Depends on T18 (ADR-D06 pipeline spec).

### EXACT TOOLS

fastText (langdetect), unicodedata (stdlib), ai4bharat/IndicXlit, pytest

### OBJECTIVE

Implement Stage 1–3 of the multilingual pipeline: language detection for FIR text → Unicode NFC normalisation → conditional Romanised Gujarati transliteration. This module is consumed by T20 (preprocessing) and T21 (IndicBERT).

### INPUTS

- ADR-D06 (signed in T18) — stage-by-stage spec
- Real anonymised FIR samples (4 text patterns, at least 5 examples each)
- fastText language ID model (lid.176.bin — download during setup)

### STEPS

**Step 1: Install dependencies**

```bash
# Add to backend/requirements.txt:
# fasttext-wheel==0.9.2  (pre-built wheels; no C++ compile)
# xlit==1.2              (IndicXlit for Romanised-Gujarati transliteration)
# indic-nlp-library==0.91

pip install fasttext-wheel xlit indic-nlp-library

# Download fastText language detection model:
Invoke-WebRequest -Uri "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin" -OutFile "backend/models/lid.176.bin"
```

**Step 2: Implement the language detection + normalisation module**

```bash
claude "Create backend/app/nlp/language.py with the following:

1. Function detect_language(text: str) -> dict:
   - Loads fastText model from path in config (FASTTEXT_MODEL_PATH env var, default: 'backend/models/lid.176.bin')
   - Detects primary language of text
   - Returns: {'language': str ('gu'|'en'|'mixed'|'romanised_gu'), 'confidence': float}
   - Mixed detection logic: if top-2 predictions are 'gu' and 'en' with confidence gap < 0.3, return 'mixed'
   - Romanised Gujarati detection: if predicted 'en' but text contains common Gujarati Romanisation patterns (regex: r'(?:aavyo|karyo|hato|hati|avyu|chhe|nathi|ane|thi|ma |nu |ni )'), return 'romanised_gu' with confidence 0.6
   - If confidence < 0.7, return 'mixed' as safe fallback
   - Cache the model at module level (load once on first call)

2. Function normalise_text(text: str) -> str:
   - Apply unicodedata.normalize('NFC', text)
   - Remove zero-width joiners and zero-width non-joiners only if they appear outside a Gujarati character's required combining sequence (use character ranges U+0A80–U+0AFF)
   - Return normalised text

3. Function transliterate_romanised_gujarati(text: str) -> str:
   - Use IndicXlit to transliterate Romanised Gujarati to Gujarati script
   - Wrap in try/except — if IndicXlit fails for any reason, return original text unchanged and log a warning
   - Log (structlog) every transliteration with: input length, output language, confidence

4. Function preprocess_text(text: str) -> dict:
   - Runs the full Stage 1–3 pipeline in order
   - Returns: {'original': str, 'language': str, 'confidence': float, 'processed': str, 'steps_applied': list[str]}
   - steps_applied tracks which stages were executed, e.g. ['normalise', 'transliterate']

Write pytest tests in backend/tests/test_nlp_language.py:
- test_detect_pure_gujarati: input with Gujarati Unicode chars → should return 'gu'
- test_detect_pure_english: input 'The accused broke into the house' → should return 'en'
- test_detect_mixed: a sentence with both Gujarati and English → should return 'mixed'
- test_normalise_nfc: verify NFC normalisation on a composed Gujarati character
- test_preprocess_returns_dict: verify preprocess_text returns all required keys

Use pytest.mark.parametrize for test cases. Mark tests requiring fastText model with pytest.mark.requires_model."
```

**Step 3: Add config entry**

```bash
claude "Add to backend/app/core/config.py:
FASTTEXT_MODEL_PATH: str = os.getenv('FASTTEXT_MODEL_PATH', 'backend/models/lid.176.bin')
INDICXLIT_ENABLED: bool = os.getenv('INDICXLIT_ENABLED', 'true').lower() == 'true'"
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend

# Run language module tests (those that don't require model download):
python -m pytest tests/test_nlp_language.py -v -m "not requires_model" --tb=short

# Quick manual smoke test (requires model downloaded):
python -c "
from app.nlp.language import preprocess_text
result = preprocess_text('accused e victim ne BNS Section 303 hethal threat kari')
print(result)
"
```

### DONE WHEN

- [ ] `backend/app/nlp/__init__.py` and `backend/app/nlp/language.py` created
- [ ] `lid.176.bin` downloaded to `backend/models/` (gitignored)
- [ ] All non-model-dependent tests passing
- [ ] `preprocess_text()` handles all 4 text patterns without crashing
- [ ] `fasttext-wheel`, `xlit`, `indic-nlp-library` added to `requirements.txt`
- [ ] PR merged: `feature/T19-language-detection` → `develop`
- [ ] Jira ATLAS-T19 moved to Done

### STORE AT

`Atlas_Platform/backend/app/nlp/language.py`
`Atlas_Platform/backend/app/nlp/__init__.py`
`Atlas_Platform/backend/tests/test_nlp_language.py`
`Atlas_Platform/backend/models/.gitkeep` (models dir, gitignored contents)

### DORA METRIC

**Lead Time (LT)** — language detection is the first stage of the NLP pipeline; unblocks T20 (preprocessing) which unblocks T21 (IndicBERT).

---
---

# T20-PROMPT — Gujarati Text Preprocessing Pipeline (IndicNLP Tokenisation)

**Assignee:** Prishiv | **Story Points:** 4 | **Days:** 4–7 | **Jira:** ATLAS-T20

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) — 10 hours across Days 4–7

### ENVIRONMENT

Claude Code terminal. Python 3.11. Local GPU. Depends on T19 (language detection module) and T18 (ADR-D06 pipeline spec, which specifies IndicNLP for Stage 4).

### EXACT TOOLS

indic-nlp-library (indic_tokenize), HuggingFace transformers (AutoTokenizer for IndicBERT), torch 2.x, pytest

### OBJECTIVE

Implement Stages 4–5 of the multilingual pipeline: IndicNLP word-level tokenisation followed by IndicBERT SentencePiece subword tokenisation. Output: `input_ids` and `attention_mask` tensors ready for IndicBERT classification or NER inference.

### INPUTS

- T19 `language.py` module — `preprocess_text()` output is the input here
- ADR-D06 — Stage 4 (IndicNLP) and Stage 5 (IndicBERT tokeniser) spec
- ADR-D02 — model ID: `ai4bharat/indic-bert` on HuggingFace

### STEPS

**Step 1: Install tokenisation dependencies**

```bash
# Verify indic-nlp-library already installed from T19
# Add to requirements.txt:
# transformers>=4.38.0
# torch>=2.2.0
# sentencepiece>=0.1.99

pip install "transformers>=4.38.0" "torch>=2.2.0" "sentencepiece>=0.1.99"
```

**Step 2: Implement the tokenisation pipeline**

```bash
claude "Create backend/app/nlp/preprocessing.py with the following:

1. Function segment_words(text: str, language: str) -> list[str]:
   - If language in ('gu', 'mixed', 'romanised_gu'): use indic_tokenize.trivial_tokenize(text, lang='gu')
   - If language == 'en': use text.split() as simple fallback (IndicBERT tokeniser handles English subwords)
   - Returns list of word tokens

2. Class IndicBERTPreprocessor:
   __init__(self, model_name: str = 'ai4bharat/indic-bert', max_length: int = 512):
     - Load AutoTokenizer.from_pretrained(model_name)
     - Cache tokenizer at instance level
     - Store max_length

   def encode(self, text: str, language: str = 'mixed') -> dict:
     - Input: text (after normalisation/transliteration from preprocess_text()) and language tag
     - Run segment_words() to get word tokens
     - Rejoin words with spaces (IndicBERT tokeniser performs its own subword segmentation)
     - Apply self.tokenizer(text, max_length=self.max_length, truncation=True, padding='max_length', return_tensors='pt')
     - Returns: {'input_ids': Tensor, 'attention_mask': Tensor, 'word_count': int, 'was_truncated': bool}

   def encode_batch(self, texts: list[str], languages: list[str] = None) -> dict:
     - Batch encode a list of texts
     - Returns batched tensors

3. Function full_pipeline(raw_text: str) -> dict:
   - Calls preprocess_text() from language.py
   - Calls IndicBERTPreprocessor().encode() with the processed text and detected language
   - Returns merged dict: {original, language, confidence, processed, steps_applied, input_ids, attention_mask, word_count, was_truncated}

Write pytest tests in backend/tests/test_nlp_preprocessing.py:
- test_segment_gujarati: Gujarati text → non-empty word list containing expected tokens
- test_segment_english: 'the accused broke into the house' → at least 7 tokens
- test_encode_returns_tensors: full_pipeline() returns dict with 'input_ids' key
- test_truncation: text > 512 tokens is truncated; was_truncated=True
- test_batch_encode: encode_batch(['text1', 'text2']) returns correct batch shape

Mark tests requiring model download with pytest.mark.requires_model"
```

**Step 3: Wire into FIR ingestion pipeline**

```bash
claude "Update backend/app/ingestion/pipeline.py to call full_pipeline() from app.nlp.preprocessing when a FIR is successfully parsed.

Add to the FIR record after successful parse:
- fir['nlp_language_detected'] = pipeline_result['language']
- fir['nlp_tokens_count'] = pipeline_result.get('word_count', 0)
- fir['nlp_was_truncated'] = pipeline_result.get('was_truncated', False)

Store these three fields in a new JSONB column 'nlp_metadata' on the firs table (add via Alembic migration).

Create Alembic migration: backend/alembic/versions/002_add_nlp_metadata.py
- upgrade(): ALTER TABLE firs ADD COLUMN nlp_metadata JSONB DEFAULT '{}'
- downgrade(): ALTER TABLE firs DROP COLUMN nlp_metadata"
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend

# Run preprocessing tests (non-model-dependent):
python -m pytest tests/test_nlp_preprocessing.py -v -m "not requires_model" --tb=short

# Full pipeline smoke test (requires model download ~400MB on first run):
python -c "
from app.nlp.preprocessing import full_pipeline
result = full_pipeline('ફરિયાદી એ જણાવ્યું કે આરોપીએ BNS Section 303 હેઠળ ધમકી આપી.')
print('Language:', result['language'])
print('Word count:', result['word_count'])
print('Input IDs shape:', result['input_ids'].shape)
"

# Verify migration file:
Test-Path "backend/alembic/versions/002_add_nlp_metadata.py"
```

### DONE WHEN

- [ ] `backend/app/nlp/preprocessing.py` implemented with `IndicBERTPreprocessor` and `full_pipeline()`
- [ ] `transformers`, `torch`, `sentencepiece` added to `requirements.txt`
- [ ] `002_add_nlp_metadata.py` Alembic migration written
- [ ] `process_pdf()` in `pipeline.py` populates `nlp_metadata` field
- [ ] Tests pass for non-model-dependent cases
- [ ] PR merged: `feature/T20-preprocessing-pipeline` → `develop`
- [ ] Jira ATLAS-T20 moved to Done

### STORE AT

`Atlas_Platform/backend/app/nlp/preprocessing.py`
`Atlas_Platform/backend/tests/test_nlp_preprocessing.py`
`Atlas_Platform/backend/alembic/versions/002_add_nlp_metadata.py`

### DORA METRIC

**Lead Time (LT)** — preprocessing pipeline unblocks T21 (IndicBERT inference scaffold). All downstream NLP quality depends on getting this right.

---
---

# T21-PROMPT — IndicBERT Inference Scaffold + Zero-Shot Baseline

**Assignee:** Prishiv | **Story Points:** 5 | **Days:** 6–10 | **Jira:** ATLAS-T21

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) — 14 hours across Days 6–10

### ENVIRONMENT

Claude Code terminal. Local GPU required (IndicBERT inference is GPU-accelerated). Python 3.11, PyTorch 2.x, HuggingFace `transformers`. Depends on T19 and T20.

### EXACT TOOLS

`ai4bharat/indic-bert` (HuggingFace), PyTorch 2.x, HuggingFace `Trainer` API, MLflow (experiment tracking), pytest

### OBJECTIVE

(1) Load IndicBERT and verify it can classify FIR text into 9 ATLAS categories in zero-shot mode (as a sanity baseline before fine-tuning). (2) Build the fine-tuning harness (`train.py`) that Prishiv will run in Sprint 3 once labels are available from T17. (3) Build the inference module (`classify.py`) that T22 (`/predict/classify` endpoint) will call.

### INPUTS

- T19 `preprocess_text()` + T20 `full_pipeline()` outputs
- ADR-D02 — model: `ai4bharat/indic-bert`, tasks: classification (9 categories) + NER
- At least 20 manually labelled FIR examples from gold standard (minimal set from T17 annotation start)

### STEPS

**Step 1: Download and verify IndicBERT**

```bash
python -c "
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained('ai4bharat/indic-bert')
tokenizer = AutoTokenizer.from_pretrained('ai4bharat/indic-bert')
print('IndicBERT loaded. Parameters:', sum(p.numel() for p in model.parameters()), 'Vocab size:', tokenizer.vocab_size)
"
# Expected: ~110M parameters, vocab size ~200,000 (SentencePiece multilingual)
```

**Step 2: Build the classification model and inference module**

```bash
claude "Create backend/app/nlp/classify.py with:

1. Class ATLASClassifier(nn.Module):
   - Wraps ai4bharat/indic-bert with a classification head
   - __init__(self, num_labels=9, model_name='ai4bharat/indic-bert'):
     - self.bert = AutoModel.from_pretrained(model_name)
     - self.dropout = nn.Dropout(0.3)
     - self.classifier = nn.Linear(768, num_labels)  # IndicBERT hidden=768
   - forward(self, input_ids, attention_mask) -> logits tensor (shape: batch × 9)

2. ATLAS_CATEGORIES list (ordered, index = class label):
   ['violent_crimes', 'crimes_against_women_children', 'property_crimes',
    'financial_economic_crime', 'cyber_crimes', 'organised_serious_crimes',
    'public_order_offences', 'traffic_negligence', 'missing_persons_misc']

3. Function load_model(model_path: str = None) -> ATLASClassifier:
   - If model_path provided and file exists: load fine-tuned weights via torch.load
   - Else: return base IndicBERT model with random classification head (zero-shot / pretrain-only baseline)
   - Move model to GPU if available (torch.cuda.is_available()), else CPU
   - Set to eval mode

4. Function classify_fir(text: str, model: ATLASClassifier = None, return_probabilities: bool = True) -> dict:
   - If model is None: use module-level cached model (loaded on first call)
   - Calls full_pipeline(text) from preprocessing.py to get input_ids and attention_mask
   - Runs model forward pass
   - Returns: {'predicted_category': str, 'confidence': float, 'probabilities': dict[str, float], 'model_version': str, 'inference_time_ms': float}
   - model_version: read from env var NLP_MODEL_VERSION (default: 'v0.0-base-no-finetune')
   - Handle GPU/CPU tensor movement transparently

5. Module-level model cache:
   - _model: Optional[ATLASClassifier] = None
   - _model_path: Optional[str] = None
   - get_model() function that initialises on first call using MODEL_PATH env var

Write tests in backend/tests/test_nlp_classify.py:
- test_classify_returns_dict: verify all required keys in return dict
- test_categories_sum_to_one: probabilities sum to 1.0 (softmax applied)
- test_classify_deterministic: same input → same output (eval mode, no dropout)
- test_confidence_in_range: confidence is float between 0 and 1

Mark GPU tests with pytest.mark.requires_gpu"
```

**Step 3: Build the fine-tuning harness**

```bash
claude "Create backend/app/ml/train.py — the fine-tuning script for Sprint 3.

Requirements:
- Accept labelled FIR data exported from Label Studio as JSONL (format: {text, label, fir_id})
- Use HuggingFace Trainer API with ATLASClassifier (from classify.py)
- Training config (argparse CLI):
  --data_path: path to labelled JSONL file
  --output_dir: where to save fine-tuned model weights
  --epochs: default 5
  --batch_size: default 16
  --learning_rate: default 2e-5
  --train_split: default 0.8 (rest is validation)
  --seed: default 42

- Data loading: FIRDataset class (torch.utils.data.Dataset) that reads JSONL, calls full_pipeline() for each text, returns {input_ids, attention_mask, labels} tensor dict
- Evaluation metrics: accuracy, macro F1, per-class precision/recall (sklearn.metrics)
- MLflow tracking: log all hyperparameters, epoch-level metrics, final model artifact
- Early stopping: if val_loss doesn't improve for 2 epochs, stop
- Save best model to output_dir/best_model.pt

DO NOT run training — this script is the harness to be invoked in Sprint 3.
Add a --dry_run flag that loads data and prints dataset statistics without training."
```

**Step 4: Set up MLflow tracking**

```bash
claude "Add MLflow to docker-compose.yml as a new service:
- Image: ghcr.io/mlflow/mlflow:v2.10.2
- Port: 5000:5000
- Volumes: atlas_mlflow_data:/mlflow
- Command: mlflow server --host 0.0.0.0 --port 5000 --default-artifact-root /mlflow/artifacts
- Named volume: atlas_mlflow_data

Add MLFLOW_TRACKING_URI=http://mlflow:5000 to backend service environment in docker-compose.yml.
Add mlflow>=2.10.2 to requirements.txt."
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend

# Test classification module (non-GPU):
python -m pytest tests/test_nlp_classify.py -v -m "not requires_gpu" --tb=short

# Zero-shot baseline smoke test (requires IndicBERT download ~400MB):
python -c "
from app.nlp.classify import classify_fir
result = classify_fir('The accused is charged under BNS Section 303 for murder.')
print('Category:', result['predicted_category'])
print('Confidence:', result['confidence'])
"

# Verify training harness runs in dry mode:
python app/ml/train.py --data_path tests/fixtures/sample_labelled.jsonl --dry_run

# Verify MLflow is accessible:
curl -s http://localhost:5000/health
```

### DONE WHEN

- [ ] `backend/app/nlp/classify.py` with `ATLASClassifier` and `classify_fir()` implemented
- [ ] `backend/app/ml/train.py` fine-tuning harness written (not run — Sprint 3)
- [ ] `backend/app/ml/__init__.py` created
- [ ] MLflow service added to `docker-compose.yml` (port 5000)
- [ ] `mlflow>=2.10.2` added to `requirements.txt`
- [ ] Tests pass for non-GPU and non-model-dependent cases
- [ ] Zero-shot baseline produces valid output (any category, must not crash)
- [ ] PR merged: `feature/T21-indicbert-scaffold` → `develop`
- [ ] Jira ATLAS-T21 moved to Done

### STORE AT

`Atlas_Platform/backend/app/nlp/classify.py`
`Atlas_Platform/backend/app/ml/train.py`
`Atlas_Platform/backend/app/ml/__init__.py`
`Atlas_Platform/backend/tests/test_nlp_classify.py`

### DORA METRIC

**Deployment Frequency (DF)** — the fine-tuning harness enables model version promotion: each new labelled batch → fine-tuning run → new model version deployed without code changes.

---
---

# T22-PROMPT — NLP Predict API Endpoint (/api/v1/predict/classify)

**Assignee:** Prishiv | **Story Points:** 3 | **Days:** 10–12 | **Jira:** ATLAS-T22

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) — 7 hours across Days 10–12

### ENVIRONMENT

Claude Code terminal. Depends on T21 (classify.py). FastAPI running locally.

### EXACT TOOLS

FastAPI, Pydantic v2, T21 `classify_fir()`, existing RBAC from Sprint 1

### OBJECTIVE

Expose classification inference as a secured API endpoint. This endpoint is what V01 (model quality validation gate) calls during automated pre-check, and what the frontend FIR review page will eventually use to show predicted crime category.

### INPUTS

- T21 `classify_fir()` function
- Sprint 1 RBAC (`get_current_user`, `require_role`)
- Prometheus metrics (existing `metrics.py`)

### STEPS

```bash
claude "Create backend/app/api/v1/predict.py with the following endpoint:

POST /api/v1/predict/classify
- Auth: require_role(Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)
  (all authenticated users can request classification; READONLY is read-only, not no-access)
- Request body (Pydantic model ClassifyRequest):
  {
    'text': str (the FIR narrative; min_length=10, max_length=5000),
    'fir_id': Optional[UUID] (if provided, updates the nlp_classification field on the firs table),
    'return_probabilities': bool = False
  }
- Response body (Pydantic model ClassifyResponse):
  {
    'predicted_category': str,
    'confidence': float,
    'probabilities': Optional[dict[str, float]],
    'model_version': str,
    'inference_time_ms': float,
    'fir_id': Optional[UUID]
  }

Implementation:
1. Call classify_fir(text, return_probabilities=request.return_probabilities)
2. If fir_id provided AND user has IO/SHO/ADMIN role: UPDATE firs SET nlp_classification=predicted_category, nlp_confidence=confidence, nlp_classified_at=now(), nlp_classified_by=username WHERE id=fir_id
3. Record a Prometheus counter: nlp_classify_requests_total{role=user_role, category=predicted_category}
4. Record a Prometheus histogram: nlp_classify_duration_seconds

Also expose:
GET /api/v1/predict/model-info
- Returns: {model_version, model_path, categories: list[str], is_finetuned: bool}
- No auth required (public endpoint for monitoring)

Wire predict router into backend/app/main.py with prefix /api/v1/predict.

Write tests in backend/tests/test_predict.py:
- test_classify_returns_200: POST with valid text → 200 with predicted_category
- test_classify_requires_auth: no token → 401
- test_classify_text_too_short: text < 10 chars → 422
- test_model_info_no_auth: GET /predict/model-info with no token → 200

Override classify_fir() in tests with a mock that returns a fixed result (no GPU needed)."
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend

python -m pytest tests/test_predict.py -v --tb=short

# Live endpoint test (server running):
curl -s -X POST http://localhost:8000/api/v1/predict/classify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Accused broke into the house and stole gold ornaments worth 50000 rupees.", "return_probabilities": true}' | python -m json.tool

curl -s http://localhost:8000/api/v1/predict/model-info | python -m json.tool
```

### DONE WHEN

- [ ] `backend/app/api/v1/predict.py` implemented with `POST /predict/classify` and `GET /predict/model-info`
- [ ] Router registered in `main.py`
- [ ] Prometheus metrics added for inference count and duration
- [ ] If `fir_id` provided: updates `firs.nlp_classification` in DB
- [ ] All tests passing
- [ ] PR merged: `feature/T22-predict-api` → `develop`
- [ ] Jira ATLAS-T22 moved to Done

### STORE AT

`Atlas_Platform/backend/app/api/v1/predict.py`
`Atlas_Platform/backend/tests/test_predict.py`

### DORA METRIC

**Deployment Frequency (DF)** — versioned `/predict/model-info` endpoint allows CI to verify which model version is deployed at any time, enabling model-as-artifact promotion.

---
---

# T23-PROMPT — Real eGujCop FIR Batch Import Pipeline

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 3–7 | **Jira:** ATLAS-T23

---

### ROLE + EST TIME

Aditya (Frontend/Data/NLP) — 8 hours across Days 3–7

### ENVIRONMENT

Claude Code terminal. Python 3.11. Access to real anonymised eGujCop data. Depends on T19 (preprocessing adds NLP metadata).

### EXACT TOOLS

pandas, psycopg2, csv/json, existing `backend/app/db/crud_fir.py`

### OBJECTIVE

Build a one-time batch import script that reads the real anonymised eGujCop FIR data into the ATLAS PostgreSQL database, applying the existing `create_fir()` pipeline (OCR-bypass since data is already digital). This replaces test fixtures with real data for all future development and testing.

### INPUTS

- Real anonymised eGujCop FIR data (CSV or JSON format — confirm format from data file)
- `backend/app/schemas/fir.py` — `FIRCreate` schema (what `create_fir()` expects)
- `backend/app/db/crud_fir.py` — `create_fir(conn, fir_data)` function

### STEPS

```bash
claude "Create scripts/batch_import_firs.py — a one-time import script that:

1. CLI interface using argparse:
   --input: path to eGujCop anonymised data file (CSV or JSON, auto-detected by extension)
   --limit: max number of FIRs to import (default: all)
   --dry_run: print statistics without writing to DB
   --district: import only FIRs from this district (optional filter)
   --batch_size: DB insert batch size (default 50)

2. Field mapping from eGujCop format to ATLAS FIRCreate schema:
   Create a FIELD_MAP dict that maps eGujCop column names to ATLAS field names.
   Expose this as a module-level constant so it can be updated when column names are confirmed.
   Handle these known mapping issues:
   - eGujCop may use IPC section numbers — map to BNS equivalents using a static IPC_TO_BNS dict
   - Date formats may vary (DD/MM/YYYY, DD-MM-YYYY) — parse with dateutil.parser
   - District names may be in Gujarati — normalise to English using a DISTRICT_NORMALISE dict

3. Validation before insert:
   - Skip records where narrative is missing or < 20 characters
   - Skip records where district is not in the 6 pilot districts
   - Skip records with duplicate fir_number + district combination (ON CONFLICT DO NOTHING)
   - Log skipped records to scripts/import_skipped.csv with reason

4. Batch insert using existing create_fir() from backend/app/db/crud_fir.py:
   - Open a single DB connection for the whole run
   - Commit every batch_size records
   - On error: log to scripts/import_errors.csv and continue (never abort the whole run)

5. Summary report printed on completion:
   - Total records in file
   - Records imported successfully
   - Records skipped (with reason breakdown)
   - Records errored
   - Per-district counts

Also create tests/test_batch_import.py with:
- test_field_mapping: verify known eGujCop field names map to correct ATLAS fields
- test_ipc_to_bns_conversion: IPC Section 302 → BNS Section 103
- test_date_parsing: verify DD/MM/YYYY and DD-MM-YYYY both parse correctly
- test_dry_run_no_db_writes: --dry_run flag produces output without any DB inserts"
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform

# Dry run to check mapping and statistics:
python scripts/batch_import_firs.py --input data/raw/egujcop_anonymised.csv --dry_run

# Import first 100 FIRs from Ahmedabad City as a pilot:
python scripts/batch_import_firs.py --input data/raw/egujcop_anonymised.csv --limit 100 --district "Ahmedabad_City"

# Verify rows in DB:
python -c "
import psycopg2, os
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*), district FROM firs GROUP BY district')
for row in cur.fetchall(): print(row)
"

# Run tests:
python -m pytest tests/test_batch_import.py -v --tb=short
```

### DONE WHEN

- [ ] `scripts/batch_import_firs.py` committed with correct field mapping for real eGujCop data
- [ ] IPC→BNS section mapping dict embedded and tested
- [ ] Dry run produces expected statistics on the real data file
- [ ] At least 100 real FIRs successfully imported into local DB
- [ ] Import error/skip logs operational
- [ ] Tests passing
- [ ] PR merged: `feature/T23-batch-import` → `develop`
- [ ] Jira ATLAS-T23 moved to Done

### STORE AT

`Atlas_Platform/scripts/batch_import_firs.py`
`Atlas_Platform/backend/tests/test_batch_import.py`

### DORA METRIC

**Lead Time (LT)** — real data in the DB unblocks all downstream development: dashboard stats (T24), FIR browse UI (T25), NLP evaluation, and annotation gold standard selection (T17).

---
---

# T24-PROMPT — Dashboard Live Stats from Real DB

**Assignee:** Aditya | **Story Points:** 2 | **Days:** 7–9 | **Jira:** ATLAS-T24

---

### ROLE + EST TIME

Aditya (Frontend/Data/NLP) — 5 hours across Days 7–9

### ENVIRONMENT

Claude Code terminal. Python 3.11. Depends on T23 (real FIRs in DB). PostgreSQL running.

### EXACT TOOLS

FastAPI, psycopg2, existing `backend/app/api/v1/dashboard.py`

### OBJECTIVE

Replace the hardcoded zero stubs in `GET /api/v1/dashboard/stats` with real queries against the PostgreSQL `firs` table. The frontend already renders these values — no frontend changes needed.

### INPUTS

- Current stub: `backend/app/api/v1/dashboard.py` returns `{total_firs: 0, districts: 6, pending_review: 0}`
- Real DB schema: `firs` table with columns: `id`, `district`, `status`, `completeness_score`, `created_at`
- RBAC: district-scoping rules from ADR-D03 (IO/SHO see only their district)

### STEPS

```bash
claude "Rewrite backend/app/api/v1/dashboard.py to return live statistics from the firs table.

GET /dashboard/stats
- Requires authentication (add Depends(get_current_user))
- District scoping: if role is IO or SHO, filter all queries by user['district']
- Queries to run (all parameterized):
  a. total_firs: SELECT COUNT(*) FROM firs [WHERE district = %s]
  b. pending_review: SELECT COUNT(*) FROM firs WHERE status = 'pending' [AND district = %s]
  c. districts_covered: SELECT COUNT(DISTINCT district) FROM firs [no scoping for IO/SHO — just count their district = 1]
  d. completeness_avg: SELECT ROUND(AVG(completeness_score), 1) FROM firs WHERE completeness_score IS NOT NULL [AND district = %s]
  e. ingested_today: SELECT COUNT(*) FROM firs WHERE created_at >= CURRENT_DATE [AND district = %s]

Response shape (update DashboardStats Pydantic model):
{
  'total_firs': int,
  'pending_review': int,
  'districts_covered': int,
  'completeness_avg': Optional[float],
  'ingested_today': int
}

Use the existing get_connection() from app.db.session.
Handle the case where completeness_avg is None (no FIRs with scores yet) — return null.

Write tests in backend/tests/test_dashboard.py:
- test_stats_returns_200: authenticated request → 200
- test_stats_requires_auth: no token → 401
- test_stats_shape: response has all 5 required fields
Override the DB connection with a fake that returns known counts."
```

Also update `frontend/src/app/dashboard/page.tsx` to display the two new fields (`completeness_avg` and `ingested_today`).

```bash
claude "Update frontend/src/app/dashboard/page.tsx to:
1. Add two new stat cards: 'Completeness Avg' (shows completeness_avg from API, formatted as e.g. '78.3%', or '—' if null) and 'Ingested Today' (shows ingested_today count)
2. The existing 4 cards already handle '—' for missing values — follow the same pattern
3. Total should now be 5 cards displayed in a 3-2 or 5-column responsive grid using Tailwind"
```

### VALIDATION COMMAND

```bash
cd D:\sem2\RP\Atlas_Platform\backend

python -m pytest tests/test_dashboard.py -v --tb=short

# Live test (requires server + real data from T23):
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/dashboard/stats | python -m json.tool
# Expected: total_firs > 0 (real data), ingested_today >= 0
```

### DONE WHEN

- [ ] `GET /dashboard/stats` returns live DB values (not hardcoded zeros)
- [ ] District-scoping applied for IO/SHO roles
- [ ] `completeness_avg` and `ingested_today` fields added to response + frontend
- [ ] All tests passing
- [ ] PR merged: `feature/T24-live-dashboard-stats` → `develop`
- [ ] Jira ATLAS-T24 moved to Done

### STORE AT

`Atlas_Platform/backend/app/api/v1/dashboard.py` (updated)
`Atlas_Platform/frontend/src/app/dashboard/page.tsx` (updated)

### DORA METRIC

**Change Failure Rate (CFR)** — replacing stubs with real queries increases the chance of catching DB schema drift early.

---
---

# T25-PROMPT — FIR Browse + Search UI

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 8–12 | **Jira:** ATLAS-T25

---

### ROLE + EST TIME

Aditya (Frontend/Data/NLP) — 8 hours across Days 8–12

### ENVIRONMENT

Claude Code terminal. Next.js 14 (App Router). Depends on T23 (real FIRs in DB) and existing `GET /api/v1/firs` API.

### EXACT TOOLS

Next.js 14 App Router, React, shadcn/ui, `apiClient` from `frontend/src/lib/api.ts`, existing `GET /api/v1/firs` (paginated, district-scoped, PII-masked)

### OBJECTIVE

Build the FIR list/browse page at `/dashboard/fir` that lets users see previously ingested FIRs, filter by district/date/status, and click to view full details. The backend `GET /api/v1/firs` endpoint already exists and is fully functional — this is purely a frontend task.

### INPUTS

- `GET /api/v1/firs?limit=10&offset=0` — returns paginated list with `{id, fir_number, district, police_station, sections, complainant_name, status, created_at, completeness_score}`
- `GET /api/v1/firs/{fir_id}` — returns full FIR details (narrative etc.)
- sprInt 1 frontend patterns: `apiClient`, `shadcn/ui` components, Tailwind

### STEPS

```bash
claude "Update frontend/src/app/dashboard/fir/page.tsx to show both:
(A) The existing upload section (drag-drop PDF) — keep this at the top
(B) A new 'Recent FIRs' section below it

The Recent FIRs section should:

1. On page load, call GET /api/v1/firs?limit=10&offset=0 via apiClient
2. Display results in a table with columns: FIR No. | District | Police Station | Sections | Status | Completeness | Date
   - Status badge: 'pending' = yellow, 'reviewed' = green, 'flagged' = red (using shadcn Badge)
   - Completeness: show as a percentage badge (e.g. '87%'); if null show '—'
   - Sections: show first 2 sections, then '+N more' if more than 2
3. Click any row → opens a slide-over panel (shadcn Sheet component) showing full FIR details:
   - FIR metadata (number, district, station, date)
   - Complainant info (PII-masked per role — just display what the API returns)
   - Narrative text in a scrollable pre-wrap box
   - Sections list (full list)
   - NLP classification badge (if nlp_classification field is present in response)
4. Pagination: Previous/Next buttons + 'Showing X–Y of Z' counter
   - Use offset += 10 / offset -= 10 pattern
   - Disable Previous at offset=0, disable Next when results.length < 10
5. Filter bar: District dropdown (populated from unique districts in current results), Status filter, Date range (from/to date pickers using shadcn Popover + Calendar)
   - Filters call API with query params: GET /api/v1/firs?district=X&status=Y&limit=10&offset=0
   - Reset button clears all filters

6. Loading skeleton: show 5 skeleton rows (animate-pulse) while fetching
7. Empty state: 'No FIRs found' with an upload-nudge link pointing to the upload section above

Use TypeScript. Define a FIR type matching the API response shape.
Follow the existing page structure (shadcn Card components, Tailwind spacing)."
```

### VALIDATION COMMAND

```bash
# Run frontend linting:
cd D:\sem2\RP\Atlas_Platform\frontend
npm run lint

# Build check (catches TypeScript errors):
npm run build

# Manual test path (with Docker stack running):
# 1. Login as io_sanand / atlas2025 → should see ONLY Ahmedabad/Sanand FIRs (district-scoped)
# 2. Login as admin / atlas2025 → should see FIRs from all districts
# 3. Click a row → slide-over panel opens with narrative
# 4. Apply district filter → results update
```

### DONE WHEN

- [ ] FIR list table renders below the upload section at `/dashboard/fir`
- [ ] Paginated (Previous/Next working)
- [ ] District filter, status filter, date range filter operational
- [ ] Row click → slide-over panel with full FIR details (narrative text visible)
- [ ] NLP classification badge shown if `nlp_classification` field is present
- [ ] No TypeScript errors (`npm run build` passes)
- [ ] District-scoping visible: IO/SHO users see only their district's FIRs
- [ ] PR merged: `feature/T25-fir-browse-ui` → `develop`
- [ ] Jira ATLAS-T25 moved to Done

### STORE AT

`Atlas_Platform/frontend/src/app/dashboard/fir/page.tsx` (updated)

### DORA METRIC

**Deployment Frequency (DF)** — the browse UI is the first feature that makes real eGujCop data visible to end users, enabling UAT preparation.

---
---

# DOC2-PROMPT — Sprint 2 Technical Documentation

**Assignee:** Both Developers | **Story Points:** 1 | **Days:** 13–14 | **Jira:** ATLAS-DOC2

---

### OBJECTIVE

Commit documentation for Sprint 2 deliverables:

1. `docs/architecture/nlp-pipeline.md` — architecture diagram of the full multilingual pipeline (Mermaid flowchart: raw text → language detection → normalisation → tokenisation → IndicBERT → classification output)
2. `docs/architecture/schema-erd.md` — updated ERD including `nlp_metadata` JSONB column added in T20, and any other schema changes from Sprint 2
3. Update `docs/progress_07April2026.md` → `docs/progress_21April2026.md` with Sprint 2 completion status

### VALIDATION COMMAND

```bash
# Verify all 4 ADRs exist:
Get-ChildItem "D:\sem2\RP\atlas-project\docs\decisions\" | Where-Object { $_.Name -match "ADR-D0[2-6]" }
```

### DONE WHEN

- [ ] NLP pipeline architecture diagram committed
- [ ] ERD updated with Sprint 2 schema changes
- [ ] Sprint 2 progress doc committed
- [ ] Jira ATLAS-DOC2 moved to Done

---
---

# SPRINT 2 GOVERNANCE

## GOV5 — Sprint 2 Planning Ceremony

**Assignee:** Amit | **Day:** 1 | **Duration:** 90 minutes

- Sprint 2 kickoff: review sprint goal, confirm T15–T26 backlog
- Confirm ADR-D02 is pre-decided (IndicBERT); schedule D03/D04/D06 deliberation sessions (T16–T18)
- Confirm eGujCop data format and column names with data holder — update T23 field mapping
- GPU verification: Prishiv confirms local GPU is accessible, CUDA version, PyTorch compatibility
- **Output:** Sprint 2 board active in Jira with all tickets (T15–T26) created and story-pointed

## GOV6 — Mid-Sprint Standup / Risk Review

**Assignee:** Amit | **Day:** 7 | **Duration:** 30 minutes

- Check T19 (language detection) status — if not merged, T20/T21 are at risk
- Check T17 (Label Studio) status — annotation must start by Day 8
- Check ADR-D03/D04/D06 status — all three must be signed before Day 7
- Risk flag: IndicBERT model download (~400MB) — confirm Prishiv has downloaded before Day 6
- **Output:** Risk register updated; any blocked tickets escalated to Amit for unblocking

## GOV7 — Sprint 2 Demo

**Assignee:** Amit | **Day:** 13 | **Duration:** 60 minutes

Demo to Gujarat Police stakeholder (or internal review if stakeholder unavailable):
1. Upload a real eGujCop PDF → see parsed FIR fields (Sprint 1)
2. Show the FIR browse page with real data from eGujCop batch import (T25)
3. Call `POST /predict/classify` with a real FIR narrative → see predicted crime category + confidence
4. Show Label Studio with 200 gold-standard FIRs loaded for annotation (T17)
5. Show MLflow at `http://localhost:5000` — experiment tracking ready for Sprint 3 fine-tuning
- **Output:** Demo recording committed to `docs/demos/sprint2-demo.mp4`; stakeholder feedback captured

## GOV8 — Sprint 2 Retrospective

**Assignee:** Amit | **Day:** 14 | **Duration:** 45 minutes

3 questions:
1. What slowed us down? (watch for: model download time, annotation tool setup friction, eGujCop data format surprises)
2. What should we carry as a Sprint 3 prerequisite? (at minimum: 200 gold-standard FIRs annotated by both developers)
3. Sprint 3 commitment preview: fine-tuning run, NER model, bias audit setup, eGujCop integration begin
- **Output:** Retro notes committed; Sprint 3 draft backlog created in Jira

---
---

## SPRINT 2 VALIDATION GATES

Before marking Sprint 2 complete, all of the following must pass:

| Gate | Criterion | Owner |
|------|-----------|-------|
| G2-1 | 4 ADRs signed (D02, D03, D04, D06) | Amit |
| G2-2 | `python -m pytest backend/tests/ -v` → 0 failures | Prishiv |
| G2-3 | `classify_fir()` returns valid JSON without crashing on any of the 4 text patterns | Prishiv |
| G2-4 | Label Studio running at localhost:8080 with 200 gold-standard FIRs loaded | Aditya |
| G2-5 | Real FIRs in DB (at minimum 100 from T23 batch import) | Aditya |
| G2-6 | `GET /dashboard/stats` returns `total_firs > 0` | Aditya |
| G2-7 | FIR browse page renders real data and pagination works | Aditya |
| G2-8 | MLflow accessible at localhost:5000 | Prishiv |
| G2-9 | Docker Compose starts all services (backend, db, redis, mongodb, prometheus, grafana, labelstudio, mlflow) without errors | Prishiv |
| G2-10 | `npm run build` in frontend passes with 0 TypeScript errors | Aditya |

---

## SPRINT 2 DEFINITION OF DONE

- [ ] All T15–T26 Jira tickets moved to Done
- [ ] All 10 validation gates above pass
- [ ] 4 ADRs (D02, D03, D04, D06) committed to `atlas-project/docs/decisions/`
- [ ] Annotation of 200 gold-standard FIRs: at least 100 completed by end of sprint (remainder Day 1–3 of Sprint 3)
- [ ] Zero known security vulnerabilities introduced (no secrets in code, all endpoints authenticated)
- [ ] `docker compose up` starts all 9 services cleanly
- [ ] Sprint 2 demo recorded and committed

## SPRINT 3 PRE-CONDITIONS (what must be true before Sprint 3 starts)

- All 200 gold-standard FIRs labelled (both classification + NER)
- Prishiv has confirmed IndicBERT fine-tuning script (`train.py`) runs in `--dry_run` mode
- eGujCop field mapping validated on full dataset (not just 100-FIR pilot)
- ADR-D05 deliberation session scheduled (Sprint 3 Gate: bias remediation protocol)
- Sprint 3 backlog created: fine-tuning run, NER model, bias metrics pipeline, eGujCop integration begin

---

*Generated: 8 April 2026 | Based on: sprint1.md template, ADR-D1-D12.md (D02–D06), R01-fir-legal-standards.md*
