"""Bias report generator for ATLAS FIR classification.

Checks for:
1. **District-level prediction skew** — chi-square test per district
   to detect if a district's prediction distribution differs significantly
   from the global distribution (p < 0.05 → flagged).

2. **Label imbalance (Gini coefficient)** — measures how unevenly
   predictions are distributed across categories.

Usage
-----
    python -m src.ml.bias.bias_report \\
        --predictions /data/predictions.csv \\
        --output      /data/bias_report.json

Input CSV columns (required)
----------------------------
``text``, ``category`` (ground-truth), ``predicted`` (model output),
``district`` (optional — skew analysis skipped if absent).

Output
------
``bias_report.json`` containing per-district chi-square results,
global Gini coefficient, top-N over-predicted categories, and a
``flags`` list of bias alerts.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _gini(counts: list[int]) -> float:
    """Gini coefficient in [0, 1] — 0 = perfectly equal, 1 = totally skewed."""
    if not counts or sum(counts) == 0:
        return 0.0
    n = len(counts)
    total = sum(counts)
    proportions = sorted(c / total for c in counts)
    cumsum = 0.0
    gini_sum = 0.0
    for i, p in enumerate(proportions, 1):
        cumsum += p
        gini_sum += (2 * i - n - 1) * p
    return abs(gini_sum) / n


def _chi2_goodness_of_fit(
    observed: list[int], expected_dist: dict[str, float]
) -> tuple[float, float]:
    """Chi-square goodness-of-fit test.

    Parameters
    ----------
    observed:
        dict of category → count for the sub-group being tested.
    expected_dist:
        dict of category → proportion (should sum to 1.0).

    Returns
    -------
    (chi2_stat, p_value) — uses scipy if available, else returns (0.0, 1.0).
    """
    try:
        from scipy.stats import chisquare  # type: ignore
    except ImportError:
        logger.debug("scipy not available — skipping chi-square test.")
        return 0.0, 1.0

    total = sum(observed)
    if total == 0:
        return 0.0, 1.0
    expected_counts = [expected_dist.get(cat, 0.0) * total for cat in expected_dist]
    observed_counts = [observed.get(cat, 0) for cat in expected_dist]  # type: ignore[attr-defined]
    stat, p_val = chisquare(observed_counts, f_exp=expected_counts)
    return float(stat), float(p_val)


# ---------------------------------------------------------------------------
# Core report generation
# ---------------------------------------------------------------------------


def generate_bias_report(
    predictions_path: str,
    *,
    output_path: Optional[str] = None,
    skew_pvalue_threshold: float = 0.05,
    top_n_overpredicted: int = 3,
) -> dict:
    """Generate a bias report from a predictions CSV.

    Parameters
    ----------
    predictions_path:
        Path to CSV with columns: text, category (ground-truth),
        predicted (model output), district (optional).
    output_path:
        If given, write the report JSON to this path.
    skew_pvalue_threshold:
        Chi-square p-value below which a district is flagged as skewed.
    top_n_overpredicted:
        Number of over-predicted categories to surface per district.

    Returns
    -------
    dict with keys: global_gini, per_class_counts, district_skew (if available),
    flags, summary.
    """
    rows: list[dict] = []
    with open(predictions_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if "category" in row and "predicted" in row:
                rows.append({
                    "true": row["category"].strip(),
                    "pred": row["predicted"].strip(),
                    "district": row.get("district", "").strip(),
                })

    if not rows:
        raise ValueError(f"No valid rows found in {predictions_path}")

    # ── Global prediction distribution ──────────────────────────────────────
    pred_counter = Counter(r["pred"] for r in rows)
    all_categories = sorted(pred_counter.keys() | Counter(r["true"] for r in rows).keys())
    total = len(rows)
    global_dist = {cat: pred_counter[cat] / total for cat in all_categories}

    # ── Global Gini ──────────────────────────────────────────────────────────
    gini_val = _gini([pred_counter.get(c, 0) for c in all_categories])

    # ── Per-class precision / recall (simple) ────────────────────────────────
    per_class: dict[str, dict] = {}
    for cat in all_categories:
        tp = sum(1 for r in rows if r["true"] == cat and r["pred"] == cat)
        fp = sum(1 for r in rows if r["true"] != cat and r["pred"] == cat)
        fn = sum(1 for r in rows if r["true"] == cat and r["pred"] != cat)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        per_class[cat] = {
            "predicted_count": pred_counter.get(cat, 0),
            "true_count": sum(1 for r in rows if r["true"] == cat),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    # ── District-level skew analysis ─────────────────────────────────────────
    district_skew: list[dict] = []
    flags: list[str] = []

    districts = sorted({r["district"] for r in rows if r["district"]})
    if districts:
        for dist in districts:
            dist_rows = [r for r in rows if r["district"] == dist]
            dist_pred_counter = Counter(r["pred"] for r in dist_rows)
            chi2, pval = _chi2_goodness_of_fit(
                dist_pred_counter, global_dist  # type: ignore[arg-type]
            )
            is_skewed = pval < skew_pvalue_threshold
            top_over = [
                cat for cat, _ in dist_pred_counter.most_common(top_n_overpredicted)
            ]
            entry = {
                "district": dist,
                "n_firs": len(dist_rows),
                "chi2_stat": round(chi2, 4),
                "p_value": round(pval, 6),
                "flagged_skewed": is_skewed,
                "top_predicted": top_over,
            }
            district_skew.append(entry)
            if is_skewed:
                flags.append(
                    f"District '{dist}' has statistically significant prediction skew "
                    f"(chi2={chi2:.2f}, p={pval:.4f}) — over-represented: {', '.join(top_over)}"
                )

    # ── Gini threshold flag ───────────────────────────────────────────────────
    if gini_val > 0.4:
        flags.append(
            f"Global prediction Gini coefficient is {gini_val:.3f} (> 0.4) "
            "— class imbalance is significant."
        )

    report = {
        "predictions_path": str(predictions_path),
        "total_predictions": total,
        "num_categories": len(all_categories),
        "global_gini": round(gini_val, 4),
        "per_class": per_class,
        "district_skew": district_skew,
        "flags": flags,
        "summary": (
            f"{len(flags)} bias flag(s) raised across "
            f"{len(district_skew)} district(s)."
        ),
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Bias report saved to {output_path}")

    print(f"\nBias summary: {report['summary']}")
    if flags:
        for f in flags:
            print(f"  ⚠ {f}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Generate a bias report from ATLAS FIR model predictions."
    )
    parser.add_argument(
        "--predictions",
        required=True,
        help="Path to predictions CSV (columns: text, category, predicted, district).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the bias report JSON.",
    )
    parser.add_argument(
        "--pvalue_threshold",
        type=float,
        default=0.05,
        help="Chi-square p-value threshold for district skew flagging (default 0.05).",
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=3,
        help="Number of top over-predicted categories to surface per district.",
    )
    args = parser.parse_args()

    try:
        generate_bias_report(
            args.predictions,
            output_path=args.output,
            skew_pvalue_threshold=args.pvalue_threshold,
            top_n_overpredicted=args.top_n,
        )
        sys.exit(0)
    except Exception:
        logger.exception("Bias report generation failed.")
        sys.exit(2)
