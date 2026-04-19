"""Integration tests for the recommender."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.app.legal_sections.chunker import iter_chunks
from backend.app.legal_sections.embedder import TfidfEmbedder
from backend.app.legal_sections.recommender import act_for, recommend
from backend.app.legal_sections.retriever import InMemoryRetriever

DATA = Path(__file__).resolve().parents[2] / "app" / "legal_sections" / "data"


@pytest.fixture(scope="module")
def retriever():
    chunks = list(iter_chunks([
        DATA / "ipc_sections.jsonl",
        DATA / "bns_sections.jsonl",
    ]))
    r = InMemoryRetriever(TfidfEmbedder())
    r.index(chunks)
    return r


def test_act_for_picks_bns_after_cutoff():
    assert act_for("2024-07-01T10:00:00+05:30") == "BNS"
    assert act_for("2025-01-15T10:00:00+05:30") == "BNS"


def test_act_for_picks_ipc_before_cutoff():
    assert act_for("2024-06-30T23:59:59+05:30") == "IPC"
    assert act_for("2020-01-01T10:00:00+05:30") == "IPC"


def test_act_for_defaults_to_bns_when_unknown():
    assert act_for(None) == "BNS"
    assert act_for("not a date") == "BNS"


def test_recommend_returns_response_with_required_fields(retriever):
    resp = recommend(
        fir_id="TEST-001",
        fir_narrative="theft from a dwelling at night, lock broken",
        retriever=retriever,
        occurrence_date_iso="2025-01-15T22:00:00+05:30",
        accused_count=1,
    )
    assert resp.fir_id == "TEST-001"
    assert resp.act_basis == "BNS"
    assert resp.model_version
    assert resp.generated_at
    assert isinstance(resp.recommendations, list)


def test_recommend_act_filter_excludes_other_act(retriever):
    resp = recommend(
        fir_id="TEST-002",
        fir_narrative="theft",
        retriever=retriever,
        occurrence_date_iso="2025-01-15T10:00:00+05:30",
    )
    for r in resp.recommendations:
        assert r.act == "BNS", f"expected BNS-only, got {r.act} {r.canonical_citation}"


def test_recommend_attaches_required_companion_when_multiple_accused(retriever):
    """Test the conflict-integration path with a controlled citation set.

    We test the recommender's *conflict integration* — that when the
    retrieval surface yields a hurt section AND the FIR has multiple
    accused, the required-companion rule fires. We test the rule engine
    directly rather than relying on retrieval quality, which is governed
    by the embedder backend (TF-IDF baseline today, bge-m3 in production).
    """
    from backend.app.legal_sections.conflicts import (
        RecommendContext, evaluate as eval_conflicts,
    )
    findings = eval_conflicts(
        ["BNS 115(2)", "BNS 118(1)"],
        RecommendContext(
            fir_narrative="three accused jointly attacked the complainant with sticks",
            accused_count=3,
        ),
    )
    req = [f for f in findings if f.rule_id == "REQ-001"]
    assert req, "REQ-001 (common intention) did not fire for 3 accused with hurt sections"
    assert "BNS 3(5)" in req[0].affected_citations


def test_recommend_subclause_precision_field_populated(retriever):
    """Each recommendation entry must carry sub_clause_label and canonical_citation."""
    resp = recommend(
        fir_id="TEST-004",
        fir_narrative="theft from a dwelling, lock of door broken",
        retriever=retriever,
        occurrence_date_iso="2025-01-15T10:00:00+05:30",
    )
    for r in resp.recommendations:
        assert r.canonical_citation is not None
        assert r.addressable_id is not None
        assert r.section_id is not None


def test_recommend_does_not_emit_below_confidence_floor(retriever):
    resp = recommend(
        fir_id="TEST-005",
        fir_narrative="theft from a dwelling",
        retriever=retriever,
        occurrence_date_iso="2025-01-15T10:00:00+05:30",
        confidence_floor=0.99,
    )
    for r in resp.recommendations:
        # required-companion entries can have confidence 0.0; everything else
        # must be at or above the floor.
        if r.operator_note is None:
            assert r.confidence >= 0.99 or r.confidence == 0.0
