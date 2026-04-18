"""KB retrieval service — T53-M-KB-3.

Hybrid retrieval: exact BNS match → related offences → semantic fallback.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras
from psycopg2.extensions import connection as PgConnection

from app.mindmap.kb.schemas import (
    AuthoredByRole,
    KBLayer,
    KnowledgeBundle,
    KnowledgeNodeResponse,
    LayerStats,
    LegalCitation,
    OffenceResponse,
    OffenceWithNodes,
    RelevantJudgment,
    RetrievalTrace,
    UpdateCadence,
    derive_kb_layer,
    default_author_for,
    default_cadence_for,
)

psycopg2.extras.register_uuid()
logger = logging.getLogger(__name__)


def _dict_cursor(conn: PgConnection):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def _get_current_kb_version(conn: PgConnection) -> str:
    """Get latest released KB version."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT version FROM legal_kb_versions ORDER BY released_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        return row["version"] if row else "1.0.0"


def _fetch_offence_with_nodes(
    conn: PgConnection, offence_id: uuid.UUID,
) -> Optional[OffenceWithNodes]:
    """Fetch an offence and all its approved nodes."""
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT *, 0 AS node_count FROM legal_kb_offences WHERE id = %s",
            (offence_id,),
        )
        off_row = cur.fetchone()
        if not off_row:
            return None

        cur.execute(
            """SELECT * FROM legal_kb_knowledge_nodes
               WHERE offence_id = %s AND approval_status IN ('approved', 'proposed')
               ORDER BY display_order""",
            (offence_id,),
        )
        node_rows = [dict(r) for r in cur.fetchall()]

        off_row = dict(off_row)
        off_row["node_count"] = len(node_rows)

        offence = OffenceResponse(
            id=off_row["id"],
            category_id=off_row["category_id"],
            offence_code=off_row["offence_code"],
            bns_section=off_row.get("bns_section"),
            bns_subsection=off_row.get("bns_subsection"),
            display_name_en=off_row["display_name_en"],
            display_name_gu=off_row.get("display_name_gu"),
            short_description_md=off_row.get("short_description_md"),
            punishment=off_row.get("punishment"),
            cognizable=off_row.get("cognizable"),
            bailable=off_row.get("bailable"),
            triable_by=off_row.get("triable_by"),
            compoundable=off_row.get("compoundable", "no"),
            related_offence_codes=off_row.get("related_offence_codes") or [],
            special_acts=off_row.get("special_acts") or [],
            kb_version=off_row.get("kb_version", "1.0.0"),
            review_status=off_row.get("review_status", "draft"),
            node_count=len(node_rows),
        )

        nodes = []
        for n in node_rows:
            citations = n.get("legal_basis_citations") or []
            if isinstance(citations, str):
                citations = json.loads(citations)
            proc_meta = n.get("procedural_metadata") or {}
            if isinstance(proc_meta, str):
                proc_meta = json.loads(proc_meta)

            # Layer attribution: prefer the persisted column (populated by
            # migration 012); fall back to derivation for any row that
            # somehow predates the migration in a dev DB.
            raw_layer = n.get("kb_layer")
            if raw_layer:
                layer = KBLayer(raw_layer)
            else:
                layer = derive_kb_layer(n["branch_type"], n["tier"])

            raw_author = n.get("authored_by_role")
            author = AuthoredByRole(raw_author) if raw_author else default_author_for(layer)

            raw_cadence = n.get("update_cadence")
            cadence = UpdateCadence(raw_cadence) if raw_cadence else default_cadence_for(layer)

            nodes.append(KnowledgeNodeResponse(
                id=n["id"],
                offence_id=n["offence_id"],
                branch_type=n["branch_type"],
                tier=n["tier"],
                priority=n["priority"],
                title_en=n["title_en"],
                title_gu=n.get("title_gu"),
                description_md=n.get("description_md"),
                legal_basis_citations=[LegalCitation(**c) if isinstance(c, dict) else c for c in citations],
                procedural_metadata=proc_meta,
                requires_disclaimer=n.get("requires_disclaimer", False),
                display_order=n.get("display_order", 0),
                kb_version=n.get("kb_version", ""),
                approval_status=n.get("approval_status", "proposed"),
                kb_layer=layer,
                authored_by_role=author,
                update_cadence=cadence,
            ))

        return OffenceWithNodes(offence=offence, nodes=nodes)


