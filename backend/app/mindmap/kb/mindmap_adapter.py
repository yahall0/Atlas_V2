"""KB-to-Mindmap adapter — 3-layer aware (T53-M-KB-4 + KB-LAYER refactor).

Converts a KnowledgeBundle into mindmap nodes. Top-level structure is now
the three KB layers, each rendered as a trunk under the root:

    Investigation Mindmap
    ├── Layer 1 — Statutory Framework        (canonical_legal)
    │     ├── Applicable Legal Sections      (BNS / BNSS / BSA)
    │     └── ... (other legal_section nodes)
    ├── Layer 2 — Investigation Playbook     (investigation_playbook)
    │     ├── Immediate Actions
    │     ├── Panchnama Requirements
    │     ├── Evidence Collection
    │     ├── Witness Statements (Bayan)
    │     ├── Forensic / Blood / DNA
    │     └── Procedural Safeguards
    └── Layer 3 — Case Law Intelligence      (case_law_intelligence)
          ├── Acquittal Patterns & Standards
          └── Relevant Judgments (top-N by binding authority)

Each child node carries its KB layer in the metadata JSON so the frontend
can colour-band nodes by authority (binding statute vs. SOP best practice
vs. judicial standard).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List, Set, Tuple

from psycopg2.extensions import connection as PgConnection

from app.mindmap.kb.schemas import (
    KBLayer,
    KnowledgeBundle,
    KnowledgeNodeResponse,
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
    "procedural_safeguard": "evidence",
}

# Map KB tier → mindmap source (kept for back-compat with downstream
# mindmap consumers that filter by source).
_TIER_TO_SOURCE = {
    "canonical": "static_template",
    "judgment_derived": "ml_suggestion",
}

# Branch display order *within* each layer.
_BRANCH_ORDER_BY_LAYER: Dict[KBLayer, List[str]] = {
    KBLayer.CANONICAL_LEGAL: ["legal_section"],
    KBLayer.INVESTIGATION_PLAYBOOK: [
        "immediate_action",
        "panchnama",
        "evidence",
        "witness_bayan",
        "forensic",
        "procedural_safeguard",
    ],
    KBLayer.CASE_LAW_INTELLIGENCE: [
        "gap_historical",
        # Anything else that ended up tagged as case-law gets surfaced too:
        "legal_section",
        "evidence",
        "witness_bayan",
        "forensic",
        "panchnama",
        "procedural_safeguard",
        "immediate_action",
    ],
}

_LAYER_TRUNK_TITLE = {
    KBLayer.CANONICAL_LEGAL: "Layer 1 — Statutory Framework (BNS / BNSS / BSA)",
    KBLayer.INVESTIGATION_PLAYBOOK: "Layer 2 — Investigation Playbook (SOP)",
    KBLayer.CASE_LAW_INTELLIGENCE: "Layer 3 — Case Law Intelligence",
}

_LAYER_TRUNK_BLURB = {
    KBLayer.CANONICAL_LEGAL: (
        "Statutory text — what the law itself says. Binding absolutely. "
        "Authored by legal advisor. Updates only on Parliamentary amendment."
    ),
    KBLayer.INVESTIGATION_PLAYBOOK: (
        "What good investigation looks like — panchnama, evidence packaging, "
        "forensic sequencing, bayan technique. Authored by senior IPS / "
        "Gujarat Police training wing. Institutional best practice, not statute."
    ),
    KBLayer.CASE_LAW_INTELLIGENCE: (
        "What courts have ruled on investigation quality, evidentiary "
        "standards, and acquittal patterns. Graded by court "
        "(SC > HC-Gujarat > HC-other > District). Updates continuously."
    ),
}


def insert_nodes_from_kb(
    conn: PgConnection,
    mindmap_id: uuid.UUID,
    bundle: KnowledgeBundle,
) -> uuid.UUID:
    """Insert mindmap nodes from a KnowledgeBundle, grouped by KB layer.

    Returns the root_node_id.
    """
    seen: Set[Tuple[str, str, str]] = set()  # (layer, branch_type, title)
    root_id = uuid.uuid4()
    order = 0

    grouped_by_layer = bundle.nodes_by_layer()
    layer_to_offence_codes = _build_offence_index(bundle)

    with conn.cursor() as cur:
        # Root node
        cur.execute(
            """INSERT INTO mindmap_nodes
               (id, mindmap_id, parent_id, node_type, title, description_md,
                source, priority, requires_disclaimer, display_order, metadata)
               VALUES (%s, %s, NULL, 'evidence', %s, %s, 'static_template',
                       'critical', false, %s, %s::jsonb)""",
            (
                root_id, mindmap_id, "Investigation Mindmap",
                f"Generated from KB v{bundle.kb_version} — 3-layer view "
                f"(L1: {bundle.layer_stats.canonical_legal} | "
                f"L2: {bundle.layer_stats.investigation_playbook} | "
                f"L3: {bundle.layer_stats.case_law_intelligence})",
                order,
                json.dumps({
                    "kb_version": bundle.kb_version,
                    "layer_stats": bundle.layer_stats.model_dump(),
                }),
            ),
        )
        order += 1

        # One trunk per layer, in fixed order so the IO always sees
        # statute → playbook → case-law from top to bottom.
        for layer in (
            KBLayer.CANONICAL_LEGAL,
            KBLayer.INVESTIGATION_PLAYBOOK,
            KBLayer.CASE_LAW_INTELLIGENCE,
        ):
            nodes_in_layer = grouped_by_layer.get(layer, [])
            # Layer 3 also gets the judgment_context list appended below,
            # so emit the trunk even if there are no extracted nodes yet.
            if not nodes_in_layer and not (
                layer == KBLayer.CASE_LAW_INTELLIGENCE and bundle.judgment_context
            ):
                continue

            trunk_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, 'evidence', %s, %s, 'static_template',
                           'critical', false, %s, %s::jsonb)""",
                (
                    trunk_id, mindmap_id, root_id,
                    _LAYER_TRUNK_TITLE[layer],
                    _LAYER_TRUNK_BLURB[layer],
                    order,
                    json.dumps({
                        "kb_layer": layer.value,
                        "trunk": True,
                        "node_count": len(nodes_in_layer),
                    }),
                ),
            )
            order += 1

            # Group this layer's nodes by branch_type
            by_branch: Dict[str, List[KnowledgeNodeResponse]] = {}
            for n in nodes_in_layer:
                bt = n.branch_type.value if hasattr(n.branch_type, "value") else n.branch_type
                by_branch.setdefault(bt, []).append(n)

            for bt in _BRANCH_ORDER_BY_LAYER[layer]:
                bucket = by_branch.pop(bt, [])
                if not bucket:
                    continue
                order = _emit_branch(
                    cur, mindmap_id, trunk_id, layer, bt, bucket,
                    seen, order, layer_to_offence_codes, bundle.kb_version,
                )

            # Catch-all for any branch_type not in the per-layer order list.
            for bt, bucket in by_branch.items():
                order = _emit_branch(
                    cur, mindmap_id, trunk_id, layer, bt, bucket,
                    seen, order, layer_to_offence_codes, bundle.kb_version,
                )

            # Layer 3 — append the relevant judgments under their own
            # sub-branch so the IO sees the actual citations alongside
            # the extracted intelligence.
            if layer == KBLayer.CASE_LAW_INTELLIGENCE and bundle.judgment_context:
                jud_branch_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, 'evidence', 'Relevant Judgments', %s,
                               'ml_suggestion', 'advisory', true, %s, %s::jsonb)""",
                    (
                        jud_branch_id, mindmap_id, trunk_id,
                        f"{len(bundle.judgment_context)} relevant judgments "
                        f"ranked by binding authority",
                        order,
                        json.dumps({"kb_layer": layer.value}),
                    ),
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
                        (
                            jnode_id, mindmap_id, jud_branch_id,
                            f"{jc.citation} — {jc.case_name or ''}",
                            jc.summary_md or "",
                            order,
                            json.dumps({
                                "kb_layer": layer.value,
                                "judgment_id": str(jc.id),
                                "court": jc.court,
                                "binding_authority": jc.binding_authority,
                            }),
                        ),
                    )
                    order += 1

    logger.info(
        "Inserted mindmap nodes from KB v%s — %d nodes across 3 layers "
        "(L1=%d, L2=%d, L3=%d)",
        bundle.kb_version, order,
        bundle.layer_stats.canonical_legal,
        bundle.layer_stats.investigation_playbook,
        bundle.layer_stats.case_law_intelligence,
    )
    return root_id


def _build_offence_index(bundle: KnowledgeBundle) -> Dict[str, str]:
    """Return {node_id: offence_code} for metadata enrichment."""
    idx: Dict[str, str] = {}
    for ow in bundle.primary_offences + bundle.related_offences:
        for n in ow.nodes:
            idx[str(n.id)] = ow.offence.offence_code
    return idx


def _emit_branch(
    cur,
    mindmap_id: uuid.UUID,
    trunk_id: uuid.UUID,
    layer: KBLayer,
    branch_type: str,
    nodes: List[KnowledgeNodeResponse],
    seen: Set[Tuple[str, str, str]],
    order: int,
    offence_index: Dict[str, str],
    kb_version: str,
) -> int:
    """Insert a branch parent + its children under the given trunk."""
    branch_id = uuid.uuid4()
    node_type = _BRANCH_TO_NODE_TYPE.get(branch_type, "evidence")
    branch_title = _branch_display_name(branch_type)

    cur.execute(
        """INSERT INTO mindmap_nodes
           (id, mindmap_id, parent_id, node_type, title, description_md,
            source, priority, requires_disclaimer, display_order, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, 'static_template',
                   'critical', false, %s, %s::jsonb)""",
        (
            branch_id, mindmap_id, trunk_id, node_type,
            branch_title, f"{len(nodes)} items",
            order,
            json.dumps({
                "kb_layer": layer.value,
                "branch_type": branch_type,
            }),
        ),
    )
    order += 1

    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "advisory": 4}
    tier_order = {"canonical": 0, "judgment_derived": 1}
    nodes.sort(key=lambda n: (
        tier_order.get(n.tier.value if hasattr(n.tier, "value") else n.tier, 1),
        priority_order.get(n.priority.value if hasattr(n.priority, "value") else n.priority, 2),
    ))

    for kn in nodes:
        dedup_key = (layer.value, branch_type, kn.title_en)
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
        for cit in kn.legal_basis_citations:
            if hasattr(cit, "framework"):
                fw, sec = cit.framework, cit.section
            elif isinstance(cit, dict):
                fw, sec = cit.get("framework"), cit.get("section")
            else:
                continue
            if fw == "BNS" and sec:
                bns_section = sec
            elif fw in ("IPC", None) and sec:
                ipc_section = sec

        offence_code = offence_index.get(str(kn.id), "")
        author = kn.authored_by_role.value if hasattr(kn.authored_by_role, "value") else kn.authored_by_role
        cadence = kn.update_cadence.value if hasattr(kn.update_cadence, "value") else kn.update_cadence

        metadata = {
            "kb_layer": layer.value,
            "branch_type": branch_type,
            "offence_code": offence_code,
            "kb_version": kb_version,
            "tier": kn.tier.value if hasattr(kn.tier, "value") else kn.tier,
            "authored_by_role": author,
            "update_cadence": cadence,
            "kb_node_id": str(kn.id),
        }

        cur.execute(
            """INSERT INTO mindmap_nodes
               (id, mindmap_id, parent_id, node_type, title, description_md,
                source, bns_section, ipc_section,
                priority, requires_disclaimer, display_order, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
            (
                child_id, mindmap_id, branch_id, node_type,
                kn.title_en, kn.description_md,
                source, bns_section, ipc_section,
                priority, kn.requires_disclaimer, order,
                json.dumps(metadata),
            ),
        )
        order += 1

    return order


def _branch_display_name(branch_type: str) -> str:
    names = {
        "legal_section": "Applicable Legal Sections",
        "immediate_action": "Immediate Actions",
        "panchnama": "Panchnama Requirements",
        "evidence": "Evidence Collection",
        "witness_bayan": "Witness Statements (Bayan)",
        "forensic": "Forensic / Blood / DNA",
        "gap_historical": "Acquittal Patterns & Court-Set Standards",
        "procedural_safeguard": "Procedural Safeguards",
    }
    return names.get(branch_type, branch_type.replace("_", " ").title())
