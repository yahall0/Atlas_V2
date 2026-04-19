"""Playbook-based mindmap generator (ADR-D19 wiring).

Sister of ``generator.py``. Where ``generator.py`` builds a mindmap from
the model-authored JSON templates under ``backend/app/mindmap/templates/``,
this module builds a mindmap from the **Delhi Police Academy Compendium of
Scenarios** (KB ingested per ADR-D19).

Public API:

    generate_playbook_mindmap(fir_id, citations, conn=None, regenerate=False)
        Returns a ``MindmapResponse``-shaped dict assembled from the
        Compendium scenarios that match ``citations``. If ``conn`` is
        provided, the mindmap and its nodes are persisted to the existing
        ``chargesheet_mindmaps`` and ``mindmap_nodes`` tables.
        If ``conn`` is None (test/preview mode), the structure is returned
        without DB writes.

    has_playbook_for(citations) -> bool
        Cheap predicate: do any of the supplied citations resolve to a
        Compendium scenario? Used by ``generator.generate_mindmap`` to
        choose between playbook and template paths.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from app.legal_sections.io_scenarios import find_scenarios_for_sections
from app.legal_sections.scenario_adapter import (
    MindmapNode,
    build_chargesheet_mindmap,
    mindmap_nodes_for_scenario,
)

logger = logging.getLogger(__name__)

PLAYBOOK_MODEL_VERSION = "playbook-v1+delhi-pa-compendium-2024"


def has_playbook_for(citations: Iterable[str]) -> bool:
    """Return True if at least one Compendium scenario covers these citations."""
    try:
        return bool(find_scenarios_for_sections(citations))
    except Exception:
        return False


def generate_chargesheet_mindmap(
    fir: dict,
    citations: list[str],
    *,
    completeness_gaps: list[dict] | None = None,
    conn=None,
) -> dict | None:
    """Build the canonical 6-branch chargesheet-checklist mindmap.

    Hub label: ``FIR <number> | <classification>``.
    Branches: Applicable BNS Sections, Panchnama, Evidence,
    Blood/DNA/Forensics, Witness/Bayan, Gaps in FIR.

    Always returns a tree (even if no Compendium scenario matched), because
    the IO still needs the section list and FIR-gap branches. ``None`` only
    on hard failure.
    """
    fir_id = fir.get("id")
    if fir_id is None:
        logger.warning("generate_chargesheet_mindmap: fir has no id")
        return None

    root = build_chargesheet_mindmap(
        fir=fir,
        citations=list(citations),
        completeness_gaps=completeness_gaps or [],
    )
    case_category = (
        fir.get("nlp_classification") or "chargesheet_checklist"
    )
    root_dict = _node_to_dict(root)

    if conn is not None:
        try:
            mindmap_id = uuid.uuid4()
            _persist(conn, mindmap_id, uuid.UUID(str(fir_id)), case_category, root_dict)
            return {
                "id": str(mindmap_id),
                "fir_id": str(fir_id),
                "case_category": case_category,
                "template_version": "playbook-v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_by_model_version": PLAYBOOK_MODEL_VERSION,
                "status": "active",
                "root": root_dict,
            }
        except Exception:
            try:
                conn.rollback()
            except Exception:                                            # pragma: no cover
                pass
            logger.exception("Chargesheet mindmap persistence failed; returning preview")

    return {
        "id": None,
        "fir_id": str(fir_id),
        "case_category": case_category,
        "template_version": "playbook-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by_model_version": PLAYBOOK_MODEL_VERSION,
        "status": "preview",
        "root": root_dict,
    }


def _node_to_dict(node: MindmapNode, parent_id: str | None = None,
                  display_order: int = 0) -> dict:
    """Flatten a MindmapNode into the API-shape dict used by MindmapResponse."""
    nid = str(uuid.uuid4())
    children = []
    for i, child in enumerate(node.children):
        children.append(_node_to_dict(child, parent_id=nid, display_order=i))
    return {
        "id": nid,
        "parent_id": parent_id,
        "node_type": node.node_type,
        "title": node.title,
        "description_md": node.description_md,
        "source": node.source,
        "priority": node.priority,
        "display_order": display_order,
        "bns_section": node.bns_section,
        "metadata": dict(node.metadata) if node.metadata else {},
        "children": children,
    }


def _persist(conn, mindmap_id: uuid.UUID, fir_id: uuid.UUID,
             case_category: str, root_node: dict) -> None:
    """Persist mindmap + node tree (DFS) into the existing tables.

    Mirrors ``generator._insert_nodes`` structure but for playbook nodes.
    """
    from psycopg2.extras import Json  # noqa: PLC0415
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO chargesheet_mindmaps
               (id, fir_id, case_category, template_version,
                generated_at, generated_by_model_version, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'active')""",
            (mindmap_id, fir_id, case_category,
             "playbook-v1", now, PLAYBOOK_MODEL_VERSION),
        )

        # DFS insert
        stack: list[tuple[dict, str | None]] = [(root_node, None)]
        root_db_id: uuid.UUID | None = None
        while stack:
            node, parent_db_id = stack.pop()
            db_id = uuid.UUID(node["id"])
            # Map node_type to legacy enum (legacy schema doesn't know
            # 'suggested_section' yet — fall back to 'legal_section').
            node_type = node["node_type"]
            if node_type not in {"legal_section", "immediate_action", "evidence",
                                  "interrogation", "panchnama", "forensic",
                                  "witness_bayan", "gap_from_fir", "custom"}:
                node_type = "custom"
            # Map source enum: legacy schema only allows 4 values. The frontend
            # type allows 'playbook' but until migration 014 lands we persist
            # as 'static_template' and rely on `metadata.source_kind` for the
            # UI to detect playbook origin.
            metadata = dict(node.get("metadata") or {})
            metadata["source_kind"] = "playbook"
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title,
                    description_md, source, priority, requires_disclaimer,
                    display_order, bns_section, ipc_section, crpc_section,
                    metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, 'static_template', %s,
                           false, %s, %s, %s, %s, %s)""",
                (
                    db_id, mindmap_id, parent_db_id,
                    node_type, node["title"][:512], node["description_md"],
                    node["priority"], node["display_order"],
                    node["bns_section"], None, None, Json(metadata),
                ),
            )
            if parent_db_id is None:
                root_db_id = db_id
            for child in reversed(node["children"]):
                stack.append((child, db_id))

        cur.execute(
            "UPDATE chargesheet_mindmaps SET root_node_id = %s WHERE id = %s",
            (root_db_id, mindmap_id),
        )
    conn.commit()


def generate_playbook_mindmap(
    fir_id: uuid.UUID | str,
    citations: Iterable[str],
    *,
    conn=None,
    regenerate: bool = False,
) -> dict | None:
    """Build a Compendium-grounded mindmap for the given citations.

    Returns the mindmap structure (root node tree) or ``None`` if no
    Compendium scenario matches ``citations``.
    """
    citations = list(citations)
    scenarios = find_scenarios_for_sections(citations)
    if not scenarios:
        logger.info("No Compendium scenarios match citations %s; playbook path skipped", citations)
        return None

    # Identify which of the requested citations a Compendium scenario covers
    # vs which fall outside the Compendium's scope. Both lists are surfaced
    # to the IO so they know when to fall back to general guidance.
    covered: set[str] = set()
    for sc in scenarios:
        covered.update(sc.get("applicable_sections", []))
    uncovered = [c for c in citations if c not in covered]

    # Compose so the rendered tree is always 3 levels deep (hub → branch →
    # leaf). Multi-scenario merge keeps each scenario's phases as top-level
    # branches under the hub (NOT wrapped under a per-scenario sub-root).
    if len(scenarios) == 1 and not uncovered:
        # Single-scenario, fully covered: use the scenario's own root
        # (already 3 levels deep).
        root = mindmap_nodes_for_scenario(scenarios[0])
    else:
        # Build per-scenario subtrees, then *promote* their phase children
        # straight under the synthetic hub so depth stays at 3.
        if uncovered and len(scenarios) >= 1:
            title_suffix = (
                f"{len(scenarios)} playbook" + ("s" if len(scenarios) > 1 else "")
                + f" · {len(uncovered)} section"
                + ("s" if len(uncovered) > 1 else "")
                + " uncovered"
            )
        else:
            title_suffix = f"{len(scenarios)} playbooks apply"

        root = MindmapNode(
            title=f"Playbook · {title_suffix}",
            description_md=(
                f"**Sections requested:** {', '.join(citations)}\n\n"
                f"**Covered by Compendium:** {', '.join(sorted(covered)) or '—'}\n\n"
                + (f"**Not in Compendium:** {', '.join(uncovered)}\n\n"
                   "Use general investigation guidance for the un-covered "
                   "sections; the Compendium currently spans 20 scenarios."
                   if uncovered else "")
            ),
            node_type="legal_section",
            source="playbook",
            priority="critical",
            metadata={
                "scenario_ids": [sc["scenario_id"] for sc in scenarios],
                "covered_sections": sorted(covered),
                "uncovered_sections": uncovered,
                "applicable_sections": citations,
                "source_kind": "playbook",
            },
        )

        for sc in scenarios:
            sc_root = mindmap_nodes_for_scenario(sc)
            # When more than one scenario is being merged, prefix the phase
            # title with a short scenario tag so the IO can see which
            # scenario each branch came from.
            prefix = ""
            if len(scenarios) > 1:
                short_id = sc.get("scenario_id", "").replace("SCN_", "")
                prefix = f"[{short_id}] "
            for phase_branch in sc_root.children:
                if prefix:
                    phase_branch.title = prefix + phase_branch.title
                root.children.append(phase_branch)

        # Surface uncovered sections as a clean advisory branch with a
        # leaf per uncovered section, so the IO sees them in the tree.
        if uncovered:
            advisory = MindmapNode(
                title=f"⚠ Not in Compendium ({len(uncovered)})",
                description_md=(
                    f"These sections were recommended but the Delhi Police "
                    f"Academy Compendium does not include a dedicated chapter:\n\n"
                    + "\n".join(f"- {c}" for c in uncovered)
                    + "\n\n"
                    "Use general investigation guidance and the chargesheet "
                    "gap analyser for evidence checklists."
                ),
                node_type="custom",
                source="playbook",
                priority="recommended",
                metadata={
                    "advisory": True,
                    "uncovered_sections": uncovered,
                    "source_kind": "playbook",
                },
            )
            for cit in uncovered:
                advisory.children.append(MindmapNode(
                    title=cit,
                    description_md=(
                        f"**{cit}** is not in the Compendium of Scenarios. "
                        "Refer to the statute text and the chargesheet gap "
                        "analyser for guidance."
                    ),
                    node_type="custom",
                    source="playbook",
                    priority="recommended",
                    metadata={"uncovered": True, "source_kind": "playbook"},
                ))
            root.children.append(advisory)

    # Convert to dict tree; use first scenario's name as case_category
    case_category = scenarios[0]["scenario_name"]
    root_dict = _node_to_dict(root)

    if conn is not None:
        try:
            mindmap_id = uuid.uuid4()
            _persist(conn, mindmap_id, uuid.UUID(str(fir_id)), case_category, root_dict)
        except Exception as exc:
            # Roll back so the connection is reusable by the caller's
            # template-path fallback (the failed INSERT poisoned the tx).
            try:
                conn.rollback()
            except Exception:                                            # pragma: no cover
                pass
            logger.exception(
                "Playbook mindmap persistence failed; returning structure only (rolled back)"
            )
        else:
            return {
                "id": str(mindmap_id),
                "fir_id": str(fir_id),
                "case_category": case_category,
                "template_version": "playbook-v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generated_by_model_version": PLAYBOOK_MODEL_VERSION,
                "status": "active",
                "root": root_dict,
                "playbook_scenarios": [
                    {"scenario_id": sc["scenario_id"], "name": sc["scenario_name"],
                     "page_start": sc["page_start"], "page_end": sc["page_end"]}
                    for sc in scenarios
                ],
            }

    return {
        "id": None,
        "fir_id": str(fir_id),
        "case_category": case_category,
        "template_version": "playbook-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by_model_version": PLAYBOOK_MODEL_VERSION,
        "status": "preview",
        "root": root_dict,
        "playbook_scenarios": [
            {"scenario_id": sc["scenario_id"], "name": sc["scenario_name"],
             "page_start": sc["page_start"], "page_end": sc["page_end"]}
            for sc in scenarios
        ],
    }


__all__ = [
    "PLAYBOOK_MODEL_VERSION",
    "has_playbook_for",
    "generate_playbook_mindmap",
    "generate_chargesheet_mindmap",
]