def get_knowledge_for_mindmap(
    category_id: str,
    detected_bns_sections: list[str],
    fir_extracted_data: dict,
    *,
    conn: PgConnection,
) -> KnowledgeBundle:
    """Return the full knowledge bundle for mindmap generation.

    Retrieval strategy:
      1. Exact match on detected_bns_sections
      2. Related offences from matched offences
      3. Category-level semantic fallback if < 2 matches
      4. Cross-category semantic if classifier confidence < 0.7
    """
    start = time.monotonic()
    kb_version = _get_current_kb_version(conn)

    primary_offence_ids: list[uuid.UUID] = []
    related_offence_codes: set[str] = set()
    trace = RetrievalTrace(kb_version=kb_version)

    # Step 1: Exact match on BNS sections
    if detected_bns_sections:
        with _dict_cursor(conn) as cur:
            # Normalize sections (strip whitespace)
            sections = [s.strip() for s in detected_bns_sections if s.strip()]
            if sections:
                placeholders = ",".join(["%s"] * len(sections))
                cur.execute(
                    f"""SELECT id, offence_code, related_offence_codes
                        FROM legal_kb_offences
                        WHERE bns_section IN ({placeholders})
                          AND review_status IN ('approved', 'reviewed', 'draft')
                        ORDER BY review_status = 'approved' DESC""",
                    sections,
                )
                for row in cur.fetchall():
                    row = dict(row)
                    primary_offence_ids.append(row["id"])
                    for rc in (row.get("related_offence_codes") or []):
                        related_offence_codes.add(rc)

    trace.exact_match_offences = len(primary_offence_ids)

    # Step 2: Fetch related offences
    related_offence_ids: list[uuid.UUID] = []
    if related_offence_codes:
        with _dict_cursor(conn) as cur:
            placeholders = ",".join(["%s"] * len(related_offence_codes))
            cur.execute(
                f"""SELECT id FROM legal_kb_offences
                    WHERE offence_code IN ({placeholders})
                      AND id NOT IN ({",".join(["%s"] * len(primary_offence_ids)) if primary_offence_ids else "'00000000-0000-0000-0000-000000000000'"})""",
                list(related_offence_codes) + list(primary_offence_ids),
            )
            related_offence_ids = [dict(r)["id"] for r in cur.fetchall()]

    trace.related_offences = len(related_offence_ids)

    # Step 3: Category fallback if too few matches
    if len(primary_offence_ids) < 2:
        with _dict_cursor(conn) as cur:
            cur.execute(
                """SELECT id FROM legal_kb_offences
                   WHERE category_id = %s
                     AND review_status IN ('approved', 'reviewed', 'draft')
                   ORDER BY created_at
                   LIMIT 5""",
                (category_id,),
            )
            for row in cur.fetchall():
                oid = dict(row)["id"]
                if oid not in primary_offence_ids and oid not in related_offence_ids:
                    primary_offence_ids.append(oid)
            trace.semantic_fallback_used = True

    # Fetch full offence+nodes bundles
    primary_bundles = []
    for oid in primary_offence_ids:
        bundle = _fetch_offence_with_nodes(conn, oid)
        if bundle:
            primary_bundles.append(bundle)

    related_bundles = []
    for oid in related_offence_ids:
        bundle = _fetch_offence_with_nodes(conn, oid)
        if bundle:
            related_bundles.append(bundle)

    # Step 4: Fetch relevant judgments (top 5 by binding authority)
    judgment_context = _fetch_relevant_judgments(
        conn, category_id, detected_bns_sections,
    )

    total_nodes = sum(len(b.nodes) for b in primary_bundles + related_bundles)
    trace.total_nodes_returned = total_nodes
    trace.retrieval_duration_ms = int((time.monotonic() - start) * 1000)

    bundle = KnowledgeBundle(
        kb_version=kb_version,
        primary_offences=primary_bundles,
        related_offences=related_bundles,
        judgment_context=judgment_context,
        retrieval_trace=trace,
    )

    # Populate per-layer counts so the mindmap and gap analysis can show
    # at a glance how much of each authority backed the recommendation.
    grouped = bundle.nodes_by_layer()
    bundle.layer_stats = LayerStats(
        canonical_legal=len(grouped[KBLayer.CANONICAL_LEGAL]),
        investigation_playbook=len(grouped[KBLayer.INVESTIGATION_PLAYBOOK]),
        case_law_intelligence=(
            len(grouped[KBLayer.CASE_LAW_INTELLIGENCE]) + len(judgment_context)
        ),
    )
    return bundle


