"""Chargesheet Mindmap API endpoints — T53-M4.

Mounted at /api/v1/fir/{fir_id}/mindmap
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.rbac import Role, get_current_user, require_role
from app.db.session import get_connection
from app.mindmap.generator import (
    add_custom_node,
    generate_mindmap,
    get_latest_mindmap,
    get_mindmap_by_id,
    get_node_status_history,
    list_mindmap_versions,
    update_node_status,
)
from app.mindmap.schemas import (
    CustomNodeCreate,
    MindmapNodeResponse,
    MindmapResponse,
    MindmapVersionSummary,
    NodeStatusResponse,
    NodeStatusUpdate,
    RegenerateRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["mindmap"])

# ── Role sets ────────────────────────────────────────────────────────────────
_WRITE_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN)
_READ_ROLES = (Role.IO, Role.SHO, Role.DYSP, Role.SP, Role.ADMIN, Role.READONLY)

# District-scoped roles
_DISTRICT_SCOPED = {Role.IO.value, Role.SHO.value}


def _check_district_scope(user: dict, fir: dict | None) -> None:
    """Ensure district-scoped users can only access FIRs in their district."""
    if user["role"] in _DISTRICT_SCOPED and fir:
        if fir.get("district") and fir["district"] != user.get("district"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="FIR not in your district scope",
            )


def _get_fir_or_404(conn, fir_id: UUID) -> dict:
    """Fetch FIR or raise 404."""
    import psycopg2.extras
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM firs WHERE id = %s", (fir_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FIR '{fir_id}' not found",
            )
        return dict(row)


# ── POST / — Generate or fetch latest mindmap (idempotent) ───────────────────

@router.post(
    "/fir/{fir_id}/mindmap",
    response_model=MindmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate or fetch chargesheet mindmap",
)
def create_mindmap_endpoint(
    fir_id: UUID,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)
        result = generate_mindmap(fir_id, conn=conn)
        logger.info(
            "mindmap.generated",
            fir_id=str(fir_id),
            mindmap_id=str(result.id),
            case_category=result.case_category,
            user=user["username"],
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.generate_error", fir_id=str(fir_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── GET / — Return latest mindmap ────────────────────────────────────────────

@router.get(
    "/fir/{fir_id}/mindmap",
    response_model=MindmapResponse,
    summary="Get latest chargesheet mindmap",
)
def get_mindmap_endpoint(
    fir_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)
        result = get_latest_mindmap(conn, fir_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No mindmap generated for this FIR yet",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.get_error", fir_id=str(fir_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── GET /versions — List all mindmap versions ────────────────────────────────

@router.get(
    "/fir/{fir_id}/mindmap/versions",
    response_model=list[MindmapVersionSummary],
    summary="List mindmap versions",
)
def list_versions_endpoint(
    fir_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)
        versions = list_mindmap_versions(conn, fir_id)
        return [MindmapVersionSummary(**v) for v in versions]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.list_versions_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── GET /versions/{mindmap_id} — Specific historical version ─────────────────

@router.get(
    "/fir/{fir_id}/mindmap/versions/{mindmap_id}",
    response_model=MindmapResponse,
    summary="Get specific mindmap version",
)
def get_version_endpoint(
    fir_id: UUID,
    mindmap_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)
        result = get_mindmap_by_id(conn, mindmap_id)
        if result is None or result.fir_id != fir_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mindmap version not found",
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.get_version_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── PATCH /nodes/{node_id}/status — Update node status ───────────────────────

@router.patch(
    "/fir/{fir_id}/mindmap/nodes/{node_id}/status",
    response_model=NodeStatusResponse,
    summary="Update node status (append-only)",
)
def patch_node_status_endpoint(
    fir_id: UUID,
    node_id: UUID,
    payload: NodeStatusUpdate,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)

        result = update_node_status(
            conn, node_id,
            user_id=user["username"],
            status=payload.status.value,
            note=payload.note or "",
            evidence_ref=payload.evidence_ref or "",
            hash_prev=payload.hash_prev,
        )

        logger.info(
            "mindmap.node_status_changed",
            node_id=str(node_id),
            new_status=payload.status.value,
            user=user["username"],
        )
        return NodeStatusResponse(**result)

    except ValueError as exc:
        if "Hash chain conflict" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.node_status_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── GET /nodes/{node_id}/history — Full status chain ─────────────────────────

@router.get(
    "/fir/{fir_id}/mindmap/nodes/{node_id}/history",
    response_model=list[NodeStatusResponse],
    summary="Get node status history",
)
def get_node_history_endpoint(
    fir_id: UUID,
    node_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)
        history = get_node_status_history(conn, node_id)
        return [NodeStatusResponse(**h) for h in history]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.node_history_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── POST /nodes — Add custom node ────────────────────────────────────────────

@router.post(
    "/fir/{fir_id}/mindmap/nodes",
    response_model=MindmapNodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add custom node",
)
def add_custom_node_endpoint(
    fir_id: UUID,
    payload: CustomNodeCreate,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)

        # Get the active mindmap
        latest = get_latest_mindmap(conn, fir_id)
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No mindmap exists for this FIR. Generate one first.",
            )

        result = add_custom_node(
            conn,
            mindmap_id=latest.id,
            parent_id=payload.parent_id,
            title=payload.title,
            description_md=payload.description_md,
            node_type=payload.node_type.value,
            priority=payload.priority.value,
            user_id=user["username"],
        )

        logger.info(
            "mindmap.custom_node_added",
            mindmap_id=str(latest.id),
            node_id=str(result["id"]),
            user=user["username"],
        )

        return MindmapNodeResponse(
            id=result["id"],
            mindmap_id=result["mindmap_id"],
            parent_id=result["parent_id"],
            node_type=result["node_type"],
            title=result["title"],
            description_md=result.get("description_md"),
            source=result["source"],
            bns_section=result.get("bns_section"),
            ipc_section=result.get("ipc_section"),
            crpc_section=result.get("crpc_section"),
            priority=result["priority"],
            requires_disclaimer=result["requires_disclaimer"],
            display_order=result["display_order"],
            metadata=result.get("metadata") or {},
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    except Exception as exc:
        logger.error("mindmap.add_node_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── POST /regenerate — Force new version ─────────────────────────────────────

@router.post(
    "/fir/{fir_id}/mindmap/regenerate",
    response_model=MindmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Regenerate mindmap (creates new version)",
)
def regenerate_mindmap_endpoint(
    fir_id: UUID,
    payload: RegenerateRequest,
    user: dict = Depends(require_role(*_WRITE_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)

        result = generate_mindmap(fir_id, conn=conn, regenerate=True)

        logger.info(
            "mindmap.regenerated",
            fir_id=str(fir_id),
            mindmap_id=str(result.id),
            justification=payload.justification,
            user=user["username"],
        )
        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.regenerate_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


# ── GET /export/pdf — PDF checklist export ────────────────────────────────────

@router.get(
    "/fir/{fir_id}/mindmap/export/pdf",
    summary="Export mindmap as PDF checklist",
    responses={200: {"content": {"application/pdf": {}}}},
)
def export_pdf_endpoint(
    fir_id: UUID,
    user: dict = Depends(require_role(*_READ_ROLES)),
):
    try:
        conn = get_connection()
        fir = _get_fir_or_404(conn, fir_id)
        _check_district_scope(user, fir)

        mindmap = get_latest_mindmap(conn, fir_id)
        if mindmap is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No mindmap to export",
            )

        html = _render_checklist_html(mindmap, fir)

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
        except ImportError:
            # Fallback: return HTML if WeasyPrint not installed
            return StreamingResponse(
                io.BytesIO(html.encode("utf-8")),
                media_type="text/html",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="mindmap_{fir_id}.html"'
                    ),
                },
            )

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="mindmap_{fir_id}.pdf"'
                ),
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("mindmap.export_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc),
        )


def _render_checklist_html(mindmap: MindmapResponse, fir: dict) -> str:
    """Render mindmap as an HTML checklist for PDF export."""
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<style>",
        "body{font-family:Arial,sans-serif;margin:2cm;font-size:11pt}",
        ".disclaimer{background:#fff3cd;border:1px solid #ffc107;padding:10px;margin-bottom:20px;font-size:10pt}",
        "h1{font-size:16pt} h2{font-size:13pt;margin-top:18px}",
        ".node{margin-left:20px;margin-bottom:6px}",
        ".status{font-size:9pt;color:#666;margin-left:8px}",
        ".section-pill{background:#e3f2fd;border-radius:4px;padding:2px 6px;font-size:9pt}",
        ".priority-critical{color:#d32f2f;font-weight:bold}",
        ".priority-recommended{color:#f57c00}",
        ".priority-optional{color:#388e3c}",
        "</style></head><body>",
        f"<h1>Chargesheet Mindmap — FIR {fir.get('fir_number', str(fir.get('id', ''))[:8])}</h1>",
        f"<p><strong>Case Category:</strong> {mindmap.case_category} | "
        f"<strong>Generated:</strong> {mindmap.generated_at.strftime('%Y-%m-%d %H:%M')} | "
        f"<strong>Version:</strong> {mindmap.template_version}</p>",
        '<div class="disclaimer">',
        "<strong>Advisory:</strong> AI-generated suggestions. "
        "Investigating Officer retains full discretion. "
        "Not a substitute for legal judgment.",
        "</div>",
    ]

    def render_node(node: MindmapNodeResponse, depth: int = 0):
        indent = "  " * depth
        status_txt = f' <span class="status">[{node.current_status}]</span>' if node.current_status else ""
        priority_cls = f"priority-{node.priority}"
        section = ""
        if node.ipc_section or node.bns_section:
            parts = []
            if node.ipc_section:
                parts.append(f"IPC {node.ipc_section}")
            if node.bns_section:
                parts.append(f"BNS {node.bns_section}")
            section = f' <span class="section-pill">{" / ".join(parts)}</span>'

        lines.append(
            f'{indent}<div class="node">'
            f'<input type="checkbox" {"checked" if node.current_status == "addressed" else ""}/> '
            f'<span class="{priority_cls}">{node.title}</span>'
            f"{section}{status_txt}"
        )
        if node.description_md:
            lines.append(f'{indent}  <div style="font-size:9pt;color:#555;margin-left:24px">{node.description_md}</div>')
        lines.append(f"{indent}</div>")

        for child in node.children:
            render_node(child, depth + 1)

    for node in mindmap.nodes:
        lines.append(f"<h2>{node.title}</h2>")
        for child in node.children:
            render_node(child, 0)

    lines.append("</body></html>")
    return "\n".join(lines)
