"""Legal KB API endpoints — T53-M-KB-6.

Mounted at /api/v1/kb
"""

from __future__ import annotations

import logging
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.rbac import Role, require_role
from app.db.session import get_connection
from app.mindmap.kb.retrieval import (
    create_knowledge_node,
    create_offence,
    delete_knowledge_node,
    get_knowledge_for_mindmap,
    get_offence_detail,
    get_judgment_with_insights,
    list_judgments,
    list_offences,
    list_pending_insights,
    review_offence,
    update_knowledge_node,
    update_offence,
)
from app.mindmap.kb.judgment_pipeline import (
    approve_insight,
    chunk_judgment,
    extract_insights,
    ingest_judgment,
    reject_insight,
)
from app.mindmap.kb.schemas import (
    InsightReviewRequest,
    JudgmentInsightResponse,
    JudgmentResponse,
    JudgmentUploadRequest,
    KBVersionReleaseRequest,
    KnowledgeBundle,
    KnowledgeNodeCreateRequest,
    KnowledgeNodeResponse,
    KnowledgeNodeUpdateRequest,
    OffenceCreateRequest,
    OffenceResponse,
    OffenceReviewRequest,
    OffenceUpdateRequest,
    OffenceWithNodes,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["knowledge-base"])

_ADMIN_ROLES = (Role.ADMIN, Role.SP)
_READ_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)


# ── KB Offences ──────────────────────────────────────────────────────────────

@router.get("/kb/offences", response_model=list[OffenceResponse],
            summary="List KB offences")
