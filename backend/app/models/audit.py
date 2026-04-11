"""Pydantic models for the tamper-evident audit system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    CHARGESHEET_UPLOADED = "CHARGESHEET_UPLOADED"
    CHARGESHEET_PARSED = "CHARGESHEET_PARSED"
    VALIDATION_RUN = "VALIDATION_RUN"
    EVIDENCE_ANALYSIS_RUN = "EVIDENCE_ANALYSIS_RUN"
    RECOMMENDATION_ACCEPTED = "RECOMMENDATION_ACCEPTED"
    RECOMMENDATION_MODIFIED = "RECOMMENDATION_MODIFIED"
    RECOMMENDATION_DISMISSED = "RECOMMENDATION_DISMISSED"
    REVIEW_STARTED = "REVIEW_STARTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REVIEW_FLAGGED = "REVIEW_FLAGGED"
    FIELD_EDITED = "FIELD_EDITED"
    EXPORT_GENERATED = "EXPORT_GENERATED"
    DOCUMENT_VIEWED = "DOCUMENT_VIEWED"


class AuditEntry(BaseModel):
    id: UUID
    chargesheet_id: UUID
    user_id: str
    action: str
    detail_json: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    previous_hash: str
    entry_hash: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChainVerification(BaseModel):
    valid: bool
    total_entries: int
    first_break_at: Optional[int] = None
    verified_at: datetime


class RecommendationActionRequest(BaseModel):
    """Request body for POST /recommendation."""
    recommendation_id: str
    recommendation_type: str = Field(..., pattern=r"^(legal_validation|evidence_gap)$")
    action: str = Field(..., pattern=r"^(accepted|modified|dismissed)$")
    original_text: Optional[str] = None
    modified_text: Optional[str] = None
    reason: Optional[str] = None
    source_rule: Optional[str] = None


class ReviewCompleteRequest(BaseModel):
    """Request body for POST /complete."""
    overall_assessment: Optional[str] = None
    flag_for_senior: bool = False
