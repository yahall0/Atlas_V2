"""Mindmap generation service — T53-M3.

Generates a case-type-aware chargesheet mindmap tree from FIR data,
completeness flags, and (optionally) ML evidence gap suggestions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from app.mindmap.registry import load_template, template_version
from app.mindmap.schemas import (
    MindmapNodeResponse,
    MindmapResponse,
    MindmapStatus,
    NodePriority,
    NodeSource,
    NodeStatus,
    NodeType,
    TemplateTree,
)

psycopg2.extras.register_uuid()
logger = logging.getLogger(__name__)

_GENESIS = "GENESIS"
_MODEL_VERSION = "template-v1+completeness"


# ── Hash-chain utility (reuses SHA-256 pattern from T56 audit_chain) ─────────

def _compute_status_hash(
    node_id: str, user_id: str, status: str,
    note: str, evidence_ref: str, timestamp: str, previous_hash: str,
) -> str:
    payload = (
        f"{node_id}|{user_id}|{status}|{note}|"
        f"{evidence_ref}|{timestamp}|{previous_hash}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_fir_data(conn: PgConnection, fir_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Fetch FIR structured data (T47 extraction output)."""
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM firs WHERE id = %s", (fir_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _get_case_category(fir: Dict[str, Any]) -> Tuple[str, bool]:
    """Determine case category via NLP classification (T28).

    Returns (category, is_uncertain).
    Uses top-1 label at confidence >= 0.7, else flags as uncertain.
    """
    classification = fir.get("nlp_classification")
    confidence = fir.get("nlp_confidence")

    if classification and confidence is not None and confidence >= 0.7:
        return classification, False

    if classification:
        return classification, True

    return "generic", True


def _get_completeness_gaps(fir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract completeness gaps from T48 output.

    Converts missing-field flags into gap_from_fir node definitions.
    """
    gaps = []
    completeness_pct = fir.get("completeness_pct")
    if completeness_pct is not None and completeness_pct < 100:
        # Check for common missing fields
        missing_fields = []
        if not fir.get("fir_number"):
            missing_fields.append(("FIR Number", "FIR registration number is missing"))
        if not fir.get("complainant_name"):
            missing_fields.append(("Complainant Name", "Complainant name not recorded"))
        if not fir.get("accused_name"):
            missing_fields.append(("Accused Details", "Accused person details not available"))
        if not fir.get("place_address"):
            missing_fields.append(("Place of Occurrence", "Location of incident not recorded"))
        if not fir.get("occurrence_from") and not fir.get("occurrence_start"):
            missing_fields.append(("Date/Time of Occurrence", "Occurrence date/time not specified"))
        if not fir.get("primary_sections") or len(fir.get("primary_sections", [])) == 0:
            missing_fields.append(("Legal Sections", "No legal sections cited in FIR"))
        if not fir.get("io_name"):
            missing_fields.append(("IO Assignment", "Investigating Officer not assigned"))
        if not fir.get("district"):
            missing_fields.append(("District", "District information missing"))

        for title, desc in missing_fields:
            gaps.append({
                "title": f"FIR Gap: {title}",
                "description_md": desc,
                "priority": "critical",
            })

    return gaps


def _get_evidence_gaps(conn: PgConnection, fir_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Fetch T55 evidence gap classifier output if available."""
    try:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT * FROM evidence_gap_reports
                   WHERE fir_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (fir_id,),
            )
            row = cur.fetchone()
            if not row:
                return []

            suggestions = []
            report_data = row.get("report_data") or row.get("gaps") or {}
            if isinstance(report_data, str):
                report_data = json.loads(report_data)

            for gap in report_data if isinstance(report_data, list) else []:
                suggestions.append({
                    "title": gap.get("title", gap.get("evidence_type", "Evidence Gap")),
                    "description_md": gap.get("description", gap.get("detail", "")),
                    "priority": gap.get("priority", "recommended"),
                })
            return suggestions
    except Exception:
        logger.warning("Could not fetch evidence gap data for FIR %s", fir_id)
        return []


