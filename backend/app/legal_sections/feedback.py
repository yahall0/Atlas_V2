"""Feedback capture for the section recommender.

Every IO/court action on a recommendation entry is captured here. Two
sinks:

* **Audit chain** — append-only, hash-linked record for compliance
  (per ADR-D15 §5 and the platform-wide audit-chain contract).
* **Feedback ledger** — a denormalised JSONL store keyed by
  ``(addressable_id, action)`` used as a re-ranking signal in Phase 2.

The audit chain is the source of truth; the feedback ledger is a derived,
re-buildable index. Either can be lost without losing the other.
"""
from __future__ import annotations

import enum
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent / "data" / "feedback_ledger.jsonl"


class FeedbackAction(str, enum.Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    DISMISS = "dismiss"
    REQUEST_MORE_INFO = "request_more_info"


@dataclass
class FeedbackEntry:
    fir_id: str
    addressable_id: str
    action: str
    notes: str | None
    user_id: str | None
    timestamp: str          # ISO-8601 UTC
    audit_action: str       # canonical audit-chain action code


# ---------- Audit chain hook ---------- #


def _emit_audit(entry: FeedbackEntry) -> None:
    """Forward to the platform audit-chain.

    Imported lazily so this module remains usable in tests / scripts that
    don't have the full backend wired (e.g. the eval harness).
    """
    try:
        from app.audit_chain import append_entry  # type: ignore
    except ImportError:
        return  # graceful in test envs
    try:
        append_entry(
            user_id=entry.user_id,
            action=entry.audit_action,
            resource_type="LEGAL_SECTION_RECOMMENDATION",
            resource_id=f"{entry.fir_id}:{entry.addressable_id}",
            details={
                "addressable_id": entry.addressable_id,
                "fir_id": entry.fir_id,
                "feedback_action": entry.action,
                "notes": entry.notes,
            },
        )
    except Exception as exc:                                  # pragma: no cover
        # Never let audit failure block the feedback path; the operator
        # action is still recorded in the ledger and can be replayed.
        import logging
        logging.getLogger(__name__).exception("audit_chain.emit_failed", extra={"exc": str(exc)})


def _audit_action_code(action: FeedbackAction) -> str:
    return {
        FeedbackAction.ACCEPT: "RECOMMENDATION_ACCEPTED",
        FeedbackAction.MODIFY: "RECOMMENDATION_MODIFIED",
        FeedbackAction.DISMISS: "RECOMMENDATION_DISMISSED",
        FeedbackAction.REQUEST_MORE_INFO: "RECOMMENDATION_INFO_REQUESTED",
    }[action]


# ---------- Public API ---------- #


def record_feedback(
    *,
    fir_id: str,
    addressable_id: str,
    action: FeedbackAction,
    notes: str | None = None,
    user_id: str | None = None,
    timestamp: datetime | None = None,
    ledger_path: Path | None = None,
) -> FeedbackEntry:
    """Record one feedback action.

    Side effects:
        - Append a JSON line to the feedback ledger.
        - Emit an audit-chain entry (best-effort).

    Returns the persisted entry for the caller to echo back to the IO.
    """
    ts = timestamp or datetime.now(timezone.utc)
    entry = FeedbackEntry(
        fir_id=fir_id,
        addressable_id=addressable_id,
        action=action.value if isinstance(action, FeedbackAction) else str(action),
        notes=notes,
        user_id=user_id,
        timestamp=ts.isoformat(),
        audit_action=_audit_action_code(FeedbackAction(action)),
    )
    path = ledger_path or LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
    _emit_audit(entry)
    return entry


def load_signals(ledger_path: Path | None = None) -> dict[str, dict[str, int]]:
    """Aggregate the ledger into per-addressable-id action counts.

    Used by the re-ranker as a prior:
        accept_weight = log(1 + accept_count) − log(1 + dismiss_count)
    """
    path = ledger_path or LEDGER_PATH
    out: dict[str, dict[str, int]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts = out.setdefault(e["addressable_id"], {})
            counts[e["action"]] = counts.get(e["action"], 0) + 1
    return out


__all__ = [
    "FeedbackAction",
    "FeedbackEntry",
    "record_feedback",
    "load_signals",
    "LEDGER_PATH",
]
