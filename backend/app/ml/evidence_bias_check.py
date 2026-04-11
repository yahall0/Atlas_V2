"""Evidence gap bias checker — Sprint 5 BIAS3 checkpoint.

Checks whether gap detection rates vary significantly by district
when crime category is controlled. Flags districts with >15% deviation
from the mean gap rate.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def check_evidence_bias(
    reports: List[Dict[str, Any]],
    threshold: float = 0.15,
) -> Dict[str, Any]:
    """Check for district-level bias in evidence gap detection.

    Parameters
    ----------
    reports : list[dict]
        List of EvidenceGapReport dicts. Each should have
        ``crime_category``, ``total_gaps``, ``total_expected``, and
        the chargesheet's ``district`` key.
    threshold : float
        Maximum allowed deviation from mean gap rate (default 15%).

    Returns
    -------
    dict
        BiasReport with ``flagged`` bool, ``flags`` list, and per-district
        breakdown.
    """
    # Group by (crime_category, district)
    groups: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in reports:
        crime = r.get("crime_category", "unknown")
        district = r.get("district", "unknown")
        total_exp = r.get("total_expected", 0)
        total_gaps = r.get("total_gaps", 0)
        if total_exp > 0:
            gap_rate = total_gaps / total_exp
            groups[crime][district].append(gap_rate)

    flags: List[Dict[str, Any]] = []
    district_breakdown: Dict[str, Any] = {}

    for crime, districts in groups.items():
        # Compute overall mean gap rate for this crime category
        all_rates: List[float] = []
        for rates in districts.values():
            all_rates.extend(rates)

        if not all_rates:
            continue

        mean_rate = sum(all_rates) / len(all_rates)

        for district, rates in districts.items():
            dist_mean = sum(rates) / len(rates)
            deviation = abs(dist_mean - mean_rate)

            key = f"{crime}:{district}"
            district_breakdown[key] = {
                "crime_category": crime,
                "district": district,
                "mean_gap_rate": round(dist_mean, 3),
                "overall_mean": round(mean_rate, 3),
                "deviation": round(deviation, 3),
                "sample_count": len(rates),
                "flagged": deviation > threshold,
            }

            if deviation > threshold and len(rates) >= 3:
                flags.append({
                    "crime_category": crime,
                    "district": district,
                    "deviation": round(deviation, 3),
                    "district_rate": round(dist_mean, 3),
                    "overall_rate": round(mean_rate, 3),
                    "message": (
                        f"District '{district}' shows {deviation:.1%} deviation "
                        f"from mean gap rate for {crime} cases "
                        f"(district: {dist_mean:.1%}, overall: {mean_rate:.1%})."
                    ),
                })

    return {
        "flagged": len(flags) > 0,
        "threshold": threshold,
        "total_reports_analyzed": len(reports),
        "flags": flags,
        "district_breakdown": district_breakdown,
    }
