"""Tests for the gap aggregation service — T56-E12."""

from __future__ import annotations

import json
import uuid

import pytest

from app.chargesheet.gap_aggregator import (
    _compute_action_hash,
    _convert_evidence_gaps,
    _convert_legal_findings,
    _compute_mindmap_divergences,
    _deduplicate,
    _run_completeness_rules,
)


class TestLegalFindingConversion:
    def test_converts_critical_finding(self):
        findings = [{
            "rule_id": "RULE_5",
            "severity": "CRITICAL",
            "section": "164 CrPC",
            "description": "Missing magistrate statement",
            "recommendation": "Record statement under Section 164",
            "confidence": 0.95,
        }]
        gaps = _convert_legal_findings(findings)
        assert len(gaps) == 1
        assert gaps[0]["category"] == "legal"
        assert gaps[0]["severity"] == "critical"
        assert gaps[0]["source"] == "T54_legal_validator"
        assert gaps[0]["requires_disclaimer"] is False

    def test_converts_warning_to_medium(self):
        findings = [{"severity": "WARNING", "description": "Missing companion",
                      "recommendation": "Add companion", "confidence": 0.8}]
        gaps = _convert_legal_findings(findings)
        assert gaps[0]["severity"] == "medium"

    def test_empty_findings(self):
        assert _convert_legal_findings([]) == []


class TestEvidenceGapConversion:
    def test_converts_evidence_gap(self):
        evidence = [{
            "category": "post_mortem_report",
            "tier": "rule_based",
            "severity": "critical",
            "recommendation": "Attach PM report",
            "legal_basis": "Section 174 CrPC",
            "confidence": 0.85,
        }]
        gaps = _convert_evidence_gaps(evidence)
        assert len(gaps) == 1
        assert gaps[0]["category"] == "evidence"
        assert gaps[0]["source"] == "T55_evidence_ml"
        assert gaps[0]["requires_disclaimer"] is True
        assert gaps[0]["confidence"] == 0.85

    def test_ml_pattern_gap(self):
        evidence = [{"category": "witness_statements", "tier": "ml_pattern",
                      "severity": "suggested", "recommendation": "More witnesses",
                      "confidence": 0.6}]
        gaps = _convert_evidence_gaps(evidence)
        assert gaps[0]["severity"] == "medium"


class TestMindmapDivergence:
    def test_unmatched_addressed_node_creates_divergence(self):
        mindmap_data = {
            "mindmap_id": str(uuid.uuid4()),
            "nodes": [{
                "id": uuid.uuid4(),
                "node_type": "forensic",
                "title": "DNA Analysis",
                "current_status": "addressed",
                "bns_section": None,
                "ipc_section": None,
            }],
        }
        cs = {"raw_text": "some unrelated text", "evidence_json": [],
              "witnesses_json": [], "charges_json": []}
        divs = _compute_mindmap_divergences(mindmap_data, cs)
        assert len(divs) == 1
        assert divs[0]["category"] == "mindmap_divergence"
        assert "DNA Analysis" in divs[0]["title"]

    def test_matched_node_no_divergence(self):
        mindmap_data = {
            "mindmap_id": str(uuid.uuid4()),
            "nodes": [{
                "id": uuid.uuid4(),
                "node_type": "forensic",
                "title": "DNA Analysis",
                "current_status": "addressed",
                "bns_section": None,
                "ipc_section": None,
            }],
        }
        cs = {"raw_text": "the forensic dna report was submitted to fsl",
              "evidence_json": [], "witnesses_json": [], "charges_json": []}
        divs = _compute_mindmap_divergences(mindmap_data, cs)
        assert len(divs) == 0

    def test_non_addressed_nodes_ignored(self):
        mindmap_data = {
            "mindmap_id": str(uuid.uuid4()),
            "nodes": [{
                "id": uuid.uuid4(),
                "node_type": "evidence",
                "title": "Something",
                "current_status": "open",
                "bns_section": None,
                "ipc_section": None,
            }],
        }
        cs = {"raw_text": "", "evidence_json": [], "witnesses_json": [], "charges_json": []}
        divs = _compute_mindmap_divergences(mindmap_data, cs)
        assert len(divs) == 0

    def test_legal_section_match_by_ipc(self):
        mindmap_data = {
            "mindmap_id": str(uuid.uuid4()),
            "nodes": [{
                "id": uuid.uuid4(),
                "node_type": "legal_section",
                "title": "IPC 302 Murder",
                "current_status": "addressed",
                "bns_section": "103(1)",
                "ipc_section": "302",
            }],
        }
        cs = {"raw_text": "", "evidence_json": [], "witnesses_json": [],
              "charges_json": [{"section": "302 IPC"}]}
        divs = _compute_mindmap_divergences(mindmap_data, cs)
        assert len(divs) == 0

    def test_no_mindmap_returns_empty(self):
        assert _compute_mindmap_divergences(None, {}) == []


