"""Pydantic v2 models for the Legal Knowledge Base (T53-M-KB)."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class ApprovalStatus(str, enum.Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    CONTESTED = "contested"
    DEPRECATED = "deprecated"


class BranchType(str, enum.Enum):
    LEGAL_SECTION = "legal_section"
    IMMEDIATE_ACTION = "immediate_action"
    PANCHNAMA = "panchnama"
    EVIDENCE = "evidence"
    WITNESS_BAYAN = "witness_bayan"
    FORENSIC = "forensic"
    GAP_HISTORICAL = "gap_historical"
    PROCEDURAL_SAFEGUARD = "procedural_safeguard"


class Tier(str, enum.Enum):
    CANONICAL = "canonical"
    JUDGMENT_DERIVED = "judgment_derived"


class NodePriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ADVISORY = "advisory"


class CourtType(str, enum.Enum):
    SUPREME_COURT = "supreme_court"
    GUJARAT_HC = "gujarat_hc"
    OTHER_HC = "other_hc"
    DISTRICT = "district"


class InsightType(str, enum.Enum):
    NEW_PROCEDURAL = "new_procedural_requirement"
    EVIDENTIARY_CLARIFICATION = "evidentiary_standard_clarification"
    RIGHTS_SAFEGUARD = "rights_safeguard"
    ACQUITTAL_PATTERN = "acquittal_pattern"
    CONTRADICTS = "contradicts_existing_node"
    REINFORCES = "reinforces_existing_node"
    GENERAL = "general"


class ProposedAction(str, enum.Enum):
    ADD_NEW = "add_new_node"
    UPDATE = "update_node"
    FLAG_CONTESTED = "flag_contested"
    DEPRECATE = "deprecate_node"
    REINFORCE = "reinforce_only"


class InsightReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class JudgmentReviewStatus(str, enum.Enum):
    INGESTED = "ingested"
    EXTRACTED = "extracted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── Nested models ────────────────────────────────────────────────────────────

class LegalCitation(BaseModel):
    framework: Optional[str] = None  # BNS, BNSS, BSA, etc.
    section: Optional[str] = None
    subsection: Optional[str] = None
    case_citation: Optional[str] = None
    source_authority: Optional[str] = None


# ── Seed YAML schema ────────────────────────────────────────────────────────

class SeedKnowledgeNode(BaseModel):
    branch_type: BranchType
    tier: Tier = Tier.CANONICAL
    priority: NodePriority = NodePriority.MEDIUM
    title_en: str
    title_gu: Optional[str] = None
    description_md: str = ""
    legal_basis_citations: list[LegalCitation] = Field(default_factory=list)
    procedural_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_disclaimer: bool = False


class SeedOffence(BaseModel):
    offence_code: str
    category_id: str
    bns_section: Optional[str] = None
    bns_subsection: Optional[str] = None
    display_name_en: str
    display_name_gu: Optional[str] = None
    short_description_md: str = ""
    punishment: Optional[str] = None
    cognizable: Optional[bool] = None
    bailable: Optional[bool] = None
    triable_by: Optional[str] = None
    compoundable: str = "no"
    schedule_reference: Optional[str] = None
    related_offence_codes: list[str] = Field(default_factory=list)
    special_acts: list[str] = Field(default_factory=list)
    knowledge_nodes: list[SeedKnowledgeNode] = Field(default_factory=list)


# ── API response models ─────────────────────────────────────────────────────

class OffenceResponse(BaseModel):
    id: UUID
    category_id: str
    offence_code: str
    bns_section: Optional[str] = None
    bns_subsection: Optional[str] = None
    display_name_en: str
    display_name_gu: Optional[str] = None
    short_description_md: Optional[str] = None
    punishment: Optional[str] = None
    cognizable: Optional[bool] = None
    bailable: Optional[bool] = None
    triable_by: Optional[str] = None
    compoundable: str = "no"
    related_offence_codes: list[str] = Field(default_factory=list)
    special_acts: list[str] = Field(default_factory=list)
    kb_version: str
    review_status: str
    node_count: int = 0
    schedule_reference: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KnowledgeNodeResponse(BaseModel):
    id: UUID
    offence_id: UUID
    branch_type: BranchType
    tier: Tier
    priority: NodePriority
    title_en: str
    title_gu: Optional[str] = None
    description_md: Optional[str] = None
    legal_basis_citations: list[LegalCitation] = Field(default_factory=list)
    procedural_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_disclaimer: bool = False
    display_order: int = 0
    kb_version: str = ""
    approval_status: str = "proposed"

    model_config = {"from_attributes": True}


class OffenceWithNodes(BaseModel):
    offence: OffenceResponse
    nodes: list[KnowledgeNodeResponse] = Field(default_factory=list)


class RelevantJudgment(BaseModel):
    id: UUID
    citation: str
    case_name: Optional[str] = None
    court: str
    judgment_date: Optional[date] = None
    binding_authority: int
    summary_md: Optional[str] = None
    similarity_score: float = 0.0


class RetrievalTrace(BaseModel):
    exact_match_offences: int = 0
    related_offences: int = 0
    semantic_fallback_used: bool = False
    total_nodes_returned: int = 0
    kb_version: str = ""
    retrieval_duration_ms: int = 0


class KnowledgeBundle(BaseModel):
    kb_version: str
    primary_offences: list[OffenceWithNodes] = Field(default_factory=list)
    related_offences: list[OffenceWithNodes] = Field(default_factory=list)
    judgment_context: list[RelevantJudgment] = Field(default_factory=list)
    retrieval_trace: RetrievalTrace = Field(default_factory=RetrievalTrace)


# ── Judgment models ──────────────────────────────────────────────────────────

class JudgmentResponse(BaseModel):
    id: UUID
    citation: str
    case_name: Optional[str] = None
    court: str
    jurisdiction: Optional[str] = None
    judgment_date: Optional[date] = None
    bench: Optional[str] = None
    binding_authority: int
    summary_md: Optional[str] = None
    related_bns_sections: list[str] = Field(default_factory=list)
    related_offence_codes: list[str] = Field(default_factory=list)
    review_status: str
    ingested_at: Optional[datetime] = None
    insight_count: int = 0

    model_config = {"from_attributes": True}


class JudgmentInsightResponse(BaseModel):
    id: UUID
    judgment_id: UUID
    target_offence_id: Optional[UUID] = None
    insight_type: str
    branch_type: Optional[str] = None
    title_en: str
    description_md: Optional[str] = None
    extracted_quote: Optional[str] = None
    extraction_confidence: float = 0.0
    proposed_action: Optional[str] = None
    review_status: str
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Request models ───────────────────────────────────────────────────────────

class JudgmentUploadRequest(BaseModel):
    citation: str
    case_name: Optional[str] = None
    court: CourtType
    jurisdiction: Optional[str] = None
    judgment_date: Optional[date] = None
    bench: Optional[str] = None
    full_text: str = Field(..., min_length=100)
    summary_md: Optional[str] = None
    related_bns_sections: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class InsightReviewRequest(BaseModel):
    action: InsightReviewStatus  # approved, rejected, needs_revision
    review_notes: Optional[str] = None


class KBVersionReleaseRequest(BaseModel):
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    changelog_md: str = Field(..., min_length=5)


# ── Admin CRUD request models ──────────────────────────────────────────────


class OffenceCreateRequest(BaseModel):
    offence_code: str = Field(..., min_length=1, max_length=50)
    category_id: str = Field(..., min_length=1)
    display_name_en: str = Field(..., min_length=1)
    bns_section: Optional[str] = None
    bns_subsection: Optional[str] = None
    display_name_gu: Optional[str] = None
    short_description_md: str = ""
    punishment: Optional[str] = None
    cognizable: Optional[bool] = None
    bailable: Optional[bool] = None
    triable_by: Optional[str] = None
    compoundable: str = "no"
    schedule_reference: Optional[str] = None
    related_offence_codes: list[str] = Field(default_factory=list)
    special_acts: list[str] = Field(default_factory=list)


class OffenceUpdateRequest(BaseModel):
    offence_code: Optional[str] = None
    category_id: Optional[str] = None
    display_name_en: Optional[str] = None
    bns_section: Optional[str] = None
    bns_subsection: Optional[str] = None
    display_name_gu: Optional[str] = None
    short_description_md: Optional[str] = None
    punishment: Optional[str] = None
    cognizable: Optional[bool] = None
    bailable: Optional[bool] = None
    triable_by: Optional[str] = None
    compoundable: Optional[str] = None
    schedule_reference: Optional[str] = None
    related_offence_codes: Optional[list[str]] = None
    special_acts: Optional[list[str]] = None
    review_status: Optional[ReviewStatus] = None


class OffenceReviewRequest(BaseModel):
    review_status: ReviewStatus


class KnowledgeNodeCreateRequest(BaseModel):
    branch_type: BranchType
    title_en: str = Field(..., min_length=1)
    priority: NodePriority = NodePriority.MEDIUM
    title_gu: Optional[str] = None
    description_md: str = ""
    legal_basis_citations: list[LegalCitation] = Field(default_factory=list)
    procedural_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_disclaimer: bool = False
    display_order: int = 0


class KnowledgeNodeUpdateRequest(BaseModel):
    branch_type: Optional[BranchType] = None
    priority: Optional[NodePriority] = None
    title_en: Optional[str] = None
    title_gu: Optional[str] = None
    description_md: Optional[str] = None
    legal_basis_citations: Optional[list[LegalCitation]] = None
    procedural_metadata: Optional[dict[str, Any]] = None
    requires_disclaimer: Optional[bool] = None
    display_order: Optional[int] = None
