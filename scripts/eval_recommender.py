"""Evaluation harness for the section recommender (Q9c).

Loads the gold-standard FIR set, runs the recommender against each, and
reports:

* top-1, top-3, top-5, top-10 hit rate (any expected citation present in top-K)
* full-set recall  — fraction of expected citations recovered overall
* sub-clause-level precision/recall   — recommendations that match an
  expected canonical citation exactly (sub-clause precision per ADR-D15)
* over-charging rate                  — fraction of recommendations not in
  the expected set (false positives)
* missed-charging rate                — expected citations missing from
  recommendations (false negatives)
* per-FIR breakdown                   — written to a JSON report

Usage::

    python scripts/eval_recommender.py
    python scripts/eval_recommender.py --status sme_ratified   # ratified-only
    python scripts/eval_recommender.py --confidence-floor 0.10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.legal_sections.chunker import iter_chunks  # noqa: E402
from backend.app.legal_sections.embedder import get_embedder  # noqa: E402
from backend.app.legal_sections.recommender import recommend  # noqa: E402
from backend.app.legal_sections.retriever import InMemoryRetriever  # noqa: E402

DATA_DIR = ROOT / "backend" / "app" / "legal_sections" / "data"
DEFAULT_GOLD = DATA_DIR / "gold_standard.jsonl"
DEFAULT_REPORT = DATA_DIR / "eval_report.json"


def _load_gold(path: Path, status_filter: str | None) -> list[dict]:
    items: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if status_filter and item.get("status") != status_filter:
                continue
            items.append(item)
    return items


def _build_retriever(act_filter: str | None = None):
    chunks = list(iter_chunks([
        DATA_DIR / "ipc_sections.jsonl",
        DATA_DIR / "bns_sections.jsonl",
    ]))
    embedder = get_embedder()  # honours ATLAS_EMBEDDER env var
    retriever = InMemoryRetriever(embedder)
    retriever.index(chunks)
    return retriever, len(chunks)


def evaluate(
    gold_items: list[dict],
    retriever: InMemoryRetriever,
    confidence_floor: float,
    top_k_retrieve: int,
) -> dict:
    per_fir: list[dict] = []
    sums = {
        "top1_hit": 0,
        "top3_hit": 0,
        "top5_hit": 0,
        "top10_hit": 0,
        "exact_recovery": 0,  # all expected present somewhere in returned set
    }
    total_expected = 0
    total_recovered = 0
    total_recommended = 0
    over_charges = 0

    for item in gold_items:
        expected = set(item["expected_citations"])
        resp = recommend(
            fir_id=item["fir_id"],
            fir_narrative=item["narrative"],
            retriever=retriever,
            occurrence_date_iso=item.get("occurrence_date_iso"),
            accused_count=item.get("accused_count", 1),
            confidence_floor=confidence_floor,
            top_k_retrieve=top_k_retrieve,
        )
        recommended = [r.canonical_citation for r in resp.recommendations]
        recommended_set = set(recommended)

        top1 = bool(expected.intersection(recommended[:1]))
        top3 = bool(expected.intersection(recommended[:3]))
        top5 = bool(expected.intersection(recommended[:5]))
        top10 = bool(expected.intersection(recommended[:10]))
        all_recovered = expected.issubset(recommended_set)
        recovered = expected.intersection(recommended_set)

        sums["top1_hit"] += int(top1)
        sums["top3_hit"] += int(top3)
        sums["top5_hit"] += int(top5)
        sums["top10_hit"] += int(top10)
        sums["exact_recovery"] += int(all_recovered)
        total_expected += len(expected)
        total_recovered += len(recovered)
        total_recommended += len(recommended)
        over_charges += len(recommended_set - expected)

        per_fir.append({
            "fir_id": item["fir_id"],
            "expected": sorted(expected),
            "recommended_top10": recommended[:10],
            "recovered": sorted(recovered),
            "missed": sorted(expected - recommended_set),
            "over_charges": sorted(recommended_set - expected),
            "top1_hit": top1, "top3_hit": top3, "top5_hit": top5, "top10_hit": top10,
            "exact_recovery": all_recovered,
            "conflict_findings": [
                {"rule_id": f["rule_id"], "severity": f["severity"]}
                for f in resp.conflict_findings
            ],
        })

    n = max(len(gold_items), 1)
    return {
        "n_fir": len(gold_items),
        "top1_accuracy": round(sums["top1_hit"] / n, 4),
        "top3_accuracy": round(sums["top3_hit"] / n, 4),
        "top5_accuracy": round(sums["top5_hit"] / n, 4),
        "top10_accuracy": round(sums["top10_hit"] / n, 4),
        "exact_recovery_rate": round(sums["exact_recovery"] / n, 4),
        "subclause_recall": round(total_recovered / max(total_expected, 1), 4),
        "subclause_precision": round(
            (total_recovered / max(total_recommended, 1)), 4
        ),
        "over_charging_rate": round(over_charges / max(total_recommended, 1), 4),
        "missed_charging_rate": round(
            (total_expected - total_recovered) / max(total_expected, 1), 4
        ),
        "per_fir": per_fir,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(DEFAULT_GOLD))
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--status", default=None,
                    help="Filter by status (e.g. 'sme_ratified'). Default: all.")
    ap.add_argument("--confidence-floor", type=float, default=0.10)
    ap.add_argument("--top-k-retrieve", type=int, default=60)
    args = ap.parse_args()

    gold = _load_gold(Path(args.gold), args.status)
    if not gold:
        print(f"No gold-standard items found at {args.gold}"
              f" (status filter: {args.status})")
        sys.exit(2)

    retriever, n_chunks = _build_retriever()
    print(f"Indexed {n_chunks} chunks across IPC + BNS.")
    print(f"Evaluating against {len(gold)} gold-standard FIRs ...")

    report = evaluate(
        gold_items=gold,
        retriever=retriever,
        confidence_floor=args.confidence_floor,
        top_k_retrieve=args.top_k_retrieve,
    )
    Path(args.report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = {k: v for k, v in report.items() if k != "per_fir"}
    print(json.dumps(summary, indent=2))
    print(f"Full report written to: {args.report}")


if __name__ == "__main__":
    main()