def _existing_mindmap(
    conn: PgConnection, fir_id: uuid.UUID, tpl_version: str,
) -> Optional[Dict[str, Any]]:
    """Check if a mindmap already exists for this FIR + template version."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT * FROM chargesheet_mindmaps
               WHERE fir_id = %s AND template_version = %s AND status = 'active'
               ORDER BY generated_at DESC LIMIT 1""",
            (fir_id, tpl_version),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _insert_nodes(
    conn: PgConnection,
    mindmap_id: uuid.UUID,
    template: TemplateTree,
    completeness_gaps: List[Dict[str, Any]],
    evidence_gaps: List[Dict[str, Any]],
) -> uuid.UUID:
    """Persist template nodes + ML/completeness nodes. Returns root_node_id."""
    # Dedup key: (node_type, bns_section, title)
    seen: set = set()
    root_id = uuid.uuid4()
    order = 0

    with conn.cursor() as cur:
        # Insert root node
        cur.execute(
            """INSERT INTO mindmap_nodes
               (id, mindmap_id, parent_id, node_type, title, description_md,
                source, priority, requires_disclaimer, display_order, metadata)
               VALUES (%s, %s, NULL, 'evidence', %s, %s, 'static_template',
                       'critical', false, %s, '{}'::jsonb)""",
            (root_id, mindmap_id, "Chargesheet Mindmap",
             "Root node for chargesheet investigation guidance", order),
        )
        order += 1

        # Insert static template branches
        for branch in template.branches:
            branch_id = uuid.uuid4()
            key = (branch.node_type.value, None, branch.title)
            seen.add(key)

            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, 'static_template',
                           %s, %s, %s, '{}'::jsonb)""",
                (branch_id, mindmap_id, root_id, branch.node_type.value,
                 branch.title, branch.description_md,
                 branch.priority.value, branch.requires_disclaimer, order),
            )
            order += 1

            for child in branch.children:
                child_id = uuid.uuid4()
                child_key = (child.node_type.value, child.bns_section, child.title)
                if child_key in seen:
                    continue
                seen.add(child_key)

                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, bns_section, ipc_section, crpc_section,
                        priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, 'static_template',
                               %s, %s, %s, %s, %s, %s, '{}'::jsonb)""",
                    (child_id, mindmap_id, branch_id, child.node_type.value,
                     child.title, child.description_md,
                     child.bns_section, child.ipc_section, child.crpc_section,
                     child.priority.value, child.requires_disclaimer, order),
                )
                order += 1

        # Insert completeness gap nodes under a "FIR Gaps" branch
        if completeness_gaps:
            gaps_branch_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, 'gap_from_fir', 'FIR Gaps',
                           'Missing or incomplete information identified from the FIR',
                           'completeness_engine', 'critical', true, %s, '{}'::jsonb)""",
                (gaps_branch_id, mindmap_id, root_id, order),
            )
            order += 1

            for gap in completeness_gaps:
                gap_key = ("gap_from_fir", None, gap["title"])
                if gap_key in seen:
                    continue
                seen.add(gap_key)

                gap_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, 'gap_from_fir', %s, %s,
                               'completeness_engine', %s, true, %s, '{}'::jsonb)""",
                    (gap_id, mindmap_id, gaps_branch_id,
                     gap["title"], gap.get("description_md", ""),
                     gap.get("priority", "critical"), order),
                )
                order += 1

        # Insert ML evidence gap nodes
        if evidence_gaps:
            ml_branch_id = uuid.uuid4()
            cur.execute(
                """INSERT INTO mindmap_nodes
                   (id, mindmap_id, parent_id, node_type, title, description_md,
                    source, priority, requires_disclaimer, display_order, metadata)
                   VALUES (%s, %s, %s, 'evidence',
                           'ML-Suggested Evidence Gaps',
                           'Evidence gaps identified by the ML evidence gap classifier',
                           'ml_suggestion', 'recommended', true, %s, '{}'::jsonb)""",
                (ml_branch_id, mindmap_id, root_id, order),
            )
            order += 1

            for eg in evidence_gaps:
                eg_key = ("evidence", None, eg["title"])
                if eg_key in seen:
                    continue
                seen.add(eg_key)

                eg_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO mindmap_nodes
                       (id, mindmap_id, parent_id, node_type, title, description_md,
                        source, priority, requires_disclaimer, display_order, metadata)
                       VALUES (%s, %s, %s, 'evidence', %s, %s,
                               'ml_suggestion', %s, true, %s, '{}'::jsonb)""",
                    (eg_id, mindmap_id, ml_branch_id,
                     eg["title"], eg.get("description_md", ""),
                     eg.get("priority", "recommended"), order),
                )
                order += 1

    return root_id


def _fetch_mindmap_tree(conn: PgConnection, mindmap_id: uuid.UUID) -> MindmapResponse:
    """Fetch full mindmap with nodes and current statuses."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM chargesheet_mindmaps WHERE id = %s", (mindmap_id,)
        )
        mm = dict(cur.fetchone())

        cur.execute(
            """SELECT n.*,
                      (SELECT s.status FROM mindmap_node_status s
                       WHERE s.node_id = n.id
                       ORDER BY s.updated_at DESC LIMIT 1) AS current_status
               FROM mindmap_nodes n
               WHERE n.mindmap_id = %s
               ORDER BY n.display_order""",
            (mindmap_id,),
        )
        nodes = [dict(r) for r in cur.fetchall()]

    # Build tree structure
    node_map: Dict[uuid.UUID, MindmapNodeResponse] = {}
    root_nodes: List[MindmapNodeResponse] = []

    for n in nodes:
        resp = MindmapNodeResponse(
            id=n["id"],
            mindmap_id=n["mindmap_id"],
            parent_id=n["parent_id"],
            node_type=n["node_type"],
            title=n["title"],
            description_md=n.get("description_md"),
            source=n["source"],
            bns_section=n.get("bns_section"),
            ipc_section=n.get("ipc_section"),
            crpc_section=n.get("crpc_section"),
            priority=n["priority"],
            requires_disclaimer=n["requires_disclaimer"],
            display_order=n["display_order"],
            metadata=n.get("metadata") or {},
            current_status=n.get("current_status"),
        )
        node_map[n["id"]] = resp

    for n in nodes:
        resp = node_map[n["id"]]
        pid = n["parent_id"]
        if pid and pid in node_map:
            node_map[pid].children.append(resp)
        else:
            root_nodes.append(resp)

    return MindmapResponse(
        id=mm["id"],
        fir_id=mm["fir_id"],
        case_category=mm["case_category"],
        template_version=mm["template_version"],
        generated_at=mm["generated_at"],
        generated_by_model_version=mm.get("generated_by_model_version"),
        root_node_id=mm.get("root_node_id"),
        status=mm["status"],
        nodes=root_nodes,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def _recommended_citations_from_fir(fir: Dict[str, Any]) -> List[str]:
    """Extract sub-clause-precise citations recorded in the FIR's nlp_metadata.

    The recommender (per ADR-D17) writes its output to
    ``firs.nlp_metadata['recommended_sections']`` after the auto-trigger
    runs. This helper reads that list back so the mindmap generator can
    decide whether the playbook path applies.
    """
    meta = fir.get("nlp_metadata") or {}
    recs = meta.get("recommended_sections") or []
    out: list[str] = []
    for r in recs:
        if isinstance(r, str):
            out.append(r)
        elif isinstance(r, dict) and r.get("canonical_citation"):
            out.append(r["canonical_citation"])
    # Fallback: primary_sections (raw, may not be sub-clause precise)
    if not out:
        for s in (fir.get("primary_sections") or []):
            out.append(f"BNS {s}" if not s.startswith(("BNS", "IPC")) else s)
    return out


def generate_mindmap(
    fir_id: uuid.UUID,
    *,
    conn: PgConnection,
    regenerate: bool = False,
) -> MindmapResponse:
    """Generate (or return existing) chargesheet mindmap for a FIR.

    Idempotent: if a mindmap already exists for (fir_id, template_version),
    returns it. Set regenerate=True to force a new version (old one retained).

    Routing (ADR-D19):
      1. If the FIR's recommended citations match a Delhi Police Academy
         Compendium scenario, build the mindmap from that scenario
         (government-authority playbook).
      2. Otherwise, fall back to the model-authored case-category template.
    """
    fir = _get_fir_data(conn, fir_id)
    if fir is None:
        raise ValueError(f"FIR {fir_id} not found")

    case_category, is_uncertain = _get_case_category(fir)
    tpl_version = template_version(case_category)

    # Idempotency check (template path)
    if not regenerate:
        existing = _existing_mindmap(conn, fir_id, tpl_version)
        if existing:
            logger.info(
                "Returning existing mindmap %s for FIR %s",
                existing["id"], fir_id,
            )
            return _fetch_mindmap_tree(conn, existing["id"])

    # ── Compendium-playbook path (preferred, ADR-D19) ────────────────────────
    try:
        from app.mindmap.playbook_generator import (  # noqa: PLC0415
            generate_playbook_mindmap,
            has_playbook_for,
        )
        citations = _recommended_citations_from_fir(fir)
        if citations and has_playbook_for(citations):
            logger.info(
                "Using Compendium playbook for FIR %s (citations=%s)",
                fir_id, citations,
            )
            playbook_resp = generate_playbook_mindmap(
                fir_id=fir_id, citations=citations, conn=conn,
                regenerate=regenerate,
            )
            if playbook_resp:
                # Re-fetch via the standard reader so the returned tree
                # exactly matches the MindmapResponse contract.
                return _fetch_mindmap_tree(conn, uuid.UUID(playbook_resp["id"]))
    except Exception:
        # Playbook is best-effort augmentation; fall through to template path.
        logger.exception(
            "Playbook mindmap path failed for FIR %s; falling back to template",
            fir_id,
        )

    # If regenerating, mark old as superseded
    if regenerate:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE chargesheet_mindmaps
                   SET status = 'superseded'
                   WHERE fir_id = %s AND status = 'active'""",
                (fir_id,),
            )

    # Load template
    template = load_template(case_category)

    # Gather completeness gaps (T48)
    completeness_gaps = _get_completeness_gaps(fir)

    # Gather ML evidence gaps (T55) — graceful degradation
    evidence_gaps = _get_evidence_gaps(conn, fir_id)

    # Create mindmap record
    mindmap_id = uuid.uuid4()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    model_version = _MODEL_VERSION
    if is_uncertain:
        model_version += "+uncertain"

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO chargesheet_mindmaps
               (id, fir_id, case_category, template_version,
                generated_at, generated_by_model_version, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'active')""",
            (mindmap_id, fir_id, case_category, tpl_version,
             now, model_version),
        )

    # Insert all nodes
    root_node_id = _insert_nodes(
        conn, mindmap_id, template, completeness_gaps, evidence_gaps,
    )

    # Update root_node_id
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE chargesheet_mindmaps SET root_node_id = %s WHERE id = %s",
            (root_node_id, mindmap_id),
        )

    conn.commit()

    logger.info(
        "Generated mindmap %s for FIR %s (category=%s, uncertain=%s)",
        mindmap_id, fir_id, case_category, is_uncertain,
    )

    return _fetch_mindmap_tree(conn, mindmap_id)


