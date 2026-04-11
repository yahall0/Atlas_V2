"""Pydantic schemas for charge-sheet data."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Nested entity schemas
# ─────────────────────────────────────────────


class ChargeSheetAccused(BaseModel):
    """A single accused person extracted from the charge-sheet."""

    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    address: Optional[str] = None
    role: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChargeSheetCharge(BaseModel):
    """A charge section (IPC/BNS) listed in the charge-sheet."""

    section: Optional[str] = None
    act: Optional[str] = None
    description: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChargeSheetEvidence(BaseModel):
    """An evidence item listed in the charge-sheet."""

    type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChargeSheetWitness(BaseModel):
    """A witness from the witness schedule."""

    name: Optional[str] = None
    role: Optional[str] = None
    statement_summary: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ─────────────────────────────────────────────
# Parsed result from the chargesheet parser
# ─────────────────────────────────────────────


class ChargeSheetParsed(BaseModel):
    """Structured output from the charge-sheet parser.

    Every field is optional to tolerate partial / OCR-degraded documents.
    """

    fir_reference_number: Optional[str] = None
    court_name: Optional[str] = None
    filing_date: Optional[str] = None
    investigation_officer: Optional[str] = None
    district: Optional[str] = None
    police_station: Optional[str] = None

    accused_list: List[ChargeSheetAccused] = Field(default_factory=list)
    charge_sections: List[ChargeSheetCharge] = Field(default_factory=list)
    evidence_list: List[ChargeSheetEvidence] = Field(default_factory=list)
    witness_schedule: List[ChargeSheetWitness] = Field(default_factory=list)

    completeness_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    raw_text: Optional[str] = None


# ─────────────────────────────────────────────
# API request / response schemas
# ─────────────────────────────────────────────


class ChargeSheetResponse(BaseModel):
    """Full charge-sheet representation returned by the API."""

    id: UUID
    fir_id: Optional[UUID] = None
    filing_date: Optional[date] = None
    court_name: Optional[str] = None

    accused_json: Optional[List[Dict[str, Any]]] = None
    charges_json: Optional[List[Dict[str, Any]]] = None
    evidence_json: Optional[List[Dict[str, Any]]] = None
    witnesses_json: Optional[List[Dict[str, Any]]] = None

    io_name: Optional[str] = None
    raw_text: Optional[str] = None
    parsed_json: Optional[Dict[str, Any]] = None

    status: Optional[str] = None
    reviewer_notes: Optional[str] = None
    uploaded_by: Optional[str] = None
    district: Optional[str] = None
    police_station: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChargeSheetReviewRequest(BaseModel):
    """Payload for PATCH /chargesheet/{id}/review."""

    status: str = Field(..., pattern=r"^(reviewed|flagged)$")
    reviewer_notes: Optional[str] = None
