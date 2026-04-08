#!/usr/bin/env python3
"""Create a stratified gold-standard annotation set from ingested FIRs.

Samples up to ``--total`` FIRs from the ATLAS PostgreSQL database using
stratified sampling across districts, ensuring each district contributes
proportionally.  The output is a JSON-Lines file suitable for import into
Label Studio via the batch tasks API.

Usage
-----
    python scripts/create_gold_standard.py \\
        --db_url     postgresql://atlas:atlaspass@localhost:5432/atlas_db \\
        --total      200 \\
        --output     gold_standard.jsonl

Sampling logic
--------------
1.  Count FIRs per district.
2.  Allocate sample slots proportionally (at least 1 per district if present).
3.  For each district randomly sample the allocated count.
4.  Shuffle the combined set.
5.  Write each row as a JSON object on its own line.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
from collections import defaultdict

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def load_firs(db_url: str) -> list[dict]:
    """Load all FIR rows needed for sampling."""
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        logger.error("psycopg2 is required. pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    sql = """
        SELECT
            id::text,
            fir_number,
            district,
            police_station,
            narrative,
            primary_sections,
            completeness_pct,
            nlp_classification,
            status
        FROM firs
        WHERE narrative IS NOT NULL AND LENGTH(narrative) > 50
        ORDER BY created_at DESC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def stratified_sample(rows: list[dict], total: int, seed: int = 42) -> list[dict]:
    """Return a stratified random sample of *total* rows."""
    random.seed(seed)

    # Group by district
    by_district: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_district[r.get("district") or "unknown"].append(r)

    n_districts = len(by_district)
    if total >= len(rows):
        logger.info("Requested sample >= total rows; returning all %d rows.", len(rows))
        return rows[:]

    # Proportional allocation
    total_rows = len(rows)
    allocation: dict[str, int] = {}
    remaining = total
    districts = sorted(by_district.keys())

    for i, dist in enumerate(districts):
        proportion = len(by_district[dist]) / total_rows
        alloc = max(1, math.floor(proportion * total))
        # Last district gets whatever is left
        if i == len(districts) - 1:
            alloc = remaining
        else:
            alloc = min(alloc, remaining, len(by_district[dist]))
        allocation[dist] = alloc
        remaining -= alloc
        if remaining <= 0:
            break

    sampled: list[dict] = []
    for dist, count in allocation.items():
        sampled.extend(random.sample(by_district[dist], min(count, len(by_district[dist]))))

    random.shuffle(sampled)
    return sampled[:total]


def format_for_labelstudio(row: dict) -> dict:
    """Convert a FIR row to a Label Studio task dict."""
    return {
        "data": {
            "id": row["id"],
            "fir_number": row.get("fir_number", ""),
            "district": row.get("district", ""),
            "text": row.get("narrative", ""),
            "primary_sections": row.get("primary_sections") or [],
            "completeness_pct": float(row.get("completeness_pct") or 0),
            "existing_classification": row.get("nlp_classification", ""),
        }
    }


def main(db_url: str, total: int, output: str, seed: int) -> None:
    logger.info("Loading FIRs from database …")
    rows = load_firs(db_url)
    if not rows:
        logger.error("No annotatable FIRs found in the database.")
        sys.exit(1)

    logger.info("Total annotatable FIRs: %d", len(rows))
    sampled = stratified_sample(rows, total, seed=seed)
    logger.info("Sampled %d FIRs across %d districts.", len(sampled),
                len({r.get("district") for r in sampled}))

    with open(output, "w", encoding="utf-8") as fh:
        for row in sampled:
            fh.write(json.dumps(format_for_labelstudio(row), ensure_ascii=False) + "\n")

    logger.info("Gold standard written to %s (%d tasks).", output, len(sampled))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create stratified gold-standard annotation set from ATLAS FIRs."
    )
    parser.add_argument(
        "--db_url",
        default="postgresql://atlas:atlaspass@localhost:5432/atlas_db",
        help="PostgreSQL connection string.",
    )
    parser.add_argument("--total", type=int, default=200, help="Number of FIRs to sample.")
    parser.add_argument("--output", default="gold_standard.jsonl", help="Output file path.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    args = parser.parse_args()
    main(args.db_url, args.total, args.output, args.seed)