def get_latest_mindmap(
    conn: PgConnection, fir_id: uuid.UUID,
) -> Optional[MindmapResponse]:
    """Fetch the latest active mindmap for a FIR."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT id FROM chargesheet_mindmaps
               WHERE fir_id = %s AND status = 'active'
               ORDER BY generated_at DESC LIMIT 1""",
            (fir_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return _fetch_mindmap_tree(conn, row["id"])


def get_mindmap_by_id(
    conn: PgConnection, mindmap_id: uuid.UUID,
) -> Optional[MindmapResponse]:
    """Fetch a specific mindmap version by its ID."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT id FROM chargesheet_mindmaps WHERE id = %s", (mindmap_id,),
        )
        if cur.fetchone() is None:
            return None
    return _fetch_mindmap_tree(conn, mindmap_id)


def list_mindmap_versions(
    conn: PgConnection, fir_id: uuid.UUID,
) -> List[Dict[str, Any]]:
    """List all mindmap versions for a FIR."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT m.id, m.case_category, m.template_version,
                      m.generated_at, m.status,
                      (SELECT COUNT(*) FROM mindmap_nodes n
                       WHERE n.mindmap_id = m.id) AS node_count
               FROM chargesheet_mindmaps m
               WHERE m.fir_id = %s
               ORDER BY m.generated_at DESC""",
            (fir_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def update_node_status(
    conn: PgConnection,
    node_id: uuid.UUID,
    user_id: str,
    status: str,
    note: str = "",
    evidence_ref: str = "",
    hash_prev: str = "",
) -> Dict[str, Any]:
    """Append a new status entry to the hash chain for a node.

    Returns the new status entry. Raises ValueError on hash_prev mismatch (409).
    """
    with _dict_cursor(conn) as cur:
        # Verify node exists
        cur.execute("SELECT id FROM mindmap_nodes WHERE id = %s", (node_id,))
        if cur.fetchone() is None:
            raise ValueError(f"Node {node_id} not found")

        # Get latest hash
        cur.execute(
            """SELECT hash_self FROM mindmap_node_status
               WHERE node_id = %s
               ORDER BY updated_at DESC LIMIT 1""",
            (node_id,),
        )
        latest = cur.fetchone()
        actual_prev = latest["hash_self"] if latest else _GENESIS

        if hash_prev != actual_prev:
            raise ValueError(
                f"Hash chain conflict: expected {actual_prev}, got {hash_prev}. "
                "Another user may have updated this node."
            )

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        entry_id = uuid.uuid4()

        hash_self = _compute_status_hash(
            str(node_id), user_id, status,
            note or "", evidence_ref or "",
            now_iso, actual_prev,
        )

        cur.execute(
            """INSERT INTO mindmap_node_status
               (id, node_id, user_id, status, note, evidence_ref,
                updated_at, hash_prev, hash_self)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (entry_id, node_id, user_id, status,
             note or None, evidence_ref or None,
             now.replace(tzinfo=None), actual_prev, hash_self),
        )
        row = dict(cur.fetchone())
        conn.commit()

    return row


