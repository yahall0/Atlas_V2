# How to Train the ATLAS FIR Classifier

> **TL;DR — one command:** `python scripts/train_and_deploy.py --data_path data/my_firs.csv`  
> That script wraps all 6 steps below end-to-end. Read on for manual steps and details.

This guide covers the complete training pipeline end-to-end: from a fresh checkout to a saved
fine-tuned MuRIL checkpoint at `backend/models/atlas_classifier_v1/`.

---

## Prerequisites

- Docker Desktop running with at least **6 GB RAM** allocated to containers
- `docker compose up -d` has been run (all services healthy)
- Python 3.9+ on the host (only needed for the one-time model download)

---

## Automated Pipeline — `train_and_deploy.py`

`scripts/train_and_deploy.py` runs all 6 steps below in sequence and handles every detail:
validates input, copies data into the container, trains, verifies the checkpoint, restarts the
backend, and prints a summary.

### Train on your own labelled CSV

```powershell
python scripts/train_and_deploy.py --data_path data/my_firs.csv
```

The CSV must have at minimum two columns: `text` (FIR narrative) and `category` (crime type).

### Train on auto-generated synthetic data (no CSV needed)

```powershell
python scripts/train_and_deploy.py --synthetic --samples_per_class 30
```

### Quick smoke test (fast, 50 samples)

```powershell
python scripts/train_and_deploy.py --data_path data/my_firs.csv --max_samples 50 --epochs 1
```

### All flags

| Flag | Default | Description |
|---|---|---|
| `--data_path CSV` | *(required or --synthetic)* | Host path to labelled FIR CSV |
| `--synthetic` | off | Generate synthetic data inside the container |
| `--samples_per_class N` | `30` | Rows per class when using `--synthetic` |
| `--epochs N` | `3` | Training epochs |
| `--batch_size N` | `2` | Per-device batch size |
| `--max_length N` | `128` | Tokeniser padding length |
| `--lr F` | `2e-5` | AdamW learning rate |
| `--max_samples N` | None | Cap training rows (smoke tests) |
| `--no_class_weights` | off | Disable inverse-frequency weighting |
| `--output_dir PATH` | `backend/models/atlas_classifier_v1` | Host checkpoint path |
| `--container NAME` | `atlas_platform-backend-1` | Backend container name |
| `--skip_deploy` | off | Train only; skip backend restart |

### What the script does

```
[1/6] Checks container is running
[2/6] Checks MuRIL base model exists at /app/models/hf_cache/muril-base-cased/
[3/6] Copies CSV into container at /data/training_input.csv (or generates synthetic data)
[4/6] Runs python -m app.ml.train inside the container
[5/6] Reads evaluation_metrics.json; prints val_f1, test_accuracy
[6/6] Runs docker compose restart backend; polls /api/v1/health until up
```

---

## Manual Steps

---

## Step 1 — Download the Base Model (once, on host)

The container runs fully offline (`TRANSFORMERS_OFFLINE=1`). The base model must be downloaded
to the host first so it is available via the bind mount.

```powershell
# Install only the downloader (no torch needed on host)
pip install huggingface_hub

# Download ~900 MB of PyTorch weights to backend/models/hf_cache/muril-base-cased/
python scripts/download_base_model.py
```

**What it downloads:** `google/muril-base-cased` — Google's multilingual BERT covering 17 Indian
languages (Gujarati, Hindi, Marathi, Bengali, etc.). TF/Flax/Rust weights are skipped to save
~500 MB.

**Where it lands:** `backend/models/hf_cache/muril-base-cased/`  
This folder is bind-mounted into the container at `/app/models/hf_cache/muril-base-cased`.

> You only need to do this once. Skip this step on subsequent re-trains.

---

## Step 2 — Generate Synthetic Training Data

The synthetic data generator creates a labelled FIR corpus with no real annotations required.

```powershell
# Run inside the backend container (data directory is /data)
docker exec atlas_platform-backend-1 python scripts/generate_synthetic_training_data.py `
  --output_dir /data `
  --samples_per_class 30
```

Or on the host, then copy in:

```powershell
# On host
python scripts/generate_synthetic_training_data.py --output_dir data --samples_per_class 30

# Copy to container
docker exec atlas_platform-backend-1 mkdir -p /data
docker cp data/synthetic_fir_training.csv atlas_platform-backend-1:/data/synthetic_fir_training.csv
docker cp data/synthetic_fir_test.csv     atlas_platform-backend-1:/data/synthetic_fir_test.csv
```

