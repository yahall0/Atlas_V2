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
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_INDIC_BERT_MODEL = os.getenv("INDIC_BERT_MODEL", "ai4bharat/indic-bert")
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


def _make_hf_dataset(rows: list[dict], label_map: dict[str, int], tokenizer):
    """Convert a list of row dicts into a HuggingFace Dataset."""
    from datasets import Dataset  # type: ignore

    texts = [r[CSV_TEXT_COL] for r in rows]
    labels = [label_map[r[CSV_LABEL_COL]] for r in rows]
    encoded = tokenizer(
        texts,
        max_length=512,
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
    acc = accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="macro", zero_division=0)
    return {"accuracy": acc, "f1_macro": f1}


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------


def train(
    data_path: str,
    output_dir: str,
    *,
    epochs: int = 3,
    batch_size: int = 16,
    lr: float = 2e-5,
    dry_run: bool = False,
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

    mlflow.set_tracking_uri(_MLFLOW_TRACKING_URI)
    mlflow.transformers.autolog()

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

    label_map = build_label_map(rows)
    id2label = {v: k for k, v in label_map.items()}
    num_labels = len(label_map)
    logger.info("Labels (%d): %s", num_labels, list(label_map.keys()))

    train_rows, val_rows, test_rows = split_data(rows)
    train_ds = _make_hf_dataset(train_rows, label_map, tokenizer)
    val_ds = _make_hf_dataset(val_rows, label_map, tokenizer)
    test_ds = _make_hf_dataset(test_rows, label_map, tokenizer)

    logger.info("Train=%d Val=%d Test=%d", len(train_rows), len(val_rows), len(test_rows))

    model = AutoModelForSequenceClassification.from_pretrained(
        _INDIC_BERT_MODEL,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label_map,
        cache_dir=_CACHE_DIR,
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_dir=str(Path(output_dir) / "logs"),
        report_to=["mlflow"],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=_compute_metrics,
    )

    with mlflow.start_run(run_name="atlas_bert_finetune"):
        mlflow.log_params(
            {
                "base_model": _INDIC_BERT_MODEL,
                "epochs": epochs,
                "batch_size": batch_size,
                "lr": lr,
                "train_size": len(train_rows),
                "num_labels": num_labels,
            }
        )
        trainer.train()
        results = trainer.evaluate(test_ds)
        mlflow.log_metrics(
            {
                "test_accuracy": results.get("eval_accuracy", 0.0),
                "test_f1_macro": results.get("eval_f1_macro", 0.0),
            }
        )

    # Save checkpoint + label map
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out))
    tokenizer.save_pretrained(str(out))
    (out / "label_map.json").write_text(json.dumps(label_map, ensure_ascii=False), encoding="utf-8")
    logger.info("Checkpoint saved to %s", output_dir)


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
    args = parser.parse_args()
    train(
        args.data_path,
        args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        dry_run=args.dry_run,
    )
