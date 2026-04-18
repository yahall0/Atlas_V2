"""Observability for Chargesheet Gap Analysis — T56-E13/E14."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

import structlog

try:
    from prometheus_client import Counter, Histogram

    atlas_cs_gap_reports_total = Counter(
        "atlas_chargesheet_gap_reports_total",
        "Total gap reports generated",
        ["case_category"],
    )
    atlas_cs_gap_report_duration = Histogram(
        "atlas_chargesheet_gap_report_duration_seconds",
        "Time to generate a gap report",
        buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0],
    )
    atlas_cs_gaps_by_severity = Counter(
        "atlas_chargesheet_gaps_by_severity",
        "Gaps created by severity and source",
        ["severity", "source"],
    )
    atlas_cs_gap_actions_total = Counter(
        "atlas_chargesheet_gap_actions_total",
        "Gap actions taken",
        ["action", "category"],
    )
    atlas_cs_suggestions_applied = Counter(
        "atlas_chargesheet_suggestions_applied_total",
        "Suggestions applied to chargesheets",
    )
    atlas_cs_exports_total = Counter(
        "atlas_chargesheet_exports_total",
        "Chargesheet exports generated",
        ["export_type"],
    )
    _PROM = True
except ImportError:
    _PROM = False

logger = structlog.get_logger(__name__)


def record_report_generated(case_category: str, gap_count: int, duration_s: float) -> None:
    if _PROM:
        atlas_cs_gap_reports_total.labels(case_category=case_category).inc()
        atlas_cs_gap_report_duration.observe(duration_s)


def record_gaps_created(gaps: list) -> None:
    if not _PROM:
        return
    for g in gaps:
        atlas_cs_gaps_by_severity.labels(
            severity=g.get("severity", "medium"),
            source=g.get("source", "unknown"),
        ).inc()


def record_action(action: str, category: str) -> None:
    if _PROM:
        atlas_cs_gap_actions_total.labels(action=action, category=category).inc()


def record_suggestion_applied() -> None:
    if _PROM:
        atlas_cs_suggestions_applied.inc()


def record_export(export_type: str) -> None:
    if _PROM:
        atlas_cs_exports_total.labels(export_type=export_type).inc()


# ── Structured log events ───────────────────────────────────────────────────

def log_report_generated(cs_id: str, report_id: str, gap_count: int, user: str, sources: list) -> None:
    logger.info("chargesheet.gap_report_generated", chargesheet_id=cs_id,
                report_id=report_id, gap_count=gap_count, user=user,
                sources=sources)


def log_report_regenerated(cs_id: str, report_id: str, justification: str, user: str) -> None:
    logger.info("chargesheet.gap_report_regenerated", chargesheet_id=cs_id,
                report_id=report_id, justification=justification, user=user)


def log_action_taken(gap_id: str, action: str, category: str, severity: str, user: str) -> None:
    logger.info("chargesheet.gap_action_taken", gap_id=gap_id, action=action,
                category=category, severity=severity, user=user)


def log_suggestion_applied(gap_id: str, cs_id: str, user: str) -> None:
    logger.info("chargesheet.suggestion_applied", gap_id=gap_id,
                chargesheet_id=cs_id, user=user)


def log_exported(cs_id: str, export_type: str, user: str) -> None:
    logger.info("chargesheet.exported", chargesheet_id=cs_id,
                export_type=export_type, user=user)


def log_hash_chain_violation(gap_id: str) -> None:
    logger.error("chargesheet.hash_chain_violation", gap_id=gap_id,
                 severity="CRITICAL")
