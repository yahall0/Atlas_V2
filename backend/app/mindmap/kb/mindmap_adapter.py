"""KB-to-Mindmap adapter — T53-M-KB-4.

Converts KnowledgeBundle into mindmap nodes, replacing the old template
assembly. Called by generator.py when KB is available.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List, Optional, Set, Tuple

from psycopg2.extensions import connection as PgConnection

from app.mindmap.kb.schemas import (
    KnowledgeBundle,
    KnowledgeNodeResponse,
    OffenceWithNodes,
)

logger = logging.getLogger(__name__)

# Map KB branch_type → mindmap node_type
_BRANCH_TO_NODE_TYPE = {
    "legal_section": "legal_section",
    "immediate_action": "immediate_action",
    "panchnama": "panchnama",
    "evidence": "evidence",
    "witness_bayan": "witness_bayan",
    "forensic": "forensic",
    "gap_historical": "gap_from_fir",
    "procedural_safeguard": "evidence",  # mapped to evidence for display
}

# Map KB tier → mindmap source
_TIER_TO_SOURCE = {
    "canonical": "static_template",
    "judgment_derived": "ml_suggestion",
}


def insert_nodes_from_kb(
    conn: PgConnection,
    mindmap_id: uuid.UUID,
    bundle: KnowledgeBundle,
) -> uuid.UUID:
    """Insert mindmap nodes from a KnowledgeBundle. Returns root_node_id.

    Groups all KB nodes by branch_type, creates branch parent nodes,
    then inserts child nodes under each branch.
    """
    seen: Set[Tuple[str, str]] = set()
    root_id = uuid.uuid4()
    order = 0

    with conn.cursor() as cur:
        # Root node
        cur.execute(
            """INSERT INTO mindmap_nodes
               (id, mindmap_id, parent_id, node_type, title, description_md,
                source, priority, requires_disclaimer, display_order, metadata)
               VALUES (%s, %s, NULL, 'evidence', %s, %s, 'static_template',
                       'critical', false, %s, %s::jsonb)""",
            (root_id, mindmap_id, "Chargesheet Mindmap",
             f"Generated from KB v{bundle.kb_version}",
             order, json.dumps({"kb_version": bundle.kb_version})),
        )
        order += 1

        # Collect all nodes across offences, grouped by branch_type
        branch_groups: Dict[str, List[Tuple[KnowledgeNodeResponse, str]]] = {}
        all_offences = bundle.primary_offences + bundle.related_offences

        for ow in all_offences:
            offence_code = ow.offence.offence_code
            for node in ow.nodes:
                bt = node.branch_type.value if hasattr(node.branch_type, "value") else node.branch_type
                if bt not in branch_groups:
                    branch_groups[bt] = []
                branch_groups[bt].append((node, offence_code))

        # Branch display order
        branch_order = [
            "legal_section", "immediate_action", "panchnama", "evidence",
            "witness_bayan", "forensic", "procedural_safeguard", "gap_historical",
        ]

        for bt in branch_order:
            nodes_in_branch = branch_groups.get(bt, [])
            if not nodes_in_branch:
                continue

            # Create branch parent node
            branch_id = uuid.uuid4()
            node_type = _BRANCH_TO_NODE_TYPE.get(bt, "evidence")
            branch_title = _branch_display_name(bt)

            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, 'static_template',
                           'critical', false, %s, '{}'::jsonb)""",
                (branch_id, mindmap_id, root_id, node_type,
                 branch_title, f"{len(nodes_in_branch)} items", order),
            )
            order += 1

            # Sort: canonical before judgment_derived, critical before advisory
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}
            tier_order = {"canonical": 0, "judgment_derived": 1}
            nodes_in_branch.sort(key=lambda x: (
                tier_order.get(x[0].tier.value if hasattr(x[0].tier, "value") else x[0].tier, 1),
                priority_order.get(x[0].priority.value if hasattr(x[0].priority, "value") else x[0].priority, 2),
            ))

            for kn, offence_code in nodes_in_branch:
                dedup_key = (bt, kn.title_en)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                child_id = uuid.uuid4()
                source = _TIER_TO_SOURCE.get(
                    kn.tier.value if hasattr(kn.tier, "value") else kn.tier,
                    "static_template",
                )
                priority = kn.priority.value if hasattr(kn.priority, "value") else kn.priority
                bns_section = None
                ipc_section = None

                # Extract section references from citations
                for cit in kn.legal_basis_citations:
                    if hasattr(cit, "framework"):
                        fw = cit.framework
                        sec = cit.section
                    elif isinstance(cit, dict):
                        fw = cit.get("framework")
                        sec = cit.get("section")
                    else:
                        continue
                    if fw == "BNS" and sec:
                        bns_section = sec
                    elif fw in ("IPC", None) and sec:
                        ipc_section = sec

                metadata = {
                    "offence_code": offence_code,
                    "kb_version": bundle.kb_version,
                    "tier": kn.tier.value if hasattr(kn.tier, "value") else kn.tier,
                }

                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, bns_section, ipc_section,
                        priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                    (child_id, mindmap_id, branch_id, node_type,
                     kn.title_en, kn.description_md,
                     source, bns_section, ipc_section,
                     priority, kn.requires_disclaimer, order,
                     json.dumps(metadata)),
                )
                order += 1

        # Add judgment context as advisory nodes
        if bundle.judgment_context:
            jud_branch_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, 'evidence', 'Relevant Judgments', %s,
                           'ml_suggestion', 'advisory', true, %s, '{}'::jsonb)""",
                (jud_branch_id, mindmap_id, root_id,
                 f"{len(bundle.judgment_context)} relevant judgments found",
                 order),
            )
            order += 1

            for jc in bundle.judgment_context:
                jnode_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, 'evidence', %s, %s,
                               'ml_suggestion', 'advisory', true, %s, %s::jsonb)""",
                    (jnode_id, mindmap_id, jud_branch_id,
                     f"{jc.citation} — {jc.case_name or ''}",
                     jc.summary_md or "",
                     order,
                     json.dumps({
                         "judgment_id": str(jc.id),
                         "court": jc.court,
                         "binding_authority": jc.binding_authority,
                     })),
                )
                order += 1

    logger.info(
        "Inserted %d mindmap nodes from KB v%s",
        order, bundle.kb_version,
    )
    return root_id


def _branch_display_name(branch_type: str) -> str:
    names = {
        "legal_section": "Applicable Legal Sections",
        "immediate_action": "Immediate Actions",
        "panchnama": "Panchnama Requirements",
        "evidence": "Evidence Collection",
        "witness_bayan": "Witness Statements",
        "forensic": "Forensic Requirements",
        "gap_historical": "Historical Gap Patterns",
        "procedural_safeguard": "Procedural Safeguards",
    }
    return names.get(branch_type, branch_type.replace("_", " ").title())
