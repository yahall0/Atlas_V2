"""Gold-standard ratification workflow.

Lifecycle of a gold-standard FIR entry:

    model_generated_awaiting_sme
              │
              │  (AI curation pass — this module + scripts/curate_gold.py)
              ▼
    ai_curated_pending_sme
              │
              │  (SME panel review — scripts/ratify_gold.py)
              ▼
    sme_ratified
              │
              │  (defect found later in production)
              ▼
    sme_revised  ─or─  withdrawn

Every transition emits an audit-chain entry with the actor, the previous
labels, the new labels, and the diff hash, so the lineage of every gold
record is reconstructible at appeal time.
"""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

GOLD_PATH = Path(__file__).resolve().parent / "data" / "gold_standard.jsonl"
LEDGER_PATH = Path(__file__).resolve().parent / "data" / "ratification_ledger.jsonl"


class RatificationStatus(str, enum.Enum):
    MODEL_GENERATED = "model_generated_awaiting_sme"
    AI_CURATED = "ai_curated_pending_sme"
    SME_RATIFIED = "sme_ratified"
    SME_REVISED = "sme_revised"
    WITHDRAWN = "withdrawn"


class RatificationAction(str, enum.Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"
    DEFER = "defer"


@dataclass
class CitationLabel:
    """One expected citation with a reason and a confidence."""
    citation: str                        # e.g. "BNS 305(a)"
    rationale: str                       # one sentence: why this section applies
    confidence: float = 0.95             # author's confidence in this label


@dataclass
class GoldEntry:
    fir_id: str
    narrative: str
    occurrence_date_iso: str | None
    accused_count: int
    expected_citations: list[str]                # legacy flat list (kept for eval compat)
    expected_labels: list[CitationLabel] = field(default_factory=list)
    rationale_facts: list[str] = field(default_factory=list)
    source: str = ""
    status: str = RatificationStatus.MODEL_GENERATED.value
    sme_ratified_by: str | None = None
    sme_ratified_at: str | None = None
    ai_curated_by: str | None = None
    ai_curated_at: str | None = None
    ai_curator_notes: str | None = None
    schema_version: str = "v2.0"


@dataclass
class RatificationEvent:
    fir_id: str
    actor: str                          # "ai-curator-v1" / "sme:<name>" / "system"
    previous_status: str
    new_status: str
    action: str                          # accept / modify / reject / defer
    previous_labels_hash: str
    new_labels_hash: str
    diff: dict                           # {"added": [...], "removed": [...], "kept": [...]}
    notes: str | None
    timestamp: str


# ---------- Helpers ---------- #


def label_hash(labels: list[str]) -> str:
    canonical = json.dumps(sorted(labels), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def diff_labels(old: list[str], new: list[str]) -> dict:
    old_set, new_set = set(old), set(new)
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
        "kept": sorted(old_set & new_set),
    }


def emit_event(event: RatificationEvent, ledger_path: Path | None = None) -> None:
    path = ledger_path or LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    # Best-effort audit-chain hook
    try:
        from app.audit_chain import append_entry  # type: ignore
        append_entry(
            user_id=None if event.actor.startswith("ai-") or event.actor == "system" else event.actor,
            action=f"GOLD_RATIFIED_{event.action.upper()}",
            resource_type="GOLD_STANDARD_FIR",
            resource_id=event.fir_id,
            details=asdict(event),
        )
    except Exception:
        pass


# ---------- File I/O ---------- #


def load_gold(path: Path | None = None) -> list[dict]:
    p = path or GOLD_PATH
    out: list[dict] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def save_gold(entries: list[dict], path: Path | None = None) -> None:
    p = path or GOLD_PATH
    with p.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def transition(
    entry: dict,
    *,
    new_status: RatificationStatus,
    actor: str,
    new_labels: list[str] | None = None,
    action: RatificationAction = RatificationAction.MODIFY,
    notes: str | None = None,
) -> dict:
    """Apply a status transition to a gold entry, emit an event, return updated entry."""
    old_status = entry.get("status", RatificationStatus.MODEL_GENERATED.value)
    old_labels = list(entry.get("expected_citations", []))
    nl = list(new_labels) if new_labels is not None else old_labels

    event = RatificationEvent(
        fir_id=entry["fir_id"],
        actor=actor,
        previous_status=old_status,
        new_status=new_status.value,
        action=action.value,
        previous_labels_hash=label_hash(old_labels),
        new_labels_hash=label_hash(nl),
        diff=diff_labels(old_labels, nl),
        notes=notes,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    emit_event(event)

    entry["expected_citations"] = nl
    entry["status"] = new_status.value
    if new_status is RatificationStatus.AI_CURATED:
        entry["ai_curated_by"] = actor
        entry["ai_curated_at"] = event.timestamp
        if notes:
            entry["ai_curator_notes"] = notes
    elif new_status is RatificationStatus.SME_RATIFIED:
        entry["sme_ratified_by"] = actor
        entry["sme_ratified_at"] = event.timestamp
    return entry


__all__ = [
    "RatificationStatus", "RatificationAction", "CitationLabel",
    "GoldEntry", "RatificationEvent",
    "label_hash", "diff_labels", "emit_event",
    "load_gold", "save_gold", "transition",
]
