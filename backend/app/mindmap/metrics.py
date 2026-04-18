"""Observability for Chargesheet Mindmap — T53-M9.

Prometheus metrics and structlog event helpers.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

import structlog

try:
    from prometheus_client import Counter, Histogram

    atlas_mindmap_generated_total = Counter(
        "atlas_mindmap_generated_total",
        "Total mindmaps generated",
        ["case_category"],
    )

    atlas_mindmap_generation_duration_seconds = Histogram(
        "atlas_mindmap_generation_duration_seconds",
        "Time to generate a mindmap",
        buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
    )

    atlas_mindmap_node_status_changes_total = Counter(
        "atlas_mindmap_node_status_changes_total",
        "Total node status changes",
        ["from_status", "to_status"],
    )

    atlas_mindmap_hash_chain_violations_total = Counter(
        "atlas_mindmap_hash_chain_violations_total",
        "Hash chain violations detected (alert if >0)",
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

logger = structlog.get_logger(__name__)


# ── Metric helpers ───────────────────────────────────────────────────────────

def record_mindmap_generated(case_category: str) -> None:
    if _PROMETHEUS_AVAILABLE:
        atlas_mindmap_generated_total.labels(case_category=case_category).inc()


@contextmanager
def measure_generation_time() -> Generator[None, None, None]:
    start = time.monotonic()
    yield
    duration = time.monotonic() - start
    if _PROMETHEUS_AVAILABLE:
        atlas_mindmap_generation_duration_seconds.observe(duration)


def record_status_change(from_status: str, to_status: str) -> None:
    if _PROMETHEUS_AVAILABLE:
        atlas_mindmap_node_status_changes_total.labels(
            from_status=from_status, to_status=to_status,
        ).inc()


def record_hash_chain_violation() -> None:
    if _PROMETHEUS_AVAILABLE:
        atlas_mindmap_hash_chain_violations_total.inc()
    logger.error(
        "mindmap.hash_chain_violation",
        event="hash_chain_violation",
        severity="CRITICAL",
    )


# ── Structured log events ───────────────────────────────────────────────────

def log_mindmap_generated(
    fir_id: str, mindmap_id: str, case_category: str, user: str,
) -> None:
    logger.info(
        "mindmap.generated",
        fir_id=fir_id,
        mindmap_id=mindmap_id,
        case_category=case_category,
        user=user,
    )


def log_mindmap_regenerated(
    fir_id: str, mindmap_id: str, justification: str, user: str,
) -> None:
    logger.info(
        "mindmap.regenerated",
        fir_id=fir_id,
        mindmap_id=mindmap_id,
        justification=justification,
        user=user,
    )


def log_node_status_changed(
    node_id: str, new_status: str, user: str,
) -> None:
    logger.info(
        "mindmap.node_status_changed",
        node_id=node_id,
        new_status=new_status,
        user=user,
    )


def log_custom_node_added(
    mindmap_id: str, node_id: str, user: str,
) -> None:
    logger.info(
        "mindmap.custom_node_added",
        mindmap_id=mindmap_id,
        node_id=node_id,
        user=user,
    )
