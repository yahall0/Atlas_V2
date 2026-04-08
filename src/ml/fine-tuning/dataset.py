"""HuggingFace Dataset builder for ATLAS FIR training data.

Converts CSV (from generate_synthetic_training_data.py) or Label Studio
JSON export into a HuggingFace ``datasets.DatasetDict`` with
train / val / test splits.

Usage
-----
From Python::

    from src.ml.fine_tuning.dataset import build_dataset

    ds = build_dataset("data/synthetic_fir_training.csv",
                       label_map_path="data/label_map.json")
    print(ds)  # DatasetDict({train: ..., val: ..., test: ...})

From CLI::

    python src/ml/fine-tuning/dataset.py \\
        --csv data/synthetic_fir_training.csv \\
        --label_map data/label_map.json \\
        --output data/atlas_dataset

Label Studio export format
--------------------------
Label Studio JSON export is a list of task objects::

    [{"data": {"text": "..."}, "annotations": [{"result": [{"value": {"choices": ["theft"]}}]}]}]

Pass ``--format label_studio`` to use this path.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TEXT_COL = "text"
LABEL_COL = "category"


# ─────────────────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[dict]:
    """Load rows from a CSV with at minimum ``text`` and ``category`` columns."""
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if TEXT_COL in row and LABEL_COL in row:
                rows.append({TEXT_COL: row[TEXT_COL], LABEL_COL: row[LABEL_COL]})
    return rows


def load_label_studio_json(path: str) -> list[dict]:
    """Load rows exported from Label Studio (for FIR_Category project).

    Expected structure::

        [
            {
                "data": {"text": "..."},
                "annotations": [
                    {
                        "result": [
                            {"value": {"choices": ["theft"]}}
                        ]
                    }
                ]
            },
            ...
        ]
    """
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        tasks = json.load(fh)

    for task in tasks:
        text = task.get("data", {}).get("text", "")
        annotations = task.get("annotations", [])
        if not annotations:
            continue
        # Take the first completed annotation result
        for ann in annotations:
            for result in ann.get("result", []):
                choices = result.get("value", {}).get("choices", [])
                if choices:
                    rows.append({TEXT_COL: text, LABEL_COL: choices[0].lower()})
                    break
            else:
                continue
            break

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Splitter
# ─────────────────────────────────────────────────────────────────────────────

def stratified_split(
    rows: list[dict],
    train_frac: float = 0.8,
    val_frac: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Stratified split preserving per-class distribution.

    Returns (train, val, test) row lists.
    """
    rng = random.Random(seed)

    # Group by label
    by_label: dict[str, list[dict]] = {}
    for row in rows:
        by_label.setdefault(row[LABEL_COL], []).append(row)

    train, val, test = [], [], []
    for label, label_rows in by_label.items():
        shuffled = label_rows[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        t_end = max(1, int(n * train_frac))
        v_end = t_end + max(1, int(n * val_frac))
        train.extend(shuffled[:t_end])
        val.extend(shuffled[t_end:v_end])
        test.extend(shuffled[v_end:])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


# ─────────────────────────────────────────────────────────────────────────────
# Dataset builder
# ─────────────────────────────────────────────────────────────────────────────

def build_dataset(
    data_path: str,
    label_map_path: Optional[str] = None,
    fmt: str = "csv",
    train_frac: float = 0.8,
    val_frac: float = 0.1,
    seed: int = 42,
):
    """Build a HuggingFace ``DatasetDict`` from a CSV or Label Studio JSON file.

    Parameters
    ----------
    data_path:
        Path to the CSV (``fmt="csv"``) or Label Studio export JSON
        (``fmt="label_studio"``).
    label_map_path:
        Optional path to a ``label_map.json`` file (category → int).
        If ``None`` the map is derived from the data.
    fmt:
        ``"csv"`` or ``"label_studio"``.
    train_frac, val_frac:
        Fractions for train and validation splits. Remainder goes to test.
    seed:
        Random seed for reproducible splits.

    Returns
    -------
    datasets.DatasetDict
        With keys ``"train"``, ``"val"``, ``"test"``.  Each split has
        columns ``text``, ``label`` (int), ``category`` (str).
    """
    from datasets import Dataset, DatasetDict  # type: ignore

    if fmt == "label_studio":
        rows = load_label_studio_json(data_path)
    else:
        rows = load_csv(data_path)

    if not rows:
        raise ValueError(f"No valid rows loaded from {data_path!r}")

    # Build or load label map
    if label_map_path and Path(label_map_path).exists():
        with open(label_map_path, encoding="utf-8") as fh:
            label_map: dict[str, int] = json.load(fh)
    else:
        categories = sorted({r[LABEL_COL] for r in rows})
        label_map = {cat: i for i, cat in enumerate(categories)}
        logger.info("Derived label map: %s", label_map)

    train_rows, val_rows, test_rows = stratified_split(
        rows, train_frac=train_frac, val_frac=val_frac, seed=seed
    )
    logger.info(
        "Split sizes — train: %d, val: %d, test: %d",
        len(train_rows), len(val_rows), len(test_rows),
    )

    def _to_hf_dict(split_rows: list[dict]) -> dict:
        texts = [r[TEXT_COL] for r in split_rows]
        labels = [label_map.get(r[LABEL_COL], 0) for r in split_rows]
        categories = [r[LABEL_COL] for r in split_rows]
        return {"text": texts, "label": labels, "category": categories}

    return DatasetDict(
        {
            "train": Dataset.from_dict(_to_hf_dict(train_rows)),
            "val": Dataset.from_dict(_to_hf_dict(val_rows)),
            "test": Dataset.from_dict(_to_hf_dict(test_rows)),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Build HuggingFace DatasetDict for ATLAS training.")
    parser.add_argument("--csv", required=True, help="Path to input CSV or Label Studio JSON")
    parser.add_argument("--label_map", default=None, help="Path to label_map.json")
    parser.add_argument("--output", required=True, help="Directory to save Arrow datasets")
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=["csv", "label_studio"],
        default="csv",
    )
    parser.add_argument("--train_frac", type=float, default=0.8)
    parser.add_argument("--val_frac", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ds = build_dataset(
        args.csv,
        label_map_path=args.label_map,
        fmt=args.fmt,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
        seed=args.seed,
    )
    print(ds)
    ds.save_to_disk(args.output)
    print(f"Saved dataset to {args.output}")
