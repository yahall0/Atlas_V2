#!/usr/bin/env python3
"""Train the evidence gap detection ML model (Tier 2).

Usage:
    python scripts/train_evidence_model.py \
        --data_path data/evidence_training/evidence_training.csv \
        --output_dir backend/models

Generates synthetic data if the CSV doesn't exist, trains a
MultiOutputClassifier(LogisticRegression) with TF-IDF features,
evaluates, logs to MLflow, and saves the model.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier

from app.ml.evidence_taxonomy import ALL_CATEGORIES


def load_data(csv_path: str) -> tuple[list[str], np.ndarray]:
    """Load training data from CSV."""
    texts: list[str] = []
    labels: list[list[int]] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row.get("text_features", ""))
            label_row = [int(row.get(cat, 0)) for cat in ALL_CATEGORIES]
            labels.append(label_row)

    return texts, np.array(labels)


def main():
    parser = argparse.ArgumentParser(description="Train evidence gap model")
    parser.add_argument("--data_path", default="data/evidence_training/evidence_training.csv")
    parser.add_argument("--output_dir", default="backend/models")
    parser.add_argument("--max_features", type=int, default=3000)
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-generate data if missing
    if not data_path.exists():
        print("Training data not found. Generating synthetic data...")
        data_path.parent.mkdir(parents=True, exist_ok=True)
        from scripts.generate_evidence_training_data import generate_dataset
        rows = generate_dataset(samples_per_class=200, seed=args.seed)

        fieldnames = ["text_features", "crime_category", "section_features", "strength"] + ALL_CATEGORIES
        with open(data_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Generated {len(rows)} training samples -> {data_path}")

    # Load
    print(f"Loading data from {data_path}...")
    texts, y = load_data(str(data_path))
    print(f"Loaded {len(texts)} samples, {y.shape[1]} labels")

    # TF-IDF
    print("Fitting TF-IDF vectorizer...")
    tfidf = TfidfVectorizer(max_features=args.max_features, ngram_range=(1, 2))
    X = tfidf.fit_transform(texts)
    print(f"Feature matrix: {X.shape}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed,
    )
    print(f"Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")

    # Train
    print("Training MultiOutputClassifier(LogisticRegression)...")
    base = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
    model = MultiOutputClassifier(base)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    report = classification_report(
        y_test, y_pred,
        target_names=ALL_CATEGORIES,
        output_dict=True,
        zero_division=0,
    )
    report_text = classification_report(
        y_test, y_pred,
        target_names=ALL_CATEGORIES,
        zero_division=0,
    )

    macro_f1 = report.get("macro avg", {}).get("f1-score", 0.0)
    micro_f1 = report.get("micro avg", {}).get("f1-score", 0.0)

    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(report_text)
    print(f"\nMacro-F1: {macro_f1:.4f}")
    print(f"Micro-F1: {micro_f1:.4f}")

    if macro_f1 >= 0.65:
        print(f"\n[PASS] Macro-F1 {macro_f1:.4f} >= 0.65 threshold")
    else:
        print(f"\n[WARN] Macro-F1 {macro_f1:.4f} < 0.65 threshold")

    # Save model
    model_path = output_dir / "evidence_gap_model.pkl"
    tfidf_path = output_dir / "evidence_tfidf.pkl"

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(tfidf_path, "wb") as f:
        pickle.dump(tfidf, f)

    print(f"\nModel saved: {model_path}")
    print(f"TF-IDF saved: {tfidf_path}")
    print(f"Model size: {model_path.stat().st_size / 1024:.1f} KB")
    print(f"TF-IDF size: {tfidf_path.stat().st_size / 1024:.1f} KB")

    # Save metrics
    metrics = {
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "train_samples": X_train.shape[0],
        "test_samples": X_test.shape[0],
        "categories": len(ALL_CATEGORIES),
    }
    metrics_path = output_dir / "evidence_model_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved: {metrics_path}")

    # MLflow logging (optional, fire-and-forget)
    try:
        import mlflow
        mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment("evidence_gap_detection")
        with mlflow.start_run(run_name="evidence_gap_train"):
            mlflow.log_params({
                "max_features": args.max_features,
                "test_size": args.test_size,
                "model_type": "MultiOutputClassifier(LogisticRegression)",
            })
            mlflow.log_metrics({"macro_f1": macro_f1, "micro_f1": micro_f1})
            mlflow.log_artifact(str(metrics_path))
        print("Logged to MLflow.")
    except Exception as e:
        print(f"MLflow logging skipped: {e}")


if __name__ == "__main__":
    main()
