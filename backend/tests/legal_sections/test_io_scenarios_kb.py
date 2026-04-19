"""Tests for the IO Scenarios KB (Delhi Police Academy Compendium)."""
from __future__ import annotations

import pytest

from backend.app.legal_sections.io_scenarios import (
    SCENARIOS,
    find_scenarios_for_sections,
    load_kb,
)
from backend.app.legal_sections.scenario_adapter import (
    checklist_for_scenarios,
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
    rape = next(sc for sc in kb if sc["scenario_id"] == "SCN_001")
    root = mindmap_nodes_for_scenario(rape)
    assert root.title.startswith("Rape with POCSO")
    assert root.children, "phases should be top-level children"
    # phase → sub-block → item
    phase = root.children[0]
    assert phase.children, "sub-blocks expected"
    sb = phase.children[0]
    assert sb.children, "items expected"
    item = sb.children[0]
    assert item.metadata
    # metadata contains the playbook keys
    assert "actors" in item.metadata
    assert "legal_refs" in item.metadata
    assert "forms" in item.metadata


def test_checklist_aggregates_across_scenarios(kb):
    scenarios = [sc for sc in kb if sc["scenario_id"] in ("SCN_001", "SCN_006")]
    checklist = checklist_for_scenarios(scenarios)
    assert checklist["evidence_to_collect"]
    assert checklist["forms_required"]
    assert "source_scenarios" in checklist
    assert len(checklist["source_scenarios"]) == 2


def test_scenarios_specs_match_kb_count():
    """Defensive: SCENARIOS table and built KB should agree."""
    assert len(SCENARIOS) == 20
    kb = load_kb()
    spec_ids = {s["id"] for s in SCENARIOS}
    kb_ids = {sc["scenario_id"] for sc in kb}
    assert spec_ids == kb_ids
