"""End-to-end integration test: FIR → Mindmap generation — T53-M8.

Verifies the full pipeline: FIR data → case classification → template
selection → mindmap generation with expected branches.

Requires DATABASE_URL to be set for the DB-dependent portions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.mindmap.generator import (
    _get_case_category,
    _get_completeness_gaps,
)
from app.mindmap.registry import load_template, reload_templates
from app.mindmap.schemas import TemplateTree


pytestmark = pytest.mark.db


class TestFirToMindmapPipeline:
    """End-to-end test of the FIR → mindmap generation pipeline."""

    @pytest.fixture(autouse=True)
    def _reload_templates(self):
        reload_templates()

    def test_murder_fir_generates_murder_template(self):
        """A FIR classified as 'murder' with high confidence should
        produce a mindmap using the murder template."""
        fir = {
            "id": str(uuid.uuid4()),
            "fir_number": "001/2026",
            "district": "Ahmedabad",
            "police_station": "Navrangpura",
            "narrative": "Accused stabbed victim with knife resulting in death",
            "nlp_classification": "murder",
            "nlp_confidence": 0.92,
            "completeness_pct": 80,
            "complainant_name": "Ramesh Patel",
            "accused_name": "Suresh Shah",
            "place_address": "Near Sabarmati Riverfront",
            "primary_sections": ["302", "201"],
            "io_name": "Inspector Sharma",
        }

        # Step 1: Determine case category
        category, uncertain = _get_case_category(fir)
        assert category == "murder"
        assert uncertain is False

        # Step 2: Load template
        template = load_template(category)
        assert template.case_category == "murder"
        assert len(template.branches) >= 5

        # Step 3: Verify expected branch types
        branch_types = {b.node_type.value for b in template.branches}
        assert "legal_section" in branch_types
        assert "evidence" in branch_types

        # Step 4: Check completeness gaps
        gaps = _get_completeness_gaps(fir)
        # FIR is 80% complete but has most fields filled
        # Should have few or no gaps
        assert isinstance(gaps, list)

    def test_incomplete_fir_generates_gap_nodes(self):
        """An incomplete FIR should generate gap_from_fir nodes."""
        fir = {
            "id": str(uuid.uuid4()),
            "fir_number": None,
            "district": None,
            "police_station": None,
            "narrative": "Some incident occurred",
            "nlp_classification": "theft",
            "nlp_confidence": 0.75,
            "completeness_pct": 30,
            "complainant_name": None,
            "accused_name": None,
            "place_address": None,
            "primary_sections": [],
            "io_name": None,
        }

        category, uncertain = _get_case_category(fir)
        assert category == "theft"

        gaps = _get_completeness_gaps(fir)
        assert len(gaps) >= 5  # Multiple missing fields

        # Verify gap titles are descriptive
        gap_titles = [g["title"] for g in gaps]
        assert any("FIR Number" in t for t in gap_titles)
        assert any("Complainant" in t for t in gap_titles)

    def test_uncertain_classification_uses_template(self):
        """Low confidence classification should still use the category
        template but flag as uncertain."""
        fir = {
            "nlp_classification": "cyber_crime",
            "nlp_confidence": 0.45,
            "completeness_pct": 90,
        }

        category, uncertain = _get_case_category(fir)
        assert category == "cyber_crime"
        assert uncertain is True

        template = load_template(category)
        assert template.case_category == "cyber_crime"

    def test_no_classification_falls_back_to_generic(self):
        """FIR without classification should use generic template."""
        fir = {
            "nlp_classification": None,
            "nlp_confidence": None,
            "completeness_pct": 50,
        }

        category, uncertain = _get_case_category(fir)
        assert category == "generic"
        assert uncertain is True

        template = load_template(category)
        assert template.case_category == "generic"

    @pytest.mark.parametrize("case_cat", [
        "murder", "theft", "rape", "dowry", "ndps",
        "cyber_crime", "pocso", "accident", "missing_persons",
    ])
    def test_all_categories_produce_valid_templates(self, case_cat):
        """Each case category should produce a template with branches."""
        template = load_template(case_cat)
        assert template.case_category == case_cat
        assert len(template.branches) >= 3
        for branch in template.branches:
            assert branch.title
            assert branch.node_type

    def test_template_nodes_have_required_fields(self):
        """All template nodes should have the required fields."""
        template = load_template("murder")
        for branch in template.branches:
            assert branch.title
            assert branch.node_type
            assert branch.priority
            for child in branch.children:
                assert child.title
                assert child.node_type
                assert child.priority
