"""IndicBERT fine-tuning harness for ATLAS FIR classification.

Usage
-----
Fine-tune on a labelled CSV::

    python -m app.ml.train \\
        --data_path /data/fir_labelled.csv \\
        --output_dir /models/atlas_bert_v1 \\
        --epochs 3

Dry-run (no GPU / no data required — validates the pipeline logic)::

    python -m app.ml.train --dry_run

The script:
1. Loads and splits data (80/10/10 train/val/test).
2. Tokenises with IndicBERT tokeniser.
3. Fine-tunes using HuggingFace ``Trainer`` with MLflow autologging.
4. Saves the final checkpoint + label mapping.
5. Logs test accuracy/F1 to MLflow.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_INDIC_BERT_MODEL = os.getenv("INDIC_BERT_MODEL", "google/muril-base-cased")
_CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/transformers_cache")
_MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# Expected CSV columns
CSV_TEXT_COL = "text"
CSV_LABEL_COL = "category"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def load_csv(path: str) -> list[dict]:
    """Load rows from a CSV file with at minimum ``text`` and ``category`` columns."""
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if CSV_TEXT_COL in row and CSV_LABEL_COL in row:
                rows.append({CSV_TEXT_COL: row[CSV_TEXT_COL], CSV_LABEL_COL: row[CSV_LABEL_COL]})
    return rows


def build_label_map(rows: list[dict]) -> dict[str, int]:
    """Return an alphabetically-sorted label → int mapping."""
    labels = sorted({r[CSV_LABEL_COL] for r in rows})
    return {lbl: i for i, lbl in enumerate(labels)}


def split_data(rows: list[dict], seed: int = 42) -> tuple[list, list, list]:
    """Split rows into train (80%), val (10%), test (10%)."""
    random.seed(seed)
    shuffled = rows[:]
    random.shuffle(shuffled)
    n = len(shuffled)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)
    return shuffled[:train_end], shuffled[train_end:val_end], shuffled[val_end:]


# ---------------------------------------------------------------------------
# HuggingFace Dataset wrapper
# ---------------------------------------------------------------------------


def _make_hf_dataset(rows: list[dict], label_map: dict[str, int], tokenizer, max_length: int = 128):
    """Convert a list of row dicts into a HuggingFace Dataset."""
    from datasets import Dataset  # type: ignore

    texts = [r[CSV_TEXT_COL] for r in rows]
    labels = [label_map[r[CSV_LABEL_COL]] for r in rows]
    encoded = tokenizer(
        texts,
        max_length=max_length,
        truncation=True,
        padding="max_length",
    )
    encoded["labels"] = labels
    return Dataset.from_dict(dict(encoded))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_metrics(eval_pred):
    """Compute accuracy and macro-F1 for ``Trainer``."""
    import numpy as np  # type: ignore
    from sklearn.metrics import accuracy_score, f1_score  # type: ignore

    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = float(accuracy_score(labels, preds))
    f1 = float(f1_score(labels, preds, average="macro", zero_division=0))
    return {"accuracy": acc, "f1_macro": f1}


def _class_weights(rows: list[dict], label_map: dict[str, int]):
    """Compute inverse-frequency class weights as a torch.Tensor."""
    import torch  # type: ignore

    counts = [0] * len(label_map)
    for r in rows:
        counts[label_map[r[CSV_LABEL_COL]]] += 1
    total = sum(counts)
    weights = [total / (len(counts) * max(c, 1)) for c in counts]
    return torch.tensor(weights, dtype=torch.float)


class WeightedTrainer:  # type: ignore
    """HuggingFace Trainer subclass that applies class-weight loss."""

    # Will be set before instantiation
    _class_weights = None

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        import torch  # type: ignore
        import torch.nn as nn  # type: ignore

        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        device = logits.device
        weights = (
            self._class_weights.to(device)
            if self._class_weights is not None
            else None
        )
        loss = nn.CrossEntropyLoss(weight=weights)(logits, labels)
        return (loss, outputs) if return_outputs else loss


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------


def train(
    data_path: str,
    output_dir: str,
    *,
    epochs: int = 3,
    batch_size: int = 2,
    lr: float = 2e-5,
    dry_run: bool = False,
    cpu_mode: bool = False,
    max_samples: Optional[int] = None,
    use_class_weights: bool = True,
    max_length: int = 128,
) -> None:
    """Fine-tune IndicBERT and save the checkpoint.

    Parameters
    ----------
    data_path:
        Path to the labelled CSV (columns: text, category).
    output_dir:
        Directory to save the fine-tuned checkpoint.
    epochs:
        Number of training epochs.
    batch_size:
        Per-device training batch size.
    lr:
        Learning rate for AdamW.
    dry_run:
        If ``True``, skip actual training and just validate the pipeline.
    """
    import mlflow  # type: ignore
    from transformers import (  # type: ignore
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    if cpu_mode:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        logger.info("CPU mode enabled — CUDA disabled.")

    mlflow.set_tracking_uri(_MLFLOW_TRACKING_URI)
    try:
        mlflow.transformers.autolog()
    except Exception as _autolog_exc:
        logger.warning("mlflow.transformers.autolog() unavailable (%s) — using manual logging.", _autolog_exc)

    logger.info("Loading tokeniser from %s …", _INDIC_BERT_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(_INDIC_BERT_MODEL, cache_dir=_CACHE_DIR)

    if dry_run:
        logger.info("Dry-run mode: skipping data load and training.")
        print("Dry-run OK — tokeniser loaded successfully.")
        return

    logger.info("Loading data from %s …", data_path)
    rows = load_csv(data_path)
    if not rows:
        raise ValueError(f"No valid rows found in {data_path}")

    if max_samples and max_samples < len(rows):
        random.shuffle(rows)
        rows = rows[:max_samples]
        logger.info("Capped to %d samples (--max_samples).", max_samples)

    label_map = build_label_map(rows)
    id2label = {v: k for k, v in label_map.items()}
    num_labels = len(label_map)
    logger.info("Labels (%d): %s", num_labels, list(label_map.keys()))

    train_rows, val_rows, test_rows = split_data(rows)
    train_ds = _make_hf_dataset(train_rows, label_map, tokenizer, max_length=max_length)
    val_ds = _make_hf_dataset(val_rows, label_map, tokenizer, max_length=max_length)
    test_ds = _make_hf_dataset(test_rows, label_map, tokenizer, max_length=max_length)

    logger.info("Train=%d Val=%d Test=%d", len(train_rows), len(val_rows), len(test_rows))

    model = AutoModelForSequenceClassification.from_pretrained(
        _INDIC_BERT_MODEL,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label_map,
        cache_dir=_CACHE_DIR,
    )
    # Reduce peak memory during backprop (trades compute for memory)
    model.gradient_checkpointing_enable()

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        report_to=["mlflow"],
        use_cpu=cpu_mode,
        dataloader_num_workers=0,
    )

    from transformers import Trainer as _BaseTrainer  # type: ignore

    TrainerClass = _BaseTrainer
    if use_class_weights:
        try:
            cw = _class_weights(train_rows, label_map)
            WeightedTrainer._class_weights = cw

            class _WeightedTrainer(WeightedTrainer, _BaseTrainer):  # type: ignore
                pass

            TrainerClass = _WeightedTrainer
            logger.info("Using class-weighted loss.")
        except Exception as exc:
            logger.warning("Could not apply class weights: %s", exc)

    trainer = TrainerClass(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=_compute_metrics,
    )

    # Run training — trainer.train() is always executed
    trainer.train()
    results = trainer.evaluate(test_ds)
    test_acc = results.get("eval_accuracy", 0.0)
    test_f1 = results.get("eval_f1_macro", 0.0)

    # MLflow logging is best-effort — never block the checkpoint save
    try:
        with mlflow.start_run(run_name="atlas_bert_finetune"):
            mlflow.log_params(
                {
                    "base_model": _INDIC_BERT_MODEL,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "lr": lr,
                    "train_size": len(train_rows),
                    "num_labels": num_labels,
                    "cpu_mode": cpu_mode,
                    "max_samples": max_samples,
                }
            )
            mlflow.log_metrics({"test_accuracy": test_acc, "test_f1_macro": test_f1})

            try:
                import numpy as np  # type: ignore
                from sklearn.metrics import classification_report, confusion_matrix  # type: ignore

                preds_output = trainer.predict(test_ds)
                y_pred = np.argmax(preds_output.predictions, axis=-1)
                y_true = preds_output.label_ids
                cm = confusion_matrix(y_true, y_pred).tolist()
                cr = classification_report(
                    y_true, y_pred,
                    target_names=[id2label[i] for i in range(num_labels)],
                    output_dict=True,
                    zero_division=0,
                )
                artifacts_dir = Path(output_dir) / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                (artifacts_dir / "confusion_matrix.json").write_text(
                    json.dumps(cm), encoding="utf-8"
                )
                (artifacts_dir / "classification_report.json").write_text(
                    json.dumps(cr, ensure_ascii=False), encoding="utf-8"
                )
                mlflow.log_artifacts(str(artifacts_dir), artifact_path="evaluation")
            except Exception as exc:
                logger.warning("Could not generate confusion matrix: %s", exc)
    except Exception as exc:
        logger.warning("MLflow logging failed (non-fatal): %s", exc)

    # Save checkpoint + label map + evaluation metrics
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "label_map.json").write_text(
        json.dumps(label_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    eval_metrics = {
        "model_version": Path(output_dir).name,
        "base_model": _INDIC_BERT_MODEL,
        "best_val_f1": test_f1,
        "test_accuracy": test_acc,
        "num_labels": num_labels,
        "train_size": len(train_rows),
        "training_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epochs": epochs,
    }
    (out / "evaluation_metrics.json").write_text(
        json.dumps(eval_metrics, indent=2), encoding="utf-8"
    )
    logger.info("Checkpoint + metrics saved to %s", output_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Fine-tune IndicBERT for ATLAS FIR classification.")
    parser.add_argument("--data_path", default="", help="Path to labelled CSV")
    parser.add_argument("--output_dir", default="/models/atlas_bert_v1", help="Checkpoint output dir")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--dry_run", action="store_true", help="Validate pipeline without training")
    parser.add_argument("--cpu_mode", action="store_true", help="Disable CUDA (CPU-only training)")
    parser.add_argument("--max_samples", type=int, default=None, help="Cap dataset rows (for testing)")
    parser.add_argument("--no_class_weights", action="store_true", help="Disable class-weight balancing")
    parser.add_argument("--max_length", type=int, default=128, help="Max token length for tokenizer")
    args = parser.parse_args()
    train(
        args.data_path,
        args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        dry_run=args.dry_run,
        cpu_mode=args.cpu_mode,
        max_samples=args.max_samples,
        use_class_weights=not args.no_class_weights,
        max_length=args.max_length,
    )
