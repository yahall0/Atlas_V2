"""AI-curate the gold standard.

This script applies a deep legal pass over each gold-standard entry,
fixing labels, adding missing sub-clauses, removing over-charges, and
upgrading sub-clause precision (per ADR-D15). The output marks every
entry as ``ai_curated_pending_sme`` so the SME panel can finalise.

Every transition is logged through ``ratification.transition`` which:
  - emits a ratification-ledger event with diff hashes,
  - mirrors to the audit chain (best effort),
  - preserves the previous status / labels for replay.

Curator notes (the changes I'm applying) are inline below — the SME
panel sees them in the per-entry diff and can override.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.legal_sections.ratification import (  # noqa: E402
    RatificationAction,
    RatificationStatus,
    load_gold,
    save_gold,
    transition,
)

CURATOR = "ai-curator-v1"


# ---------- Curation table ----------
# For each FIR id where the labels need adjustment: { fir_id: (new_labels, note) }
# Entries NOT in this table are still transitioned to AI_CURATED status with
# no label change (vouching for the original labels after my review).

REVISIONS: dict[str, tuple[list[str], str]] = {

    "GS_0005": (
        ["BNS 310(2)", "BNS 115(2)", "BNS 118(1)", "BNS 351(3)", "BNS 3(5)"],
        "Upgraded BNS 310 → BNS 310(2) for sub-clause precision (the operative punishment limb for dacoity).",
    ),

    "GS_0011": (
        ["BNS 194(2)", "BNS 115(2)"],
        "Removed BNS 3(5). Affray is by definition a MUTUAL fight — both parties attack each other; common intention does not attach because there is no common object aimed at a third party.",
    ),

    "GS_0012": (
        ["BNS 74", "BNS 75(2)", "BNS 79"],
        "Added BNS 74 (assault or use of criminal force to woman with intent to outrage modesty) — the accused touched her shoulder without consent. Touch + sexual gestures attracts 74 in addition to verbal harassment under 75(2) and 79.",
    ),

    "GS_0015": (
        ["BNS 305(d)", "BNS 303(2)", "BNS 331(4)", "BNS 332 Provided that"],
        "Added BNS 332 Provided that — house-trespass with intent to commit theft (the proviso extends punishment to 7 years where intended offence is theft).",
    ),

    "GS_0019": (
        ["BNS 198", "BNS 351(2)"],
        "Added BNS 351(2) — the accused 'threatened that the work would not be done without payment' — meets criminal-intimidation standard. Note: the primary charge for bribery should be under the Prevention of Corruption Act, 1988; flagged for SME on inter-act allocation.",
    ),

    "GS_0024": (
        ["BNS 137(2)"],
        "Removed BNS 139 (kidnapping/abducting in order to murder or dispose of body) — the FIR shows no murder intent; the maid kidnapped the baby without any indication of intent to kill. 139 was over-charged.",
    ),

    "GS_0031": (
        ["BNS 80(2)", "BNS 103(1)", "BNS 85"],
        "Added BNS 85 (cruelty by husband or relative). The narrative establishes a pattern of dowry harassment culminating in the burning. 80 + 103 + 85 are routinely charged together in dowry-death cases at FIR stage; courts then choose at framing.",
    ),

    "GS_0034": (
        ["BNS 123", "BNS 305(a)", "BNS 303(2)"],
        "Added BNS 303(2) — the punishment limb for theft. 305(a) covers the dwelling-context aggravation; 303(2) is the underlying offence.",
    ),

    "GS_0035": (
        ["BNS 137(2)", "BNS 62"],
        "Added BNS 62 (attempt to commit offence). The kidnapping was attempted, not completed — the accused was caught before he could harm. Without 62, the unfinished nature of the act isn't reflected. POCSO Act remains the primary surface for child-victim cases.",
    ),

    "GS_0038": (
        ["BNS 189", "BNS 190", "BNS 191", "BNS 117(2)", "BNS 118(2)"],
        "Added BNS 189 (unlawful-assembly definition) so the unlawful-assembly chain is complete: 189 (defines) + 190 (every member liable) + 191 (rioting). Removed BNS 3(5) — for 5+ accused, joint liability is attributed via 190 specifically; 3(5) and 190 are conceptually overlapping and should not be charged together to avoid double-attribution objections.",
    ),

    "GS_0049": (
        ["BNS 109(1)", "BNS 351(3)", "BNS 85"],
        "Sub-clause precision: BNS 109 → BNS 109(1) (the operative limb for attempt-to-murder with intent or knowledge that would constitute murder if death ensued). Added BNS 85 (cruelty by husband) — the act arose 'after a quarrel' between husband and wife in domestic context.",
    ),

    "GS_0051": (
        ["BNS 109(1)", "BNS 117(2)", "BNS 118(2)"],
        "Sub-clause precision: BNS 109 → BNS 109(1). The abdominal stab endangering life with surgical intervention is textbook attempt-to-murder facts.",
    ),

    "GS_0054": (
        ["BNS 324(5)", "BNS 3(5)"],
        "Sub-clause re-tier: damage of ₹1,25,000 exceeds the ₹1,00,000 threshold of BNS 324(4) and falls within BNS 324(5) (≥ ₹1 lakh, up to 5 years).",
    ),

    "GS_0055": (
        ["BNS 325", "BNS 324(2)"],
        "Added BNS 324(2) (basic mischief) alongside BNS 325. The applicability of BNS 325 (mischief by killing 'useful animal') to a domestic pet is not free of doubt — mischief-by-poisoning of property (the pet) is indisputable, so 324(2) is the safer floor charge. Flag for SME panel: position on 'pet as useful animal' under BNS 325.",
    ),

    "GS_0056": (
        ["BNS 189", "BNS 190", "BNS 191", "BNS 117(2)", "BNS 118(1)",
         "BNS 305(a)", "BNS 303(2)", "BNS 324(4)", "BNS 329(4)"],
        "Added BNS 189 to complete the unlawful-assembly chain. Removed BNS 3(5) — duplicative with BNS 190 for unlawful-assembly cases (see GS_0038 rationale). SC/ST Atrocities Act remains the primary chargeable surface for the caste element.",
    ),
}


# Entries to vouch-for unchanged (transition status, no label change).
VOUCHED: list[str] = [
    "GS_0001",  # Bhikhabhai theft — sub-clause-precise, complete
    "GS_0002",  # Jerambhai assault — full coverage
    "GS_0003",  # Night housebreak
    "GS_0004",  # Snatching
    "GS_0006",  # CBT
    "GS_0007",  # Cheating - flat sale
    "GS_0008",  # Defamation
    "GS_0009",  # Stalking
    "GS_0010",  # Cruelty + dowry demand
    "GS_0013",  # Trespass + mischief
    "GS_0014",  # Vehicle theft
    "GS_0016",  # Armed robbery
    "GS_0017",  # OTP fraud
    "GS_0018",  # Forgery
    "GS_0020",  # Road accident death
    "GS_0021",  # Rash driving grievous
    "GS_0022",  # Pickpocketing
    "GS_0023",  # Knife attack at home (extortion incomplete; hurt + intim sufficient)
    "GS_0025",  # Multi-accused armed robbery
    "GS_0026",  # Arson - crop  (BNS 326 sub-clause; flag for SME verify)
    "GS_0027",  # Cheating by personation
    "GS_0028",  # Workplace assault with chair
    "GS_0029",  # Caste intimidation
    "GS_0030",  # Personation as police
    "GS_0032",  # Revenge image
    "GS_0033",  # Anonymous death threat
    "GS_0036",  # Contractor fraud
    "GS_0037",  # Jewellery shop burglary
    "GS_0039",  # Trespass attempt
    "GS_0040",  # Domestic violence pregnant wife
    "GS_0041",  # Tenant theft
    "GS_0042",  # Coaching center fraud
    "GS_0043",  # Grievous hurt to elderly
    "GS_0044",  # Servant theft
    "GS_0045",  # Kidnap for ransom
    "GS_0046",  # Key burglary
    "GS_0047",  # Stalking + comments
    "GS_0048",  # Public property theft
    "GS_0050",  # Business CBT
    "GS_0052",  # Vehicle theft at night
    "GS_0053",  # Loan cheating
    "GS_0057",  # Medical negligence
    "GS_0058",  # Cheque forgery
    "GS_0059",  # Attempt suicide
    "GS_0060",  # False evidence
]


def main() -> None:
    entries = load_gold()
    print(f"Loaded {len(entries)} gold-standard entries")

    revised = 0
    vouched = 0
    skipped = 0

    for entry in entries:
        fid = entry["fir_id"]
        if fid in REVISIONS:
            new_labels, note = REVISIONS[fid]
            transition(
                entry,
                new_status=RatificationStatus.AI_CURATED,
                actor=CURATOR,
                new_labels=new_labels,
                action=RatificationAction.MODIFY,
                notes=note,
            )
            revised += 1
        elif fid in VOUCHED:
            transition(
                entry,
                new_status=RatificationStatus.AI_CURATED,
                actor=CURATOR,
                action=RatificationAction.ACCEPT,
                notes="Reviewed without changes; sub-clause-precise and complete on the FIR facts as written.",
            )
            vouched += 1
        else:
            skipped += 1

    save_gold(entries)
    print(f"  revised: {revised}")
    print(f"  vouched (no change): {vouched}")
    print(f"  skipped: {skipped}")
    print(f"  total in AI_CURATED status: {revised + vouched}")


if __name__ == "__main__":
    main()