**Output files:**

| File | Description |
|---|---|
| `synthetic_fir_training.csv` | ~264 rows (train + val split handled by train.py) |
| `synthetic_fir_test.csv` | Held-out 20% test set |
| `label_map.json` | `{"assault": 0, "cybercrime": 1, ...}` (11 classes, alphabetically sorted) |

**Columns:** `text`, `category`, `language`, `district`

**Categories (11):** `theft`, `assault`, `fraud`, `murder`, `rape_sexoff`, `cybercrime`,
`narcotics`, `kidnapping`, `dacoity_robbery`, `domestic_violence`, `other`

---

## Step 3 — Run Training

### Standard run (CPU, full dataset, 3 epochs)

```powershell
docker exec atlas_platform-backend-1 python -m app.ml.train `
  --data_path  /data/synthetic_fir_training.csv `
  --output_dir /app/models/atlas_classifier_v1 `
  --epochs     3 `
  --batch_size 2 `
  --cpu_mode
```

**Expected duration:** ~25–35 minutes on a 4-core CPU container.  
**Effective batch size:** 8 (`batch_size=2` × `gradient_accumulation_steps=4`).

### Quick smoke test (50 samples, 1 epoch — ~4 minutes)

```powershell
docker exec atlas_platform-backend-1 python -m app.ml.train `
  --data_path  /data/synthetic_fir_training.csv `
  --output_dir /app/models/atlas_classifier_v1 `
  --epochs     1 `
  --batch_size 2 `
  --cpu_mode `
  --max_samples 50
```

### Pipeline validation only (no training, no data needed)

```powershell
docker exec atlas_platform-backend-1 python -m app.ml.train --dry_run
```

Loads the tokeniser and exits with `Dry-run OK` — confirms the model is accessible offline.

---

## All CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--data_path` | *(required)* | Path to labelled CSV inside the container |
| `--output_dir` | `/models/atlas_bert_v1` | Where to save the checkpoint |
| `--epochs` | `3` | Number of full passes over the training data |
| `--batch_size` | `2` | Per-device batch size (2 is safe for CPU; effective batch = 8 via accum) |
| `--lr` | `2e-5` | AdamW learning rate |
| `--max_length` | `128` | Tokeniser padding length — do NOT increase above 256 on CPU (OOM) |
| `--cpu_mode` | off | Disables CUDA (`CUDA_VISIBLE_DEVICES=""`, `use_cpu=True`) |
| `--max_samples` | None | Cap dataset size — useful for CI or smoke tests |
| `--no_class_weights` | off | Disable inverse-frequency class weighting |
| `--dry_run` | off | Load tokeniser only; skip data load and training |

---

## What Happens During Training

1. **Tokenisation** — all texts padded/truncated to `max_length=128` tokens
2. **80/10/10 split** — train / validation / test (deterministic, `seed=42`)
3. **Class-weighted loss** — `CrossEntropyLoss` with inverse-frequency weights so rare
   categories (`dacoity_robbery`, `kidnapping`) are not dominated by `theft` / `fraud`
4. **Gradient checkpointing** — enabled to reduce peak RAM during backprop
5. **Epoch-level eval + save** — checkpoint saved at the end of every epoch; best checkpoint
   (by macro-F1 on validation) is loaded at the end
6. **MLflow logging** — params, metrics, confusion matrix, classification report logged to
   `http://localhost:5000` (non-fatal if MLflow is unreachable)
7. **Checkpoint written** — `model.safetensors`, `tokenizer.json`, `label_map.json`,
   `evaluation_metrics.json` saved to `--output_dir`

---

## Checkpoint Files

After a successful run, `backend/models/atlas_classifier_v1/` will contain:

```
atlas_classifier_v1/
├── config.json                  # Model architecture + id2label map
├── model.safetensors            # Fine-tuned weights (~350 MB)
├── tokenizer.json               # MuRIL tokeniser
├── tokenizer_config.json
├── training_args.bin
├── label_map.json               # {"assault": 0, ...} — 11 classes
├── evaluation_metrics.json      # Metrics + metadata (see below)
├── checkpoint-N/                # Per-epoch checkpoint(s)
└── artifacts/
    ├── confusion_matrix.json
    └── classification_report.json
```

