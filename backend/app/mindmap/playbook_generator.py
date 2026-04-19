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
        ``chargesheet_mindmaps`` and ``chargesheet_mindmap_nodes`` tables.
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
            cur.execute(
                """INSERT INTO chargesheet_mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title,
                    description_md, source, priority, display_order,
                    bns_section, ipc_section, crpc_section, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    db_id, mindmap_id, parent_db_id,
                    node["node_type"], node["title"], node["description_md"],
                    node["source"], node["priority"], node["display_order"],
                    node["bns_section"], None, None, Json(node["metadata"]),
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

    # Compose: a synthetic "Investigation playbook" root with each matching
    # scenario as a top-level branch. This handles cases where multiple
    # scenarios apply (e.g. assault + dacoity in the same FIR).
    if len(scenarios) == 1:
        root = mindmap_nodes_for_scenario(scenarios[0])
    else:
        root = MindmapNode(
            title=f"Investigation Playbook — {len(scenarios)} scenarios apply",
            description_md=f"Sections covered: {', '.join(citations)}",
            node_type="legal_section",
            source="playbook",
            priority="critical",
            metadata={
                "scenario_ids": [sc["scenario_id"] for sc in scenarios],
                "applicable_sections": citations,
            },
            children=[mindmap_nodes_for_scenario(sc) for sc in scenarios],
        )

    # Convert to dict tree; use first scenario's name as case_category
    case_category = scenarios[0]["scenario_name"]
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
                "playbook_scenarios": [
                    {"scenario_id": sc["scenario_id"], "name": sc["scenario_name"],
                     "page_start": sc["page_start"], "page_end": sc["page_end"]}
                    for sc in scenarios
                ],
            }
        except Exception:
            logger.exception("Playbook mindmap persistence failed; returning structure only")

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
]