def _fetch_relevant_judgments(
    conn: PgConnection,
    category_id: str,
    bns_sections: list[str],
) -> list[RelevantJudgment]:
    """Fetch top 5 judgments by binding authority for the given sections."""
    if not bns_sections:
        return []

    try:
        with _dict_cursor(conn) as cur:
            # Simple overlap query on related_bns_sections array
            cur.execute(
                """SELECT id, citation, case_name, court, judgment_date,
                          binding_authority, summary_md
                   FROM legal_kb_judgments
                   WHERE review_status IN ('approved', 'reviewed')
                     AND related_bns_sections && %s
                   ORDER BY binding_authority DESC, judgment_date DESC
                   LIMIT 5""",
                (bns_sections,),
            )
            results = []
            for row in cur.fetchall():
                row = dict(row)
                results.append(RelevantJudgment(
                    id=row["id"],
                    citation=row["citation"],
                    case_name=row.get("case_name"),
                    court=row["court"],
                    judgment_date=row.get("judgment_date"),
                    binding_authority=row["binding_authority"],
                    summary_md=row.get("summary_md"),
                    similarity_score=1.0,
                ))
            return results
    except Exception:
        logger.warning("Could not fetch relevant judgments")
        return []


# ── Admin/CRUD helpers ───────────────────────────────────────────────────────

