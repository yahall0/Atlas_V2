"""Unit tests for the chunker."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.legal_sections.chunker import chunk_section, iter_chunks

DATA = Path(__file__).resolve().parents[2] / "app" / "legal_sections" / "data"


def _section(act: str, num: str) -> dict:
    path = DATA / f"{act.lower()}_sections.jsonl"
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        if r["section_number"] == num:
            return r
    raise KeyError(f"{act} {num} not found")


def test_chunker_emits_header_and_subclauses_for_bns_305():
    rec = _section("BNS", "305")
    chunks = chunk_section(rec)
    types = [c.chunk_type for c in chunks]
    assert "header" in types
    assert types.count("sub_clause") == 5  # (a)..(e)
    cits = {c.canonical_citation for c in chunks}
    assert {"BNS 305", "BNS 305(a)", "BNS 305(b)", "BNS 305(c)",
            "BNS 305(d)", "BNS 305(e)"} <= cits


def test_chunker_uses_section_body_when_no_subclauses():
    """A section with no enumerated alternatives gets one section_body chunk."""
    rec = _section("BNS", "114")  # Hurt — definition only
    chunks = chunk_section(rec)
    body_chunks = [c for c in chunks if c.chunk_type == "section_body"]
    sub_chunks = [c for c in chunks if c.chunk_type == "sub_clause"]
    assert len(body_chunks) == 1
    assert len(sub_chunks) == 0


def test_chunk_text_is_verbatim_subclause_text():
    rec = _section("BNS", "305")
    chunks = chunk_section(rec)
    sca = next(c for c in chunks if c.canonical_citation == "BNS 305(a)")
    # The chunk text must be the verbatim sub-clause text — used both for
    # embedding AND as the rationale_quote returned to the IO.
    assert "dwelling" in sca.text
    assert sca.text.startswith("(a)")


def test_chunk_ids_are_globally_unique_within_corpus():
    chunks = list(iter_chunks([
        DATA / "ipc_sections.jsonl",
        DATA / "bns_sections.jsonl",
    ]))
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_id collisions detected"


def test_corpus_chunk_count_in_expected_range():
    chunks = list(iter_chunks([
        DATA / "ipc_sections.jsonl",
        DATA / "bns_sections.jsonl",
    ]))
    # Lower bound: 943 sections × at least 1 header + 1 body each.
    # Upper bound: rough sanity — illustrations/explanations are ~3,000 max.
    assert 1800 <= len(chunks) <= 6000, f"unexpected chunk count: {len(chunks)}"
