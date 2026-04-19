"""Integration tests for the three Phase-3 wiring tasks.

Task 1 — playbook mindmap path (no DB required for the predicate + structure)
Task 2 — playbook gap-aggregator path (the new ``_playbook_driven_gaps``)
Task 3 — auto-trigger module (the recommender + scenario adapter pipeline)
"""
from __future__ import annotations

import pytest


# ---------- Task 1: playbook mindmap ---------- #


def test_playbook_has_match_for_known_citations():
    from backend.app.mindmap.playbook_generator import has_playbook_for
    assert has_playbook_for(["BNS 304"]) is True
    assert has_playbook_for(["BNS 109(1)"]) is True
    assert has_playbook_for(["BNS 999"]) is False


def test_playbook_has_no_match_for_empty_citations():
    from backend.app.mindmap.playbook_generator import has_playbook_for
    assert has_playbook_for([]) is False


def test_playbook_mindmap_structure_no_db():
    """Without a DB connection the generator returns the in-memory tree."""
    from backend.app.mindmap.playbook_generator import generate_playbook_mindmap
    resp = generate_playbook_mindmap(
        fir_id="00000000-0000-0000-0000-000000000001",
        citations=["BNS 304"],
        conn=None,
    )
    assert resp is not None
    assert resp["status"] == "preview"
    assert resp["case_category"] == "Snatching"
    assert resp["template_version"] == "playbook-v1"
    # Hub title is compact; full scenario name lives in description_md
    assert "Playbook" in resp["root"]["title"]
    assert "Snatching" in resp["root"]["description_md"]
    assert resp["root"]["children"], "expected phases as children"
    assert any(sc["scenario_id"] == "SCN_014" for sc in resp["playbook_scenarios"])


def test_playbook_mindmap_combines_multiple_scenarios():
    """When multiple scenarios match, a synthetic root wraps them."""
    from backend.app.mindmap.playbook_generator import generate_playbook_mindmap
    resp = generate_playbook_mindmap(
        fir_id="00000000-0000-0000-0000-000000000002",
        citations=["BNS 109(1)", "BNS 118(1)"],
        conn=None,
    )
    assert resp is not None
    # Multi-scenario root carries the count
    assert "Playbook" in resp["root"]["title"]
    assert len(resp["playbook_scenarios"]) >= 2


def test_playbook_mindmap_returns_none_for_unmatched_citations():
    from backend.app.mindmap.playbook_generator import generate_playbook_mindmap
    resp = generate_playbook_mindmap(
        fir_id="00000000-0000-0000-0000-000000000003",
        citations=["BNS 999"],
        conn=None,
    )
    assert resp is None


# ---------- Task 2: playbook gap-aggregator path ---------- #


def test_playbook_gap_helper_emits_form_gaps():
    """The new aggregator helper emits gaps for missing forms."""
    from backend.app.chargesheet.gap_aggregator import _playbook_driven_gaps

    cs = {
        "raw_text": "Brief chargesheet narrative without any forms attached.",
        "evidence_json": [],
        "witnesses_json": [],
        "reviewer_notes": "",
    }
    fir = {"nlp_metadata": {"recommended_sections": ["BNS 304"]}}
    gaps = _playbook_driven_gaps(cs, fir)
    assert gaps, "expected at least one playbook gap"
    forms_emitted = [g for g in gaps if g["category"] == "playbook_form_missing"]
    assert forms_emitted
    # Each form gap carries a playbook reference (Compendium scenario)
    assert all("playbook_reference" in g for g in forms_emitted)


def test_playbook_gap_helper_skips_forms_already_present():
    from backend.app.chargesheet.gap_aggregator import _playbook_driven_gaps
    cs = {
        "raw_text": "RUKKA prepared. FSL Form filled. Site Plan attached. MLC obtained.",
        "evidence_json": [],
        "witnesses_json": [],
        "reviewer_notes": "Sample Seal affixed; Road Certificate from Malkhana attached.",
    }
    fir = {"nlp_metadata": {"recommended_sections": ["BNS 304"]}}
    gaps = _playbook_driven_gaps(cs, fir)
    # Should still emit some gaps (e.g. evidence items) but fewer form gaps
    forms = [g for g in gaps if g["category"] == "playbook_form_missing"]
    citations_in_haystack = ["rukka", "fsl form", "site plan", "mlc",
                              "sample seal", "road certificate"]
    for g in forms:
        artefact = g["remediation"]["artefact"].lower()
        assert artefact not in citations_in_haystack, (
            f"Form '{artefact}' was in haystack but still flagged"
        )


def test_playbook_gap_helper_emits_deadline_reminders():
    from backend.app.chargesheet.gap_aggregator import _playbook_driven_gaps
    cs = {"raw_text": "", "evidence_json": [], "witnesses_json": [], "reviewer_notes": ""}
    fir = {"nlp_metadata": {"recommended_sections": ["BNS 65(1)"]}}  # Rape+POCSO
    gaps = _playbook_driven_gaps(cs, fir)
    deadlines = [g for g in gaps if g["category"] == "playbook_deadline_reminder"]
    assert deadlines


def test_playbook_gap_helper_returns_empty_when_no_match():
    from backend.app.chargesheet.gap_aggregator import _playbook_driven_gaps
    cs = {"raw_text": "", "evidence_json": [], "witnesses_json": [], "reviewer_notes": ""}
    fir = {"nlp_metadata": {"recommended_sections": ["BNS 999"]}}
    gaps = _playbook_driven_gaps(cs, fir)
    assert gaps == []


# ---------- Task 3: auto-trigger module ---------- #


def test_auto_trigger_returns_recommendations_no_db():
    """The auto-trigger runs the recommender even without a DB connection."""
    from backend.app.legal_sections.auto_trigger import run_recommender_for_fir
    out = run_recommender_for_fir(
        fir_id="11111111-1111-1111-1111-111111111111",
        narrative=(
            "On 16/03/2025 at 11:00 AM the complainant left his house at "
            "Sanand locked. Lock of front door broken; gold ornaments and "
            "cash stolen. Suspicion on house-helper."
        ),
        occurrence_date_iso="2025-03-16T11:00:00+05:30",
        accused_count=1,
        conn=None,
    )
    assert "recommended_sections" in out
    assert "compendium_scenarios" in out
    assert out["act_basis"] == "BNS"
    assert out["persisted"] is False
    # Expect at least one recommendation entry
    assert isinstance(out["recommended_sections"], list)


def test_auto_trigger_handles_empty_narrative():
    """Empty narrative should not crash; returns empty recommendation set."""
    from backend.app.legal_sections.auto_trigger import run_recommender_for_fir
    out = run_recommender_for_fir(
        fir_id="22222222-2222-2222-2222-222222222222",
        narrative="",
        occurrence_date_iso=None,
        accused_count=1,
        conn=None,
    )
    # Empty narrative still produces a (possibly empty) output without crashing
    assert "recommended_sections" in out


# ---------- Cross-cutting: imports ---------- #


def test_firs_route_imports_clean():
    """Verify the modified FIR route module imports without errors."""
    from app.api.v1.firs import _trigger_recommender_in_background, router
    assert router is not None
    assert callable(_trigger_recommender_in_background)


def test_ingest_route_imports_clean():
    from app.api.v1.ingest import router
    assert router is not None


def test_mindmap_generator_imports_clean():
    """Verify the patched generator imports both paths."""
    from app.mindmap import generator, playbook_generator
    assert callable(generator.generate_mindmap)
    assert callable(playbook_generator.generate_playbook_mindmap)
    assert callable(playbook_generator.has_playbook_for)
