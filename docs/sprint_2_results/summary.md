# Sprint 2 Results — ATLAS Platform
**Date:** 2026-04-08 | **Velocity:** 40 SP | **Duration:** 14 days

---

## What was built

### 1. Database Migrations
| File | Change |
|---|---|
| `002_add_sprint2_nlp_columns.py` | Added `status TEXT DEFAULT 'pending'` and `nlp_metadata JSONB DEFAULT '{}'` to `firs` table |
| `003_add_nlp_classification.py` | Added `nlp_classification`, `nlp_confidence`, `nlp_classified_at`, `nlp_classified_by` to `firs` table |

---

### 2. NLP Pipeline (`backend/app/nlp/`)
| Module | What it does |
|---|---|
| `language.py` | fastText language detection (Gujarati/Hindi/English), Unicode NFC normalisation, IndicXlit Romanised-Gujarati transliteration, `preprocess_text()` orchestrator |
| `preprocessing.py` | `IndicBERTPreprocessor` — wraps `ai4bharat/indic-bert` tokeniser, IndicNLP sentence splitting, `truncate_to_fit()` for 512-token limit |
| `classify.py` | `ATLASClassifier` — 11-category crime classifier; keyword-heuristic mode for Sprint 2 scaffold, fine-tuned IndicBERT model slot for Sprint 3; `classify_fir()` with optional MLflow logging |

---

### 3. ML Training Harness (`backend/app/ml/train.py`)
- Fine-tuning script for IndicBERT on labelled FIR CSV data
- 80/10/10 train/val/test split, HuggingFace `Trainer`, MLflow autolog
- `--dry_run` flag for CI validation without GPU or data
- Saves checkpoint + `label_map.json` to output directory

---

### 4. New API Endpoints
| Endpoint | Role(s) | Description |
|---|---|---|
| `POST /api/v1/predict/classify` | IO+ | Classify FIR text; optionally persist result to DB (SHO+) |
| `GET /api/v1/predict/model-info` | All authenticated | Returns active model variant and category list |
| `PATCH /api/v1/firs/{id}/classification` | SHO, DYSP, SP, ADMIN | Manually override NLP classification; writes audit log |
| `GET /api/v1/dashboard/stats` | All authenticated | **Replaced hardcoded stub** — 5 live SQL queries, district-scoped for IO/SHO |

---

### 5. RBAC & Security Improvements (`backend/app/core/pii.py`)
- **BNS §73 / S.228A CrPC victim identity masking** — unconditional for all roles when FIR sections include any BNS §63-99 or IPC §376 family section:
  - `complainant_name` → `[VICTIM-PROTECTED]`
  - `place_address` → `[ADDRESS-PROTECTED]`
- Existing Aadhaar / phone / name masking unchanged

---

### 6. Schema Update (`backend/app/schemas/fir.py`)
Added to `FIRResponse`: `status`, `nlp_metadata`, `nlp_classification`, `nlp_confidence`, `nlp_classified_at`, `nlp_classified_by`

---

### 7. Frontend Updates
| File | Change |
|---|---|
| `dashboard/page.tsx` | 5-card live stats grid — added `completeness_avg` and `ingested_today` cards; shows error state on API failure |
| `dashboard/fir/page.tsx` | Full FIR browse table under the upload zone: pagination (Load more), district filter, status colour badges, NLP category badge, slide-over detail panel with narrative and classification info |

---

### 8. Infrastructure (`docker-compose.yml`)
Added two new services:
- **Label Studio** (`localhost:8080`) — self-hosted annotation tool for FIR_NER and FIR_Category projects
- **MLflow** (`localhost:5000`) — experiment tracking for fine-tuning runs
- Backend environment variables added: `MLFLOW_TRACKING_URI`, `FASTTEXT_MODEL_PATH`, `TRANSFORMERS_CACHE`

---

### 9. Scripts (`scripts/`)
| Script | Purpose |
|---|---|
| `batch_import_firs.py` | Bulk-imports eGujCop FIR PDFs via `/api/v1/ingest`; applies IPC→BNS section mapping; writes summary CSV |
| `setup_labelstudio.py` | Creates `FIR_NER` and `FIR_Category` annotation projects in Label Studio via SDK |
| `create_gold_standard.py` | Stratified random sample of 200 FIRs from DB → JSON-Lines file for Label Studio task import |

---

### 10. Tests (`backend/tests/`)
| File | Coverage |
|---|---|
| `test_nlp_language.py` | `normalise_text`, `detect_language`, `transliterate_romanised_gujarati`, `preprocess_text` |
| `test_nlp_classify.py` | `ATLASClassifier` heuristic mode, all 11 categories, confidence range, `classify_fir()` |
| `test_pii.py` | Role-based masking (all 6 roles), victim identity masking for BNS §63-99 / IPC §376 |
| `test_predict.py` | `POST /predict/classify` schema + auth + empty-text rejection; `GET /predict/model-info` |
| `test_dashboard.py` | `GET /dashboard/stats` auth requirement, response schema, live value assertions |

---

### 11. ADR Documents (`docs/decisions/`)
| Document | Decision |
|---|---|
| `ADR-D02-model-selection.md` | Selected `ai4bharat/indic-bert` (110M) for on-prem Gujarati FIR classification |
| `ADR-D03-rbac-matrix.md` | Full RBAC write-permission and PII masking matrix for all 6 roles |
| `ADR-D04-annotation-strategy.md` | Label Studio (self-hosted Docker) for FIR NER + classification annotation |
| `ADR-D06-multilingual-pipeline.md` | Three-stage pipeline: NFC → fastText → IndicXlit → IndicNLP → IndicBERT tokeniser |

---

### 12. Dependency additions (`backend/requirements.txt`)
```
fasttext-wheel==0.9.2
xlit==1.2
indic-nlp-library==0.91
transformers>=4.38.0
torch>=2.2.0
sentencepiece>=0.1.99
mlflow>=2.10.2
label-studio-sdk>=0.8.0
```

---

## Sprint 2 → Sprint 3 Handoff

| Item | Status |
|---|---|
| IndicBERT fine-tuning (needs 500 labelled FIRs) | Scaffold ready; fine-tuning in Sprint 3 |
| fastText model file `lid.176.bin` | Must be manually downloaded to `backend/models/` (gitignored, 126 MB) |
| IndicBERT weights | Auto-downloaded at first run via HuggingFace (`~400 MB`) |
| Annotation corpus | 200-FIR gold standard to be labelled in Label Studio during Sprint 2 annotation phase |
