"""Phase 2 smoke tests — reranker, feedback, route wiring, acts registry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.legal_sections.acts import all_acts, get, ingested_acts
from backend.app.legal_sections.feedback import (
    FeedbackAction,
    load_signals,
    record_feedback,
)
from backend.app.legal_sections.reranker import DevReranker, get_reranker
from backend.app.legal_sections.retriever import RetrievedChunk
from backend.app.legal_sections.chunker import Chunk


def _chunk(text: str, citation: str = "BNS 999", chunk_id: str | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id or f"test__{citation}",
        section_id="BNS_999",
        act="BNS",
        section_number="999",
        section_title="Test",
        chapter_number=None,
        chapter_title=None,
        chunk_type="sub_clause",
        chunk_index=0,
        text=text,
        canonical_citation=citation,
        addressable_id="BNS_999",
        sub_clause_label=None,
    )


# ---------- Reranker ---------- #


def test_dev_reranker_promotes_token_overlap():
    candidates = [
        RetrievedChunk(chunk=_chunk("about the weather today", "BNS 1", "c1"), score=0.5),
        RetrievedChunk(chunk=_chunk("theft of mobile phone from a person", "BNS 2", "c2"), score=0.4),
    ]
    reranked = DevReranker(alpha=0.5).rerank("theft of mobile phone", candidates, k=2)
    assert reranked[0].chunk.canonical_citation == "BNS 2"


def test_get_reranker_returns_dev_by_default():
    r = get_reranker()
    assert r.name.startswith("dev")


# ---------- Feedback ---------- #


def test_record_feedback_writes_ledger(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    record_feedback(
        fir_id="FIR-1",
        addressable_id="BNS_305_a",
        action=FeedbackAction.ACCEPT,
        notes="confirmed by SHO",
        user_id="user-uuid",
        ledger_path=ledger,
    )
    record_feedback(
        fir_id="FIR-1",
        addressable_id="BNS_305_a",
        action=FeedbackAction.ACCEPT,
        ledger_path=ledger,
    )
    record_feedback(
        fir_id="FIR-2",
        addressable_id="BNS_117_2",
        action=FeedbackAction.DISMISS,
        ledger_path=ledger,
    )

    signals = load_signals(ledger)
    assert signals["BNS_305_a"]["accept"] == 2
    assert signals["BNS_117_2"]["dismiss"] == 1


def test_record_feedback_rejects_unknown_action(tmp_path: Path):
    with pytest.raises(ValueError):
        record_feedback(
            fir_id="x",
            addressable_id="BNS_1",
            action=FeedbackAction("nope"),  # type: ignore[arg-type]
            ledger_path=tmp_path / "l.jsonl",
        )


# ---------- Route wiring ---------- #


def test_route_module_imports_cleanly():
    """Smoke test — module-level import is what FastAPI does at boot."""
    from backend.app.legal_sections.routes import router
    assert router is not None
    paths = {route.path for route in router.routes}  # type: ignore[attr-defined]
    assert "/firs/{fir_id}/recommend-sections" in paths


# ---------- Acts registry ---------- #


def test_ipc_and_bns_are_ingested():
    ingested = {a.code for a in ingested_acts()}
    assert {"IPC", "BNS"} <= ingested


def test_special_acts_are_scaffolded():
    """The framework lists the special acts so adding them is mechanical."""
    expected = {"BNSS", "BSA", "NDPS", "POCSO", "IT_ACT", "MV_ACT",
                "DOWRY", "ARMS", "SCST", "DV"}
    have = {a.code for a in all_acts()}
    assert expected <= have, f"missing scaffolded acts: {expected - have}"


def test_act_lookup_by_code():
    bns = get("BNS")
    assert bns is not None
    assert bns.short_name == "BNS"
    assert bns.commencement is not None