### `evaluation_metrics.json` example

```json
{
  "model_version": "atlas_classifier_v1",
  "base_model": "/app/models/hf_cache/muril-base-cased",
  "best_val_f1": 0.73,
  "test_accuracy": 0.78,
  "num_labels": 11,
  "train_size": 211,
  "training_date": "2026-04-08T17:12:40Z",
  "epochs": 3
}
```

---

## Step 4 — Verify the Checkpoint

```powershell
docker exec atlas_platform-backend-1 cat /app/models/atlas_classifier_v1/evaluation_metrics.json
```

Check that `best_val_f1` and `test_accuracy` are non-zero.

```powershell
# List all saved files
docker exec atlas_platform-backend-1 find /app/models/atlas_classifier_v1 -type f
```

---

## Step 5 — Reload the Backend

The checkpoint is loaded on startup. Restart the backend to pick it up without rebuilding:

```powershell
docker compose restart backend
```

Then confirm the endpoint returns the new model info:

```powershell
curl http://localhost:8000/api/v1/predict/model-info
```

Expected response includes `"model_version": "atlas_classifier_v1"` and a non-null `best_f1`.

---

## Step 6 — Run Evaluation and Bias Report

### Offline evaluation (CI gate: fails if macro-F1 < 0.80)

```powershell
docker exec atlas_platform-backend-1 python -m app.ml.evaluate `
  --checkpoint /app/models/atlas_classifier_v1 `
  --test_data  /data/synthetic_fir_test.csv `
  --output     /app/models/atlas_classifier_v1/artifacts/full_eval.json
```

### Bias report (after generating predictions)

```powershell
# First generate a predictions CSV (the evaluate script emits one)
docker exec atlas_platform-backend-1 python -m app.ml.bias_report `
  --predictions /app/models/atlas_classifier_v1/artifacts/predictions.csv `
  --output      /app/models/atlas_classifier_v1/artifacts/bias_report.json
```

---

## Troubleshooting

### `Killed` with no traceback
The OS OOM-killed the process. Reduce memory usage:
```powershell
# Use --max_length 64 and --batch_size 1
docker exec atlas_platform-backend-1 python -m app.ml.train `
  --data_path /data/synthetic_fir_training.csv `
  --output_dir /app/models/atlas_classifier_v1 `
  --epochs 3 --batch_size 1 --max_length 64 --cpu_mode
```
Or increase Docker Desktop RAM allocation (Settings → Resources → Memory → 8 GB).

### `OSError: Can't load tokenizer for '...'`
The base model is not at the expected path. Re-run Step 1:
```powershell
python scripts/download_base_model.py
```
Then verify: `docker exec atlas_platform-backend-1 ls /app/models/hf_cache/muril-base-cased/`

### `No valid rows found in ...`
The CSV is not inside the container. Copy it in:
```powershell
docker exec atlas_platform-backend-1 mkdir -p /data
docker cp data/synthetic_fir_training.csv atlas_platform-backend-1:/data/synthetic_fir_training.csv
```

### `evaluation_metrics.json` missing after training
Training completed but crashed during save. Capture full output to see the error:
```powershell
docker exec atlas_platform-backend-1 sh -c "python -m app.ml.train `
  --data_path /data/synthetic_fir_training.csv `
  --output_dir /app/models/atlas_classifier_v1 `
  --epochs 1 --batch_size 2 --cpu_mode --max_samples 50 2>&1"
```

### MLflow errors (`Run already active`, connection refused)
Non-fatal — MLflow logging is wrapped in try/except. The checkpoint will still save.
To disable MLflow logging entirely, the `report_to` field in `TrainingArguments` can be changed to `[]`.

---

## Environment Variables (set in `docker-compose.yml`)

| Variable | Value | Purpose |
|---|---|---|
| `INDIC_BERT_MODEL` | `/app/models/hf_cache/muril-base-cased` | Path to base MuRIL model |
| `INDIC_BERT_CHECKPOINT` | `/app/models/atlas_classifier_v1` | Path to fine-tuned checkpoint |
| `TRANSFORMERS_CACHE` | `/app/models/hf_cache` | HuggingFace cache dir |
| `TRANSFORMERS_OFFLINE` | `1` | Block all outbound HF network calls |
| `HF_DATASETS_OFFLINE` | `1` | Block dataset hub calls |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | MLflow server for experiment tracking |
