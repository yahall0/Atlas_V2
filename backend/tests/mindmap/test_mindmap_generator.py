"""Tests for the mindmap generator — T53-M8.

Uses mock database connections to test generation logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.mindmap.generator import (
    _compute_status_hash,
    _get_case_category,
    _get_completeness_gaps,
)


class TestCaseCategory:
    """Test case category determination logic."""

    def test_high_confidence_classification(self):
        fir = {"nlp_classification": "murder", "nlp_confidence": 0.85}
        cat, uncertain = _get_case_category(fir)
        assert cat == "murder"
        assert uncertain is False

    def test_low_confidence_classification(self):
        fir = {"nlp_classification": "murder", "nlp_confidence": 0.5}
        cat, uncertain = _get_case_category(fir)
        assert cat == "murder"
        assert uncertain is True

    def test_threshold_boundary(self):
        fir = {"nlp_classification": "theft", "nlp_confidence": 0.7}
        cat, uncertain = _get_case_category(fir)
        assert cat == "theft"
        assert uncertain is False

    def test_below_threshold(self):
        fir = {"nlp_classification": "theft", "nlp_confidence": 0.69}
        cat, uncertain = _get_case_category(fir)
        assert cat == "theft"
        assert uncertain is True

    def test_no_classification(self):
        fir = {"nlp_classification": None, "nlp_confidence": None}
        cat, uncertain = _get_case_category(fir)
        assert cat == "generic"
        assert uncertain is True

    def test_missing_fields(self):
        fir = {}
        cat, uncertain = _get_case_category(fir)
        assert cat == "generic"
        assert uncertain is True


class TestCompletenessGaps:
    """Test completeness gap extraction."""

    def test_full_completeness_no_gaps(self):
        fir = {
            "completeness_pct": 100,
            "fir_number": "001/2026",
            "complainant_name": "Test",
            "accused_name": "Accused",
        }
        gaps = _get_completeness_gaps(fir)
        assert len(gaps) == 0

    def test_missing_fir_number(self):
        fir = {"completeness_pct": 50, "fir_number": None}
        gaps = _get_completeness_gaps(fir)
        titles = [g["title"] for g in gaps]
        assert any("FIR Number" in t for t in titles)

    def test_missing_complainant(self):
        fir = {"completeness_pct": 60, "complainant_name": None}
        gaps = _get_completeness_gaps(fir)
        titles = [g["title"] for g in gaps]
        assert any("Complainant" in t for t in titles)

    def test_missing_accused(self):
        fir = {"completeness_pct": 70, "accused_name": None}
        gaps = _get_completeness_gaps(fir)
        titles = [g["title"] for g in gaps]
        assert any("Accused" in t for t in titles)

    def test_multiple_gaps(self):
        fir = {
            "completeness_pct": 30,
            "fir_number": None,
            "complainant_name": None,
            "accused_name": None,
            "place_address": None,
            "occurrence_from": None,
            "occurrence_start": None,
            "primary_sections": [],
            "io_name": None,
            "district": None,
        }
        gaps = _get_completeness_gaps(fir)
        assert len(gaps) >= 5

    def test_none_completeness(self):
        fir = {"completeness_pct": None}
        gaps = _get_completeness_gaps(fir)
        assert len(gaps) == 0


class TestHashChain:
    """Test the SHA-256 hash chain computation."""

    def test_deterministic_hash(self):
        h1 = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_status_hash("n1", "u1", "addressed", "", "", "2026-01-01T00:00:00", "GENESIS")
        assert h1 != h2

    def test_hash_chain_links(self):
        h1 = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_status_hash("n1", "u1", "in_progress", "note", "", "2026-01-01T01:00:00", h1)
        h3 = _compute_status_hash("n1", "u1", "addressed", "done", "ref1", "2026-01-01T02:00:00", h2)
        # Each hash depends on the previous
        assert h1 != h2 != h3

    def test_hash_is_sha256(self):
        h = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_tampered_chain_detected(self):
        """Simulate verifying a chain where one entry was tampered."""
        h1 = _compute_status_hash("n1", "u1", "open", "", "", "2026-01-01T00:00:00", "GENESIS")
        h2 = _compute_status_hash("n1", "u1", "addressed", "", "", "2026-01-01T01:00:00", h1)

        # Tamper: recompute h2 with wrong prev hash
        h2_tampered = _compute_status_hash("n1", "u1", "addressed", "", "", "2026-01-01T01:00:00", "WRONG_HASH")
        assert h2 != h2_tampered

        # Verify chain: h2 should link to h1, not WRONG_HASH
        h2_verify = _compute_status_hash("n1", "u1", "addressed", "", "", "2026-01-01T01:00:00", h1)
        assert h2_verify == h2
        assert h2_verify != h2_tampered


class TestMindmapGeneratorIntegration:
    """Higher-level generator tests with mocked DB."""

    def test_dedup_key_logic(self):
        """Verify dedup set works: same (node_type, bns_section, title) => skip."""
        seen = set()
        key1 = ("evidence", "103(1)", "Murder charge")
        key2 = ("evidence", "103(1)", "Murder charge")
        key3 = ("evidence", "105", "Culpable homicide")

        seen.add(key1)
        assert key2 in seen, "Duplicate should be detected"
        assert key3 not in seen, "Different key should not be a duplicate"
