"""Pydantic v2 schemas for the legal_sections module.

These schemas form the API contract honoured by the section recommender and
the legal-knowledge retrieval surface. ADR-D15 (sub-clause precision) is the
binding reference for the citation-related fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------- Sub-clause types ---------- #

SchemeCode = Literal[
    "num", "alpha_lower", "alpha_upper",
    "roman_lower", "roman_upper", "ordinal", "proviso",
]


class SubClauseModel(BaseModel):
    """Addressable sub-unit of a statutory section (ADR-D15)."""

    section_id: str = Field(..., description="Parent section identifier, e.g. 'BNS_305'.")
    label: str = Field(..., description="Raw marker as it appears in the source, e.g. '(a)' or 'Provided that'.")
    canonical_label: str = Field(..., description="Normalised marker form.")
    scheme: SchemeCode = Field(..., description="Enumeration scheme classification.")
    depth: int = Field(..., ge=1, description="Nesting depth; 1 for top-level.")
    parent_path: list[str] = Field(default_factory=list, description="Ancestor labels in document order.")
    canonical_citation: str = Field(..., description="Court-ready citation, e.g. 'BNS 305(a)'.")
    addressable_id: str = Field(..., description="URL-safe identifier, e.g. 'BNS_305_a'.")
    text: str = Field(..., description="Verbatim text span of this sub-clause.")
    offset_start: int
    offset_end: int


# ---------- Section types ---------- #


class SectionModel(BaseModel):
    """Verbatim canonical record of one statutory section."""

    id: str = Field(..., description="Composite key, e.g. 'IPC_302' or 'BNS_103'.")
    act: Literal["IPC", "BNS"] = Field(..., description="Originating act.")
    section_number: str = Field(..., description="Section number; may include letter suffix (e.g. '120A').")
    section_title: str | None
    chapter_number: str | None
    chapter_title: str | None
    full_text: str = Field(..., description="Verbatim section text.")
    sub_clauses: list[SubClauseModel] = Field(
        default_factory=list,
        description="Structural decomposition; empty when the section has no enumerated alternatives.",
    )
    illustrations: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    cross_references: list[str] = Field(default_factory=list)
    source_page_start: int | None
    source_page_end: int | None
    cognizable: bool | None = None
    bailable: bool | None = None
    triable_by: str | None = None
    compoundable: bool | None = None
    punishment: str | None = None


# ---------- Recommendation types ---------- #


class SectionRecommendation(BaseModel):
    """One recommendation entry returned by the section recommender.

    Fields ``sub_clause``, ``canonical_citation`` and ``addressable_id`` are
    populated when the matched evidence corresponds to a specific sub-clause
    rather than the umbrella section. See ADR-D15.
    """

    section_id: str = Field(..., description="Parent section identifier, e.g. 'BNS_305'.")
    act: Literal["IPC", "BNS"]
    section_number: str
    section_title: str

    # Sub-clause precision fields
    sub_clause_label: str | None = Field(
        None,
        description="Sub-clause marker, e.g. '(a)' or 'Provided that'. Null when the recommendation is at the umbrella section level.",
    )
    canonical_citation: str = Field(
        ...,
        description="Court-ready citation, e.g. 'BNS 305(a)' or 'BNS 305' when no sub-clause matched.",
    )
    addressable_id: str = Field(
        ...,
        description="URL-safe identifier including sub-clause if present, e.g. 'BNS_305_a'.",
    )

    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale_quote: str = Field(
        ...,
        description="Verbatim text of the matched sub-clause (or section, if no sub-clause).",
    )
    matching_fir_facts: list[str] = Field(default_factory=list)
    related_sections: list[str] = Field(default_factory=list)
    borderline_with: list[str] = Field(default_factory=list)
    operator_note: str | None = None


class RecommendationResponse(BaseModel):
    fir_id: str
    act_basis: Literal["IPC", "BNS"]
    occurrence_start: str | None
    commission_window: dict | None = None
    model_version: str
    generated_at: str
    recommendations: list[SectionRecommendation]
