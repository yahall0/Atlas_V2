"""Tests for the mindmap template registry — T53-M8."""

import pytest

from app.mindmap.registry import (
    list_templates,
    load_template,
    reload_templates,
    template_version,
)
from app.mindmap.schemas import TemplateTree


EXPECTED_CATEGORIES = [
    "murder",
    "theft",
    "rape",
    "dowry",
    "ndps",
    "cyber_crime",
    "pocso",
    "accident",
    "missing_persons",
]


class TestTemplateRegistry:
    """Verify all 9 templates load and validate correctly."""

    @pytest.fixture(autouse=True)
    def _reload(self):
        reload_templates()

    def test_all_templates_load(self):
        """All 9 expected templates should load without errors."""
        templates = list_templates()
        loaded_categories = {t.case_category for t in templates}
        for cat in EXPECTED_CATEGORIES:
            assert cat in loaded_categories, f"Template for '{cat}' not loaded"

    def test_template_count(self):
        templates = list_templates()
        assert len(templates) >= 9

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_load_specific_template(self, category):
        tree = load_template(category)
        assert isinstance(tree, TemplateTree)
        assert tree.case_category == category
        assert len(tree.branches) > 0

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_template_has_version(self, category):
        ver = template_version(category)
        assert ver
        assert "." in ver  # semver-like

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_template_branches_have_children(self, category):
        tree = load_template(category)
        for branch in tree.branches:
            assert branch.title, "Branch must have a title"
            assert branch.node_type, "Branch must have a node_type"

    def test_unknown_category_returns_generic(self):
        tree = load_template("nonexistent_category_xyz")
        assert tree.case_category == "generic"

    def test_template_version_unknown_returns_generic_version(self):
        ver = template_version("nonexistent_category_xyz")
        assert ver == "1.0.0"

    def test_list_templates_returns_summaries(self):
        summaries = list_templates()
        for s in summaries:
            assert s.case_category
            assert s.template_version
            assert s.branch_count > 0
            assert s.total_nodes > 0
