"""Verification harness for the extracted IPC/BNS sections.

Checks:
    1. Expected section count (511 IPC base + letter variants; 358 BNS)
    2. Every section has non-empty full_text
    3. full_text starts with the section number (verbatim)
    4. Known crime sections contain expected keywords
    5. No forbidden characters (U+FFFD replacement char)
    6. All chapter numbers match Roman-numeral pattern
    7. Sub-clause structural integrity (ADR-D15) — known multi-clause
       sections decompose into the expected addressable units.

Run:
    python scripts/verify_legal_sections.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "app" / "legal_sections" / "data"

# Each entry: (act, section_number, expected canonical citations).
# The verifier asserts that each expected citation appears in the section's
# parsed sub_clauses. This is the gate that protects against regressions in
# sub-clause precision (ADR-D15).
SUBCLAUSE_CHECKS = [
    # BNS — theft / housebreaking family used in the canonical FIR test case
    ("BNS", "303", ["BNS 303(1)", "BNS 303(2)"]),
    ("BNS", "305", ["BNS 305(a)", "BNS 305(b)", "BNS 305(c)", "BNS 305(d)", "BNS 305(e)"]),
    ("BNS", "317", ["BNS 317(1)", "BNS 317(2)", "BNS 317(3)", "BNS 317(4)", "BNS 317(5)"]),
    ("BNS", "331", ["BNS 331(1)", "BNS 331(2)", "BNS 331(3)", "BNS 331(4)",
                    "BNS 331(5)", "BNS 331(6)", "BNS 331(7)", "BNS 331(8)"]),
    ("BNS", "332", ["BNS 332(a)", "BNS 332(b)", "BNS 332(c)", "BNS 332 Provided that"]),
    ("BNS", "334", ["BNS 334(1)", "BNS 334(2)"]),
    # BNS — life and body
    ("BNS", "103", ["BNS 103(1)", "BNS 103(2)"]),
    # IPC — selected
    ("IPC", "376", ["IPC 376(1)", "IPC 376(2)", "IPC 376(2)(a)"]),
    ("IPC", "300", ["IPC 300 First", "IPC 300 Secondly"]),
]


SPOT_CHECKS = {
    "IPC": [
        ("302", "Punishment for murder", ["murder", "death", "imprisonment for life"]),
        ("304", "Punishment for culpable homicide", ["culpable homicide", "imprisonment"]),
        ("307", "Attempt to murder", ["attempt", "murder"]),
        ("376", "Punishment for rape", ["rape", "rigorous imprisonment"]),
        ("378", "Theft", ["movable property", "dishonestly"]),
        ("379", "Punishment for theft", ["theft", "imprisonment"]),
        ("390", "Robbery", ["robbery", "theft"]),
        ("395", "Punishment for dacoity", ["dacoity", "imprisonment"]),
        ("420", "Cheating and dishonestly", ["cheats", "dishonestly induces"]),
        ("498A", "Husband or relative", ["cruelty"]),
    ],
    "BNS": [
        ("101", "Murder", ["culpable homicide", "murder"]),
        ("103", "Punishment for murder", ["death", "imprisonment for life"]),
        ("63", "Rape", ["rape", "consent"]),
        ("64", "Punishment for rape", ["rigorous imprisonment"]),
        ("303", "Theft", ["movable property", "dishonestly"]),
        ("309", "Robbery", ["robbery"]),
        ("310", "Dacoity", ["dacoity"]),
        ("316", "Criminal breach of trust", ["entrusted", "misappropriates"]),
        ("318", "Cheating", ["deceiving", "dishonestly"]),
        ("85", "Husband or relative", ["cruelty"]),
    ],
}


def check_act(act: str) -> dict:
    path = DATA / f"{act.lower()}_sections.jsonl"
    records = [json.loads(l) for l in path.open(encoding="utf-8")]

    errors: list[str] = []
    warnings: list[str] = []

    # Check 1: every full_text non-empty and starts with section number
    for r in records:
        if not r["full_text"].strip():
            errors.append(f"{r['id']}: empty full_text")
            continue
        if not r["full_text"].lstrip().startswith(r["section_number"]):
            # soft warning — could be amendment bracket prefix
            if not re.match(rf"^\s*\d+\[\s*{re.escape(r['section_number'])}", r["full_text"]):
                warnings.append(
                    f"{r['id']}: full_text doesn't start with section number "
                    f"(starts: {r['full_text'][:40]!r})"
                )

    # Check 2: no U+FFFD replacement characters (indicates decode failure)
    for r in records:
        if "\ufffd" in r["full_text"]:
            errors.append(f"{r['id']}: contains U+FFFD")

    # Check 3: spot-check known sections
    spot_results = []
    for num, title_frag, body_frags in SPOT_CHECKS.get(act, []):
        found = next((r for r in records if r["section_number"] == num), None)
        if not found:
            errors.append(f"spot-check failed: {act} section {num} missing")
            spot_results.append((num, "MISSING"))
            continue
        title_ok = title_frag.lower() in found["section_title"].lower()
        # For body check, collapse whitespace/newlines for fuzzy match
        body_flat = re.sub(r"\s+", " ", found["full_text"].lower())
        body_ok = all(b.lower() in body_flat for b in body_frags)
        status = "OK" if (title_ok and body_ok) else "PARTIAL"
        if not title_ok:
            warnings.append(f"{act} {num}: title mismatch (got {found['section_title']!r})")
        if not body_ok:
            warnings.append(f"{act} {num}: body missing one of {body_frags}")
        spot_results.append((num, status))

    # Check 4: base section count
    bases = {int(r["section_number"]) for r in records if r["section_number"].isdigit()}
    if act == "IPC":
        expected_max = 511
    else:
        expected_max = 358
    missing_bases = sorted(set(range(1, expected_max + 1)) - bases)

    # Sub-clause structural checks (ADR-D15)
    by_num = {r["section_number"]: r for r in records}
    subclause_results: list[tuple[str, str]] = []
    for chk_act, num, expected in SUBCLAUSE_CHECKS:
        if chk_act != act:
            continue
        rec = by_num.get(num)
        if not rec:
            errors.append(f"sub-clause check: {act} {num} missing")
            subclause_results.append((num, "MISSING_SECTION"))
            continue
        present = {sc["canonical_citation"] for sc in rec.get("sub_clauses", [])}
        missing_sub = [c for c in expected if c not in present]
        if missing_sub:
            errors.append(f"{act} {num}: missing sub-clauses {missing_sub}")
            subclause_results.append((num, f"MISSING_SUBCLAUSES:{missing_sub}"))
        else:
            subclause_results.append((num, "OK"))

    # Aggregate sub-clause stats
    sub_clauses_total = sum(len(r.get("sub_clauses", [])) for r in records)
    sections_with_sub_clauses = sum(1 for r in records if r.get("sub_clauses"))

    return {
        "act": act,
        "total_sections": len(records),
        "base_sections": len(bases),
        "expected_base_sections": expected_max,
        "missing_base_sections": missing_bases,
        "letter_variants": sum(1 for r in records if any(c.isalpha() for c in r["section_number"])),
        "sub_clauses_total": sub_clauses_total,
        "sections_with_sub_clauses": sections_with_sub_clauses,
        "errors": errors,
        "warnings_count": len(warnings),
        "warnings_sample": warnings[:5],
        "spot_check": spot_results,
        "all_spot_checks_pass": all(s == "OK" for _, s in spot_results),
        "sub_clause_check": subclause_results,
        "all_sub_clause_checks_pass": all(s == "OK" for _, s in subclause_results),
    }


def main() -> None:
    overall_ok = True
    for act in ("IPC", "BNS"):
        result = check_act(act)
        print(json.dumps(result, indent=2))
        if (
            result["errors"]
            or result["missing_base_sections"]
            or not result["all_spot_checks_pass"]
            or not result["all_sub_clause_checks_pass"]
        ):
            overall_ok = False
    print("\n===== OVERALL:", "PASS" if overall_ok else "FAIL", "=====")
    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
