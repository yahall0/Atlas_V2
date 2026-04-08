"""Pydantic schemas for FIR (First Information Report) data."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Nested entity schemas
# ─────────────────────────────────────────────


class ComplainantCreate(BaseModel):
    """Fields accepted when creating a complainant record."""

    name: Optional[str] = None
    father_name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    address: Optional[str] = None


class Complainant(ComplainantCreate):
    """Complainant as stored in the database."""

    id: UUID
    fir_id: UUID

    class Config:
        from_attributes = True


class AccusedCreate(BaseModel):
    """Fields accepted when creating an accused record."""

    name: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    address: Optional[str] = None


class Accused(AccusedCreate):
    """Accused as stored in the database."""

    id: UUID
    fir_id: UUID

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# FIR schemas
# ─────────────────────────────────────────────


class FIRCreate(BaseModel):
    """Payload accepted when creating a new FIR.

    ``narrative`` is the only required field — all other fields are optional to
    tolerate partial / legacy data from semi-structured police systems such as
    eGujCop.  The ``narrative`` field accepts any Unicode text (Gujarati,
    English, mixed) and is the primary input for future NLP processing.
    """

    # narrative is REQUIRED — it is the core NLP input
    narrative: str

    fir_number: Optional[str] = None
    police_station: Optional[str] = None
    district: Optional[str] = None

    # Dates
    fir_date: Optional[date] = None
    occurrence_start: Optional[datetime] = None
    occurrence_end: Optional[datetime] = None

    # Legal classification
    primary_act: Optional[str] = None
    primary_sections: List[str] = Field(default_factory=list)
    sections_flagged: List[str] = Field(default_factory=list)

    # Participants extracted from OCR
    complainant_name: Optional[str] = None
    accused_name: Optional[str] = None

    # Investigating officer
    gpf_no: Optional[str] = None

    # Occurrence window (all four corners of the crime window)
    occurrence_from: Optional[date] = None
    occurrence_to: Optional[date] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None

    # Information received at PS
    info_received_date: Optional[date] = None
    info_received_time: Optional[str] = None

    # Type of information (oral / written)
    info_type: Optional[str] = None

    # Place of occurrence
    place_distance_km: Optional[str] = None
    place_address: Optional[str] = None

    # Extended complainant details
    complainant_father_name: Optional[str] = None
    complainant_age: Optional[int] = Field(default=None, ge=0, le=150)
    complainant_nationality: Optional[str] = None
    complainant_occupation: Optional[str] = None

    # Investigating / signing officer
    io_name: Optional[str] = None
    io_rank: Optional[str] = None
    io_number: Optional[str] = None
    officer_name: Optional[str] = None

    # Dispatch
    dispatch_date: Optional[date] = None
    dispatch_time: Optional[str] = None

    # Stolen property (arbitrary JSON)
    stolen_property: Optional[dict] = None

    # Completeness score (0-100)
    completeness_pct: Optional[float] = None

    # Original unprocessed text (falls back to narrative if omitted)
    raw_text: Optional[str] = None

    # Metadata
    source_system: str = "manual"

    # Nested entities
    complainants: List[ComplainantCreate] = Field(default_factory=list)
    accused: List[AccusedCreate] = Field(default_factory=list)

    @field_validator("narrative")
    @classmethod
    def validate_narrative(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Narrative is required and must not be blank.")
        return v

    @field_validator("primary_sections", mode="before")
    @classmethod
    def coerce_sections(cls, v):
        """Accept a bare string in addition to a list of strings."""
        if isinstance(v, str):
            return [v]
        if v is None:
            return []
        return v


class FIRResponse(BaseModel):
    """Full FIR representation returned by the API."""

    id: UUID
    fir_number: Optional[str] = None
    police_station: Optional[str] = None
    district: Optional[str] = None

    fir_date: Optional[date] = None
    occurrence_start: Optional[datetime] = None
    occurrence_end: Optional[datetime] = None

    primary_act: Optional[str] = None
    primary_sections: Optional[List[str]] = None
    sections_flagged: Optional[List[str]] = None

    complainant_name: Optional[str] = None
    accused_name: Optional[str] = None
    gpf_no: Optional[str] = None

    occurrence_from: Optional[date] = None
    occurrence_to: Optional[date] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None

    info_received_date: Optional[date] = None
    info_received_time: Optional[str] = None
    info_type: Optional[str] = None

    place_distance_km: Optional[str] = None
    place_address: Optional[str] = None

    complainant_father_name: Optional[str] = None
    complainant_age: Optional[int] = None
    complainant_nationality: Optional[str] = None
    complainant_occupation: Optional[str] = None

    io_name: Optional[str] = None
    io_rank: Optional[str] = None
    io_number: Optional[str] = None
    officer_name: Optional[str] = None

    dispatch_date: Optional[date] = None
    dispatch_time: Optional[str] = None

    stolen_property: Optional[dict] = None
    completeness_pct: Optional[float] = None

    narrative: Optional[str] = None
    raw_text: Optional[str] = None

    source_system: str
    created_at: datetime

    complainants: List[Complainant] = Field(default_factory=list)
    accused: List[Accused] = Field(default_factory=list)

    class Config:
        from_attributes = True