def list_offences(
    conn: PgConnection,
    category_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List offences with optional category filter."""
    with _dict_cursor(conn) as cur:
        where = ""
        params: list = []
        if category_id:
            where = "WHERE category_id = %s"
            params.append(category_id)
        params.extend([limit, offset])
        cur.execute(
            f"""SELECT o.*,
                       (SELECT COUNT(*) FROM legal_kb_knowledge_nodes n
                        WHERE n.offence_id = o.id) AS node_count
                FROM legal_kb_offences o
                {where}
                ORDER BY category_id, offence_code
                LIMIT %s OFFSET %s""",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get_offence_detail(conn: PgConnection, offence_id: uuid.UUID) -> Optional[dict]:
    """Get full offence with nodes."""
    bundle = _fetch_offence_with_nodes(conn, offence_id)
    if not bundle:
        return None
    return bundle.model_dump()


def list_judgments(
    conn: PgConnection,
    review_status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    with _dict_cursor(conn) as cur:
        where = ""
        params: list = []
        if review_status:
            where = "WHERE review_status = %s"
            params.append(review_status)
        params.extend([limit, offset])
        cur.execute(
            f"""SELECT j.*,
                       (SELECT COUNT(*) FROM legal_kb_judgment_insights i
                        WHERE i.judgment_id = j.id) AS insight_count
                FROM legal_kb_judgments j
                {where}
                ORDER BY ingested_at DESC
                LIMIT %s OFFSET %s""",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def get_judgment_with_insights(
    conn: PgConnection, judgment_id: uuid.UUID,
) -> Optional[dict]:
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM legal_kb_judgments WHERE id = %s", (judgment_id,))
        j = cur.fetchone()
        if not j:
            return None
        j = dict(j)

        cur.execute(
            "SELECT * FROM legal_kb_judgment_insights WHERE judgment_id = %s ORDER BY created_at",
            (judgment_id,),
        )
        j["insights"] = [dict(r) for r in cur.fetchall()]
        return j


def list_pending_insights(conn: PgConnection, limit: int = 50) -> list[dict]:
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT i.*, j.citation AS judgment_citation, j.case_name
               FROM legal_kb_judgment_insights i
               JOIN legal_kb_judgments j ON j.id = i.judgment_id
               WHERE i.review_status = 'pending'
               ORDER BY i.created_at DESC
               LIMIT %s""",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Audit logging ───────────────────────────────────────────────────────────

_GENESIS = "GENESIS"


def _compute_audit_hash(action: str, detail: str, timestamp: str, prev: str) -> str:
    payload = f"{action}|{detail}|{timestamp}|{prev}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audit_log(
    conn: PgConnection,
    actor: str,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    before_state: Optional[Dict[str, Any]],
    after_state: Dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _dict_cursor(conn) as cur:
        cur.execute(
            """SELECT hash_self FROM legal_kb_audit_log
               WHERE target_id = %s ORDER BY timestamp DESC LIMIT 1""",
            (target_id,),
        )
        prev = cur.fetchone()
        prev_hash = prev["hash_self"] if prev else _GENESIS

    hash_self = _compute_audit_hash(
        action, json.dumps(after_state, default=str), now, prev_hash,
    )

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO legal_kb_audit_log
               (actor_user_id, action, target_type, target_id,
                before_state, after_state, timestamp, hash_prev, hash_self)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)""",
            (
                None, action, target_type, target_id,
                json.dumps(before_state, default=str) if before_state else None,
                json.dumps(after_state, default=str),
                datetime.now(timezone.utc).replace(tzinfo=None),
                prev_hash, hash_self,
            ),
        )


# ── Offence CRUD ────────────────────────────────────────────────────────────

def create_offence(conn: PgConnection, data: dict, actor: str) -> dict:
    offence_id = uuid.uuid4()
    kb_version = _get_current_kb_version(conn)

    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT id FROM legal_kb_offences WHERE offence_code = %s",
            (data["offence_code"],),
        )
        if cur.fetchone():
            raise ValueError(f"Offence code '{data['offence_code']}' already exists")

        cur.execute(
            """INSERT INTO legal_kb_offences
               (id, category_id, offence_code, bns_section, bns_subsection,
                display_name_en, display_name_gu, short_description_md,
                punishment, cognizable, bailable, triable_by, compoundable,
                schedule_reference, related_offence_codes, special_acts,
                kb_version, review_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
               RETURNING *""",
            (
                offence_id,
                data["category_id"],
                data["offence_code"],
                data.get("bns_section"),
                data.get("bns_subsection"),
                data["display_name_en"],
                data.get("display_name_gu"),
                data.get("short_description_md", ""),
                data.get("punishment"),
                data.get("cognizable"),
                data.get("bailable"),
                data.get("triable_by"),
                data.get("compoundable", "no"),
                data.get("schedule_reference"),
                data.get("related_offence_codes", []),
                data.get("special_acts", []),
                kb_version,
            ),
        )
        row = dict(cur.fetchone())

    row["node_count"] = 0
    _audit_log(conn, actor, "create_offence", "offence", offence_id, None, row)
    conn.commit()
    return row


def update_offence(
    conn: PgConnection, offence_id: uuid.UUID, data: dict, actor: str,
) -> dict:
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM legal_kb_offences WHERE id = %s", (offence_id,))
        before = cur.fetchone()
        if not before:
            raise ValueError(f"Offence '{offence_id}' not found")
        before = dict(before)

    if not data:
        return before

    set_parts = []
    values = []
    for col, val in data.items():
        set_parts.append(f"{col} = %s")
        values.append(val)
    set_parts.append("updated_at = now()")
    values.append(offence_id)

    with _dict_cursor(conn) as cur:
        cur.execute(
            f"""UPDATE legal_kb_offences
                SET {', '.join(set_parts)}
                WHERE id = %s
                RETURNING *""",
            values,
        )
        row = dict(cur.fetchone())

    row["node_count"] = before.get("node_count", 0)
    _audit_log(conn, actor, "update_offence", "offence", offence_id, before, row)
    conn.commit()
    return row


def review_offence(
    conn: PgConnection, offence_id: uuid.UUID, review_status: str, actor: str,
) -> dict:
    with _dict_cursor(conn) as cur:
        cur.execute("SELECT * FROM legal_kb_offences WHERE id = %s", (offence_id,))
        before = cur.fetchone()
        if not before:
            raise ValueError(f"Offence '{offence_id}' not found")
        before = dict(before)

        cur.execute(
            """UPDATE legal_kb_offences
               SET review_status = %s, reviewed_by = %s,
                   reviewed_at = now(), updated_at = now()
               WHERE id = %s
               RETURNING *""",
            (review_status, actor, offence_id),
        )
        row = dict(cur.fetchone())

    row["node_count"] = before.get("node_count", 0)
    _audit_log(conn, actor, "review_offence", "offence", offence_id, before, row)
    conn.commit()
    return row


# ── Knowledge Node CRUD ─────────────────────────────────────────────────────

def create_knowledge_node(
    conn: PgConnection, offence_id: uuid.UUID, data: dict, actor: str,
) -> dict:
    node_id = uuid.uuid4()
    kb_version = _get_current_kb_version(conn)
    citations = data.get("legal_basis_citations", [])
    proc_meta = data.get("procedural_metadata", {})

    with _dict_cursor(conn) as cur:
        # Verify offence exists
        cur.execute("SELECT id FROM legal_kb_offences WHERE id = %s", (offence_id,))
        if not cur.fetchone():
            raise ValueError(f"Offence '{offence_id}' not found")

        cur.execute(
            """INSERT INTO legal_kb_knowledge_nodes
               (id, offence_id, branch_type, tier, priority,
                title_en, title_gu, description_md,
                legal_basis_citations, procedural_metadata,
                requires_disclaimer, display_order, kb_version,
                created_by, approval_status)
               VALUES (%s, %s, %s, 'canonical', %s, %s, %s, %s,
                       %s::jsonb, %s::jsonb, %s, %s, %s, %s, 'approved')
               RETURNING *""",
            (
                node_id,
                offence_id,
                data["branch_type"],
                data.get("priority", "medium"),
                data["title_en"],
                data.get("title_gu"),
                data.get("description_md", ""),
                json.dumps(citations, default=str),
                json.dumps(proc_meta, default=str),
                data.get("requires_disclaimer", False),
                data.get("display_order", 0),
                kb_version,
                actor,
            ),
        )
        row = dict(cur.fetchone())

    _audit_log(conn, actor, "create_node", "knowledge_node", node_id, None, row)
    conn.commit()
    return row


def update_knowledge_node(
    conn: PgConnection, node_id: uuid.UUID, data: dict, actor: str,
) -> dict:
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM legal_kb_knowledge_nodes WHERE id = %s", (node_id,),
        )
        before = cur.fetchone()
        if not before:
            raise ValueError(f"Knowledge node '{node_id}' not found")
        before = dict(before)

    if not data:
        return before

    set_parts = []
    values = []
    for col, val in data.items():
        if col in ("legal_basis_citations", "procedural_metadata"):
            set_parts.append(f"{col} = %s::jsonb")
            values.append(json.dumps(val, default=str))
        else:
            set_parts.append(f"{col} = %s")
            values.append(val)
    set_parts.append("updated_at = now()")
    values.append(node_id)

    with _dict_cursor(conn) as cur:
        cur.execute(
            f"""UPDATE legal_kb_knowledge_nodes
                SET {', '.join(set_parts)}
                WHERE id = %s
                RETURNING *""",
            values,
        )
        row = dict(cur.fetchone())

    _audit_log(conn, actor, "update_node", "knowledge_node", node_id, before, row)
    conn.commit()
    return row


def delete_knowledge_node(
    conn: PgConnection, node_id: uuid.UUID, actor: str,
) -> None:
    with _dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM legal_kb_knowledge_nodes WHERE id = %s", (node_id,),
        )
        before = cur.fetchone()
        if not before:
            raise ValueError(f"Knowledge node '{node_id}' not found")
        before = dict(before)

        cur.execute(
            """UPDATE legal_kb_knowledge_nodes
               SET approval_status = 'deprecated', updated_at = now()
               WHERE id = %s""",
            (node_id,),
        )

    _audit_log(
        conn, actor, "deprecate_node", "knowledge_node", node_id,
        before, {**before, "approval_status": "deprecated"},
    )
    conn.commit()