class TestDeduplication:
    def test_dedup_merges_same_key(self):
        gaps = [
            {"category": "legal", "severity": "medium", "source": "T54_legal_validator",
             "title": "Missing section", "confidence": 0.9, "tags": ["R1"],
             "_dedup_key": ("legal", "302", "RULE_2")},
            {"category": "legal", "severity": "critical", "source": "completeness_rules",
             "title": "Missing section", "confidence": 1.0, "tags": ["COMP_007"],
             "_dedup_key": ("legal", "302", "RULE_2")},
        ]
        result = _deduplicate(gaps)
        assert len(result) == 1
        # Should keep higher severity
        assert result[0]["severity"] == "critical"

    def test_dedup_keeps_different_keys(self):
        gaps = [
            {"category": "legal", "severity": "high", "source": "T54",
             "title": "A", "confidence": 0.8, "tags": [],
             "_dedup_key": ("legal", "302", "")},
            {"category": "evidence", "severity": "medium", "source": "T55",
             "title": "B", "confidence": 0.7, "tags": [],
             "_dedup_key": ("evidence", "pm_report", "")},
        ]
        result = _deduplicate(gaps)
        assert len(result) == 2


class TestCompletenessRules:
    def test_missing_witnesses_detected(self):
        cs = {"witnesses_json": [], "raw_text": "", "fir_id": None,
              "charges_json": [], "evidence_json": [], "accused_json": [],
              "filing_date": None}
        gaps = _run_completeness_rules(cs, "generic")
        titles = [g["title"] for g in gaps]
        assert any("Witness" in t for t in titles)

    def test_missing_accused_detected(self):
        cs = {"accused_json": [], "raw_text": "", "witnesses_json": [],
              "fir_id": None, "charges_json": [], "evidence_json": [],
              "filing_date": None}
        gaps = _run_completeness_rules(cs, "generic")
        titles = [g["title"] for g in gaps]
        assert any("Accused" in t for t in titles)

    def test_complete_chargesheet_fewer_gaps(self):
        cs = {
            "accused_json": [{"name": "Test"}],
            "witnesses_json": [{"name": "W1"}],
            "charges_json": [{"section": "302"}],
            "evidence_json": [{"type": "PM report"}],
            "raw_text": "investigating officer IO seizure memo court magistrate bail",
            "fir_id": str(uuid.uuid4()),
            "filing_date": "2026-04-01",
        }
        gaps = _run_completeness_rules(cs, "generic")
        # Should have fewer gaps than empty chargesheet
        cs_empty = {"accused_json": [], "witnesses_json": [], "charges_json": [],
                     "evidence_json": [], "raw_text": "", "fir_id": None,
                     "filing_date": None}
        gaps_empty = _run_completeness_rules(cs_empty, "generic")
        assert len(gaps) < len(gaps_empty)


class TestActionHashChain:
    def test_deterministic(self):
        h1 = _compute_action_hash("g1", "u1", "accepted", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_action_hash("g1", "u1", "accepted", "", "2026-01-01T00:00:00", "GENESIS")
        assert h1 == h2

    def test_different_actions_different_hash(self):
        h1 = _compute_action_hash("g1", "u1", "accepted", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_action_hash("g1", "u1", "dismissed", "", "2026-01-01T00:00:00", "GENESIS")
        assert h1 != h2

    def test_chain_linkage(self):
        h1 = _compute_action_hash("g1", "u1", "accepted", "", "t1", "GENESIS")
        h2 = _compute_action_hash("g1", "u1", "modified", "fix", "t2", h1)
        assert len(h1) == 64
        assert len(h2) == 64
        assert h1 != h2
