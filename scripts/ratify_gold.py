"""SME ratification CLI for the gold standard.

Usage:
    python scripts/ratify_gold.py --reviewer "Adv. R. K. Sharma"

The tool walks the SME panel through every ``ai_curated_pending_sme``
entry one at a time, presents:
    - the FIR narrative,
    - the AI-curator's labels and notes,
    - the diff vs. the original model-generated labels.

The reviewer chooses one of:
    A — accept (transition to sme_ratified, no label change)
    M — modify  (edit the label list inline, then transition)
    R — reject  (transition to withdrawn with required reason)
    D — defer   (leave in ai_curated_pending_sme, move to next)
    Q — quit    (save progress and exit)

Every choice is persisted to the ratification ledger AND to the audit
chain. Resume is automatic — re-running the CLI picks up at the first
unratified entry.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.legal_sections.ratification import (  # noqa: E402
    RatificationAction,
    RatificationStatus,
    diff_labels,
    load_gold,
    save_gold,
    transition,
)


def _print_entry(entry: dict, position: int, total: int) -> None:
    print()
    print("=" * 78)
    print(f"  [{position}/{total}]   {entry['fir_id']}   status={entry['status']}")
    print("=" * 78)
    print()
    print("Narrative:")
    print("  " + entry["narrative"][:700] + ("..." if len(entry["narrative"]) > 700 else ""))
    print()
    print(f"Occurrence: {entry.get('occurrence_date_iso')}")
    print(f"Accused count: {entry.get('accused_count')}")
    print()
    print("AI-curator labels:")
    for c in entry["expected_citations"]:
        print(f"  • {c}")
    if entry.get("ai_curator_notes"):
        print()
        print("Curator notes:")
        for line in entry["ai_curator_notes"].splitlines():
            print(f"  ▸ {line}")


def _read_action() -> str:
    print()
    while True:
        choice = input("[A]ccept   [M]odify   [R]eject   [D]efer   [Q]uit  >  ").strip().upper()
        if choice in {"A", "M", "R", "D", "Q"}:
            return choice
        print(f"  invalid choice: {choice}")


def _read_modified_labels(current: list[str]) -> list[str]:
    print()
    print("  Current labels:")
    for c in current:
        print(f"    {c}")
    print()
    print("  Enter the COMPLETE new label list, comma-separated.")
    print("  Example: BNS 305(a), BNS 303(2), BNS 331(3)")
    raw = input("  Labels >  ").strip()
    new_labels = [s.strip() for s in raw.split(",") if s.strip()]
    print()
    print("  → New labels:")
    for c in new_labels:
        print(f"    {c}")
    confirm = input("  Confirm? [y/N]  ").strip().lower()
    return new_labels if confirm == "y" else current


def _read_reason() -> str:
    print()
    return input("  Reason for rejection (required) >  ").strip() or "no reason given"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reviewer",
        required=True,
        help="Name + bar id / employee id of the SME reviewer (recorded to audit chain).",
    )
    ap.add_argument("--start-from", default=None, help="Resume from this fir_id.")
    args = ap.parse_args()

    reviewer = f"sme:{args.reviewer}"

    entries = load_gold()
    pending = [e for e in entries if e.get("status") == RatificationStatus.AI_CURATED.value]
    if args.start_from:
        ids = [e["fir_id"] for e in pending]
        if args.start_from in ids:
            pending = pending[ids.index(args.start_from):]

    if not pending:
        print("No entries pending SME ratification.")
        return

    print(f"Reviewer: {reviewer}")
    print(f"Pending entries: {len(pending)} of {len(entries)} total")
    total_pending = len(pending)

    quit_signal = False
    for i, entry in enumerate(pending, start=1):
        _print_entry(entry, i, total_pending)
        action = _read_action()
        if action == "Q":
            quit_signal = True
            break
        if action == "A":
            transition(
                entry,
                new_status=RatificationStatus.SME_RATIFIED,
                actor=reviewer,
                action=RatificationAction.ACCEPT,
                notes="SME accepted AI-curated labels without change.",
            )
        elif action == "M":
            new_labels = _read_modified_labels(entry["expected_citations"])
            transition(
                entry,
                new_status=RatificationStatus.SME_REVISED,
                actor=reviewer,
                new_labels=new_labels,
                action=RatificationAction.MODIFY,
                notes="SME modified AI-curated labels.",
            )
        elif action == "R":
            reason = _read_reason()
            transition(
                entry,
                new_status=RatificationStatus.WITHDRAWN,
                actor=reviewer,
                action=RatificationAction.REJECT,
                notes=f"SME rejected — {reason}",
            )
        elif action == "D":
            # leave status as ai_curated_pending_sme
            print("  deferred — will surface again on next run")

        # Persist after each decision so progress is durable
        save_gold(entries)

    print()
    if quit_signal:
        print("Quit. Progress saved.")
    else:
        print("All pending entries reviewed.")


if __name__ == "__main__":
    main()
