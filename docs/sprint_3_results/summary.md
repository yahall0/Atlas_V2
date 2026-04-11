# Sprint 3 Results — ATLAS Platform
**Date:** 2026-04-14 | **Velocity:** 42 SP | **Duration:** 14 days

---

## What was built

### 1. Synthetic Training Data Generator (`scripts/generate_synthetic_training_data.py`)
- Generates a labelled FIR corpus with no real annotated data required
- 11 BNS-aligned crime categories × 6 narrative templates each (Gujarati/Hindi/English/mixed)
- `generate_corpus(samples_per_class, seed)` → randomised rows with text, category, language, district
- Outputs `synthetic_fir_training.csv`, `synthetic_fir_test.csv`, and `label_map.json`
- CLI: `--output_dir`, `--samples_per_class`, `--seed`

---

### 2. HuggingFace Dataset Builder (`src/ml/fine-tuning/dataset.py`)
- Converts raw CSV or Label Studio JSON exports into a `DatasetDict` (train/val/test)
- Stratified split preserving per-class distribution
- Handles both Sprint 3 synthetic data (CSV) and Sprint 4 real annotations (Label Studio JSON)
- CLI: `--csv`, `--label_map`, `--output`, `--format [csv|label_studio]`

---

### 3. Training Harness Improvements (`backend/app/ml/train.py`)
| Addition | Detail |
|---|---|
| `_class_weights()` | Inverse-frequency class weights as a `torch.Tensor` |
| `WeightedTrainer` | HuggingFace `Trainer` subclass with `CrossEntropyLoss(weight=...)` override; `compute_loss` accepts `**kwargs` for forward compatibility |
| `--cpu_mode` | Sets `CUDA_VISIBLE_DEVICES=""` + `use_cpu=True` (HF Trainer ≥ 4.45 API) — runs in CPU-only Docker environment |
| `--max_samples` | Caps dataset rows for fast iteration / CI smoke tests |
| `--max_length` | Tokeniser max token length (default **128**; 512 causes OOM on CPU containers) |
| `--no_class_weights` | Opt-out of weighted loss |
| Confusion matrix artifact | Saves `confusion_matrix.json` + `classification_report.json` → MLflow `evaluation/` |
| `evaluation_metrics.json` | Written alongside checkpoint: `model_version`, `base_model`, `best_val_f1`, `test_accuracy`, `num_labels`, `train_size`, `training_date`, `epochs` |
| Memory optimisations | `gradient_checkpointing_enable()`, `gradient_accumulation_steps=4`, `dataloader_num_workers=0` — required for CPU containers with ≤ 4 GB RAM |

**Base model:** `google/muril-base-cased` (switched from `ai4bharat/indic-bert` which is gated).

---

### 4. Training Orchestration Script (`src/ml/fine-tuning/run_training.sh`)
- End-to-end fine-tuning in one command from repo root
- Auto-generates synthetic data inside the container if `synthetic_fir_training.csv` is absent
- Runs `app.ml.train` via `docker exec` with configurable epochs, batch size, max samples
- Default `--batch_size 2` (with `gradient_accumulation_steps=4` = effective batch 8) to fit CPU RAM
- Verifies checkpoint presence and prints `evaluation_metrics.json` after training
- CLI: `--epochs`, `--batch_size`, `--max_samples`, `--data_path`, `--output_dir`

### 4a. Base Model Download Script (`scripts/download_base_model.py`)
- Downloads `google/muril-base-cased` to `backend/models/hf_cache/muril-base-cased/` on the host using `huggingface_hub.snapshot_download` (no PyTorch needed on host)
- Skips TF/Flax/Rust weights (`*.h5`, `flax_model*`, `tf_model*`, `rust_model*`) — saves ~500 MB
- Container uses `TRANSFORMERS_OFFLINE=1` so no outbound network calls during training
- Run once before `docker compose up`: `python scripts/download_base_model.py`

---

### 5. Offline Evaluation Harness (`src/ml/evaluation/evaluate.py`)
- Loads checkpoint + test CSV, runs batched inference, computes metrics
- **CI/CD gate**: exits with code `1` if macro-F1 < 0.80 (configurable via `--threshold`)
- Outputs: macro-F1, accuracy, per-class P/R/F1, confusion matrix, `passes_gate` flag
- Writes full evaluation JSON report to `--output` path
- CLI: `--checkpoint`, `--test_data`, `--output`, `--threshold`, `--batch_size`

---

