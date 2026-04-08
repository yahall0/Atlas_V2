"""Offline evaluation harness for an ATLAS IndicBERT checkpoint.

Usage
-----
Evaluate against a test CSV::

    python -m src.ml.evaluation.evaluate \\
        --checkpoint /app/models/atlas_classifier_v1 \\
        --test_data  /data/synthetic_fir_test.csv \\
        --output     /tmp/eval_results.json

Exit codes
----------
0 — macro-F1 >= acceptance threshold (default 0.80)
1 — macro-F1 below threshold (pipeline gate failure)
2 — runtime error
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Acceptance gate — exit 1 if macro-F1 is below this value
ACCEPTANCE_THRESHOLD = 0.80


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_csv(path: str) -> tuple[list[str], list[str]]:
    """Return (texts, labels) from a CSV with 'text' and 'category' columns."""
    texts, labels = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if "text" in row and "category" in row:
                texts.append(row["text"])
                labels.append(row["category"])
    if not texts:
        raise ValueError(f"No valid rows found in {path}")
    return texts, labels


def _load_label_map(checkpoint_dir: str) -> dict[str, int]:
    """Load label_map.json from checkpoint directory."""
    label_map_path = Path(checkpoint_dir) / "label_map.json"
    if not label_map_path.exists():
        raise FileNotFoundError(f"label_map.json not found in {checkpoint_dir}")
    return json.loads(label_map_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    checkpoint_dir: str,
    test_data_path: str,
    *,
    output_path: Optional[str] = None,
    threshold: float = ACCEPTANCE_THRESHOLD,
    batch_size: int = 32,
) -> dict:
    """Run full evaluation of checkpoint against test CSV.

    Parameters
    ----------
    checkpoint_dir:
        Path to the fine-tuned checkpoint directory.
    test_data_path:
        Path to the test CSV with columns ``text``, ``category``.
    output_path:
        If given, write the evaluation report JSON here.
    threshold:
        Macro-F1 acceptance gate value.
    batch_size:
        Inference batch size.

    Returns
    -------
    dict with keys: macro_f1, accuracy, per_class, confusion_matrix, passes_gate

    Raises
    ------
    SystemExit(1) — if macro_f1 < threshold
    SystemExit(2) — on runtime error
    """
    try:
        import numpy as np  # type: ignore
        from sklearn.metrics import (  # type: ignore
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
        )
        from transformers import (  # type: ignore
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
        import torch  # type: ignore
    except ImportError as exc:
        logger.error("Missing dependency: %s", exc)
        sys.exit(2)

    print(f"Loading checkpoint from {checkpoint_dir} …")
    try:
        tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
        model = AutoModelForSequenceClassification.from_pretrained(checkpoint_dir)
        model.eval()
    except Exception as exc:
        logger.error("Could not load checkpoint '%s': %s", checkpoint_dir, exc)
        sys.exit(2)

    # Build id2label — prefer config, fall back to label_map.json
    id2label: dict[int, str] = model.config.id2label or {}
    if not id2label:
        try:
            label_map = _load_label_map(checkpoint_dir)
            id2label = {v: k for k, v in label_map.items()}
        except FileNotFoundError:
            logger.warning("No id2label in config and no label_map.json found.")

    print(f"Loading test data from {test_data_path} …")
    texts, true_labels = _load_csv(test_data_path)

    # Build label_map from available labels + checkpoint
    all_label_names = sorted(set(true_labels) | set(id2label.values()))
    str2int = {lab: i for i, lab in enumerate(sorted(set(id2label.values())))}

    # Encode groundtruth — skip rows whose label is not in str2int
    filtered_texts, y_true_int = [], []
    for txt, lbl in zip(texts, true_labels):
        if lbl in str2int:
            filtered_texts.append(txt)
            y_true_int.append(str2int[lbl])
        else:
            logger.warning("Unknown label '%s' in test data — skipping row.", lbl)

    if not filtered_texts:
        logger.error("No valid test rows after label filtering.")
        sys.exit(2)

    print(f"Running inference on {len(filtered_texts)} samples …")

    # Batched inference
    y_pred_int: list[int] = []
    for i in range(0, len(filtered_texts), batch_size):
        batch_texts = filtered_texts[i : i + batch_size]
        inputs = tokenizer(
            batch_texts,
            max_length=512,
            truncation=True,
            padding=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**inputs).logits
        preds = torch.argmax(logits, dim=-1).tolist()
        y_pred_int.extend(preds)

    y_true = np.array(y_true_int)
    y_pred = np.array(y_pred_int)

    label_names = [id2label.get(i, str(i)) for i in range(model.config.num_labels)]

    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    accuracy = float(accuracy_score(y_true, y_pred))
    cm = confusion_matrix(y_true, y_pred).tolist()
    cr = classification_report(
        y_true, y_pred,
        target_names=label_names,
        output_dict=True,
        zero_division=0,
    )

    passes_gate = macro_f1 >= threshold

    report = {
        "checkpoint": str(checkpoint_dir),
        "test_data": str(test_data_path),
        "num_samples": len(filtered_texts),
        "macro_f1": round(macro_f1, 4),
        "accuracy": round(accuracy, 4),
        "passes_gate": passes_gate,
        "acceptance_threshold": threshold,
        "per_class": {
            name: {
                "precision": round(cr[name]["precision"], 4),
                "recall": round(cr[name]["recall"], 4),
                "f1": round(cr[name]["f1-score"], 4),
                "support": cr[name]["support"],
            }
            for name in label_names
            if name in cr
        },
        "confusion_matrix": cm,
        "label_order": label_names,
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report saved to {output_path}")

    print(f"\n{'='*50}")
    print(f"  Macro F1 : {macro_f1:.4f}  (threshold: {threshold})")
    print(f"  Accuracy : {accuracy:.4f}")
    print(f"  Gate     : {'PASS ✓' if passes_gate else 'FAIL ✗'}")
    print(f"{'='*50}\n")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Evaluate an ATLAS IndicBERT checkpoint against a test CSV."
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Path to the fine-tuned checkpoint directory.",
    )
    parser.add_argument(
        "--test_data",
        required=True,
        help="Path to test CSV with columns: text, category.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON evaluation report.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=ACCEPTANCE_THRESHOLD,
        help=f"Macro-F1 acceptance threshold (default {ACCEPTANCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=32,
        help="Inference batch size (default 32).",
    )
    args = parser.parse_args()

    try:
        report = evaluate(
            args.checkpoint,
            args.test_data,
            output_path=args.output,
            threshold=args.threshold,
            batch_size=args.batch_size,
        )
        sys.exit(0 if report["passes_gate"] else 1)
    except SystemExit:
        raise
    except Exception:
        logger.exception("Evaluation failed with an unexpected error.")
        sys.exit(2)
