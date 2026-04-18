"""Pydantic v2 models for the Chargesheet Mindmap feature (T53-M)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class NodeType(str, enum.Enum):
    LEGAL_SECTION = "legal_section"
    IMMEDIATE_ACTION = "immediate_action"
    EVIDENCE = "evidence"
    INTERROGATION = "interrogation"
    PANCHNAMA = "panchnama"
    FORENSIC = "forensic"
    WITNESS_BAYAN = "witness_bayan"
    GAP_FROM_FIR = "gap_from_fir"
    CUSTOM = "custom"


class NodeSource(str, enum.Enum):
    STATIC_TEMPLATE = "static_template"
    ML_SUGGESTION = "ml_suggestion"
    COMPLETENESS_ENGINE = "completeness_engine"
    IO_CUSTOM = "io_custom"


class NodePriority(str, enum.Enum):
    CRITICAL = "critical"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class NodeStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ADDRESSED = "addressed"
    NOT_APPLICABLE = "not_applicable"
    DISPUTED = "disputed"


class MindmapStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


# ── Template models (for JSON schema validation at startup) ──────────────────

class TemplateNodeChild(BaseModel):
    node_type: NodeType
    title: str
    description_md: str = ""
    ipc_section: Optional[str] = None
    bns_section: Optional[str] = None
    crpc_section: Optional[str] = None
    priority: NodePriority = NodePriority.RECOMMENDED
    requires_disclaimer: bool = False


class TemplateBranch(BaseModel):
    node_type: NodeType
    title: str
    description_md: str = ""
    priority: NodePriority = NodePriority.RECOMMENDED
    requires_disclaimer: bool = False
    children: list[TemplateNodeChild] = Field(default_factory=list)


class TemplateTree(BaseModel):
    case_category: str
    template_version: str
    description: str = ""
    branches: list[TemplateBranch]


class TemplateSummary(BaseModel):
    case_category: str
    template_version: str
    description: str
    branch_count: int
    total_nodes: int


# ── API request / response models ────────────────────────────────────────────

class NodeStatusUpdate(BaseModel):
    status: NodeStatus
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    hash_prev: str = Field(
        ..., description="Hash of the most recent status entry the client knows about"
    )


class CustomNodeCreate(BaseModel):
    parent_id: Optional[UUID] = None
    node_type: NodeType = NodeType.CUSTOM
    title: str = Field(..., min_length=1, max_length=512)
    description_md: str = ""
    priority: NodePriority = NodePriority.OPTIONAL


class RegenerateRequest(BaseModel):
    justification: str = Field(..., min_length=5, max_length=2000)


class NodeStatusResponse(BaseModel):
    id: UUID
    node_id: UUID
    user_id: str
    status: NodeStatus
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    updated_at: datetime
    hash_prev: str
    hash_self: str


class MindmapNodeResponse(BaseModel):
    id: UUID
    mindmap_id: UUID
    parent_id: Optional[UUID] = None
    node_type: NodeType
    title: str
    description_md: Optional[str] = None
    source: NodeSource
    bns_section: Optional[str] = None
    ipc_section: Optional[str] = None
    crpc_section: Optional[str] = None
    priority: NodePriority
    requires_disclaimer: bool
    display_order: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    current_status: Optional[NodeStatus] = None
    children: list[MindmapNodeResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MindmapResponse(BaseModel):
    id: UUID
    fir_id: UUID
    case_category: str
    template_version: str
    generated_at: datetime
    generated_by_model_version: Optional[str] = None
    root_node_id: Optional[UUID] = None
    status: MindmapStatus
    nodes: list[MindmapNodeResponse] = Field(default_factory=list)
    disclaimer: str = (
        "Advisory — AI-generated suggestions. "
        "Investigating Officer retains full discretion. "
        "Not a substitute for legal judgment."
    )

    model_config = {"from_attributes": True}


class MindmapVersionSummary(BaseModel):
    id: UUID
    case_category: str
    template_version: str
    generated_at: datetime
    status: MindmapStatus
    node_count: int


# Allow recursive model
MindmapNodeResponse.model_rebuild()
