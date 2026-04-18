"""Tests for KB retrieval logic — T53-M-KB."""

import pytest
from app.mindmap.kb.schemas import KnowledgeBundle, RetrievalTrace


class TestKnowledgeBundleStructure:
    def test_bundle_has_version(self):
        bundle = KnowledgeBundle(kb_version="1.2.0")
        assert bundle.kb_version == "1.2.0"

    def test_bundle_empty_by_default(self):
        bundle = KnowledgeBundle(kb_version="1.0.0")
        assert len(bundle.primary_offences) == 0
        assert len(bundle.related_offences) == 0
        assert len(bundle.judgment_context) == 0

    def test_retrieval_trace_defaults(self):
        trace = RetrievalTrace()
        assert trace.exact_match_offences == 0
        assert trace.semantic_fallback_used is False
        assert trace.kb_version == ""


class TestMindmapAdapterBranchMapping:
    def test_branch_type_to_node_type(self):
        from app.mindmap.kb.mindmap_adapter import _BRANCH_TO_NODE_TYPE
        assert _BRANCH_TO_NODE_TYPE["legal_section"] == "legal_section"
        assert _BRANCH_TO_NODE_TYPE["immediate_action"] == "immediate_action"
        assert _BRANCH_TO_NODE_TYPE["gap_historical"] == "gap_from_fir"

    def test_tier_to_source(self):
        from app.mindmap.kb.mindmap_adapter import _TIER_TO_SOURCE
        assert _TIER_TO_SOURCE["canonical"] == "static_template"
        assert _TIER_TO_SOURCE["judgment_derived"] == "ml_suggestion"

    def test_branch_display_names(self):
        from app.mindmap.kb.mindmap_adapter import _branch_display_name
        assert _branch_display_name("legal_section") == "Applicable Legal Sections"
        assert _branch_display_name("panchnama") == "Panchnama Requirements"
        assert _branch_display_name("gap_historical") == "Historical Gap Patterns"
        assert _branch_display_name("unknown_type") == "Unknown Type"