### 6. Bias Report Generator (`src/ml/bias/bias_report.py`)
| Check | Method |
|---|---|
| District-level prediction skew | Chi-square goodness-of-fit vs. global distribution (p < 0.05 → flagged) |
| Label imbalance | Gini coefficient — flagged if > 0.4 |
| Per-class P/R/F1 | Computed from predictions CSV without needing a model |
- Takes a `predictions.csv` with columns: `text`, `category`, `predicted`, `district`
- Writes `bias_report.json` with `flags` list and per-district breakdown
- CLI: `--predictions`, `--output`, `--pvalue_threshold`, `--top_n`

---

### 7. Classifier Hardening (`backend/app/nlp/classify.py`)
- `_load_model()` now falls back to loading `label_map.json` from the checkpoint directory when `model.config.id2label` is empty (happens with some checkpoint save configurations)
- Added `from pathlib import Path` for robust path construction

---

### 8. Database Migration (`backend/alembic/versions/004_add_nlp_model_version.py`)
- Added `nlp_model_version TEXT` column to `firs` table
- Indexed (`idx_firs_nlp_model_version`) for filtering by model version
- Enables traceability: each classification row records which checkpoint produced it

---

### 9. Predict API & Schema Updates
| File | Change |
|---|---|
| `predict.py` — `_persist_classification` | Reads `evaluation_metrics.json` from checkpoint dir; writes `nlp_model_version` to DB on every classification persist |
| `predict.py` — `ModelInfoResponse` | Added `model_version: Optional[str]`, `best_f1: Optional[float]`, `training_date: Optional[str]` |
| `predict.py` — `model_info_endpoint` | Now reads `evaluation_metrics.json` and returns `model_version`, `best_f1`, `training_date` alongside existing fields |

---

### 10. Infrastructure (`docker-compose.yml`)
- `./backend/models:/app/models` bind mount added to backend service
- `INDIC_BERT_MODEL=/app/models/hf_cache/muril-base-cased` — points to locally-cached MuRIL model
- `INDIC_BERT_CHECKPOINT=/app/models/atlas_classifier_v1` — points to fine-tuned checkpoint
- `TRANSFORMERS_OFFLINE=1` and `HF_DATASETS_OFFLINE=1` — no model downloads inside container
- `TRANSFORMERS_CACHE=/app/models/hf_cache` — shared cache dir
- Named volume `atlas_models` added to volumes section
- When the fine-tuned checkpoint is trained and placed in `backend/models/atlas_classifier_v1/`, the backend picks it up automatically on restart — no image rebuild needed

**New runtime dependencies added to `requirements.txt`:**
| Package | Version | Reason |
|---|---|---|
| `torch` | `>=2.6.0` (CPU wheel) | CVE-2025-32434 — `torch.load` blocks earlier versions |
| `datasets` | `>=2.18.0` | Required by HuggingFace `Trainer` for Dataset input |
| `accelerate` | `>=1.1.0` | Required by HuggingFace `Trainer` for PyTorch training loop |

---

### 11. Frontend Updates
| File | Change |
|---|---|
| `dashboard/page.tsx` | 6th card "Model F1" — fetches `GET /predict/model-info`, shows `best_f1` or "heuristic" if no checkpoint; also shows `model_version` string below the value |
| `dashboard/fir/page.tsx` | NLP Category column now shows badge + inline blue confidence bar with % label (was: badge only) |
| `dashboard/page.tsx` | Sprint label updated to "Sprint 3"; grid changed from `lg:grid-cols-5` to `lg:grid-cols-6` |

---

### 12. Architecture Decision Record
- **ADR-D05** (`docs/decisions/ADR-D05-evaluation-strategy.md`) — documents macro-F1 ≥ 0.80 gate, dataset splits, MLflow artifact strategy, bias check cadence, retraining triggers, and tradeoffs vs. micro-F1 / accuracy metrics

---

## State at Sprint End

| Component | Status |
|---|---|
| MuRIL checkpoint | **Trained and saved** — `backend/models/atlas_classifier_v1/model.safetensors` written |
| Base model | `google/muril-base-cased` (public) — downloaded to `backend/models/hf_cache/muril-base-cased/` |
| Classifier mode | Fine-tuned MuRIL (or heuristic fallback if checkpoint missing at startup) |
| `INDIC_BERT_CHECKPOINT` env var | Set in docker-compose; backend loads checkpoint on startup |
| Label Studio annotation | In progress — gold standard FIRs created in Sprint 2 |
| Real-annotation test set | Deferred to Sprint 4 |
| Training defaults | `--batch_size 2`, `--max_length 128`, `--epochs 3`, CPU mode, gradient accumulation ×4 |
