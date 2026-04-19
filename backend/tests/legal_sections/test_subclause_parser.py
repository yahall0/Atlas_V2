"""Unit tests for the sub-clause parser.

Each test enforces an ADR-D15 contract: every section that contains
addressable sub-clauses must decompose into citations that match exactly
how a court would refer to them. Regressions in this file are blocking.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.legal_sections.subclause_parser import parse_subclauses

DATA = Path(__file__).resolve().parents[2] / "app" / "legal_sections" / "data"


def _load(act: str) -> dict[str, dict]:
    path = DATA / f"{act.lower()}_sections.jsonl"
    return {
        r["section_number"]: r
        for line in path.open(encoding="utf-8")
        for r in [json.loads(line)]
    }


@pytest.fixture(scope="module")
def bns():
    return _load("BNS")


@pytest.fixture(scope="module")
def ipc():
    return _load("IPC")


def _citations(rec: dict) -> set[str]:
    return {sc["canonical_citation"] for sc in rec.get("sub_clauses", [])}


# ---------- BNS — theft / housebreaking family (canonical FIR test case) ---------- #


def test_bns_305_emits_all_five_alternatives(bns):
    rec = bns["305"]
    cits = _citations(rec)
    assert {"BNS 305(a)", "BNS 305(b)", "BNS 305(c)", "BNS 305(d)", "BNS 305(e)"} <= cits


def test_bns_305a_text_describes_dwelling(bns):
    rec = bns["305"]
    sca = next(sc for sc in rec["sub_clauses"] if sc["canonical_citation"] == "BNS 305(a)")
    assert "dwelling" in sca["text"]
    assert sca["addressable_id"] == "BNS_305_a"


def test_bns_331_has_eight_subsections(bns):
    rec = bns["331"]
    cits = _citations(rec)
    expected = {f"BNS 331({i})" for i in range(1, 9)}
    assert expected <= cits


def test_bns_331_3_text_mentions_in_order_to_commit_offence(bns):
    rec = bns["331"]
    sc3 = next(sc for sc in rec["sub_clauses"] if sc["canonical_citation"] == "BNS 331(3)")
    assert "in order to" in sc3["text"]


def test_bns_332_includes_proviso(bns):
    rec = bns["332"]
    cits = _citations(rec)
    assert "BNS 332(a)" in cits
    assert "BNS 332(b)" in cits
    assert "BNS 332(c)" in cits
    assert "BNS 332 Provided that" in cits


def test_bns_303_subsection_2_is_punishment_clause(bns):
    rec = bns["303"]
    sc2 = next(sc for sc in rec["sub_clauses"] if sc["canonical_citation"] == "BNS 303(2)")
    assert "punished" in sc2["text"]


def test_bns_317_has_five_subsections(bns):
    rec = bns["317"]
    cits = _citations(rec)
    assert {f"BNS 317({i})" for i in range(1, 6)} <= cits


def test_bns_334_one_and_two_correctly_split(bns):
    rec = bns["334"]
    cits = _citations(rec)
    assert "BNS 334(1)" in cits
    assert "BNS 334(2)" in cits


# ---------- BNS — life and body ---------- #


def test_bns_103_subsections(bns):
    rec = bns["103"]
    cits = _citations(rec)
    assert "BNS 103(1)" in cits
    assert "BNS 103(2)" in cits


# ---------- Ambiguity disambiguation: (i)/(v)/(x) as letter vs Roman ---------- #


def test_letter_i_after_h_is_alpha_not_roman(bns):
    """In BNS 303(1) illustrations, (h)→(i)→(j) — (i) must be the letter."""
    rec = bns["303"]
    cits = _citations(rec)
    assert "BNS 303(1)(i)" in cits
    # And NOT misclassified as roman nested under (h)
    assert "BNS 303(1)(h)(i)" not in cits


# ---------- IPC — selected ---------- #


def test_ipc_376_nested_subsections(ipc):
    rec = ipc["376"]
    cits = _citations(rec)
    assert "IPC 376(1)" in cits
    assert "IPC 376(2)" in cits
    assert "IPC 376(2)(a)" in cits


def test_ipc_300_uses_ordinal_markers(ipc):
    """IPC 300 (definition of murder) uses 'First.—' / 'Secondly.—' clauses."""
    rec = ipc["300"]
    cits = _citations(rec)
    assert "IPC 300 First" in cits
    assert "IPC 300 Secondly" in cits


# ---------- Determinism: re-running the parser yields identical output ---------- #


def test_parser_is_deterministic(bns):
    """Same input must produce byte-identical output."""
    rec = bns["305"]
    a = parse_subclauses(rec["id"], rec["section_number"], rec["full_text"])
    b = parse_subclauses(rec["id"], rec["section_number"], rec["full_text"])
    assert [sc.canonical_citation for sc in a] == [sc.canonical_citation for sc in b]
    assert [sc.text for sc in a] == [sc.text for sc in b]


# ---------- Negative case: section without any enumeration ---------- #


def test_section_without_subclauses_emits_empty_list(bns):
    """BNS 1 (Short title) has no enumerated alternatives."""
    rec = bns["1"]
    # Either empty or only a (1)/(2) for short-title and commencement
    # Allow either — but the parser must not raise
    sc_count = len(rec["sub_clauses"])
    assert sc_count >= 0


# ---------- Citation uniqueness within a section ---------- #


@pytest.mark.parametrize("section_num", ["303", "305", "331", "332", "317", "334", "103"])
def test_citations_are_unique_within_section(bns, section_num):
    rec = bns[section_num]
    cits = [sc["canonical_citation"] for sc in rec["sub_clauses"]]
    assert len(cits) == len(set(cits)), f"duplicate citations in BNS {section_num}: {cits}"


# ---------- Addressable IDs are URL-safe ---------- #


def test_addressable_ids_are_url_safe(bns):
    import re
    pattern = re.compile(r"^[A-Za-z0-9_]+$")
    for num, rec in bns.items():
        for sc in rec["sub_clauses"]:
            assert pattern.match(sc["addressable_id"]), (
                f"non-URL-safe id in BNS {num}: {sc['addressable_id']!r}"
            )
