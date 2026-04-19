"""Tests for the IO Scenarios KB (Delhi Police Academy Compendium)."""
from __future__ import annotations

import pytest

from backend.app.legal_sections.io_scenarios import (
    SCENARIOS,
    find_scenarios_for_sections,
    load_kb,
)
from backend.app.legal_sections.scenario_adapter import (
    build_chargesheet_mindmap,
    categorise_compendium_items,
    checklist_for_scenarios,
    lookup_section,
    mindmap_nodes_for_scenario,
    playbook_for_recommendation,
)


@pytest.fixture(scope="module")
def kb():
    return load_kb()


def test_kb_has_twenty_scenarios(kb):
    assert len(kb) == 20


def test_every_scenario_has_phases_and_sections(kb):
    for sc in kb:
        assert sc["scenario_name"]
        assert sc["applicable_sections"], f"{sc['scenario_id']} has no sections"
        assert sc["phases"], f"{sc['scenario_id']} has no phases"


def test_rape_pocso_scenario_has_essential_phases(kb):
    rape = next(sc for sc in kb if sc["scenario_id"] == "SCN_001")
    phase_titles = {ph["title"].upper() for ph in rape["phases"]}
    assert any("CALL" in t or "INFORMATION" in t for t in phase_titles)
    assert any("FIR" in t or "REGISTRATION" in t for t in phase_titles)
    assert any("INVESTIGATION" in t for t in phase_titles)


def test_rape_pocso_evidence_catalogue_includes_mlc_and_fsl(kb):
    rape = next(sc for sc in kb if sc["scenario_id"] == "SCN_001")
    text = " ".join(rape["evidence_catalogue"]).lower()
    assert "mlc" in text or "medical" in text
    assert "fsl" in text or "forensic" in text


def test_find_scenarios_for_sections_matches_bns_109(kb):
    matches = find_scenarios_for_sections(["BNS 109(1)"])
    assert any(m["scenario_id"] == "SCN_006" for m in matches)


def test_find_scenarios_for_sections_matches_bns_304(kb):
    matches = find_scenarios_for_sections(["BNS 304"])
    assert any(m["scenario_id"] == "SCN_014" for m in matches)


def test_find_scenarios_for_sections_matches_riot_chain(kb):
    matches = find_scenarios_for_sections(["BNS 191", "BNS 190"])
    assert any(m["scenario_id"] == "SCN_013" for m in matches)


def test_playbook_for_recommendation_returns_authority(kb):
    refs = playbook_for_recommendation(["BNS 304"])
    assert refs
    ref = refs[0]
    assert ref.scenario_id == "SCN_014"
    assert "Delhi Police Academy" in ref.source_authority
    assert ref.page_start > 0 and ref.page_end > ref.page_start


def test_mindmap_nodes_for_scenario_builds_tree(kb):
    """The mindmap is intentionally 3 levels deep (hub → phase → sub-block leaf)
    to match the renderer; per-item detail lives in metadata.items.
    """
    rape = next(sc for sc in kb if sc["scenario_id"] == "SCN_001")
    root = mindmap_nodes_for_scenario(rape)
    # Hub title is compact; scenario name appears in description_md
    assert "Playbook" in root.title
    assert "Rape with POCSO" in root.description_md
    assert root.children, "phases should be top-level children"
    # phase → sub-block leaf (no items as further children)
    phase = root.children[0]
    assert phase.children, "sub-blocks expected"
    sb = phase.children[0]
    # Sub-block leaf carries items in metadata, not as children
    assert sb.metadata
    assert "items" in sb.metadata
    assert isinstance(sb.metadata["items"], list)
    assert sb.metadata["items"], "expected at least one item"
    # Each metadata item has the playbook keys
    item = sb.metadata["items"][0]
    assert "marker" in item
    assert "text" in item
    assert "actors" in item
    assert "legal_refs" in item
    assert "forms" in item


def test_checklist_aggregates_across_scenarios(kb):
    scenarios = [sc for sc in kb if sc["scenario_id"] in ("SCN_001", "SCN_006")]
    checklist = checklist_for_scenarios(scenarios)
    assert checklist["evidence_to_collect"]
    assert checklist["forms_required"]
    assert "source_scenarios" in checklist
    assert len(checklist["source_scenarios"]) == 2


def test_lookup_section_returns_bns_305a():
    sec = lookup_section("BNS 305(a)")
    assert sec is not None
    assert sec["act"] == "BNS"
    assert sec["section_number"] == "305"
    assert "dwelling" in (sec.get("text") or "")


def test_lookup_section_unknown_returns_none():
    assert lookup_section("BNS 9999") is None


def test_categorise_items_buckets_correctly(kb):
    sc = next(s for s in kb if s["scenario_id"] == "SCN_008")
    buckets = categorise_compendium_items([sc])
    assert "panchnama" in buckets and "evidence" in buckets
    assert "forensics" in buckets and "witness" in buckets
    # Most scenarios have at least some witness items + some forensics items
    assert sum(len(v) for v in buckets.values()) > 0


def test_chargesheet_mindmap_has_six_branches():
    fir = {
        "id": "00000000-0000-0000-0000-000000000099",
        "fir_number": "TEST-001",
        "nlp_classification": "assault",
    }
    root = build_chargesheet_mindmap(
        fir=fir,
        citations=["BNS 118(1)", "BNS 324(2)"],
        completeness_gaps=[
            {"title": "complainant address missing", "severity": "high"},
        ],
    )
    # Hub label
    assert root.title == "FIR TEST-001 | assault"
    # Six branches in fixed order
    branches = [c.title for c in root.children]
    assert len(branches) == 6
    assert branches[0].startswith("Applicable BNS Sections")
    assert branches[1].startswith("Panchnama")
    assert branches[2].startswith("Evidence")
    assert branches[3].startswith("Blood / DNA / Forensics")
    assert branches[4].startswith("Witness / Bayan")
    assert branches[5].startswith("Gaps in FIR")
    # BNS 118(1) is in the corpus → its leaf should carry verbatim section text
    section_branch = root.children[0]
    leaves = [c.title for c in section_branch.children]
    assert any("BNS 118(1)" in t for t in leaves)
    assert any("BNS 324(2)" in t for t in leaves)
    # Gaps branch surfaces the supplied gap
    gaps_branch = root.children[5]
    gap_titles = [c.title for c in gaps_branch.children]
    assert any("address" in t.lower() for t in gap_titles)


def test_chargesheet_mindmap_renders_when_no_citations():
    """Even with no recommended sections, the 6-branch shape exists."""
    fir = {"id": "11111111-1111-1111-1111-111111111111",
           "fir_number": "EMPTY-001", "nlp_classification": "unknown"}
    root = build_chargesheet_mindmap(fir=fir, citations=[], completeness_gaps=[])
    assert len(root.children) == 6
    # Sections branch shows a "no sections recommended" placeholder leaf
    assert root.children[0].children


def test_scenarios_specs_match_kb_count():
    """Defensive: SCENARIOS table and built KB should agree."""
    assert len(SCENARIOS) == 20
    kb = load_kb()
    spec_ids = {s["id"] for s in SCENARIOS}
    kb_ids = {sc["scenario_id"] for sc in kb}
    assert spec_ids == kb_ids
