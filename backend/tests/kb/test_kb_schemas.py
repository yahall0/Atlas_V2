"""Tests for KB schema validation — T53-M-KB."""

import pytest
from app.mindmap.kb.schemas import (
    SeedOffence,
    SeedKnowledgeNode,
    LegalCitation,
    BranchType,
    Tier,
    NodePriority,
    OffenceResponse,
    KnowledgeBundle,
    RetrievalTrace,
)


class TestSeedOffenceSchema:
    def test_minimal_valid(self):
        seed = SeedOffence(
            offence_code="BNS_S103_MURDER",
            category_id="violent_crimes",
            display_name_en="Murder",
        )
        assert seed.offence_code == "BNS_S103_MURDER"
        assert seed.knowledge_nodes == []

    def test_full_valid(self):
        seed = SeedOffence(
            offence_code="BNS_S64_RAPE",
            category_id="crimes_women_children",
            bns_section="64",
            bns_subsection="(1)",
            display_name_en="Rape",
            display_name_gu="બળાત્કાર",
            short_description_md="Punishment for rape",
            punishment="Rigorous imprisonment not less than 10 years",
            cognizable=True,
            bailable=False,
            triable_by="Court of Session",
            compoundable="no",
            related_offence_codes=["BNS_S66_RAPE_DEATH"],
            special_acts=["POCSO_2012"],
            knowledge_nodes=[
                SeedKnowledgeNode(
                    branch_type=BranchType.LEGAL_SECTION,
                    tier=Tier.CANONICAL,
                    priority=NodePriority.CRITICAL,
                    title_en="BNS S.64 — Rape",
                    description_md="Punishment for rape...",
                    legal_basis_citations=[
                        LegalCitation(framework="BNS", section="64",
                                      source_authority="Bharatiya Nyaya Sanhita 2023"),
                    ],
                ),
            ],
        )
        assert len(seed.knowledge_nodes) == 1
        assert seed.knowledge_nodes[0].branch_type == BranchType.LEGAL_SECTION

    def test_invalid_branch_type_rejected(self):
        with pytest.raises(Exception):
            SeedKnowledgeNode(
                branch_type="invalid_branch",
                title_en="Test",
            )


class TestKnowledgeBundle:
    def test_empty_bundle(self):
        bundle = KnowledgeBundle(kb_version="1.0.0")
        assert bundle.primary_offences == []
        assert bundle.retrieval_trace.exact_match_offences == 0

    def test_trace_fields(self):
        trace = RetrievalTrace(
            kb_version="1.2.0",
            exact_match_offences=3,
            related_offences=2,
            semantic_fallback_used=True,
            total_nodes_returned=45,
            retrieval_duration_ms=120,
        )
        assert trace.total_nodes_returned == 45


class TestBranchTypes:
    def test_all_branch_types(self):
        expected = {
            "legal_section", "immediate_action", "panchnama",
            "evidence", "witness_bayan", "forensic",
            "gap_historical", "procedural_safeguard",
        }
        actual = {bt.value for bt in BranchType}
        assert actual == expected

    def test_tier_values(self):
        assert Tier.CANONICAL.value == "canonical"
        assert Tier.JUDGMENT_DERIVED.value == "judgment_derived"


class TestJudgmentPipelineSchemas:
    def test_insight_types_complete(self):
        from app.mindmap.kb.schemas import InsightType
        values = {it.value for it in InsightType}
        assert "acquittal_pattern" in values
        assert "new_procedural_requirement" in values
        assert "contradicts_existing_node" in values

    def test_court_types(self):
        from app.mindmap.kb.schemas import CourtType
        assert CourtType.SUPREME_COURT.value == "supreme_court"
        assert CourtType.GUJARAT_HC.value == "gujarat_hc"
