"""Pydantic v2 models for the Chargesheet Gap Analysis feature (T56-E)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class GapCategory(str, enum.Enum):
    LEGAL = "legal"
    EVIDENCE = "evidence"
    WITNESS = "witness"
    PROCEDURAL = "procedural"
    MINDMAP_DIVERGENCE = "mindmap_divergence"
    COMPLETENESS = "completeness"
    # KB-derived gaps — surfaced when the chargesheet omits an item
    # explicitly required by the 3-layer KB (Layer 2 SOP or Layer 3
    # case-law standard).
    KB_PLAYBOOK_GAP = "kb_playbook_gap"
    KB_CASELAW_GAP = "kb_caselaw_gap"


class GapSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ADVISORY = "advisory"


class GapSource(str, enum.Enum):
    T54_LEGAL_VALIDATOR = "T54_legal_validator"
    T55_EVIDENCE_ML = "T55_evidence_ml"
    MINDMAP_DIFF = "mindmap_diff"
    COMPLETENESS_RULES = "completeness_rules"
    MANUAL_REVIEW = "manual_review"
    KB_PLAYBOOK = "kb_playbook"
    KB_CASELAW = "kb_caselaw"


class KBLayerTag(str, enum.Enum):
    """Mirrors app.mindmap.kb.schemas.KBLayer for gap attribution."""

    CANONICAL_LEGAL = "canonical_legal"
    INVESTIGATION_PLAYBOOK = "investigation_playbook"
    CASE_LAW_INTELLIGENCE = "case_law_intelligence"


class GapActionType(str, enum.Enum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    DISMISSED = "dismissed"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


# ── Nested models ────────────────────────────────────────────────────────────

class GapLocation(BaseModel):
    page_num: Optional[int] = None
    char_offset_start: Optional[int] = None
    char_offset_end: Optional[int] = None
    bbox: Optional[list[float]] = None  # [x1, y1, x2, y2]


class LegalRef(BaseModel):
    framework: str  # BNS, IPC, CrPC, BNSS, BSA
    section: str
    deep_link: Optional[str] = None


class Remediation(BaseModel):
    summary: str
    steps: list[str] = Field(default_factory=list)
    suggested_language: Optional[str] = None
    sop_refs: list[dict[str, Any]] = Field(default_factory=list)
    estimated_effort: str = "minutes"  # minutes, hours, requires_investigation


# ── Gap models ───────────────────────────────────────────────────────────────

class GapResponse(BaseModel):
    id: UUID
    report_id: UUID
    category: GapCategory
    severity: GapSeverity
    source: GapSource
    requires_disclaimer: bool
    title: str
    description_md: Optional[str] = None
    location: Optional[GapLocation] = None
    legal_refs: list[LegalRef] = Field(default_factory=list)
    remediation: Remediation
    related_mindmap_node_id: Optional[UUID] = None
    confidence: float
    tags: list[str] = Field(default_factory=list)
    display_order: int
    current_action: Optional[GapActionType] = None
    # 3-layer KB attribution: which authority is the gap arguing from?
    kb_layer: Optional[KBLayerTag] = None
    kb_node_ref: Optional[UUID] = None

    model_config = {"from_attributes": True}


class LayerCounts(BaseModel):
    canonical_legal: int = 0
    investigation_playbook: int = 0
    case_law_intelligence: int = 0
    unattributed: int = 0


class GapReportResponse(BaseModel):
    id: UUID
    chargesheet_id: UUID
    generated_at: datetime
    generator_version: str
    gap_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    advisory_count: int
    generation_duration_ms: Optional[int] = None
    gaps: list[GapResponse] = Field(default_factory=list)
    # Per-KB-layer breakdown so the frontend can render three columns
    # (Statute / Playbook / Case-Law) with gap counts each.
    layer_counts: LayerCounts = Field(default_factory=LayerCounts)
    disclaimer: str = (
        "Advisory — AI-assisted review. "
        "Investigating Officer retains full legal responsibility. "
        "Not a substitute for legal judgment or supervisor review."
    )
    partial_sources: list[str] = Field(
        default_factory=list,
        description="Sources that were unavailable during analysis",
    )

    model_config = {"from_attributes": True}


class GapReportSummary(BaseModel):
    id: UUID
    chargesheet_id: UUID
    generated_at: datetime
    generator_version: str
    gap_count: int
    critical_count: int
    high_count: int


# ── Request models ───────────────────────────────────────────────────────────

class GapActionRequest(BaseModel):
    action: GapActionType
    note: Optional[str] = None
    modification_diff: Optional[str] = None
    evidence_ref: Optional[str] = None
    hash_prev: str = Field(
        ..., description="Hash of the most recent action the client knows about",
    )


class ReanalyzeRequest(BaseModel):
    justification: str = Field(..., min_length=5, max_length=2000)


class ApplySuggestionRequest(BaseModel):
    confirm: bool = True


# ── Response models ──────────────────────────────────────────────────────────

class GapActionResponse(BaseModel):
    id: UUID
    gap_id: UUID
    user_id: str
    action: GapActionType
    note: Optional[str] = None
    modification_diff: Optional[str] = None
    evidence_ref: Optional[str] = None
    created_at: datetime
    hash_prev: str
    hash_self: str


class ReadinessCategory(BaseModel):
    category: str
    status: str  # green, amber, red
    open_count: int
    critical_high_count: int
    gap_ids: list[UUID] = Field(default_factory=list)


class ReadinessResponse(BaseModel):
    categories: list[ReadinessCategory]
    overall: str  # green, amber, red