def list_offences_endpoint(
    category_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        rows = list_offences(conn, category_id=category_id, limit=limit, offset=offset)
        return [OffenceResponse(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/offences/{offence_id}", summary="Get offence with nodes")
def get_offence_endpoint(
    offence_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        result = get_offence_detail(conn, offence_id)
        if not result:
            raise HTTPException(status_code=404, detail="Offence not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/offences", response_model=OffenceResponse,
             status_code=201, summary="Create a new offence")
def create_offence_endpoint(
    payload: OffenceCreateRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        row = create_offence(conn, payload.model_dump(), user["username"])
        return OffenceResponse(**row)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/kb/offences/{offence_id}", response_model=OffenceResponse,
            summary="Update an offence")
def update_offence_endpoint(
    offence_id: UUID,
    payload: OffenceUpdateRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        data = payload.model_dump(exclude_none=True)
        if "review_status" in data:
            data["review_status"] = data["review_status"].value
        row = update_offence(conn, offence_id, data, user["username"])
        return OffenceResponse(**row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/kb/offences/{offence_id}/review", response_model=OffenceResponse,
              summary="Review/approve an offence")
def review_offence_endpoint(
    offence_id: UUID,
    payload: OffenceReviewRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        row = review_offence(conn, offence_id, payload.review_status.value, user["username"])
        return OffenceResponse(**row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/offences/{offence_id}/nodes", response_model=KnowledgeNodeResponse,
             status_code=201, summary="Create a knowledge node for an offence")
def create_node_endpoint(
    offence_id: UUID,
    payload: KnowledgeNodeCreateRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        data = payload.model_dump()
        data["branch_type"] = data["branch_type"].value
        data["priority"] = data["priority"].value
        data["legal_basis_citations"] = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in payload.legal_basis_citations
        ]
        row = create_knowledge_node(conn, offence_id, data, user["username"])
        return KnowledgeNodeResponse(**row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/kb/nodes/{node_id}", response_model=KnowledgeNodeResponse,
            summary="Update a knowledge node")
def update_node_endpoint(
    node_id: UUID,
    payload: KnowledgeNodeUpdateRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        data = payload.model_dump(exclude_none=True)
        if "branch_type" in data:
            data["branch_type"] = data["branch_type"].value
        if "priority" in data:
            data["priority"] = data["priority"].value
        if "legal_basis_citations" in data:
            data["legal_basis_citations"] = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in payload.legal_basis_citations
            ]
        row = update_knowledge_node(conn, node_id, data, user["username"])
        return KnowledgeNodeResponse(**row)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/kb/nodes/{node_id}", summary="Deprecate a knowledge node")
def delete_node_endpoint(
    node_id: UUID,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        delete_knowledge_node(conn, node_id, user["username"])
        logger.info("kb.node_deprecated", node_id=str(node_id), user=user["username"])
        return {"status": "deprecated", "node_id": str(node_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/query", response_model=KnowledgeBundle,
             summary="Query KB for mindmap generation")
def query_kb_endpoint(
    category_id: str,
    bns_sections: list[str] = [],
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        bundle = get_knowledge_for_mindmap(
            category_id=category_id,
            detected_bns_sections=bns_sections,
            fir_extracted_data={},
            conn=conn,
        )
        return bundle
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Judgments ────────────────────────────────────────────────────────────────

@router.get("/kb/judgments", summary="List judgments")
def list_judgments_endpoint(
    review_status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        rows = list_judgments(conn, review_status=review_status, limit=limit, offset=offset)
        return [JudgmentResponse(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/judgments/{judgment_id}", summary="Get judgment with insights")
def get_judgment_endpoint(
    judgment_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        result = get_judgment_with_insights(conn, judgment_id)
        if not result:
            raise HTTPException(status_code=404, detail="Judgment not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/judgments", status_code=201, summary="Ingest a judgment")
def ingest_judgment_endpoint(
    payload: JudgmentUploadRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        result = ingest_judgment(
            conn,
            citation=payload.citation,
            case_name=payload.case_name,
            court=payload.court.value,
            jurisdiction=payload.jurisdiction,
            judgment_date=str(payload.judgment_date) if payload.judgment_date else None,
            bench=payload.bench,
            full_text=payload.full_text,
            summary_md=payload.summary_md,
            related_bns_sections=payload.related_bns_sections,
            source_url=payload.source_url,
            ingested_by=user.get("username"),
        )
        logger.info("kb.judgment_ingested", citation=payload.citation, user=user["username"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kb/judgments/{judgment_id}/extract", summary="Extract insights from judgment")
def extract_insights_endpoint(
    judgment_id: UUID,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        # Chunk first
        chunk_count = chunk_judgment(conn, judgment_id)
        # Then extract
        insights = extract_insights(conn, judgment_id)
        logger.info("kb.insights_extracted", judgment_id=str(judgment_id),
                     chunks=chunk_count, insights=len(insights), user=user["username"])
        return {"chunks_created": chunk_count, "insights_extracted": len(insights),
                "insights": [JudgmentInsightResponse(**i) for i in insights]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Insight review queue ─────────────────────────────────────────────────────

@router.get("/kb/insights/pending", summary="List pending insights for review")
def pending_insights_endpoint(
    limit: int = 50,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        rows = list_pending_insights(conn, limit=limit)
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/kb/insights/{insight_id}/review", summary="Review an insight")
def review_insight_endpoint(
    insight_id: UUID,
    payload: InsightReviewRequest,
    user: dict = Depends(require_role(*_ADMIN_ROLES)),
):
    try:
        conn = get_connection()
        if payload.action.value == "approved":
            result = approve_insight(conn, insight_id, user["username"], payload.review_notes)
            logger.info("kb.insight_approved", insight_id=str(insight_id), user=user["username"])
            return result
        elif payload.action.value == "rejected":
            reject_insight(conn, insight_id, user["username"], payload.review_notes)
            logger.info("kb.insight_rejected", insight_id=str(insight_id), user=user["username"])
            return {"status": "rejected", "insight_id": str(insight_id)}
        else:
            # needs_revision
            with get_connection().cursor() as cur:
                cur.execute(
                    """UPDATE legal_kb_judgment_insights
                       SET review_status = 'needs_revision', review_notes = %s
                       WHERE id = %s""",
                    (payload.review_notes, insight_id),
                )
                conn.commit()
            return {"status": "needs_revision", "insight_id": str(insight_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── KB Versions ──────────────────────────────────────────────────────────────

@router.get("/kb/versions", summary="List KB versions")
def list_versions_endpoint(
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM legal_kb_versions ORDER BY released_at DESC")
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kb/stats", summary="KB statistics")
def kb_stats_endpoint(
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            stats = {}
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_offences")
            stats["total_offences"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes")
            stats["total_nodes"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes WHERE tier = 'canonical'")
            stats["canonical_nodes"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes WHERE tier = 'judgment_derived'")
            stats["judgment_derived_nodes"] = cur.fetchone()["c"]
            # 3-layer counts: lit up by migration 012 backfill.
            cur.execute(
                "SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes "
                "WHERE kb_layer = 'canonical_legal'"
            )
            stats["canonical_legal_nodes"] = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes "
                "WHERE kb_layer = 'investigation_playbook'"
            )
            stats["investigation_playbook_nodes"] = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) AS c FROM legal_kb_knowledge_nodes "
                "WHERE kb_layer = 'case_law_intelligence'"
            )
            stats["case_law_intelligence_nodes"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_judgments")
            stats["total_judgments"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM legal_kb_judgment_insights WHERE review_status = 'pending'")
            stats["pending_insights"] = cur.fetchone()["c"]
            cur.execute("SELECT version FROM legal_kb_versions ORDER BY released_at DESC LIMIT 1")
            v = cur.fetchone()
            stats["current_version"] = v["version"] if v else "none"
            cur.execute("SELECT category_id, COUNT(*) AS c FROM legal_kb_offences GROUP BY category_id ORDER BY category_id")
            stats["offences_by_category"] = {r["category_id"]: r["c"] for r in cur.fetchall()}
            return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
