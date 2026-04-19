"""Adapter: IO Scenarios KB ⇄ Mindmap engine ⇄ Recommender.

Two surfaces:

1. ``playbook_for_recommendation(citations)`` — given a recommendation's
   citations, returns the Compendium scenario(s) that govern those sections.
   Used to enrich each ``SectionRecommendation`` with a ``playbook_reference``
   field (Delhi Police Academy authority).

2. ``mindmap_nodes_for_scenario(scenario)`` — converts a Compendium scenario's
   phase / sub-block / item tree into the mindmap node shape that the
   existing ``backend/app/mindmap/generator.py`` consumes. Drop-in replacement
   for the model-generated templates.

3. ``checklist_for_scenarios(scenarios)`` — aggregates evidence, documentation
   and form requirements across multiple matching scenarios. Used by the
   chargesheet gap analyser as the ground-truth checklist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .io_scenarios import find_scenarios_for_sections, load_kb


@dataclass
class PlaybookReference:
    scenario_id: str
    scenario_name: str
    source_authority: str
    page_start: int
    page_end: int


@dataclass
class MindmapNode:
    """Minimal node shape compatible with backend/app/mindmap/generator.py."""
    title: str
    description_md: str = ""
    node_type: str = "investigation_step"
    source: str = "playbook"
    priority: str = "recommended"
    bns_section: str | None = None
    metadata: dict = field(default_factory=dict)
    children: list["MindmapNode"] = field(default_factory=list)


def playbook_for_recommendation(citations: Iterable[str]) -> list[PlaybookReference]:
    """Return Compendium playbook references for a list of section citations."""
    matches = find_scenarios_for_sections(citations)
    return [
        PlaybookReference(
            scenario_id=sc["scenario_id"],
            scenario_name=sc["scenario_name"],
            source_authority=sc["source_authority"],
            page_start=sc["page_start"],
            page_end=sc["page_end"],
        )
        for sc in matches
    ]


def mindmap_nodes_for_scenario(scenario: dict) -> MindmapNode:
    """Build a mindmap tree rooted at the scenario, with phases → sub-blocks → items.

    Each item carries the legal_refs and form requirements as metadata so the
    IO can drill in.
    """
    root = MindmapNode(
        title=f"{scenario['scenario_name']} — Investigation Playbook",
        description_md=(
            f"**Applicable sections:** {', '.join(scenario['applicable_sections'])}\n\n"
            f"**Punishment:** {scenario['punishment_summary']}\n\n"
            f"**Source:** {scenario['source_authority']} (pp. {scenario['page_start']}–{scenario['page_end']})\n\n"
            f"{scenario.get('case_facts_template', '')}"
        ),
        node_type="legal_section",
        source="playbook",
        priority="critical",
        metadata={
            "scenario_id": scenario["scenario_id"],
            "applicable_sections": scenario["applicable_sections"],
            "page_start": scenario["page_start"],
            "page_end": scenario["page_end"],
        },
    )

    for phase in scenario["phases"]:
        phase_node = MindmapNode(
            title=f"{phase['number']}. {phase['title']}",
            node_type=_phase_to_node_type(phase["title"]),
            source="playbook",
            priority="critical",
            metadata={"phase": phase["title"], "phase_number": phase["number"]},
        )
        for sb in phase["sub_blocks"]:
            sb_node = MindmapNode(
                title=f"{sb['label']}. {sb['title']}",
                node_type="immediate_action",
                source="playbook",
                priority="recommended",
            )
            for item in sb["items"]:
                item_node = MindmapNode(
                    title=f"{item['marker']} {item['text'][:120]}{'...' if len(item['text']) > 120 else ''}",
                    description_md=item["text"],
                    node_type=_item_to_node_type(item),
                    source="playbook",
                    priority="critical" if item["is_evidence"] else "recommended",
                    metadata={
                        "actors": item.get("actors", []),
                        "legal_refs": item.get("legal_refs", []),
                        "forms": item.get("forms", []),
                        "deadline": item.get("deadline"),
                        "is_evidence": item.get("is_evidence", False),
                    },
                )
                sb_node.children.append(item_node)
            phase_node.children.append(sb_node)
        root.children.append(phase_node)
    return root


def _phase_to_node_type(phase_title: str) -> str:
    t = phase_title.upper()
    if "CALL" in t or "INFORMATION" in t:
        return "immediate_action"
    if "REGISTRATION" in t or "FIR" in t:
        return "immediate_action"
    if "INVESTIGATION" in t:
        return "evidence"
    if "FINAL REPORT" in t or "CHARGESHEET" in t:
        return "panchnama"
    return "immediate_action"


def _item_to_node_type(item: dict) -> str:
    if item.get("is_evidence"):
        return "evidence"
    text = item["text"].lower()
    if "site plan" in text or "seizure" in text or "panchnama" in text:
        return "panchnama"
    if "magistrate" in text or "court" in text or "tip" in text:
        return "interrogation"
    if "witness" in text or "statement" in text:
        return "witness_bayan"
    if "fsl" in text or "forensic" in text or "dna" in text or "pm report" in text:
        return "forensic"
    return "immediate_action"


def checklist_for_scenarios(scenarios: list[dict]) -> dict:
    """Aggregate evidence, documentation, forms, and deadlines across scenarios."""
    evidence: list[str] = []
    forms: list[str] = []
    deadlines: list[str] = []
    docs: list[str] = []
    actors_required: set[str] = set()

    for sc in scenarios:
        for e in sc.get("evidence_catalogue", []):
            if e not in evidence:
                evidence.append(e)
        for f in sc.get("forms_required", []):
            if f not in forms:
                forms.append(f)
        for d in sc.get("deadlines", []):
            if d not in deadlines:
                deadlines.append(d)
        for ph in sc.get("phases", []):
            for sb in ph.get("sub_blocks", []):
                for item in sb.get("items", []):
                    actors_required.update(item.get("actors", []))

    return {
        "evidence_to_collect": evidence,
        "forms_required": forms,
        "deadlines": deadlines,
        "documentation_required": docs,
        "actors_required": sorted(actors_required),
        "source_scenarios": [
            {"scenario_id": sc["scenario_id"], "name": sc["scenario_name"]}
            for sc in scenarios
        ],
    }


__all__ = [
    "PlaybookReference",
    "MindmapNode",
    "playbook_for_recommendation",
    "mindmap_nodes_for_scenario",
    "checklist_for_scenarios",
]
