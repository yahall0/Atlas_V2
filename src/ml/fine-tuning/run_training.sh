#!/usr/bin/env bash
# run_training.sh — Fine-tune IndicBERT inside the running backend container.
#
# Usage (from repo root):
#   bash src/ml/fine-tuning/run_training.sh [--epochs N] [--batch_size N] [--max_samples N]
#
# Defaults: 3 epochs, batch 8, all samples.
# Generates synthetic data if synthetic_fir_training.csv is absent, then
# launches the HuggingFace Trainer via app.ml.train inside the backend service.

set -euo pipefail

# ── configurable defaults ────────────────────────────────────────────────────
EPOCHS="${EPOCHS:-3}"
BATCH_SIZE="${BATCH_SIZE:-8}"
MAX_SAMPLES="${MAX_SAMPLES:-}"         # empty → no cap
DATA_PATH="${DATA_PATH:-/data/synthetic_fir_training.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-/app/models/atlas_classifier_v1}"
CONTAINER="${CONTAINER:-atlas_platform-backend-1}"

# Allow CLI overrides
while [[ $# -gt 0 ]]; do
  case "$1" in
    --epochs)     EPOCHS="$2";      shift 2 ;;
    --batch_size) BATCH_SIZE="$2";  shift 2 ;;
    --max_samples) MAX_SAMPLES="$2"; shift 2 ;;
    --data_path)  DATA_PATH="$2";   shift 2 ;;
    --output_dir) OUTPUT_DIR="$2";  shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "═══════════════════════════════════════════════════"
echo " ATLAS IndicBERT Fine-Tuning"
echo "   Container : $CONTAINER"
echo "   Epochs    : $EPOCHS"
echo "   Batch     : $BATCH_SIZE"
echo "   Data      : $DATA_PATH"
echo "   Output    : $OUTPUT_DIR"
echo "═══════════════════════════════════════════════════"

# ── 1. Ensure synthetic training data is present ─────────────────────────────
echo "[1/3] Checking training data …"
DATA_EXISTS=$(docker exec "$CONTAINER" sh -c "test -f '$DATA_PATH' && echo yes || echo no")
if [[ "$DATA_EXISTS" != "yes" ]]; then
  echo "  → Generating synthetic data …"
  docker exec "$CONTAINER" python scripts/generate_synthetic_training_data.py \
    --output_dir /data \
    --samples_per_class 30 \
    --seed 42
  echo "  → Synthetic data written to /data/"
else
  echo "  → Found $DATA_PATH"
fi

# ── 2. Run fine-tuning ────────────────────────────────────────────────────────
echo "[2/3] Starting fine-tuning …"
MAX_SAMPLES_ARG=""
if [[ -n "$MAX_SAMPLES" ]]; then
  MAX_SAMPLES_ARG="--max_samples $MAX_SAMPLES"
fi

docker exec "$CONTAINER" python -m app.ml.train \
  --data_path    "$DATA_PATH" \
  --output_dir   "$OUTPUT_DIR" \
  --epochs       "$EPOCHS" \
  --batch_size   "$BATCH_SIZE" \
  --cpu_mode \
  $MAX_SAMPLES_ARG

echo "[3/3] Verifying checkpoint …"
docker exec "$CONTAINER" sh -c "
  if [ -f '$OUTPUT_DIR/config.json' ]; then
    echo '  → config.json present'
  else
    echo '  ✗ config.json MISSING — training may have failed'; exit 1
  fi
  if [ -f '$OUTPUT_DIR/evaluation_metrics.json' ]; then
    echo '  → evaluation_metrics.json:'; cat '$OUTPUT_DIR/evaluation_metrics.json'
  fi
"

echo ""
echo "Training complete. Restart backend to load the new checkpoint:"
echo "  docker compose restart backend"