def get_node_status_history(
    conn: PgConnection, node_id: uuid.UUID,
) -> List[Dict[str, Any]]:
    """Return the full append-only status chain for a node."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT * FROM mindmap_node_status
               WHERE node_id = %s
               ORDER BY updated_at ASC""",
            (node_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_custom_node(
    conn: PgConnection,
    mindmap_id: uuid.UUID,
    parent_id: Optional[uuid.UUID],
    title: str,
    description_md: str,
    node_type: str,
    priority: str,
    user_id: str,
) -> Dict[str, Any]:
    """Add a custom node created by the IO."""
    node_id = uuid.uuid4()

    with _dict_cursor(conn) as cur:
        # Verify mindmap exists
        cur.execute(
            "SELECT id FROM chargesheet_mindmaps WHERE id = %s", (mindmap_id,),
        )
        if cur.fetchone() is None:
            raise ValueError(f"Mindmap {mindmap_id} not found")

        # Get max display_order
        cur.execute(
            "SELECT COALESCE(MAX(display_order), 0) + 1 AS next_order FROM mindmap_nodes WHERE mindmap_id = %s",
            (mindmap_id,),
        )
        next_order = cur.fetchone()["next_order"]

        # If parent_id is provided, use it; otherwise attach to root
        if parent_id is None:
            cur.execute(
                "SELECT root_node_id FROM chargesheet_mindmaps WHERE id = %s",
                (mindmap_id,),
            )
            root = cur.fetchone()
            parent_id = root["root_node_id"] if root else None

        cur.execute(
            """INSERT INTO mindmap_nodes
               (id, mindmap_id, parent_id, node_type, title, description_md,
                source, priority, requires_disclaimer, display_order,
                metadata)
               VALUES (%s, %s, %s, %s, %s, %s, 'io_custom', %s, false, %s,
                       %s::jsonb)
               RETURNING *""",
            (node_id, mindmap_id, parent_id, node_type, title, description_md,
             priority, next_order,
             json.dumps({"created_by": user_id})),
        )
        row = dict(cur.fetchone())
        conn.commit()

    return row
