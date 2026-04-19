"""Adapter: IO Scenarios KB ⇄ Mindmap engine ⇄ Recommender.

Surfaces:

1. ``playbook_for_recommendation(citations)`` — given a recommendation's
   citations, returns the Compendium scenario(s) that govern those sections.
2. ``mindmap_nodes_for_scenario(scenario)`` — phases-first per-scenario tree.
3. ``checklist_for_scenarios(scenarios)`` — aggregated evidence/forms/etc.
4. ``build_chargesheet_mindmap(...)`` — canonical chargesheet-checklist
   mindmap with 6 fixed branches: BNS sections, panchnama, evidence,
   forensics, witness/bayan, gaps in FIR. Pulls leaves from the Compendium
   KB and the BNS/IPC section corpus.
5. ``lookup_section(citation)`` — fetch section title, body, punishment
   from the BNS/IPC JSONL corpus.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .io_scenarios import find_scenarios_for_sections, load_kb

_DATA = Path(__file__).resolve().parent / "data"
_SECTIONS_CACHE: dict[str, dict] | None = None


def _load_sections_corpus() -> dict[str, dict]:
    """Lazy-load the BNS + IPC verbatim corpus into a citation-keyed map."""
    global _SECTIONS_CACHE
    if _SECTIONS_CACHE is not None:
        return _SECTIONS_CACHE
    out: dict[str, dict] = {}
    for path in (_DATA / "bns_sections.jsonl", _DATA / "ipc_sections.jsonl"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                act = rec["act"]
                # Index every sub-clause's canonical citation
                for sc in rec.get("sub_clauses", []):
                    out[sc["canonical_citation"]] = {
                        "act": act,
                        "section_number": rec["section_number"],
                        "section_title": rec.get("section_title"),
                        "sub_clause_label": sc.get("canonical_label"),
                        "text": sc.get("text"),
                        "full_text": rec.get("full_text"),
                    }
                # Also index the umbrella section
                umbrella = f"{act} {rec['section_number']}"
                out.setdefault(umbrella, {
                    "act": act,
                    "section_number": rec["section_number"],
                    "section_title": rec.get("section_title"),
                    "sub_clause_label": None,
                    "text": rec.get("full_text"),
                    "full_text": rec.get("full_text"),
                })
    _SECTIONS_CACHE = out
    return out


def lookup_section(citation: str) -> dict | None:
    """Return verbatim section data for a citation like ``BNS 305(a)``."""
    return _load_sections_corpus().get(citation)


# ---------- Item categorisation (for the canonical chargesheet mindmap) ---------- #

_PANCHNAMA_KEYWORDS = re.compile(
    r"\b(panchnama|panchanama|seizure\s+memo|site\s+plan|sample\s+seal|"
    r"forwarding\s+letter|road\s+certificate|exhibit|recovery\s+memo|"
    r"chain\s+of\s+custody)\b",
    re.IGNORECASE,
)
_FORENSICS_KEYWORDS = re.compile(
    r"\b(blood|dna|FSL|forensic|autopsy|post[- ]?mortem|PM\s+report|"
    r"finger\s*print|chance\s*print|gun\s*shot\s*residue|GSR|ballistic|"
    r"viscera|chemical\s+analysis|toxicology)\b",
    re.IGNORECASE,
)
_WITNESS_KEYWORDS = re.compile(
    r"\b(witness|statement|bayan|180\s*BNSS|183\s*BNSS|TIP|test\s+identification|"
    r"declaration|deposition|panch\b|examined\b|examination\s+of\s+witness)\b",
    re.IGNORECASE,
)
_EVIDENCE_KEYWORDS = re.compile(
    r"\b(MLC|medical|hospital|injury|exhibit|CCTV|hash\s+value|video|photograph|"
    r"recording|CDR|IPDR|electronic|mobile|laptop|computer|weapon|blood|"
    r"clothes|garment)\b",
    re.IGNORECASE,
)


def _categorise_item(item: dict) -> str | None:
    """Return one of {'panchnama','forensics','witness','evidence'} or None.

    Categories are checked in priority order — most specific first — and
    each item is assigned to at most one category.
    """
    text = item.get("text", "")
    if _PANCHNAMA_KEYWORDS.search(text):
        return "panchnama"
    if _FORENSICS_KEYWORDS.search(text):
        return "forensics"
    if _WITNESS_KEYWORDS.search(text):
        return "witness"
    if item.get("is_evidence") or _EVIDENCE_KEYWORDS.search(text):
        return "evidence"
    return None


def categorise_compendium_items(scenarios: list[dict]) -> dict[str, list[dict]]:
    """Walk all items in the matched scenarios and bucket them.

    Returns a dict with keys ``panchnama``, ``forensics``, ``witness``,
    ``evidence``. Each value is a list of item dicts (sorted, deduplicated
    by text). Each item carries its source scenario_id and phase context
    so the leaf can show where it came from.
    """
    buckets: dict[str, list[dict]] = {
        "panchnama": [], "forensics": [], "witness": [], "evidence": [],
    }
    seen_text: set[str] = set()
    for sc in scenarios:
        for ph in sc.get("phases", []):
            for sb in ph.get("sub_blocks", []):
                for item in sb.get("items", []):
                    text = item.get("text", "").strip()
                    if not text or text in seen_text:
                        continue
                    cat = _categorise_item(item)
                    if not cat:
                        continue
                    seen_text.add(text)
                    buckets[cat].append({
                        **item,
                        "source_scenario_id": sc["scenario_id"],
                        "source_scenario_name": sc["scenario_name"],
                        "source_phase": ph.get("title"),
                        "source_sub_block": sb.get("title"),
                    })
    return buckets


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
    """Build a 3-level mindmap tree (hub → phase → sub-block leaf).

    The renderer in ``frontend/src/components/mindmap/MindmapPanel.tsx`` is
    designed for hub → branch → leaf. To stay compatible, the per-item
    detail (numbered (i), (ii), (iii) instructions) is collapsed into each
    sub-block leaf's ``description_md`` (markdown checklist) and exposed
    via ``metadata.items`` for the NodeDetailDrawer to render.
    """
    sections_short = ", ".join(scenario["applicable_sections"][:3])
    root = MindmapNode(
        title=f"Playbook · {sections_short}",
        description_md=(
            f"**{scenario['scenario_name']}**\n\n"
            f"**Sections:** {', '.join(scenario['applicable_sections'])}\n\n"
            f"**Punishment:** {scenario['punishment_summary']}\n\n"
            f"**Source:** {scenario['source_authority']} "
            f"(pp. {scenario['page_start']}–{scenario['page_end']})\n\n"
            f"{scenario.get('case_facts_template', '')}"
        ),
        node_type="legal_section",
        source="playbook",
        priority="critical",
        metadata={
            "scenario_id": scenario["scenario_id"],
            "scenario_name": scenario["scenario_name"],
            "applicable_sections": scenario["applicable_sections"],
            "page_start": scenario["page_start"],
            "page_end": scenario["page_end"],
            "source_kind": "playbook",
        },
    )

    for phase in scenario["phases"]:
        # Skip empty phases (e.g. parser couldn't find sub-blocks AND there
        # were no inline items either). Surfaces nothing useful in the UI.
        non_empty_subs = [sb for sb in phase["sub_blocks"] if sb.get("items")]
        if not non_empty_subs:
            continue

        phase_node = MindmapNode(
            title=f"{phase['number']}. {phase['title']}",
            node_type=_phase_to_node_type(phase["title"]),
            source="playbook",
            priority="critical",
            metadata={
                "phase": phase["title"],
                "phase_number": phase["number"],
                "source_kind": "playbook",
            },
        )

        for sb in non_empty_subs:
            # Aggregate items as both markdown (for the drawer) and a
            # structured list (for the UI to iterate). Cap the visible
            # title at the sub-block label; items live in description_md.
            items_md_lines = []
            forms_seen: list[str] = []
            deadlines_seen: list[str] = []
            actors_seen: set[str] = set()
            evidence_count = 0
            structured_items: list[dict] = []

            for item in sb["items"]:
                items_md_lines.append(f"- **{item['marker']}** {item['text']}")
                for f in item.get("forms", []):
                    if f not in forms_seen:
                        forms_seen.append(f)
                if item.get("deadline") and item["deadline"] not in deadlines_seen:
                    deadlines_seen.append(item["deadline"])
                actors_seen.update(item.get("actors", []))
                if item.get("is_evidence"):
                    evidence_count += 1
                structured_items.append({
                    "marker": item["marker"],
                    "text": item["text"],
                    "actors": item.get("actors", []),
                    "legal_refs": item.get("legal_refs", []),
                    "forms": item.get("forms", []),
                    "deadline": item.get("deadline"),
                    "is_evidence": item.get("is_evidence", False),
                })

            description_parts = []
            if forms_seen:
                description_parts.append(f"**Forms / artefacts:** {', '.join(forms_seen)}")
            if deadlines_seen:
                description_parts.append(f"**Deadlines:** {', '.join(deadlines_seen)}")
            if actors_seen:
                description_parts.append(f"**Actors:** {', '.join(sorted(actors_seen))}")
            if items_md_lines:
                description_parts.append("**Steps:**")
                description_parts.append("\n".join(items_md_lines))
            description_md = "\n\n".join(description_parts)

            # Choose node_type based on dominant content
            if evidence_count >= max(1, len(sb["items"]) // 3):
                node_type = "evidence"
            else:
                node_type = "immediate_action"

            # Build a clean leaf title. When the parser found items but no
            # explicit "a./b./c." heading, the sub-block carries placeholder
            # values — render as "Steps" rather than the placeholder text.
            sb_label = sb.get("label", "·")
            sb_title = sb.get("title", "")
            if not sb_title or sb_title.startswith("(no sub-block") or sb_title == "(default)":
                leaf_title = f"Steps ({len(structured_items)})"
            else:
                leaf_title = f"{sb_label}. {sb_title}"[:200]
            sb_node = MindmapNode(
                title=leaf_title,
                description_md=description_md,
                node_type=node_type,
                source="playbook",
                priority="critical" if evidence_count > 0 else "recommended",
                metadata={
                    "sub_block_label": sb["label"],
                    "sub_block_title": sb["title"],
                    "item_count": len(sb["items"]),
                    "evidence_count": evidence_count,
                    "forms": forms_seen,
                    "deadlines": deadlines_seen,
                    "actors": sorted(actors_seen),
                    "items": structured_items,
                    "source_kind": "playbook",
                },
            )
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


def _trim(text: str, n: int = 95) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _section_leaf(citation: str) -> MindmapNode:
    rec = lookup_section(citation)
    if rec:
        title = f"{citation} — {rec.get('section_title') or ''}".strip(" —")
        body = rec.get("text") or rec.get("full_text") or ""
        desc = (
            f"**{citation}**\n\n"
            f"**Title:** {rec.get('section_title') or '(no title)'}\n\n"
            f"**Verbatim text:**\n\n{body[:1500]}"
            + ("\n\n…(truncated)" if len(body) > 1500 else "")
        )
    else:
        title = citation
        desc = f"**{citation}** — section text not found in corpus."
    return MindmapNode(
        title=_trim(title, 110),
        description_md=desc,
        node_type="legal_section",
        source="playbook",
        priority="critical",
        bns_section=citation if citation.startswith("BNS") else None,
        metadata={"citation": citation, "source_kind": "playbook"},
    )


def _item_leaf(item: dict, fallback_node_type: str) -> MindmapNode:
    """Convert a categorised Compendium item into a leaf node.

    The leaf title strips the source-document numbering ((i), (ii), …) so
    the mindmap reads as a clean checklist. The marker is preserved in
    metadata for traceability.
    """
    forms = item.get("forms") or []
    deadline = item.get("deadline")
    actors = item.get("actors") or []
    raw_text = (item.get("text") or "").strip()
    # The Compendium markers ((i), (ii), (v), etc.) are useful for citation
    # back to source pages but visually noisy in mindmap leaves and the
    # checklist. Drop them from the rendered title.
    title_text = re.sub(r"^\(\s*[ivxlcdm0-9]+\s*\)\s*", "", raw_text, flags=re.IGNORECASE)
    title_text = title_text or raw_text  # fallback if regex stripped everything
    desc_lines = []
    if forms:
        desc_lines.append(f"**Forms / artefacts:** {', '.join(forms)}")
    if deadline:
        desc_lines.append(f"**Deadline:** {deadline}")
    if actors:
        desc_lines.append(f"**Actors:** {', '.join(actors)}")
    desc_lines.append(f"**Step:** {raw_text}")
    if item.get("source_scenario_name"):
        desc_lines.append(
            f"\n*Source: Compendium — {item['source_scenario_name']}"
            + (f" → {item['source_phase']}" if item.get("source_phase") else "")
            + "*"
        )
    return MindmapNode(
        title=_trim(title_text, 110),
        description_md="\n\n".join(desc_lines),
        node_type=fallback_node_type,
        source="playbook",
        priority="critical" if item.get("is_evidence") else "recommended",
        metadata={
            "marker": item["marker"],
            "actors": actors,
            "legal_refs": item.get("legal_refs") or [],
            "forms": forms,
            "deadline": deadline,
            "is_evidence": item.get("is_evidence", False),
            "source_scenario_id": item.get("source_scenario_id"),
            "source_scenario_name": item.get("source_scenario_name"),
            "source_kind": "playbook",
        },
    )


def _gap_leaf(gap: dict) -> MindmapNode:
    title = gap.get("title") or gap.get("description") or "FIR completeness gap"
    return MindmapNode(
        title=_trim(title, 90),
        description_md=(
            (gap.get("description") or title)
            + (f"\n\n**Severity:** {gap['severity']}" if gap.get("severity") else "")
        ),
        node_type="gap_from_fir",
        source="completeness_engine",
        priority="critical",
        metadata={**gap, "source_kind": "completeness"},
    )


def build_chargesheet_mindmap(
    fir: dict,
    citations: list[str],
    completeness_gaps: list[dict] | None = None,
) -> MindmapNode:
    """Build the canonical chargesheet-checklist mindmap.

    Hub label: ``FIR <fir_number> | <classification>``
    Branches (always in this order):
      1. Applicable BNS Sections — one leaf per recommended citation, with
         the verbatim section text and punishment from the corpus.
      2. Panchnama — items mentioning seizure memo, site plan, sample seal,
         road certificate, recovery memo, etc.
      3. Evidence — generic evidence items (MLC, CCTV, exhibits, weapons).
      4. Blood / DNA / Forensics — items mentioning DNA, FSL, autopsy,
         post-mortem, GSR, ballistics, fingerprints, viscera, toxicology.
      5. Witness / Bayan — items mentioning witness statements (BNSS § 180,
         § 183), TIP, panch witnesses, examined witnesses.
      6. Gaps in FIR — completeness flags from the FIR's existing analysis.

    Each leaf is sourced from the Delhi Police Academy Compendium of
    Scenarios (per ADR-D19) when applicable; uncovered citations and
    gaps still produce visible leaves so the IO has a complete checklist.
    """
    fir_number = fir.get("fir_number") or "(no number)"
    classification = (
        fir.get("nlp_classification")
        or fir.get("primary_act")
        or "unclassified"
    )

    # Pull Compendium scenarios that match the citations
    scenarios = find_scenarios_for_sections(citations) if citations else []
    buckets = categorise_compendium_items(scenarios)

    hub = MindmapNode(
        title=f"FIR {fir_number} | {classification}",
        description_md=(
            f"**FIR number:** {fir_number}\n\n"
            f"**Classification:** {classification}\n\n"
            f"**Sections recommended:** {', '.join(citations) if citations else '—'}\n\n"
            f"**Compendium scenarios matched:** "
            + (", ".join(sc["scenario_name"] for sc in scenarios) if scenarios else "—")
        ),
        node_type="legal_section",
        source="playbook",
        priority="critical",
        metadata={
            "fir_number": fir_number,
            "classification": classification,
            "citations": citations,
            "scenario_ids": [sc["scenario_id"] for sc in scenarios],
            "source_kind": "playbook",
        },
    )

    # Branch 1 — Applicable BNS Sections
    sections_branch = MindmapNode(
        title=f"Applicable BNS Sections ({len(citations)})",
        node_type="legal_section",
        source="playbook",
        priority="critical",
        metadata={"section_count": len(citations), "source_kind": "playbook"},
    )
    for cit in citations:
        sections_branch.children.append(_section_leaf(cit))
    if not citations:
        sections_branch.children.append(MindmapNode(
            title="No sections recommended yet",
            description_md="Either the FIR has no `primary_sections` recorded or the recommender has not run.",
            node_type="custom",
            source="playbook",
            priority="recommended",
        ))
    hub.children.append(sections_branch)

    # Helper to build a category branch
    def _category_branch(title: str, node_type: str, items: list[dict],
                         empty_note: str) -> MindmapNode:
        branch = MindmapNode(
            title=f"{title} ({len(items)})",
            node_type=node_type,
            source="playbook",
            priority="critical",
            metadata={"item_count": len(items), "source_kind": "playbook"},
        )
        if items:
            # Cap visible mindmap leaves to keep the layout legible. The
            # full list still lives in branch.metadata.items for the
            # checklist + drawer to render.
            VISIBLE = 10
            for item in items[:VISIBLE]:
                branch.children.append(_item_leaf(item, fallback_node_type=node_type))
            if len(items) > VISIBLE:
                branch.children.append(MindmapNode(
                    title=f"+{len(items) - VISIBLE} more — see Checklist tab",
                    description_md=(
                        f"{len(items) - VISIBLE} additional items not rendered in the "
                        "mindmap to keep the layout readable. The complete list is "
                        "available in the Checklist tab and via the node-detail drawer."
                    ),
                    node_type="custom",
                    source="playbook",
                    priority="recommended",
                ))
        else:
            branch.children.append(MindmapNode(
                title=empty_note,
                description_md=empty_note,
                node_type="custom",
                source="playbook",
                priority="recommended",
            ))
        branch.metadata["items"] = items  # full list for the drawer
        return branch

    # Branch 2 — Panchnama
    hub.children.append(_category_branch(
        "Panchnama",
        node_type="panchnama",
        items=buckets["panchnama"],
        empty_note="No panchnama-specific steps in the matched Compendium scenarios — "
                   "follow standard panchnama procedure (site plan, seizure memo, "
                   "sample seal, road certificate from Malkhana).",
    ))

    # Branch 3 — Evidence
    hub.children.append(_category_branch(
        "Evidence",
        node_type="evidence",
        items=buckets["evidence"],
        empty_note="No evidence-specific steps surfaced — collect MLC, CCTV (with "
                   "hash value), exhibits, weapons used, electronic records.",
    ))

    # Branch 4 — Blood / DNA / Forensics
    hub.children.append(_category_branch(
        "Blood / DNA / Forensics",
        node_type="forensic",
        items=buckets["forensics"],
        empty_note="No forensic-specific steps surfaced — consider DNA profiling, "
                   "FSL examination, autopsy / PM report (if death involved), "
                   "fingerprint / chance-print analysis as applicable.",
    ))

    # Branch 5 — Witness / Bayan
    hub.children.append(_category_branch(
        "Witness / Bayan",
        node_type="witness_bayan",
        items=buckets["witness"],
        empty_note="No witness-specific steps surfaced — record statements under "
                   "BNSS § 180, conduct TIP under § 54 BNSS, consider § 183 BNSS "
                   "statement before Magistrate where required.",
    ))

    # Branch 6 — Gaps in FIR
    gaps_branch = MindmapNode(
        title=f"Gaps in FIR ({len(completeness_gaps or [])})",
        node_type="gap_from_fir",
        source="completeness_engine",
        priority="critical",
        metadata={"source_kind": "completeness"},
    )
    for gap in (completeness_gaps or []):
        gaps_branch.children.append(_gap_leaf(gap))
    if not completeness_gaps:
        gaps_branch.children.append(MindmapNode(
            title="FIR registration complete",
            description_md="No structural gaps detected in the FIR record.",
            node_type="custom",
            source="completeness_engine",
            priority="recommended",
        ))
    hub.children.append(gaps_branch)

    return hub


__all__ = [
    "PlaybookReference",
    "MindmapNode",
    "playbook_for_recommendation",
    "mindmap_nodes_for_scenario",
    "checklist_for_scenarios",
    "categorise_compendium_items",
    "build_chargesheet_mindmap",
    "lookup_section",
]
