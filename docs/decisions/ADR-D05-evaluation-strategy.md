# ADR-D05: Evaluation Strategy for IndicBERT FIR Classifier

**Status:** Accepted  
**Date:** 2026-04-14  
**Deciders:** ML Lead, Backend Lead, QA Lead  
**Revises:** —  

---

## Context

Sprint 3 delivers the first fine-tuned IndicBERT checkpoint for ATLAS FIR classification
(11 BNS-aligned categories).  Before the checkpoint is promoted to production, we need a
reproducible evaluation strategy that:

1. Provides a single **pass/fail gate** the CI pipeline can enforce.
2. Detects **per-class degradation** before it affects end users.
3. Surfaces **demographic / geographic bias** (district-level prediction skew).
4. Stays **cheap to run** (CPU-only, < 5 min) given the containerised environment.

---

## Decision

### 1. Primary metric: Macro-F1 ≥ 0.80

We use **macro-averaged F1** as the primary acceptance metric because:

- It treats all 11 crime categories equally regardless of support size.
- FIRs are unevenly distributed (theft/fraud >> dacoity/kidnapping), so micro-F1
  would mask poor recall on rare categories.
- The 0.80 threshold was set against the baseline keyword heuristic (≈0.65) with a
  15-point headroom for degradation over retraining cycles.

### 2. Secondary metrics (logged, not gates)

| Metric | Tool | Purpose |
|--------|------|---------|
| Per-class P / R / F1 | `evaluate.py` | Detect tail-category regression |
| Confusion matrix | `evaluate.py` (→ MLflow artifact) | Visualise category confusion patterns |
| Classification report JSON | `evaluate.py` | Full per-label breakdown |
| Gini coefficient | `bias_report.py` | Label distribution uniformity |
| District chi-square (p < 0.05 → flag) | `bias_report.py` | Geographic prediction skew |

### 3. Dataset splits

| Split | Fraction | Source | Purpose |
|-------|----------|--------|---------|
| Train | 80% | `synthetic_fir_training.csv` + future Label Studio exports | Fine-tuning |
| Val   | 10% | Same | Hyperparameter selection, early stopping |
| Test  | 10% | `synthetic_fir_test.csv` | Final acceptance evaluation |

Stratified split is performed by `src/ml/fine-tuning/dataset.py` to preserve
per-class proportions in each split.

### 4. Evaluation artefacts stored in MLflow

Every training run writes the following artefacts to the `evaluation/` subfolder of
the MLflow run:

- `confusion_matrix.json` — serialised confusion matrix
- `classification_report.json` — per-class P/R/F1 and support

`evaluation_metrics.json` saved alongside the checkpoint records:
`model_version`, `base_model`, `best_val_f1`, `test_accuracy`, `num_labels`,
`train_size`, `training_date`, `epochs`.

### 5. CI/CD gate

`src/ml/fine-tuning/run_training.sh` followed by:

```bash
python -m src.ml.evaluation.evaluate \
  --checkpoint /app/models/atlas_classifier_v1 \
  --test_data  /data/synthetic_fir_test.csv \
  --threshold  0.80
# exits with code 1 if macro-F1 < 0.80
```

### 6. Bias check (advisory, not a hard gate)

```bash
python -m src.ml.bias.bias_report \
  --predictions /data/predictions.csv \
  --output      /data/bias_report.json
```

Output reviewed in the monthly model review meeting; flagged districts
trigger re-labelling requests via Label Studio.

### 7. Retraining cadence

| Trigger | Action |
|--------|--------|
| New Label Studio batch (≥ 200 new FIRs) | Re-run `run_training.sh` + gate check |
| Macro-F1 < 0.75 on production sample | Immediate retraining sprint |
| New BNS category | Update `ATLAS_CATEGORIES`, regenerate synthetic data, retrain |

---

## Consequences

### Positive
- Reproducible, scriptable evaluation closes the ML feedback loop.
- Macro-F1 gate prevents silent degradation when retraining on new data.
- Bias report gives early warning of district-level over/under-representation.
- CPU-only evaluation fits the existing Docker Compose environment with no GPU cost.

### Negative / Trade-offs
- Synthetic training data inflates test scores; real-annotation test set must
  supersede the synthetic test CSV by Sprint 4.
- 0.80 macro-F1 threshold may be unreachable with fewer than 300 labelled examples
  per class; threshold should be reviewed after first real-annotation batch.
- Chi-square district test requires ≥ 5 predictions per district per category
  to be statistically valid; districts with sparse data are excluded automatically.

---

## Alternatives Considered

| Alternative | Reason not chosen |
|-------------|------------------|
| Accuracy as primary metric | Misleading with class imbalance (theft dominates) |
| Weighted F1 | Disadvantages rare categories; macro-F1 preferred for fairness |
| GPU-based evaluation | Not available in Docker Compose environment |
| Separate held-out test set from additional annotation | Deferred to Sprint 4 when Label Studio annotations are complete |
